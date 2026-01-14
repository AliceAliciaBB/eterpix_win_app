"""
Main Window
メインウィンドウUI
"""

import asyncio
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QGroupBox, QStatusBar, QSystemTrayIcon, QMenu,
    QMessageBox, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QAction


class MainWindow(QMainWindow):
    """メインウィンドウ"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.app.add_callback(self._on_app_event)

        self._setup_ui()
        # self._setup_tray()  # トレイアイコン未実装
        self.tray = None
        self._update_ui()

    def _setup_ui(self):
        """UIセットアップ"""
        self.setWindowTitle("EterPix VRC Uploader")
        self.setMinimumSize(400, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # ===== ログインセクション =====
        login_group = QGroupBox("アカウント")
        login_layout = QVBoxLayout(login_group)

        # ユーザー名
        username_row = QHBoxLayout()
        username_row.addWidget(QLabel("ユーザー名:"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("ユーザー名")
        username_row.addWidget(self.username_input)
        login_layout.addLayout(username_row)

        # パスワード
        password_row = QHBoxLayout()
        password_row.addWidget(QLabel("パスワード:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("パスワード")
        password_row.addWidget(self.password_input)
        login_layout.addLayout(password_row)

        # ボタン
        btn_row = QHBoxLayout()
        self.login_btn = QPushButton("ログイン")
        self.login_btn.clicked.connect(self._on_login)
        btn_row.addWidget(self.login_btn)

        self.register_btn = QPushButton("登録")
        self.register_btn.clicked.connect(self._on_register)
        btn_row.addWidget(self.register_btn)

        self.logout_btn = QPushButton("ログアウト")
        self.logout_btn.clicked.connect(self._on_logout)
        self.logout_btn.setVisible(False)
        btn_row.addWidget(self.logout_btn)

        login_layout.addLayout(btn_row)

        # ログイン状態
        self.login_status = QLabel("未ログイン")
        self.login_status.setStyleSheet("color: #888;")
        login_layout.addWidget(self.login_status)

        layout.addWidget(login_group)

        # ===== 設定セクション =====
        settings_group = QGroupBox("設定")
        settings_layout = QVBoxLayout(settings_group)

        # サーバーURL
        server_row = QHBoxLayout()
        server_row.addWidget(QLabel("サーバー:"))
        self.server_input = QLineEdit()
        self.server_input.setText(self.app.config.server_url)
        self.server_input.textChanged.connect(self._on_server_changed)
        server_row.addWidget(self.server_input)
        settings_layout.addLayout(server_row)

        # 監視フォルダ
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("監視フォルダ:"))
        self.folder_input = QLineEdit()
        self.folder_input.setText(str(self.app.config.get_watch_folder()))
        self.folder_input.setReadOnly(True)
        folder_row.addWidget(self.folder_input)

        self.folder_btn = QPushButton("選択")
        self.folder_btn.clicked.connect(self._on_select_folder)
        folder_row.addWidget(self.folder_btn)
        settings_layout.addLayout(folder_row)

        # 公開範囲
        visibility_row = QHBoxLayout()
        visibility_row.addWidget(QLabel("デフォルト公開範囲:"))
        self.visibility_combo = QComboBox()
        for value, label in self.app.config.visibility_options:
            self.visibility_combo.addItem(label, value)
        # 現在の値を選択
        idx = self.visibility_combo.findData(self.app.config.default_visibility)
        if idx >= 0:
            self.visibility_combo.setCurrentIndex(idx)
        self.visibility_combo.currentIndexChanged.connect(self._on_visibility_changed)
        visibility_row.addWidget(self.visibility_combo)
        settings_layout.addLayout(visibility_row)

        layout.addWidget(settings_group)

        # ===== 状態セクション =====
        status_group = QGroupBox("状態")
        status_layout = QVBoxLayout(status_group)

        # VRChat情報
        self.vrc_user_label = QLabel("VRChatユーザー: -")
        status_layout.addWidget(self.vrc_user_label)

        self.vrc_world_label = QLabel("ワールド: -")
        status_layout.addWidget(self.vrc_world_label)

        # 監視状態
        watch_row = QHBoxLayout()
        self.watch_status = QLabel("監視停止中")
        watch_row.addWidget(self.watch_status)

        self.watch_btn = QPushButton("監視開始")
        self.watch_btn.clicked.connect(self._on_toggle_watch)
        watch_row.addWidget(self.watch_btn)
        status_layout.addLayout(watch_row)

        # サーバー状態
        server_status_row = QHBoxLayout()
        self.server_status_label = QLabel("サーバー: 未確認")
        self.server_status_label.setStyleSheet("color: #888;")
        server_status_row.addWidget(self.server_status_label)

        self.server_check_btn = QPushButton("状態確認")
        self.server_check_btn.clicked.connect(self._on_check_server)
        server_status_row.addWidget(self.server_check_btn)
        status_layout.addLayout(server_status_row)

        # 送信待ちキュー状態
        queue_row = QHBoxLayout()
        self.queue_label = QLabel("送信待ち: 0件")
        self.queue_label.setStyleSheet("color: #888;")
        queue_row.addWidget(self.queue_label)

        self.resend_btn = QPushButton("再送信")
        self.resend_btn.clicked.connect(self._on_resend)
        self.resend_btn.setEnabled(False)
        queue_row.addWidget(self.resend_btn)
        status_layout.addLayout(queue_row)

        layout.addWidget(status_group)

        # ===== アップロード履歴 =====
        history_group = QGroupBox("最近のアップロード")
        history_layout = QVBoxLayout(history_group)

        self.history_label = QLabel("なし")
        self.history_label.setWordWrap(True)
        history_layout.addWidget(self.history_label)

        layout.addWidget(history_group)

        # スペーサー
        layout.addStretch()

        # ステータスバー
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("準備完了")

    def _setup_tray(self):
        """システムトレイセットアップ"""
        self.tray = QSystemTrayIcon(self)
        # アイコンがない場合はデフォルト
        # self.tray.setIcon(QIcon("icon.png"))

        menu = QMenu()

        show_action = QAction("表示", self)
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)

        if self.app.config.minimize_to_tray:
            self.tray.show()

    def _update_ui(self):
        """UI状態を更新"""
        logged_in = bool(self.app.uploader.token)

        # ログイン状態に応じて表示を切り替え
        self.username_input.setVisible(not logged_in)
        self.password_input.setVisible(not logged_in)
        self.login_btn.setVisible(not logged_in)
        self.register_btn.setVisible(not logged_in)
        self.logout_btn.setVisible(logged_in)

        if logged_in:
            self.login_status.setText("ログイン済み")
            self.login_status.setStyleSheet("color: #4CAF50;")
        else:
            self.login_status.setText("未ログイン")
            self.login_status.setStyleSheet("color: #888;")

        # 監視状態
        if self.app.watcher.is_running:
            self.watch_status.setText("監視中")
            self.watch_status.setStyleSheet("color: #4CAF50;")
            self.watch_btn.setText("監視停止")
        else:
            self.watch_status.setText("監視停止中")
            self.watch_status.setStyleSheet("color: #888;")
            self.watch_btn.setText("監視開始")

        # キュー状態
        self._refresh_queue_display()

    def _on_app_event(self, event_type: str, data: dict):
        """アプリイベント処理"""
        if event_type == 'status':
            self.statusbar.showMessage(data.get('message', ''))

        elif event_type == 'upload_start':
            self.statusbar.showMessage(f"アップロード中: {data.get('path', '')}")

        elif event_type == 'upload_complete':
            self.statusbar.showMessage("アップロード完了")
            self.history_label.setText(f"最新: {data.get('path', '')}")

        elif event_type == 'upload_error':
            self.statusbar.showMessage(f"エラー: {data.get('error', '')}")

        elif event_type == 'world_joined':
            world = data.get('world_id', '-')
            instance = data.get('instance_id', '-')
            self.vrc_world_label.setText(f"ワールド: {world}:{instance}")

        elif event_type == 'world_left':
            self.vrc_world_label.setText("ワールド: -")

        elif event_type == 'user_changed':
            name = data.get('display_name', '-')
            self.vrc_user_label.setText(f"VRChatユーザー: {name}")

        elif event_type == 'photo_queued':
            count = data.get('pending_count', 0)
            self._update_queue_display(count)

        elif event_type == 'queue_item_sent':
            self._refresh_queue_display()

        elif event_type == 'queue_processed':
            remaining = data.get('remaining_photos', 0)
            self._update_queue_display(remaining)

        elif event_type == 'offline_mode':
            is_offline = data.get('is_offline', False)
            if is_offline:
                self.server_status_label.setText("サーバー: オフライン")
                self.server_status_label.setStyleSheet("color: #F44336;")
            else:
                self.server_status_label.setText("サーバー: オンライン")
                self.server_status_label.setStyleSheet("color: #4CAF50;")
            self._refresh_queue_display()

    def _on_login(self):
        """ログイン"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "エラー", "ユーザー名とパスワードを入力してください")
            return

        async def do_login():
            try:
                result = await self.app.login(username, password)
                print(f"Login result: {result}")
                if result.get('status') == 'success':
                    self.statusbar.showMessage("ログイン成功")
                    self._update_ui()
                else:
                    QMessageBox.warning(self, "エラー", result.get('message', 'ログイン失敗'))
            except Exception as e:
                QMessageBox.critical(self, "エラー", str(e))

        asyncio.create_task(do_login())

    def _on_register(self):
        """登録"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "エラー", "ユーザー名とパスワードを入力してください")
            return

        if len(username) < 3 or len(username) > 20:
            QMessageBox.warning(self, "エラー", "ユーザー名は3〜20文字で入力してください")
            return

        if len(password) < 6:
            QMessageBox.warning(self, "エラー", "パスワードは6文字以上で入力してください")
            return

        async def do_register():
            try:
                result = await self.app.register(username, password)
                if result.get('status') == 'success':
                    self.statusbar.showMessage("登録成功")
                    self._update_ui()
                else:
                    QMessageBox.warning(self, "エラー", result.get('message', '登録失敗'))
            except Exception as e:
                QMessageBox.critical(self, "エラー", str(e))

        asyncio.create_task(do_register())

    def _on_logout(self):
        """ログアウト"""
        self.app.logout()
        self.statusbar.showMessage("ログアウトしました")
        self._update_ui()

    def _on_server_changed(self, text):
        """サーバーURL変更"""
        self.app.config.server_url = text
        self.app.uploader.base_url = text
        self.app.config.save()

    def _on_select_folder(self):
        """フォルダ選択"""
        folder = QFileDialog.getExistingDirectory(
            self, "監視フォルダを選択",
            str(self.app.config.get_watch_folder())
        )
        if folder:
            self.folder_input.setText(folder)
            self.app.config.watch_folder = folder
            self.app.config.save()

    def _on_visibility_changed(self, index):
        """公開範囲変更"""
        value = self.visibility_combo.currentData()
        self.app.config.default_visibility = value
        self.app.config.save()

    def _on_toggle_watch(self):
        """監視トグル"""
        if self.app.watcher.is_running:
            self.app.stop_watching()
        else:
            self.app.start_watching()
        self._update_ui()

    def _on_check_server(self):
        """サーバー状態確認"""
        self.server_status_label.setText("サーバー: 確認中...")
        self.server_status_label.setStyleSheet("color: #888;")
        self.server_check_btn.setEnabled(False)

        async def do_check():
            try:
                is_alive = await self.app.uploader.health_check()
                if is_alive:
                    self.server_status_label.setText("サーバー: オンライン")
                    self.server_status_label.setStyleSheet("color: #4CAF50;")
                else:
                    self.server_status_label.setText("サーバー: オフライン")
                    self.server_status_label.setStyleSheet("color: #F44336;")
            except Exception:
                self.server_status_label.setText("サーバー: 接続エラー")
                self.server_status_label.setStyleSheet("color: #F44336;")
            finally:
                self.server_check_btn.setEnabled(True)

        asyncio.create_task(do_check())

    def _on_resend(self):
        """再送信ボタン"""
        self.resend_btn.setEnabled(False)
        self.statusbar.showMessage("再送信中...")

        async def do_resend():
            try:
                await self.app.force_resend()
                self._refresh_queue_display()
            finally:
                self.resend_btn.setEnabled(True)

        asyncio.create_task(do_resend())

    def _update_queue_display(self, count: int):
        """キュー表示を更新"""
        self.queue_label.setText(f"送信待ち: {count}件")
        if count > 0:
            self.queue_label.setStyleSheet("color: #FF9800;")
            self.resend_btn.setEnabled(True)
        else:
            self.queue_label.setStyleSheet("color: #888;")
            self.resend_btn.setEnabled(False)

    def _refresh_queue_display(self):
        """キュー表示を最新に更新"""
        counts = self.app.get_pending_counts()
        total = counts.get('photos', 0) + counts.get('worlds', 0)
        self._update_queue_display(total)

    def _on_tray_activated(self, reason):
        """トレイアイコンクリック"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()

    def _quit_app(self):
        """アプリケーション終了"""
        print("[MainWindow] _quit_app called", flush=True)
        self._do_quit()

    def _do_quit(self):
        """実際の終了処理"""
        import sys
        import os
        print("[MainWindow] _do_quit: stopping watcher...", flush=True)
        self.app.stop_watching()
        print("[MainWindow] _do_quit: calling QApplication.quit()...", flush=True)
        QApplication.quit()
        print("[MainWindow] _do_quit: calling sys.exit(0)...", flush=True)
        # qasync イベントループを確実に終了させる
        sys.exit(0)

    def closeEvent(self, event):
        """ウィンドウクローズ"""
        print("[MainWindow] closeEvent: quitting app", flush=True)
        event.accept()
        self._do_quit()
