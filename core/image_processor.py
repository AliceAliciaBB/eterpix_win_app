"""
Image Processor
PNG→JPG変換とVRChatカメラグリッドのデコード
"""

import io
from pathlib import Path
from typing import Tuple, Dict
from PIL import Image


class ImageProcessor:
    """画像処理クラス"""

    def __init__(self, jpeg_quality: int = 85):
        self.jpeg_quality = jpeg_quality

    def convert_png_to_jpg(self, png_path: Path) -> Tuple[bytes, Dict]:
        """
        PNGをJPGに変換し、カメラデータを抽出

        Args:
            png_path: PNGファイルのパス

        Returns:
            Tuple[bytes, Dict]: JPGバイトデータとカメラデータ
        """
        with Image.open(png_path) as img:
            width, height = img.size

            # カメラグリッドデータを抽出（変換前に）
            camera_data = self._decode_camera_grid(png_path, width, height)

            # RGBA→RGB変換
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # JPGとして保存
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=self.jpeg_quality, optimize=True)
            jpg_bytes = buffer.getvalue()

        return jpg_bytes, camera_data

    def _decode_camera_grid(self, path: Path, width: int, height: int) -> Dict:
        """
        VRChatカメラグリッドからメタデータを抽出

        Args:
            path: 画像ファイルパス
            width: 画像幅
            height: 画像高さ

        Returns:
            Dict: カメラデータ（world_code, coordinates, rotation）
        """
        try:
            # デコーダーをインポート（サーバー側と同じものを使用）
            from utils.decoder import decode_vrchat_camera_grid, calculate_grid_coords

            bottom_left, top_right = calculate_grid_coords(width, height)
            result = decode_vrchat_camera_grid(
                str(path),
                bottom_left=bottom_left,
                top_right=top_right,
                precision=8,
                debug_output=False,
                use_full_data=True
            )

            if result:
                return {
                    'world_code': result.get('world_code'),
                    'coordinate_x': result.get('x'),
                    'coordinate_y': result.get('y'),
                    'coordinate_z': result.get('z'),
                    'rotation_x': result.get('rot_x'),
                    'rotation_y': result.get('rot_y'),
                    'rotation_z': result.get('rot_z')
                }

        except ImportError:
            print("デコーダーが見つかりません。座標情報は抽出されません。")
        except Exception as e:
            print(f"カメラグリッドデコードエラー: {e}")

        return {}

    def create_thumbnail(self, jpg_bytes: bytes, max_size: Tuple[int, int] = (400, 400)) -> bytes:
        """
        サムネイルを生成

        Args:
            jpg_bytes: JPG画像のバイトデータ
            max_size: 最大サイズ（幅, 高さ）

        Returns:
            bytes: サムネイルのバイトデータ
        """
        with Image.open(io.BytesIO(jpg_bytes)) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=75)
            return buffer.getvalue()
