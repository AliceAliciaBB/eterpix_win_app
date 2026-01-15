"""
VRC Uploader Configuration
設定管理
"""

import os
import sys
import json
import winreg
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# スタートアップ登録用の定数
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APP_NAME = "EterPixVRCUploader"


def get_executable_path() -> str:
    """実行ファイルのパスを取得（exe化対応）"""
    if getattr(sys, 'frozen', False):
        # PyInstallerでexe化された場合
        return sys.executable
    else:
        # 通常実行の場合（pythonw.exe経由）
        return f'"{sys.executable}" "{Path(__file__).parent / "main.py"}"'


def is_startup_registered() -> bool:
    """スタートアップに登録されているか確認"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, STARTUP_APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"スタートアップ確認エラー: {e}")
        return False


def register_startup() -> bool:
    """スタートアップに登録"""
    try:
        exe_path = get_executable_path()
        # --minimized 引数を追加してトレイに最小化起動
        startup_command = f'"{exe_path}" --minimized' if getattr(sys, 'frozen', False) else f'{exe_path} --minimized'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, startup_command)
        return True
    except Exception as e:
        print(f"スタートアップ登録エラー: {e}")
        return False


def unregister_startup() -> bool:
    """スタートアップから解除"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, STARTUP_APP_NAME)
        return True
    except FileNotFoundError:
        # 既に登録されていない
        return True
    except Exception as e:
        print(f"スタートアップ解除エラー: {e}")
        return False


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
    watch_enabled: bool = False  # 監視状態を保存

    # 認証情報（トークン保存）
    saved_token: Optional[str] = None
    saved_username: Optional[str] = None

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
