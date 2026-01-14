"""
Uploader Client
サーバーとの通信クライアント（同期版）
"""

import httpx
from datetime import datetime
from typing import Optional, Dict


class UploaderClient:
    """アップロードクライアント（非同期版）"""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """HTTPクライアントを取得（遅延初期化）"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    @property
    def headers(self) -> Dict[str, str]:
        """リクエストヘッダー"""
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    async def login(self, username: str, password: str) -> Dict:
        """
        ログイン

        Args:
            username: ユーザー名
            password: パスワード

        Returns:
            Dict: レスポンス
        """
        try:
            response = await self.client.post(
                f'{self.base_url}/vrc/api/auth/login',
                json={'username': username, 'password': password}
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'success':
                self.token = data['data']['token']

            return data
        except httpx.HTTPStatusError as e:
            try:
                return e.response.json()
            except Exception:
                return {'status': 'error', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def register(self, username: str, password: str) -> Dict:
        """
        新規登録

        Args:
            username: ユーザー名
            password: パスワード

        Returns:
            Dict: レスポンス
        """
        try:
            response = await self.client.post(
                f'{self.base_url}/vrc/api/auth/register',
                json={'username': username, 'password': password}
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'success':
                self.token = data['data']['token']

            return data
        except httpx.HTTPStatusError as e:
            try:
                return e.response.json()
            except Exception:
                return {'status': 'error', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def upload_photo(
        self,
        jpg_bytes: bytes,
        filename: str,
        world_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        taken_at: Optional[datetime] = None,
        visibility: str = 'self',
        camera_data: Optional[Dict] = None
    ) -> Dict:
        """
        写真をアップロード

        Args:
            jpg_bytes: JPG画像データ
            filename: ファイル名
            world_id: ワールドID
            instance_id: インスタンスID
            taken_at: 撮影日時
            visibility: 公開範囲
            camera_data: カメラデータ

        Returns:
            Dict: レスポンス
        """
        try:
            files = {'image': (filename, jpg_bytes, 'image/jpeg')}
            data = {
                'visibility': visibility,
                'taken_at': (taken_at or datetime.now()).isoformat()
            }

            if world_id:
                data['world_id'] = world_id
            if instance_id:
                data['instance_id'] = instance_id
            if camera_data:
                for key, value in camera_data.items():
                    if value is not None:
                        data[key] = str(value)

            response = await self.client.post(
                f'{self.base_url}/vrc/api/photos/upload',
                headers=self.headers,
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            try:
                return e.response.json()
            except Exception:
                return {'status': 'error', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def report_instance_join(
        self,
        world_id: str,
        instance_id: str,
        vrc_user_id: str,
        vrc_display_name: str
    ) -> Dict:
        """
        インスタンス参加を報告

        Args:
            world_id: ワールドID
            instance_id: インスタンスID
            vrc_user_id: VRChatユーザーID
            vrc_display_name: VRChat表示名

        Returns:
            Dict: レスポンス
        """
        try:
            response = await self.client.post(
                f'{self.base_url}/vrc/api/instance/join',
                headers=self.headers,
                json={
                    'world_id': world_id,
                    'instance_id': instance_id,
                    'vrc_user_id': vrc_user_id,
                    'vrc_display_name': vrc_display_name
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def report_instance_leave(self) -> Dict:
        """
        インスタンス退出を報告
        サーバー側でuser_current_locations.world_instance_id = NULLに設定

        Returns:
            Dict: レスポンス
        """
        try:
            response = await self.client.post(
                f'{self.base_url}/vrc/api/instance/leave',
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_current_location(self) -> Dict:
        """
        現在地を取得

        Returns:
            Dict: 現在地情報（world_id, instance_id等）
        """
        try:
            response = await self.client.get(
                f'{self.base_url}/vrc/api/location/current',
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_me(self) -> Dict:
        """
        現在のユーザー情報を取得

        Returns:
            Dict: ユーザー情報
        """
        try:
            response = await self.client.get(
                f'{self.base_url}/vrc/api/auth/me',
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def health_check(self, timeout: float = 5.0) -> bool:
        """
        サーバーの死活確認

        Args:
            timeout: タイムアウト秒数

        Returns:
            bool: サーバーが生きていればTrue
        """
        try:
            # 短いタイムアウトで確認
            response = await self.client.get(
                f'{self.base_url}/vrc/api/health',
                timeout=timeout
            )
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """クライアントをクローズ"""
        if self._client:
            await self._client.aclose()
            self._client = None
