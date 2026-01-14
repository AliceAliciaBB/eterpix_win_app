"""
VRChat Log Parser
VRChatログファイルからユーザー・ワールド情報を抽出
"""

import re
import os
from pathlib import Path
from typing import Optional, Tuple, List, Callable


class VRChatLogParser:
    """VRChatログ解析クラス"""

    PATTERNS = {
        'user_auth': r'User Authenticated: (.*?) \((usr_[a-zA-Z0-9\-]+)\)',
        'world_join': r'Joining (wrld_[a-zA-Z0-9\-]+):(\d+)',
        'world_leave': r'Leaving wrld_',
        'timestamp': r'^(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})'
    }

    def __init__(self):
        self.log_path = self._get_log_path()
        self.current_user: Optional[Tuple[str, str]] = None  # (display_name, user_id)
        self.current_world: Optional[Tuple[str, str]] = None  # (world_id, instance_id)
        self._last_position = 0
        self._current_log_file: Optional[Path] = None

        self._callbacks = {
            'user_changed': [],
            'world_joined': [],
            'world_left': []
        }

    def _get_log_path(self) -> Path:
        """VRChatログフォルダのパスを取得"""
        appdata = os.getenv('APPDATA')
        if appdata:
            return Path(appdata).parent / 'LocalLow' / 'VRChat' / 'VRChat'
        return Path.home() / 'AppData' / 'LocalLow' / 'VRChat' / 'VRChat'

    def get_latest_log(self) -> Optional[Path]:
        """最新のログファイルを取得"""
        if not self.log_path.exists():
            return None

        log_files = list(self.log_path.glob('output_log_*.txt'))
        if not log_files:
            return None

        return max(log_files, key=lambda f: f.stat().st_mtime)

    def parse_new_lines(self):
        """新しい行を解析"""
        log_file = self.get_latest_log()
        if not log_file:
            return

        # ログファイルが変わった場合はリセット
        if log_file != self._current_log_file:
            self._current_log_file = log_file
            self._last_position = 0

        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(self._last_position)
                new_lines = f.readlines()
                self._last_position = f.tell()

            for line in new_lines:
                self._parse_line(line)

        except Exception as e:
            print(f"ログ解析エラー: {e}")

    def _parse_line(self, line: str):
        """1行を解析"""
        # ユーザー認証
        user_match = re.search(self.PATTERNS['user_auth'], line)
        if user_match:
            new_user = (user_match.group(1), user_match.group(2))
            if new_user != self.current_user:
                self.current_user = new_user
                for callback in self._callbacks['user_changed']:
                    callback(self.current_user)

        # ワールド参加
        world_match = re.search(self.PATTERNS['world_join'], line)
        if world_match:
            world_id = world_match.group(1)
            instance_id = world_match.group(2)
            self.current_world = (world_id, instance_id)
            for callback in self._callbacks['world_joined']:
                callback(world_id, instance_id)

        # ワールド退出
        leave_match = re.search(self.PATTERNS['world_leave'], line)
        if leave_match:
            old_world = self.current_world
            self.current_world = None
            for callback in self._callbacks['world_left']:
                callback(old_world)

    def on_user_changed(self, callback: Callable):
        """ユーザー変更コールバックを登録"""
        self._callbacks['user_changed'].append(callback)

    def on_world_joined(self, callback: Callable):
        """ワールド参加コールバックを登録"""
        self._callbacks['world_joined'].append(callback)

    def on_world_left(self, callback: Callable):
        """ワールド退出コールバックを登録"""
        self._callbacks['world_left'].append(callback)

    def get_status(self) -> dict:
        """現在の状態を取得"""
        return {
            'user': self.current_user,
            'world': self.current_world,
            'log_path': str(self._current_log_file) if self._current_log_file else None
        }
