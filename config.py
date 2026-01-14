"""
VRC Uploader Configuration
設定管理
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class AppConfig:
    """アプリケーション設定"""

    # サーバー設定
    server_url: str = "https://test2.eterpix.uk"

    # 監視設定
    watch_folder: str = ""  # 空の場合はデフォルトパス
    auto_upload: bool = True

    # 画像設定
    jpeg_quality: int = 85

    # デフォルト公開範囲
    default_visibility: str = "self"

    # UI設定
    auto_start: bool = False
    minimize_to_tray: bool = False  # トレイアイコン未実装のため無効
    notifications_enabled: bool = True

    # 認証情報（トークン保存）
    saved_token: Optional[str] = None

    @classmethod
    def get_config_path(cls) -> Path:
        """設定ファイルのパスを取得"""
        app_data = os.getenv('APPDATA')
        if app_data:
            config_dir = Path(app_data) / 'EterPixUploader'
        else:
            config_dir = Path.home() / '.eterpix_uploader'

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'config.json'

    @classmethod
    def load(cls) -> 'AppConfig':
        """設定を読み込み"""
        config_path = cls.get_config_path()

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return cls(**data)
            except Exception as e:
                print(f"設定読み込みエラー: {e}")

        return cls()

    def save(self):
        """設定を保存"""
        config_path = self.get_config_path()

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"設定保存エラー: {e}")

    def get_watch_folder(self) -> Path:
        """監視フォルダを取得（デフォルト: Pictures/VRChat）"""
        if self.watch_folder:
            return Path(self.watch_folder)

        # デフォルトのVRChatスクリーンショットフォルダ
        pictures = Path.home() / 'Pictures' / 'VRChat'
        if pictures.exists():
            return pictures

        return Path.home() / 'Pictures'

    @property
    def visibility_options(self) -> list:
        """公開範囲オプション"""
        return [
            ('self', '自分のみ'),
            ('friends', 'フレンド'),
            ('instance_friends', 'インスタンス&フレンド'),
            ('instance', 'インスタンス'),
            ('public', 'パブリック'),
        ]
