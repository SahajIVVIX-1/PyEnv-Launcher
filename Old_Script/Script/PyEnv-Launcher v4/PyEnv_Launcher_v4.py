import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QProgressBar,
    QListWidget, QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QDialog,
    QMenuBar, QGroupBox, QSplitter, QToolButton, QSpacerItem, QSizePolicy, QDialogButtonBox,
    QTextEdit, QTabWidget, QInputDialog, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QProcess
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon
import qtawesome as qta
import subprocess

# 1. Global Constants
class AppConfig:
    FONT_MAIN = QFont("Segoe UI", 10)
    FONT_CODE = QFont("Consolas", 10)

    DARK_THEME = {
        "background_color": "#0D1117",
        "text_color": "#C9D1D9",
        "secondary_background": "#161B22",
        "accent_color": "#58A6FF",
        "border_color": "#30363D",
        "table_header_background": "#21262D",
    }

    LIGHT_THEME = {
        "background_color": "#F0F0F0",
        "text_color": "#000000",
        "secondary_background": "#FFFFFF",
        "accent_color": "#58A6FF",
        "border_color": "#CCCCCC",
        "table_header_background": "#E0E0E0",
    }

# 2. Dialog Windows

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About PyEnv Manager")
        self.setFixedSize(400, 350)
        self.parent_widget = parent
        self.current_theme = self.parent_widget.current_theme if self.parent_widget else AppConfig.DARK_THEME
        self.setStyleSheet(self._get_dialog_style())

        layout = QVBoxLayout(self)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            icon = qta.icon("mdi.developer-board", color=self.current_theme["accent_color"])
            pixmap = icon.pixmap(QSize(64, 64))
            icon_label.setPixmap(pixmap)
        except Exception:
            icon_label.setText("[App Icon]")
        layout.addWidget(icon_label)

        app_name_label = QLabel("PyEnv Manager")
        app_name_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        app_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(app_name_label)

        version_label = QLabel("Version: 1.1.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setFont(AppConfig.FONT_MAIN)
        layout.addWidget(version_label)

        description_text = """
        <p align="center">
        A full-featured UI for managing PyEnv environments, launching scripts, Jupyter, or shells.
        Includes theme support, package management, and more.
        </p>
        """
        description_edit = QTextEdit()
        description_edit.setReadOnly(True)
        description_edit.setHtml(description_text)
        description_edit.setFont(AppConfig.FONT_MAIN)
        description_edit.setStyleSheet("border: none;")
        layout.addWidget(description_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def _get_dialog_style(self):
        return f"""
        QDialog {{
            background-color: {self.current_theme["background_color"]};
            color: {self.current_theme["text_color"]};
        }}
        QLabel {{
            color: {self.current_theme["text_color"]};
        }}
        QTextEdit {{
            color: {self.current_theme["text_color"]};
            background-color: {self.current_theme["secondary_background"]};
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton {{
            background-color: {self.current_theme["accent_color"]};
            color: #0D1117;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #0366D6;
        }}
        QPushButton:pressed {{
            background-color: #005CC5;
        }}
        """

    def accept(self):
        super().accept()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.parent_widget = parent
        self.current_theme = self.parent_widget.current_theme if self.parent_widget else AppConfig.DARK_THEME
        self.setFixedSize(420, 300)
        self.setStyleSheet(self._get_dialog_style())

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(10)

        self.python_path_label = QLabel("PyEnv Root Path:")
        self.python_path_input = QLineEdit()
        self.python_path_input.setPlaceholderText("e.g., ~/.pyenv")
        self.python_path_input.setText(os.environ.get('PYENV_ROOT', str(Path.home() / '.pyenv')))
        self.python_path_browse_btn = QPushButton("Browse...")
        self.python_path_browse_btn.clicked.connect(self._browse_path)
        browse_h_layout = QHBoxLayout()
        browse_h_layout.addWidget(self.python_path_input, 1)
        browse_h_layout.addWidget(self.python_path_browse_btn)
        form_layout.addRow(self.python_path_label, browse_h_layout)

        self.theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", AppConfig.DARK_THEME)
        self.theme_combo.addItem("Light", AppConfig.LIGHT_THEME)
        current_index = 0 if self.current_theme == AppConfig.DARK_THEME else 1
        self.theme_combo.setCurrentIndex(current_index)
        form_layout.addRow(self.theme_label, self.theme_combo)

        self.autodetect_checkbox = QCheckBox("Auto-detect PyEnv Root")
        self.autodetect_checkbox.setChecked(True)
        form_layout.addRow(self.autodetect_checkbox)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _get_dialog_style(self):
        return f"""
        QDialog {{
            background-color: {self.current_theme["background_color"]};
            color: {self.current_theme["text_color"]};
        }}
        QLabel {{
            color: {self.current_theme["text_color"]};
        }}
        QLineEdit {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 4px;
            padding: 5px;
        }}
        QPushButton {{
            background-color: {self.current_theme["accent_color"]};
            color: #0D1117;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #0366D6;
        }}
        QPushButton:pressed {{
            background-color: #005CC5;
        }}
        QComboBox {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 4px;
            padding: 5px;
        }}
        QComboBox::drop-down {{
            width: 15px;
            border-left: 1px solid {self.current_theme["border_color"]};
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
        }}
        QCheckBox {{
            color: {self.current_theme["text_color"]};
        }}
        QCheckBox::indicator {{
            width: 12px;
            height: 12px;
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 2px;
        }}
        QCheckBox::indicator:checked {{
            background-color: {self.current_theme["accent_color"]};
            border-color: {self.current_theme["accent_color"]};
        }}
        QDialogButtonBox QPushButton {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
            padding: 6px 12px;
        }}
        QDialogButtonBox QPushButton:hover {{
            background-color: #21262D;
        }}
        """

    def _browse_path(self):
        dir = QFileDialog.getExistingDirectory(self, "Select PyEnv Root")
        if dir:
            self.python_path_input.setText(dir)

    def accept(self):
        if self.autodetect_checkbox.isChecked():
            pyenv_root = os.environ.get('PYENV_ROOT', str(Path.home() / '.pyenv'))
            self.python_path_input.setText(pyenv_root)
        super().accept()

# 3. UI Manager Class
class UIManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.current_theme = self.parent_widget.current_theme

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)

        # Left Pane: Controls
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(10, 10, 10, 10)
        self.left_layout.setSpacing(15)
        self.left_panel.setMinimumWidth(400)

        self._create_header_section()
        self._create_path_section()
        self._create_mode_section()
        self._create_options_section()
        self._create_actions_section()

        self.splitter.addWidget(self.left_panel)

        # Right Pane: Tabs for Environments, Packages, Log
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(10, 10, 10, 10)
        self.right_layout.setSpacing(10)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)

        # Environments Tab
        self.environments_tab = QWidget()
        env_layout = QVBoxLayout(self.environments_tab)
        self.env_table = QTableWidget()
        self.env_table.setColumnCount(3)
        self.env_table.setHorizontalHeaderLabels(["Version", "Status", "Path"])
        self.env_table.verticalHeader().setVisible(False)
        self.env_table.setAlternatingRowColors(True)
        self.env_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.env_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.env_table.itemSelectionChanged.connect(self._on_env_selected)
        env_layout.addWidget(self.env_table)

        env_buttons_layout = QHBoxLayout()
        self.refresh_env_btn = QPushButton("Refresh")
        self.refresh_env_btn.clicked.connect(self.parent_widget._refresh_environments)
        self.create_env_btn = QPushButton("Create")
        self.create_env_btn.clicked.connect(self.parent_widget._create_environment)
        self.delete_env_btn = QPushButton("Delete")
        self.delete_env_btn.clicked.connect(self.parent_widget._delete_environment)
        env_buttons_layout.addWidget(self.refresh_env_btn)
        env_buttons_layout.addWidget(self.create_env_btn)
        env_buttons_layout.addWidget(self.delete_env_btn)
        env_layout.addLayout(env_buttons_layout)

        self.tab_widget.addTab(self.environments_tab, "Environments")

        # Packages Tab
        self.packages_tab = QWidget()
        pkg_layout = QVBoxLayout(self.packages_tab)
        self.pkg_table = QTableWidget()
        self.pkg_table.setColumnCount(2)
        self.pkg_table.setHorizontalHeaderLabels(["Package", "Version"])
        self.pkg_table.verticalHeader().setVisible(False)
        self.pkg_table.setAlternatingRowColors(True)
        self.pkg_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.pkg_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        pkg_layout.addWidget(self.pkg_table)

        pkg_buttons_layout = QHBoxLayout()
        self.refresh_pkg_btn = QPushButton("Refresh Packages")
        self.refresh_pkg_btn.clicked.connect(self.parent_widget._refresh_packages)
        self.install_pkg_btn = QPushButton("Install")
        self.install_pkg_btn.clicked.connect(self.parent_widget._install_package)
        self.uninstall_pkg_btn = QPushButton("Uninstall")
        self.uninstall_pkg_btn.clicked.connect(self.parent_widget._uninstall_package)
        pkg_buttons_layout.addWidget(self.refresh_pkg_btn)
        pkg_buttons_layout.addWidget(self.install_pkg_btn)
        pkg_buttons_layout.addWidget(self.uninstall_pkg_btn)
        pkg_layout.addLayout(pkg_buttons_layout)

        self.tab_widget.addTab(self.packages_tab, "Packages")

        # Log Tab
        self.log_tab = QWidget()
        log_layout = QVBoxLayout(self.log_tab)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(AppConfig.FONT_CODE)
        log_layout.addWidget(self.log_output)
        self.tab_widget.addTab(self.log_tab, "Log")

        self.right_layout.addWidget(self.tab_widget)
        self.splitter.addWidget(self.right_panel)

        main_layout.addWidget(self.splitter)
        self.setLayout(main_layout)

        self._apply_styles()

    def _apply_styles(self):
        style_sheet = f"""
        QWidget {{
            background-color: {self.current_theme["background_color"]};
            color: {self.current_theme["text_color"]};
            font-family: "{AppConfig.FONT_MAIN.family()}";
            font-size: {AppConfig.FONT_MAIN.pointSize()}pt;
        }}
        QGroupBox {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 5px;
            margin-top: 1.5ex;
            padding-top: 0.5ex;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px;
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            font-weight: bold;
        }}
        QLabel {{
            color: {self.current_theme["text_color"]};
        }}
        QLineEdit, QComboBox {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 4px;
            padding: 5px;
        }}
        QLineEdit:focus, QComboBox:focus {{
            border-color: {self.current_theme["accent_color"]};
        }}
        QPushButton {{
            background-color: {self.current_theme["accent_color"]};
            color: #0D1117;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #0366D6;
        }}
        QPushButton:pressed {{
            background-color: #005CC5;
        }}
        QCheckBox {{
            color: {self.current_theme["text_color"]};
        }}
        QCheckBox::indicator {{
            width: 12px;
            height: 12px;
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 2px;
        }}
        QCheckBox::indicator:checked {{
            background-color: {self.current_theme["accent_color"]};
            border-color: {self.current_theme["accent_color"]};
        }}
        QComboBox::drop-down {{
            width: 15px;
            border-left: 1px solid {self.current_theme["border_color"]};
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
        }}
        QProgressBar {{
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 4px;
            text-align: center;
            color: {self.current_theme["text_color"]};
            background-color: {self.current_theme["secondary_background"]};
        }}
        QProgressBar::chunk {{
            background-color: {self.current_theme["accent_color"]};
            border-radius: 4px;
        }}
        QTableWidget {{
            gridline-color: {self.current_theme["border_color"]};
            background-color: {self.current_theme["secondary_background"]};
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 4px;
        }}
        QTableWidget::item:selected {{
            background-color: {self.current_theme["accent_color"]};
            color: #0D1117;
        }}
        QTableWidget QHeaderView::section {{
            background-color: {self.current_theme["table_header_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
            padding: 6px;
            font-weight: bold;
        }}
        QTabWidget::pane {{
            border: 1px solid {self.current_theme["border_color"]};
            background-color: {self.current_theme["background_color"]};
        }}
        QTabBar::tab {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            padding: 8px 16px;
            border: 1px solid {self.current_theme["border_color"]};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {self.current_theme["accent_color"]};
            color: #0D1117;
        }}
        QTextEdit {{
            background-color: {self.current_theme["secondary_background"]};
            color: {self.current_theme["text_color"]};
            border: 1px solid {self.current_theme["border_color"]};
            border-radius: 4px;
        }}
        QSplitter::handle {{
            background-color: {self.current_theme["border_color"]};
        }}
        """
        self.setStyleSheet(style_sheet)

    def _create_header_section(self):
        header_layout = QHBoxLayout()

        title_label = QLabel("PyEnv Manager")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {self.current_theme['accent_color']};")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        settings_btn = QPushButton()
        settings_btn.setFixedSize(QSize(32, 32))
        settings_btn.setIcon(qta.icon("mdi.cog", color=self.current_theme["text_color"]))
        settings_btn.setIconSize(QSize(24, 24))
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self.parent_widget._open_settings)
        settings_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; padding: 4px; }
            QPushButton:hover { background-color: #21262D; }
        """)
        header_layout.addWidget(settings_btn)

        about_btn = QPushButton()
        about_btn.setFixedSize(QSize(32, 32))
        about_btn.setIcon(qta.icon("mdi.information", color=self.current_theme["text_color"]))
        about_btn.setIconSize(QSize(24, 24))
        about_btn.setToolTip("About")
        about_btn.clicked.connect(self.parent_widget._open_about)
        about_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; padding: 4px; }
            QPushButton:hover { background-color: #21262D; }
        """)
        header_layout.addWidget(about_btn)

        self.left_layout.addLayout(header_layout)

    def _create_path_section(self):
        path_group = QGroupBox("PyEnv Root")
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("~/.pyenv")
        self.path_input.textChanged.connect(self.parent_widget._on_path_changed)
        path_browse_btn = QPushButton("Browse")
        path_browse_btn.clicked.connect(self.parent_widget._on_browse_path)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(path_browse_btn)
        path_group.setLayout(path_layout)
        self.left_layout.addWidget(path_group)

    def _create_mode_section(self):
        mode_group = QGroupBox("Launch Mode")
        mode_layout = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Shell", "Run Script", "Jupyter Notebook"])
        self.mode_combo.currentIndexChanged.connect(self.parent_widget._on_mode_changed)
        mode_layout.addRow("Mode:", self.mode_combo)
        mode_group.setLayout(mode_layout)
        self.left_layout.addWidget(mode_group)

    def _create_options_section(self):
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()

        self.working_dir_input = QLineEdit()
        self.working_dir_input.setPlaceholderText("Working Directory")
        work_dir_browse = QPushButton("Browse")
        work_dir_browse.clicked.connect(self.parent_widget._on_browse_working_dir)
        work_dir_h = QHBoxLayout()
        work_dir_h.addWidget(self.working_dir_input)
        work_dir_h.addWidget(work_dir_browse)
        options_layout.addRow("Working Dir:", work_dir_h)

        self.script_path_input = QLineEdit()
        self.script_path_input.setPlaceholderText("Script Path")
        script_browse = QPushButton("Browse")
        script_browse.clicked.connect(self.parent_widget._on_browse_script)
        self.script_h = QHBoxLayout()
        self.script_h.addWidget(self.script_path_input)
        self.script_h.addWidget(script_browse)
        self.script_row = options_layout.rowCount()
        options_layout.addRow("Script:", self.script_h)

        self.args_input = QLineEdit()
        self.args_input.setPlaceholderText("Arguments")
        options_layout.addRow("Args:", self.args_input)

        self.show_details_check = QCheckBox("Show Details")
        self.show_details_check.setChecked(True)
        options_layout.addRow(self.show_details_check)

        options_group.setLayout(options_layout)
        self.left_layout.addWidget(options_group)
        self.parent_widget._on_mode_changed(0)  # Initial update

    def _create_actions_section(self):
        actions_layout = QHBoxLayout()
        self.launch_btn = QPushButton("Launch")
        self.launch_btn.clicked.connect(self.parent_widget._launch)
        actions_layout.addWidget(self.launch_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.parent_widget._stop_process)
        actions_layout.addWidget(self.stop_btn)

        self.left_layout.addLayout(actions_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        self.left_layout.addWidget(self.progress_bar)

        self.left_layout.addStretch()

    def _on_env_selected(self):
        selected = self.env_table.selectedItems()
        if selected:
            version = selected[0].text()
            self.parent_widget.selected_version = version
            self.parent_widget._refresh_packages()

# 4. Main Application Window
class PyEnvManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyEnv Manager")
        self.setGeometry(100, 100, 1200, 800)

        self.current_theme = AppConfig.DARK_THEME
        self.set_theme(self.current_theme)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.ui = UIManager(parent=self)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.addWidget(self.ui)

        self._setup_menu()
        self.selected_version = None
        self.process = None

        self.ui.path_input.setText(os.environ.get('PYENV_ROOT', str(Path.home() / '.pyenv')))
        self._refresh_environments()
        self._apply_stylesheet()
        self._center_on_screen()

    def set_theme(self, theme):
        self.current_theme = theme
        app = QApplication.instance()
        app.setPalette(self._create_palette(theme))
        if hasattr(self, 'ui'):
            self.ui.current_theme = theme
            self.ui._apply_styles()

    def _create_palette(self, theme):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["background_color"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text_color"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["secondary_background"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["text_color"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme["accent_color"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0D1117"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["accent_color"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0D1117"))
        return palette

    def _apply_stylesheet(self):
        stylesheet = f"""
        QMainWindow {{
            background-color: {self.current_theme["background_color"]};
        }}
        """
        self.setStyleSheet(stylesheet)

    def _setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        exit_action = file_menu.addAction("&Exit")
        exit_action.triggered.connect(self.close)

        edit_menu = menubar.addMenu("&Edit")
        settings_action = edit_menu.addAction("&Settings")
        settings_action.triggered.connect(self._open_settings)

        help_menu = menubar.addMenu("&Help")
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._open_about)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        geo = self.frameGeometry()
        geo.moveCenter(screen.center())
        self.move(geo.topLeft())

    def show_with_fade(self):
        self.setWindowOpacity(0.0)
        self.show()
        animation = QPropertyAnimation(self, b"windowOpacity")
        animation.setDuration(500)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutQuint)
        animation.start()

    def _open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            new_theme = dialog.theme_combo.currentData()
            if new_theme != self.current_theme:
                self.set_theme(new_theme)
            pyenv_root = dialog.python_path_input.text()
            self.ui.path_input.setText(pyenv_root)
            self._refresh_environments()

    def _open_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _on_path_changed(self, text):
        self._refresh_environments()

    def _on_browse_path(self):
        dir = QFileDialog.getExistingDirectory(self, "Select PyEnv Root")
        if dir:
            self.ui.path_input.setText(dir)
            self._refresh_environments()

    def _on_mode_changed(self, index):
        mode = self.ui.mode_combo.currentText()
        show_script = mode == "Run Script"
        options_layout = self.ui.options_group.layout()
        row_item = options_layout.itemAtPosition(self.ui.script_row, 1)
        if row_item:
            row_item.widget().setVisible(show_script)
        if not show_script:
            self.ui.script_path_input.clear()

    def _on_browse_working_dir(self):
        dir = QFileDialog.getExistingDirectory(self, "Select Working Directory")
        if dir:
            self.ui.working_dir_input.setText(dir)

    def _on_browse_script(self):
        file = QFileDialog.getOpenFileName(self, "Select Script", "", "Python Files (*.py)")
        if file[0]:
            self.ui.script_path_input.setText(file[0])

    def _refresh_environments(self):
        pyenv_root = self.ui.path_input.text()
        if not pyenv_root:
            return
        try:
            os.environ['PYENV_ROOT'] = pyenv_root
            result = subprocess.run(['pyenv', 'versions'], capture_output=True, text=True)
            versions = result.stdout.strip().split('\n')
            self.ui.env_table.setRowCount(0)
            for line in versions:
                if line.strip():
                    parts = line.split()
                    v = parts[0].replace('*', '')
                    status = "Active" if '*' in line else ""
                    path = os.path.join(pyenv_root, 'versions', v)
                    row = self.ui.env_table.rowCount()
                    self.ui.env_table.insertRow(row)
                    self.ui.env_table.setItem(row, 0, QTableWidgetItem(v))
                    self.ui.env_table.setItem(row, 1, QTableWidgetItem(status))
                    self.ui.env_table.setItem(row, 2, QTableWidgetItem(path))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load environments: {e}")
            self._log(f"Error: {e}")

    def _create_environment(self):
        version, ok = QInputDialog.getText(self, "Create Environment", "Enter Python version (e.g., 3.10.0):")
        if ok and version:
            pyenv_root = self.ui.path_input.text()
            os.environ['PYENV_ROOT'] = pyenv_root
            self._run_command(['pyenv', 'install', version], "Creating environment")

    def _delete_environment(self):
        if not self.selected_version:
            QMessageBox.warning(self, "Error", "Select an environment to delete")
            return
        reply = QMessageBox.question(self, "Confirm", f"Delete {self.selected_version}?")
        if reply == QMessageBox.StandardButton.Yes:
            pyenv_root = self.ui.path_input.text()
            os.environ['PYENV_ROOT'] = pyenv_root
            self._run_command(['pyenv', 'uninstall', '-f', self.selected_version], "Deleting environment")

    def _refresh_packages(self):
        if not self.selected_version:
            return
        pyenv_root = self.ui.path_input.text()
        python_path = os.path.join(pyenv_root, 'versions', self.selected_version, 'bin', 'python')
        try:
            result = subprocess.run([python_path, '-m', 'pip', 'list', '--format=freeze'], capture_output=True, text=True)
            packages = result.stdout.strip().split('\n')
            self.ui.pkg_table.setRowCount(0)
            for p in packages:
                if p:
                    name, ver = p.split('==')
                    row = self.ui.pkg_table.rowCount()
                    self.ui.pkg_table.insertRow(row)
                    self.ui.pkg_table.setItem(row, 0, QTableWidgetItem(name))
                    self.ui.pkg_table.setItem(row, 1, QTableWidgetItem(ver))
        except Exception as e:
            self._log(f"Error loading packages: {e}")

    def _install_package(self):
        if not self.selected_version:
            QMessageBox.warning(self, "Error", "Select an environment")
            return
        pkg, ok = QInputDialog.getText(self, "Install Package", "Enter package name:")
        if ok and pkg:
            pyenv_root = self.ui.path_input.text()
            python_path = os.path.join(pyenv_root, 'versions', self.selected_version, 'bin', 'pip')
            self._run_command([python_path, 'install', pkg], "Installing package")

    def _uninstall_package(self):
        selected = self.ui.pkg_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Error", "Select a package")
            return
        pkg = selected[0].text()
        reply = QMessageBox.question(self, "Confirm", f"Uninstall {pkg}?")
        if reply == QMessageBox.StandardButton.Yes:
            pyenv_root = self.ui.path_input.text()
            python_path = os.path.join(pyenv_root, 'versions', self.selected_version, 'bin', 'pip')
            self._run_command([python_path, 'uninstall', '-y', pkg], "Uninstalling package")

    def _launch(self):
        if not self.selected_version:
            QMessageBox.warning(self, "Error", "Select an environment")
            return
        mode = self.ui.mode_combo.currentText()
        pyenv_root = self.ui.path_input.text()
        working_dir = self.ui.working_dir_input.text() or os.getcwd()
        args = self.ui.args_input.text().split()

        env = os.environ.copy()
        env['PYENV_VERSION'] = self.selected_version
        env['PATH'] = os.path.join(pyenv_root, 'shims') + os.pathsep + env['PATH']

        if mode == "Shell":
            cmd = ['pyenv', 'shell', self.selected_version]
        elif mode == "Run Script":
            script = self.ui.script_path_input.text()
            if not script:
                QMessageBox.warning(self, "Error", "Select a script")
                return
            cmd = ['python', script] + args
        elif mode == "Jupyter Notebook":
            cmd = ['jupyter', 'notebook'] + args
        else:
            return

        self.process = QProcess(self)
        self.process.setWorkingDirectory(working_dir)
        self.process.setProcessEnvironment(QProcessEnvironment(env))
        self.process.readyReadStandardOutput.connect(self._handle_output)
        self.process.readyReadStandardError.connect(self._handle_error)
        self.process.finished.connect(self._process_finished)
        self.process.start(cmd[0], cmd[1:])
        self.ui.launch_btn.setEnabled(False)
        self.ui.stop_btn.setEnabled(True)
        self.ui.progress_bar.show()
        self._log(f"Launching {mode} in {self.selected_version}")

    def _stop_process(self):
        if self.process:
            self.process.kill()
            self._process_finished()

    def _process_finished(self):
        self.ui.launch_btn.setEnabled(True)
        self.ui.stop_btn.setEnabled(False)
        self.ui.progress_bar.hide()
        self._log("Process finished")

    def _handle_output(self):
        output = self.process.readAllStandardOutput().data().decode()
        self._log(output)

    def _handle_error(self):
        error = self.process.readAllStandardError().data().decode()
        self._log(f"Error: {error}")

    def _run_command(self, cmd, msg):
        self._log(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self._log(result.stdout)
            if "install" in cmd or "uninstall" in cmd:
                self._refresh_environments() if "pyenv" in cmd else self._refresh_packages()
        except subprocess.CalledProcessError as e:
            self._log(f"Error: {e.stderr}")

    def _log(self, message):
        self.ui.log_output.append(message.strip() + '\n')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PyEnvManager()
    window.show_with_fade()
    sys.exit(app.exec())