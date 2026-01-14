"""
Offline Queue Manager
サーバーオフライン時のデータ一時保存・再送信管理
"""

import csv
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict


@dataclass
class QueuedPhoto:
    """キューに入った写真データ"""
    id: str
    filename: str
    world_id: Optional[str]
    instance_id: Optional[str]
    visibility: str
    taken_at: str
    camera_data: Optional[Dict]
    created_at: str


@dataclass
class QueuedWorldJoin:
    """キューに入ったワールド参加データ"""
    id: str
    world_id: str
    instance_id: str
    vrc_user_id: str
    vrc_display_name: str
    created_at: str


class OfflineQueueManager:
    """オフラインキュー管理クラス"""

    PHOTOS_CSV = 'photos.csv'
    WORLDS_CSV = 'worlds.csv'
    IMAGES_DIR = 'images'

    PHOTO_FIELDS = ['id', 'filename', 'world_id', 'instance_id', 'visibility',
                    'taken_at', 'camera_data', 'created_at']
    WORLD_FIELDS = ['id', 'world_id', 'instance_id', 'vrc_user_id',
                    'vrc_display_name', 'created_at']

    def __init__(self, base_path: Optional[Path] = None):
        """
        初期化

        Args:
            base_path: 保存先ベースパス（デフォルト: vrc_uploader/temp）
        """
        if base_path is None:
            # vrc_uploader/temp をデフォルトに
            base_path = Path(__file__).parent.parent / 'temp'

        self.base_path = base_path
        self.images_path = base_path / self.IMAGES_DIR
        self._ensure_dirs()

    def _ensure_dirs(self):
        """ディレクトリを確保"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.images_path.mkdir(parents=True, exist_ok=True)

    def _get_photos_csv_path(self) -> Path:
        return self.base_path / self.PHOTOS_CSV

    def _get_worlds_csv_path(self) -> Path:
        return self.base_path / self.WORLDS_CSV

    # ========== 写真キュー操作 ==========

    def queue_photo(
        self,
        jpg_bytes: bytes,
        filename: str,
        world_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        visibility: str = 'self',
        taken_at: Optional[datetime] = None,
        camera_data: Optional[Dict] = None
    ) -> str:
        """
        写真をキューに追加

        Args:
            jpg_bytes: JPG画像データ
            filename: 元のファイル名
            world_id: ワールドID
            instance_id: インスタンスID
            visibility: 公開範囲
            taken_at: 撮影日時
            camera_data: カメラデータ

        Returns:
            str: キューID
        """
        queue_id = str(uuid.uuid4())

        # 画像を保存
        image_filename = f"{queue_id}.jpg"
        image_path = self.images_path / image_filename
        with open(image_path, 'wb') as f:
            f.write(jpg_bytes)

        # CSVに追加
        photo_data = QueuedPhoto(
            id=queue_id,
            filename=filename,
            world_id=world_id or '',
            instance_id=instance_id or '',
            visibility=visibility,
            taken_at=(taken_at or datetime.now()).isoformat(),
            camera_data=json.dumps(camera_data) if camera_data else '',
            created_at=datetime.now().isoformat()
        )

        csv_path = self._get_photos_csv_path()
        file_exists = csv_path.exists()

        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.PHOTO_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(asdict(photo_data))

        return queue_id

    def get_queued_photos(self) -> List[Tuple[QueuedPhoto, bytes]]:
        """
        キューに入っている全写真を取得

        Returns:
            List[Tuple[QueuedPhoto, bytes]]: (写真データ, 画像バイト) のリスト
        """
        csv_path = self._get_photos_csv_path()
        if not csv_path.exists():
            return []

        result = []
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 画像ファイルを読み込み
                image_path = self.images_path / f"{row['id']}.jpg"
                if not image_path.exists():
                    continue

                with open(image_path, 'rb') as img_f:
                    jpg_bytes = img_f.read()

                photo = QueuedPhoto(
                    id=row['id'],
                    filename=row['filename'],
                    world_id=row['world_id'] or None,
                    instance_id=row['instance_id'] or None,
                    visibility=row['visibility'],
                    taken_at=row['taken_at'],
                    camera_data=json.loads(row['camera_data']) if row['camera_data'] else None,
                    created_at=row['created_at']
                )
                result.append((photo, jpg_bytes))

        return result

    def remove_photo(self, queue_id: str):
        """
        写真をキューから削除

        Args:
            queue_id: キューID
        """
        # 画像ファイルを削除
        image_path = self.images_path / f"{queue_id}.jpg"
        if image_path.exists():
            image_path.unlink()

        # CSVから削除
        csv_path = self._get_photos_csv_path()
        if not csv_path.exists():
            return

        rows = []
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader if row['id'] != queue_id]

        if rows:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.PHOTO_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
        else:
            csv_path.unlink()

    # ========== ワールド参加キュー操作 ==========

    def queue_world_join(
        self,
        world_id: str,
        instance_id: str,
        vrc_user_id: str,
        vrc_display_name: str
    ) -> str:
        """
        ワールド参加をキューに追加

        Args:
            world_id: ワールドID
            instance_id: インスタンスID
            vrc_user_id: VRChatユーザーID
            vrc_display_name: VRChat表示名

        Returns:
            str: キューID
        """
        queue_id = str(uuid.uuid4())

        world_data = QueuedWorldJoin(
            id=queue_id,
            world_id=world_id,
            instance_id=instance_id,
            vrc_user_id=vrc_user_id,
            vrc_display_name=vrc_display_name,
            created_at=datetime.now().isoformat()
        )

        csv_path = self._get_worlds_csv_path()
        file_exists = csv_path.exists()

        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.WORLD_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(asdict(world_data))

        return queue_id

    def get_queued_world_joins(self) -> List[QueuedWorldJoin]:
        """
        キューに入っている全ワールド参加を取得

        Returns:
            List[QueuedWorldJoin]: ワールド参加データのリスト
        """
        csv_path = self._get_worlds_csv_path()
        if not csv_path.exists():
            return []

        result = []
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                world = QueuedWorldJoin(
                    id=row['id'],
                    world_id=row['world_id'],
                    instance_id=row['instance_id'],
                    vrc_user_id=row['vrc_user_id'],
                    vrc_display_name=row['vrc_display_name'],
                    created_at=row['created_at']
                )
                result.append(world)

        return result

    def remove_world_join(self, queue_id: str):
        """
        ワールド参加をキューから削除

        Args:
            queue_id: キューID
        """
        csv_path = self._get_worlds_csv_path()
        if not csv_path.exists():
            return

        rows = []
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = [row for row in reader if row['id'] != queue_id]

        if rows:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.WORLD_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
        else:
            csv_path.unlink()

    # ========== ユーティリティ ==========

    def get_queue_counts(self) -> Dict[str, int]:
        """
        キューに入っているデータの件数を取得

        Returns:
            Dict[str, int]: {'photos': N, 'worlds': N}
        """
        photos_count = 0
        worlds_count = 0

        photos_csv = self._get_photos_csv_path()
        if photos_csv.exists():
            with open(photos_csv, 'r', newline='', encoding='utf-8') as f:
                photos_count = sum(1 for _ in csv.DictReader(f))

        worlds_csv = self._get_worlds_csv_path()
        if worlds_csv.exists():
            with open(worlds_csv, 'r', newline='', encoding='utf-8') as f:
                worlds_count = sum(1 for _ in csv.DictReader(f))

        return {'photos': photos_count, 'worlds': worlds_count}

    def has_pending_data(self) -> bool:
        """
        送信待ちデータがあるか確認

        Returns:
            bool: 送信待ちデータがあればTrue
        """
        counts = self.get_queue_counts()
        return counts['photos'] > 0 or counts['worlds'] > 0

    def clear_all(self):
        """全キューをクリア"""
        # CSVファイルを削除
        photos_csv = self._get_photos_csv_path()
        if photos_csv.exists():
            photos_csv.unlink()

        worlds_csv = self._get_worlds_csv_path()
        if worlds_csv.exists():
            worlds_csv.unlink()

        # 画像フォルダをクリア
        if self.images_path.exists():
            shutil.rmtree(self.images_path)
            self.images_path.mkdir(parents=True, exist_ok=True)
