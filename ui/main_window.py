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
from PyQt6.QtCore import Qt, QSize, QEvent
from PyQt6.QtGui import QIcon, QAction, QPixmap
from pathlib import Path
import sys

from config import is_startup_registered, register_startup, unregister_startup


def get_resource_path(relative_path: str) -> Path:
    """リソースファイルのパスを取得（exe化対応）"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstallerでexe化された場合
        return Path(sys._MEIPASS) / relative_path
    # 通常実行の場合
    return Path(__file__).parent.parent / relative_path


class MainWindow(QMainWindow):
    """メインウィンドウ"""

    def __init__(self, app, start_minimized: bool = False):
        super().__init__()
        self.app = app
        self.app.add_callback(self._on_app_event)
        self._start_minimized = start_minimized

        self._setup_ui()
        self._setup_tray()
        self._update_ui()

    def _setup_ui(self):
        """UIセットアップ"""
        self.setWindowTitle("EterPix VRC Uploader")
        self.setMinimumSize(400, 500)

        # ウィンドウアイコン設定
        icon_path = get_resource_path("etp.png")
        pixmap = QPixmap(str(icon_path))
        if not pixmap.isNull():
            self.setWindowIcon(QIcon(pixmap))

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

        # スタートアップ設定
        startup_row = QHBoxLayout()
        startup_row.addWidget(QLabel("スタートアップ:"))
        self.startup_btn = QPushButton()
        self._update_startup_button()
        self.startup_btn.clicked.connect(self._on_toggle_startup)
        startup_row.addWidget(self.startup_btn)
        settings_layout.addLayout(startup_row)

        layout.addWidget(settings_group)

        # ===== OSCセクション =====
        osc_group = QGroupBox("OSC (VRC公開範囲連携)")
        osc_layout = QVBoxLayout(osc_group)

        # OSC状態と開始/停止ボタン
        osc_ctrl_row = QHBoxLayout()
        self.osc_status_label = QLabel("OSC: 停止中")
        self.osc_status_label.setStyleSheet("color: #888;")
        osc_ctrl_row.addWidget(self.osc_status_label)

        self.osc_btn = QPushButton("OSC開始")
        self.osc_btn.clicked.connect(self._on_toggle_osc)
        osc_ctrl_row.addWidget(self.osc_btn)
        osc_layout.addLayout(osc_ctrl_row)

        # OSC受信値表示
        self.osc_recv_label = QLabel("受信値: -")
        self.osc_recv_label.setStyleSheet("color: #888;")
        osc_layout.addWidget(self.osc_recv_label)

        # OSC説明
        osc_help = QLabel(
            "送信パラメータ: EterPixVisibility (int)\n"
            "  100=待機, 101=自分のみ, 102=フレンド, 103=インスタンス&フレンド, 104=インスタンス, 105=パブリック\n"
            "受信パラメータ: EterPixVisibilitySelect (int)\n"
            "  1=自分のみ, 2=フレンド, 3=インスタンス&フレンド, 4=インスタンス, 5=パブリック"
        )
        osc_help.setStyleSheet("color: #666; font-size: 10px;")
        osc_help.setWordWrap(True)
        osc_layout.addWidget(osc_help)

        layout.addWidget(osc_group)

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

        # アイコン設定
        icon_path = get_resource_path("etp.png")
        pixmap = QPixmap(str(icon_path))
        if pixmap.isNull():
            # フォールバック：ウィンドウアイコンを使用
            self.tray.setIcon(self.windowIcon())
        else:
            self.tray.setIcon(QIcon(pixmap))

        menu = QMenu()

        show_action = QAction("表示", self)
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("終了", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.setToolTip("EterPix VRC Uploader")
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
            username = self.app.config.saved_username or "ユーザー"
            self.login_status.setText(f"ログイン中: {username}")
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

        # OSC状態
        self._update_osc_display()

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

        elif event_type == 'osc_visibility_changed':
            # OSC経由で公開範囲が変更された
            visibility = data.get('visibility', '')
            # コンボボックスを更新
            idx = self.visibility_combo.findData(visibility)
            if idx >= 0:
                self.visibility_combo.blockSignals(True)
                self.visibility_combo.setCurrentIndex(idx)
                self.visibility_combo.blockSignals(False)
            self.statusbar.showMessage(f"OSC: 公開範囲を {visibility} に変更")
            self._update_osc_recv_display()

        elif event_type == 'osc_started':
            self._update_osc_display()
            self.statusbar.showMessage("OSC開始")

        elif event_type == 'osc_stopped':
            self._update_osc_display()
            self.statusbar.showMessage("OSC停止")

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
        # OSCにも送信
        self.app.send_visibility_to_vrc(value)

    def _update_startup_button(self):
        """スタートアップボタンの表示を更新"""
        if is_startup_registered():
            self.startup_btn.setText("登録解除")
            self.startup_btn.setStyleSheet("color: #F44336;")
        else:
            self.startup_btn.setText("登録")
            self.startup_btn.setStyleSheet("")

    def _on_toggle_startup(self):
        """スタートアップ登録/解除"""
        if is_startup_registered():
            if unregister_startup():
                self.statusbar.showMessage("スタートアップから解除しました")
            else:
                QMessageBox.warning(self, "エラー", "スタートアップの解除に失敗しました")
        else:
            if register_startup():
                self.statusbar.showMessage("スタートアップに登録しました")
            else:
                QMessageBox.warning(self, "エラー", "スタートアップの登録に失敗しました")
        self._update_startup_button()

    def _on_toggle_watch(self):
        """監視トグル"""
        if self.app.watcher.is_running:
            self.app.stop_watching()
            self.app.config.watch_enabled = False
        else:
            self.app.start_watching()
            self.app.config.watch_enabled = True
        self.app.config.save()
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

    def _on_toggle_osc(self):
        """OSC開始/停止トグル"""
        if self.app.osc_handler.is_running:
            self.app.stop_osc()
            self.app.config.osc_enabled = False
        else:
            self.app.start_osc()
            self.app.config.osc_enabled = True
        self.app.config.save()
        self._update_osc_display()

    def _update_osc_display(self):
        """OSC状態表示を更新"""
        if self.app.osc_handler.is_running:
            self.osc_status_label.setText("OSC: 動作中")
            self.osc_status_label.setStyleSheet("color: #4CAF50;")
            self.osc_btn.setText("OSC停止")
        else:
            self.osc_status_label.setText("OSC: 停止中")
            self.osc_status_label.setStyleSheet("color: #888;")
            self.osc_btn.setText("OSC開始")
        self._update_osc_recv_display()

    def _update_osc_recv_display(self):
        """OSC受信値表示を更新"""
        if self.app.osc_handler.is_running:
            recv_val = self.app.osc_handler.last_recv_value
            current = self.app.osc_handler.current_visibility
            self.osc_recv_label.setText(f"受信値: {recv_val} / 現在: {current}")
            self.osc_recv_label.setStyleSheet("color: #2196F3;")
        else:
            self.osc_recv_label.setText("受信値: -")
            self.osc_recv_label.setStyleSheet("color: #888;")

    def _on_tray_activated(self, reason):
        """トレイアイコンクリック"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        """トレイから表示"""
        self.show()
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _hide_to_tray(self):
        """トレイに隠す"""
        self.hide()
        self.tray.show()
        self.tray.showMessage(
            "EterPix VRC Uploader",
            "タスクトレイで動作中です",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )


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
        # ポップアップで選択
        msg = QMessageBox(self)
        msg.setWindowTitle("終了確認")
        msg.setText("アプリケーションをどうしますか？")
        msg.setIcon(QMessageBox.Icon.Question)

        tray_btn = msg.addButton("タスクトレイにしまう", QMessageBox.ButtonRole.ActionRole)
        quit_btn = msg.addButton("終了する", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = msg.addButton("キャンセル", QMessageBox.ButtonRole.RejectRole)

        msg.exec()

        clicked = msg.clickedButton()
        if clicked == tray_btn:
            event.ignore()
            self._hide_to_tray()
        elif clicked == quit_btn:
            print("[MainWindow] closeEvent: quitting app", flush=True)
            event.accept()
            self._do_quit()
        else:
            # キャンセル
            event.ignore()
