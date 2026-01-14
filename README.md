# VRC Uploader

VRChatスクリーンショットを自動でEterPixにアップロードするWindowsアプリケーション。

## 機能

- VRChatスクリーンショットフォルダの自動監視
- PNG→JPG自動変換
- VRChatログからワールド・インスタンス情報を自動取得
- カメラグリッドから座標・回転情報を抽出
- 公開範囲の設定（自分のみ、フレンド、インスタンス等）

## インストール

```bash
pip install -r requirements.txt
```

## 使い方

```bash
python main.py
```

1. サーバーURLを設定（デフォルト: http://localhost:5000）
2. ユーザー登録またはログイン
3. 「監視開始」ボタンをクリック
4. VRChatでスクリーンショットを撮影すると自動アップロード

## 設定

設定は以下に保存されます：
- Windows: `%APPDATA%\EterPixUploader\config.json`

### 設定項目

| 項目 | 説明 | デフォルト |
|------|------|-----------|
| server_url | サーバーURL | http://localhost:5000 |
| watch_folder | 監視フォルダ | Pictures/VRChat |
| auto_upload | 自動アップロード | true |
| jpeg_quality | JPEG品質 | 85 |
| default_visibility | デフォルト公開範囲 | self |
| minimize_to_tray | トレイに最小化 | true |

## 公開範囲

| 値 | 説明 |
|----|------|
| self | 自分のみ |
| friends | フレンドのみ |
| instance_friends | インスタンス&フレンド |
| instance | 同じインスタンスにいたユーザー |
| public | 全員に公開 |

## 依存関係

- Python 3.10+
- PyQt6
- Pillow
- httpx
- watchdog

## ビルド（exe化）

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "EterPix VRC Uploader" main.py
```
