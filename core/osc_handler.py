"""
OSC Handler
VRChat OSC通信による公開範囲変更（単一変数方式）
"""

import threading
from typing import Callable, Optional
from pythonosc import udp_client, dispatcher, osc_server


# OSCアドレス（送受信共通）
OSC_PARAM = "/avatar/parameters/EterPixVisibility"

# 公開範囲マッピング（int値 ↔ visibility文字列）
# 0 = OSC無効/変数なしアバター
# 1 = リセット（アバター変更）
# 2-6 = 公開範囲
VISIBILITY_TO_OSC = {
    'self': 2,
    'friends': 3,
    'instance_friends': 4,
    'instance': 5,
    'public': 6,
}

OSC_TO_VISIBILITY = {
    2: 'self',
    3: 'friends',
    4: 'instance_friends',
    5: 'instance',
    6: 'public',
}


class OSCHandler:
    """VRChat OSC通信ハンドラー"""

    def __init__(
        self,
        send_port: int = 9000,
        recv_port: int = 9001,
        host: str = "127.0.0.1"
    ):
        self.send_port = send_port
        self.recv_port = recv_port
        self.host = host

        self._client: Optional[udp_client.SimpleUDPClient] = None
        self._server: Optional[osc_server.ThreadingOSCUDPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._running = False

        # コールバック
        self._on_visibility_changed: Optional[Callable[[str], None]] = None

        # 現在の状態
        self._current_visibility: str = 'self'
        self._last_recv_value: int = 0

    @property
    def is_running(self) -> bool:
        """OSCが動作中かどうか"""
        return self._running

    @property
    def current_visibility(self) -> str:
        """現在の公開範囲"""
        return self._current_visibility

    @property
    def last_recv_value(self) -> int:
        """最後に受信した値"""
        return self._last_recv_value

    def on_visibility_changed(self, callback: Callable[[str], None]):
        """公開範囲変更コールバックを設定"""
        self._on_visibility_changed = callback

    def start(self):
        """OSC通信を開始"""
        if self._running:
            return

        try:
            # 送信クライアント作成
            self._client = udp_client.SimpleUDPClient(self.host, self.send_port)

            # 受信サーバー作成
            disp = dispatcher.Dispatcher()
            disp.map(OSC_PARAM, self._handle_recv)

            self._server = osc_server.ThreadingOSCUDPServer(
                (self.host, self.recv_port),
                disp
            )

            # サーバースレッド開始
            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="OSCServer"
            )
            self._server_thread.start()

            self._running = True
            print(f"[OSC] Started - Send: {self.host}:{self.send_port}, Recv: {self.host}:{self.recv_port}")

            # 初期状態を送信
            self.send_visibility(self._current_visibility)

        except Exception as e:
            print(f"[OSC] Failed to start: {e}")
            self._running = False

    def stop(self):
        """OSC通信を停止"""
        if not self._running:
            return

        try:
            if self._server:
                self._server.shutdown()
                self._server = None

            self._server_thread = None
            self._client = None
            self._running = False

            print("[OSC] Stopped")

        except Exception as e:
            print(f"[OSC] Error stopping: {e}")

    def send_visibility(self, visibility: str):
        """公開範囲をVRCに送信（2-6）"""
        if not self._client:
            return

        osc_value = VISIBILITY_TO_OSC.get(visibility, 2)
        self._current_visibility = visibility

        try:
            self._client.send_message(OSC_PARAM, osc_value)
            print(f"[OSC] Sent visibility: {visibility} -> {osc_value}")
        except Exception as e:
            print(f"[OSC] Send error: {e}")

    def _handle_recv(self, address: str, value: int):
        """VRCからの受信を処理"""
        print(f"[OSC] Received: {address} = {value}")
        self._last_recv_value = value

        # value = 0: OSC無効/変数なしアバター → 無視
        if value == 0:
            print(f"[OSC] OSC disabled or no parameter, ignoring")
            return

        # value = 1: アバター変更でリセット → 現在値を再送信
        if value == 1:
            print(f"[OSC] Avatar reset detected, resending: {self._current_visibility}")
            self.send_visibility(self._current_visibility)
            return

        # 有効な値 (2-6)
        if value in OSC_TO_VISIBILITY:
            new_visibility = OSC_TO_VISIBILITY[value]

            # 変更があった場合のみ処理
            if new_visibility != self._current_visibility:
                self._current_visibility = new_visibility
                print(f"[OSC] Visibility changed to: {new_visibility}")

                if self._on_visibility_changed:
                    self._on_visibility_changed(new_visibility)

                # 確認のため送り返す
                self.send_visibility(new_visibility)
