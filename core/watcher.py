"""
Screenshot Watcher
VRChatスクリーンショットフォルダの監視
"""

import time
import threading
from pathlib import Path
from typing import Callable, Optional
from queue import Queue
from PIL import Image

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("watchdogがインストールされていません。pip install watchdog を実行してください。")


class VRChatScreenshotHandler(FileSystemEventHandler):
    """スクリーンショット検出ハンドラー"""

    def __init__(self, queue: Queue):
        self.queue = queue
        self._processing = set()
        self._lock = threading.Lock()

    def on_created(self, event):
        if event.is_directory:
            return

        path = Path(event.src_path)

        # PNGファイルかつVRChat形式の名前をチェック
        if path.suffix.lower() != '.png':
            return

        # 重複処理を防止
        with self._lock:
            if str(path) in self._processing:
                return
            self._processing.add(str(path))

        # 別スレッドでファイル処理
        threading.Thread(target=self._process_file, args=(path,), daemon=True).start()

    def _process_file(self, path: Path):
        """ファイル処理（書き込み完了を待機）"""
        try:
            # ファイルが完全に書き込まれるまで待機
            time.sleep(0.5)

            # ファイルが存在し、有効な画像か確認
            if not path.exists():
                return

            try:
                with Image.open(path) as img:
                    img.verify()
            except Exception:
                # 画像として無効
                return

            # キューに追加（メインスレッドで処理）
            self.queue.put(path)

        except Exception as e:
            print(f"ファイル処理エラー: {path}, {e}")

        finally:
            with self._lock:
                self._processing.discard(str(path))


class ScreenshotWatcher:
    """スクリーンショット監視クラス"""

    def __init__(self):
        self.observer = None
        self._running = False
        self.queue = Queue()

    def get_vrchat_pictures_path(self) -> Path:
        """VRChatスクリーンショットフォルダを取得"""
        pictures = Path.home() / 'Pictures' / 'VRChat'
        if pictures.exists():
            return pictures
        return Path.home() / 'Pictures'

    def start(self, watch_path: Optional[Path] = None):
        """監視開始"""
        if not WATCHDOG_AVAILABLE:
            print("watchdogが利用できません")
            return

        if self._running:
            self.stop()

        path = watch_path or self.get_vrchat_pictures_path()

        if not path.exists():
            print(f"監視パスが存在しません: {path}")
            return

        handler = VRChatScreenshotHandler(self.queue)
        self.observer = Observer()
        self.observer.schedule(handler, str(path), recursive=True)
        self.observer.start()
        self._running = True

        print(f"監視開始: {path}")

    def stop(self):
        """監視停止"""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join(timeout=2)
            self._running = False
            print("監視停止")

    def get_pending_files(self) -> list:
        """保留中のファイルを取得"""
        files = []
        while not self.queue.empty():
            try:
                files.append(self.queue.get_nowait())
            except Exception:
                break
        return files

    @property
    def is_running(self) -> bool:
        return self._running
