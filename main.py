"""
VRC Uploader - VRChat Screenshot Uploader for EterPix
メインエントリーポイント
"""

import sys
import os
import asyncio
import qasync
import threading
from pathlib import Path
from queue import Queue
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from ui.main_window import MainWindow
from core.watcher import ScreenshotWatcher
from core.log_parser import VRChatLogParser
from core.image_processor import ImageProcessor
from core.uploader import UploaderClient
from core.offline_queue import OfflineQueueManager
from config import AppConfig


# 定数
HEALTH_CHECK_INTERVAL_MS = 10 * 60 * 1000  # 10分
DEBUG_LOG_INTERVAL_MS = 5000  # 5秒ごとにデバッグログ


def log_debug(msg: str):
    """デバッグログ出力"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def log_active_threads():
    """アクティブなスレッドをログ出力"""
    threads = threading.enumerate()
    log_debug(f"=== Active threads: {len(threads)} ===")
    for t in threads:
        log_debug(f"  - {t.name} (daemon={t.daemon}, alive={t.is_alive()})")
    return len(threads)


class VRCUploaderApp:
    """メインアプリケーションクラス"""

    def __init__(self):
        self.config = AppConfig.load()
        self.watcher = ScreenshotWatcher()
        self.log_parser = VRChatLogParser()
        self.processor = ImageProcessor(jpeg_quality=self.config.jpeg_quality)
        self.uploader = UploaderClient(self.config.server_url)
        self.offline_queue = OfflineQueueManager()

        self._callbacks = []
        self._task_queue = Queue()  # 非同期タスク用キュー

        # オフラインモード状態
        self._is_offline = False
        self._last_health_check = None

        # コールバック設定
        self.log_parser.on_world_joined(self._on_world_joined)
        self.log_parser.on_world_left(self._on_world_left)
        # VRCユーザー名・ID取得は無効化
        # self.log_parser.on_user_changed(self._on_user_changed)

    def add_callback(self, callback):
        """UIコールバックを追加"""
        self._callbacks.append(callback)

    def notify(self, event_type: str, data: dict):
        """UIに通知"""
        for callback in self._callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                print(f"Callback error: {e}")

    def _schedule_task(self, coro):
        """非同期タスクをキューに追加"""
        self._task_queue.put(coro)

    def process_pending_tasks(self):
        """保留中のタスクを処理（タイマーから呼ばれる）"""
        # 非同期タスクを処理
        task_count = 0
        while not self._task_queue.empty():
            try:
                coro = self._task_queue.get_nowait()
                asyncio.ensure_future(coro)
                task_count += 1
            except Exception as e:
                print(f"Task scheduling error: {e}", flush=True)

        # スクリーンショットキューを処理
        files = self.watcher.get_pending_files()
        for path in files:
            asyncio.ensure_future(self._on_new_screenshot(path))

        if task_count > 0 or files:
            log_debug(f"Processed {task_count} tasks, {len(files)} files")

    async def _on_new_screenshot(self, path: Path):
        """新しいスクリーンショット検出時"""
        if not self.uploader.token:
            self.notify('status', {'message': 'ログインしていません'})
            return

        if not self.config.auto_upload:
            self.notify('status', {'message': '自動アップロード無効'})
            return

        try:
            self.notify('upload_start', {'path': str(path)})

            # 画像処理
            jpg_bytes, camera_data = self.processor.convert_png_to_jpg(path)

            # 現在のワールド情報取得
            world_id, instance_id = self.log_parser.current_world or (None, None)

            # オフラインモードの場合は直接キューに追加
            if self._is_offline:
                self._queue_photo(jpg_bytes, path.name, world_id, instance_id, camera_data)
                return

            # アップロード試行
            try:
                result = await self.uploader.upload_photo(
                    jpg_bytes,
                    filename=path.name.replace('.png', '.jpg'),
                    world_id=world_id,
                    instance_id=instance_id,
                    visibility=self.config.default_visibility,
                    camera_data=camera_data
                )

                if result.get('status') == 'error':
                    raise Exception(result.get('message', 'Upload failed'))

                # 成功 - オンラインモードを確認
                self._set_online()

                self.notify('upload_complete', {
                    'path': str(path),
                    'photo_uuid': result.get('data', {}).get('photo_uuid')
                })

            except Exception as upload_error:
                # アップロード失敗 - オフラインモードに移行してキューに追加
                print(f"Upload failed, switching to offline mode: {upload_error}")
                self._set_offline()
                self._queue_photo(jpg_bytes, path.name, world_id, instance_id, camera_data)

        except Exception as e:
            self.notify('upload_error', {'path': str(path), 'error': str(e)})

    def _queue_photo(self, jpg_bytes: bytes, filename: str, world_id, instance_id, camera_data):
        """写真をオフラインキューに追加"""
        queue_id = self.offline_queue.queue_photo(
            jpg_bytes=jpg_bytes,
            filename=filename.replace('.png', '.jpg'),
            world_id=world_id,
            instance_id=instance_id,
            visibility=self.config.default_visibility,
            camera_data=camera_data
        )
        counts = self.offline_queue.get_queue_counts()
        self.notify('photo_queued', {
            'queue_id': queue_id,
            'filename': filename,
            'pending_count': counts['photos']
        })
        # キューに追加後、すぐに送信を試みる
        self._schedule_task(self.try_send_queue())

    def _set_offline(self):
        """オフラインモードに設定"""
        if not self._is_offline:
            self._is_offline = True
            self.notify('offline_mode', {'is_offline': True})

    def _set_online(self):
        """オンラインモードに設定"""
        if self._is_offline:
            self._is_offline = False
            self.notify('offline_mode', {'is_offline': False})

    def _on_world_joined(self, world_id: str, instance_id: str):
        """ワールド参加時"""
        self.notify('world_joined', {
            'world_id': world_id,
            'instance_id': instance_id
        })

        if self.uploader.token:
            self._schedule_task(self._report_join(world_id, instance_id))

    async def _report_join(self, world_id: str, instance_id: str):
        """インスタンス参加を報告"""
        # VRCユーザー情報は取得しない
        user_id = None
        display_name = None

        # オフラインモードの場合はキューに追加
        if self._is_offline:
            self._queue_world_join(world_id, instance_id, user_id, display_name)
            return

        try:
            result = await self.uploader.report_instance_join(
                world_id, instance_id, user_id, display_name
            )
            if result.get('status') == 'error':
                raise Exception(result.get('message', 'Report failed'))

            self._set_online()

        except Exception as e:
            print(f"Failed to report join, queuing: {e}")
            self._set_offline()
            self._queue_world_join(world_id, instance_id, user_id, display_name)

    def _queue_world_join(self, world_id: str, instance_id: str, user_id: str, display_name: str):
        """ワールド参加をオフラインキューに追加"""
        self.offline_queue.queue_world_join(
            world_id=world_id,
            instance_id=instance_id,
            vrc_user_id=user_id,
            vrc_display_name=display_name
        )
        counts = self.offline_queue.get_queue_counts()
        self.notify('world_join_queued', {
            'world_id': world_id,
            'pending_count': counts['worlds']
        })

    def _on_world_left(self, world_info):
        """ワールド退出時"""
        if world_info:
            self.notify('world_left', {
                'world_id': world_info[0],
                'instance_id': world_info[1]
            })
        self._schedule_task(self._report_leave())

    async def _report_leave(self):
        """インスタンス退出を報告（サーバー側で現在地をNULLに設定）"""
        if self.uploader.token:
            try:
                await self.uploader.report_instance_leave()
            except Exception as e:
                print(f"Failed to report leave: {e}")

    # VRCユーザー名・ID取得は無効化
    # def _on_user_changed(self, user_info):
    #     """VRChatユーザー変更時"""
    #     display_name, user_id = user_info
    #     self.notify('user_changed', {
    #         'display_name': display_name,
    #         'user_id': user_id
    #     })

    def start_watching(self):
        """監視開始"""
        watch_path = Path(self.config.watch_folder) if self.config.watch_folder else None
        self.watcher.start(watch_path)
        self.notify('status', {'message': '監視開始'})

    def stop_watching(self):
        """監視停止"""
        self.watcher.stop()
        self.notify('status', {'message': '監視停止'})

    async def login(self, username: str, password: str) -> dict:
        """ログイン"""
        result = await self.uploader.login(username, password)
        if result.get('status') == 'success':
            self.config.saved_token = self.uploader.token
            self.config.save()
        return result

    async def register(self, username: str, password: str) -> dict:
        """登録"""
        result = await self.uploader.register(username, password)
        if result.get('status') == 'success':
            self.config.saved_token = self.uploader.token
            self.config.save()
        return result

    def logout(self):
        """ログアウト"""
        self.uploader.token = None
        self.config.saved_token = None
        self.config.save()

    # ========== オフラインキュー関連 ==========

    @property
    def is_offline(self) -> bool:
        """オフラインモードかどうか"""
        return self._is_offline

    def get_pending_counts(self) -> dict:
        """送信待ちデータの件数を取得"""
        return self.offline_queue.get_queue_counts()

    async def check_server_health(self):
        """サーバーの死活確認を行い、オンラインなら再送信"""
        self._last_health_check = datetime.now()

        if not self.uploader.token:
            return

        try:
            is_alive = await self.uploader.health_check()

            if is_alive:
                # サーバー復活 - キューを処理
                if self._is_offline:
                    print("Server is back online, processing queue...")
                    self._set_online()
                    await self._process_offline_queue()
            else:
                # サーバーダウン
                if not self._is_offline:
                    print("Server is offline")
                    self._set_offline()

        except Exception as e:
            print(f"Health check error: {e}")

    async def try_send_queue(self):
        """キューにデータがあればサーバー確認して送信を試みる"""
        if not self.uploader.token:
            return

        # キューが空なら何もしない
        counts = self.offline_queue.get_queue_counts()
        if counts['photos'] == 0 and counts['worlds'] == 0:
            return

        # サーバー確認して送信
        try:
            is_alive = await self.uploader.health_check()
            if is_alive:
                self._set_online()
                await self._process_offline_queue()
        except Exception as e:
            print(f"Queue send check error: {e}")

    async def force_resend(self):
        """手動で再送信を試みる（UIの再送ボタン用）"""
        if not self.uploader.token:
            self.notify('status', {'message': 'ログインしていません'})
            return False

        counts = self.offline_queue.get_queue_counts()
        if counts['photos'] == 0 and counts['worlds'] == 0:
            self.notify('status', {'message': '送信待ちデータがありません'})
            return True

        self.notify('status', {'message': 'サーバー確認中...'})

        try:
            is_alive = await self.uploader.health_check()
            if is_alive:
                self._set_online()
                self.notify('status', {'message': '再送信中...'})
                await self._process_offline_queue()
                self.notify('status', {'message': '再送信完了'})
                return True
            else:
                self.notify('status', {'message': 'サーバーに接続できません'})
                return False
        except Exception as e:
            self.notify('status', {'message': f'再送信エラー: {e}'})
            return False

    async def _process_offline_queue(self):
        """オフラインキューを処理して送信"""
        if not self.uploader.token:
            return

        # ワールド参加を処理
        world_joins = self.offline_queue.get_queued_world_joins()
        for world_join in world_joins:
            try:
                result = await self.uploader.report_instance_join(
                    world_join.world_id,
                    world_join.instance_id,
                    world_join.vrc_user_id,
                    world_join.vrc_display_name
                )
                if result.get('status') != 'error':
                    self.offline_queue.remove_world_join(world_join.id)
                    self.notify('queue_item_sent', {
                        'type': 'world_join',
                        'world_id': world_join.world_id
                    })
                else:
                    # 送信失敗 - オフラインモードに戻る
                    self._set_offline()
                    return
            except Exception as e:
                print(f"Failed to send queued world join: {e}")
                self._set_offline()
                return

        # 写真を処理
        queued_photos = self.offline_queue.get_queued_photos()
        for photo, jpg_bytes in queued_photos:
            try:
                result = await self.uploader.upload_photo(
                    jpg_bytes,
                    filename=photo.filename,
                    world_id=photo.world_id,
                    instance_id=photo.instance_id,
                    visibility=photo.visibility,
                    camera_data=photo.camera_data
                )
                if result.get('status') != 'error':
                    self.offline_queue.remove_photo(photo.id)
                    self.notify('queue_item_sent', {
                        'type': 'photo',
                        'filename': photo.filename,
                        'photo_uuid': result.get('data', {}).get('photo_uuid')
                    })
                else:
                    # 送信失敗 - オフラインモードに戻る
                    self._set_offline()
                    return
            except Exception as e:
                print(f"Failed to send queued photo: {e}")
                self._set_offline()
                return

        # 全て送信完了
        counts = self.offline_queue.get_queue_counts()
        self.notify('queue_processed', {
            'remaining_photos': counts['photos'],
            'remaining_worlds': counts['worlds']
        })


def main():
    """エントリーポイント"""
    log_debug("=== Application starting ===")
    log_active_threads()

    app = QApplication(sys.argv)
    app.setApplicationName("EterPix VRC Uploader")
    app.setOrganizationName("EterPix")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    log_debug("Event loop created")

    # アプリケーション初期化
    uploader_app = VRCUploaderApp()
    log_debug("App initialized")

    # メインウィンドウ
    window = MainWindow(uploader_app)
    window.show()

    # ログ解析タイマー（1秒ごと）
    log_timer = QTimer()
    log_timer.timeout.connect(uploader_app.log_parser.parse_new_lines)
    log_timer.start(1000)

    # タスク処理タイマー（100msごと）
    task_timer = QTimer()
    task_timer.timeout.connect(uploader_app.process_pending_tasks)
    task_timer.start(100)

    # ヘルスチェック＆キュー送信タイマー（10分ごと）
    def schedule_health_check():
        asyncio.ensure_future(uploader_app.try_send_queue())

    health_timer = QTimer()
    health_timer.timeout.connect(schedule_health_check)
    health_timer.start(HEALTH_CHECK_INTERVAL_MS)

    # デバッグログタイマー（5秒ごと）
    def debug_log_tick():
        thread_count = log_active_threads()
        log_debug(f"Watcher running: {uploader_app.watcher.is_running}")
        log_debug(f"Task queue size: {uploader_app._task_queue.qsize()}")

    debug_timer = QTimer()
    debug_timer.timeout.connect(debug_log_tick)
    debug_timer.start(DEBUG_LOG_INTERVAL_MS)
    log_debug("All timers started")

    # 保存されたトークンでログイン復元
    if uploader_app.config.saved_token:
        uploader_app.uploader.token = uploader_app.config.saved_token

    # 起動時に保留中のキューがあれば確認
    if uploader_app.offline_queue.has_pending_data():
        uploader_app._is_offline = True
        uploader_app.notify('offline_mode', {'is_offline': True})
        # 起動後すぐにキュー送信試行
        QTimer.singleShot(3000, schedule_health_check)

    # アプリケーション終了時のクリーンアップ
    def on_quit():
        log_debug("=== on_quit called ===")
        log_active_threads()

        log_debug("Stopping watcher...")
        uploader_app.stop_watching()

        log_debug("Stopping timers...")
        log_timer.stop()
        task_timer.stop()
        health_timer.stop()
        debug_timer.stop()

        log_debug("Stopping event loop...")
        loop.stop()

        log_debug("on_quit completed")
        log_active_threads()

    app.aboutToQuit.connect(on_quit)

    log_debug("=== Starting event loop ===")

    try:
        with loop:
            loop.run_forever()
    except SystemExit:
        log_debug("SystemExit caught")
    except Exception as e:
        log_debug(f"Exception in event loop: {e}")
    finally:
        log_debug("=== Finally block - forcing exit ===")
        log_active_threads()
        # 確実に終了
        os._exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
