"""
OSC Handler
VRChat OSC通信による公開範囲変更
"""

import threading
from typing import Callable, Optional
from pythonosc import udp_client, dispatcher, osc_server


# OSCアドレス定義
OSC_PARAM_SEND = "/avatar/parameters/EterPixVisibility"  # アプリ→VRC（送信）
OSC_PARAM_RECV = "/avatar/parameters/EterPixVisibilitySelect"  # VRC→アプリ（受信）

# 公開範囲マッピング（int値 ↔ visibility文字列）
# 送信時: 101以降でアプリ→VRCに現在の公開範囲を通知
# 受信時: 1以降でVRC→アプリに選択された公開範囲を受信
VISIBILITY_TO_OSC = {
    'self': 101,
    'friends': 102,
    'instance_friends': 103,
    'instance': 104,
    'public': 105,
}

OSC_TO_VISIBILITY = {
    1: 'self',
    2: 'friends',
    3: 'instance_friends',
    4: 'instance',
    5: 'public',
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
            disp.map(OSC_PARAM_RECV, self._handle_recv)

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

            # 初期状態を送信（100 = 待機/接続確認）
            self.send_status(100)

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
        """公開範囲をVRCに送信（101以降）"""
        if not self._client:
            return

        osc_value = VISIBILITY_TO_OSC.get(visibility, 101)
        self._current_visibility = visibility

        try:
            self._client.send_message(OSC_PARAM_SEND, osc_value)
            print(f"[OSC] Sent visibility: {visibility} -> {osc_value}")
        except Exception as e:
            print(f"[OSC] Send error: {e}")

    def send_status(self, value: int):
        """ステータス値を送信"""
        if not self._client:
            return

        try:
            self._client.send_message(OSC_PARAM_SEND, value)
            print(f"[OSC] Sent status: {value}")
        except Exception as e:
            print(f"[OSC] Send status error: {e}")

    def _handle_recv(self, address: str, value: int):
        """VRCからの受信を処理"""
        print(f"[OSC] Received: {address} = {value}")
        self._last_recv_value = value

        # 有効な値か確認
        if value in OSC_TO_VISIBILITY:
            new_visibility = OSC_TO_VISIBILITY[value]

            # 変更があった場合のみコールバック
            if new_visibility != self._current_visibility:
                self._current_visibility = new_visibility
                print(f"[OSC] Visibility changed to: {new_visibility}")

                if self._on_visibility_changed:
                    self._on_visibility_changed(new_visibility)

                # 確認のため、変更後の値を送り返す
                self.send_visibility(new_visibility)
