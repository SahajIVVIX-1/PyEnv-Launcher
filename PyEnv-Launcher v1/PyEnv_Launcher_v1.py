import sys
import os
import subprocess
import time
import shutil
import traceback
import json
import tempfile
import signal
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea, QSizePolicy, QSizeGrip,
    QMessageBox, QStyle, QFrame, QTextEdit, QDialog, QListWidgetItem,
    QDialogButtonBox, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView 
)
from PyQt6.QtCore import (Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot, QSettings,
                          QPropertyAnimation, QEasingCurve, QObject)
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QAction

# --- Global Constants ---
# In your AppConfig class...

class AppConfig:
    """Stores global application constants."""
    FONT_MAIN = "Segoe UI"
    
    # --- EDIT THE DARK THEME HERE ---
    DARK_THEME = {
        "background": "#0d1117", 
        "primary": "#161b22", 
        "border": "#30363d", 
        "text": "#c9d1d9", 
        "text_header": "#f0f6fc", 
        "text_secondary": "#8b949e", 
        "accent": "#2f81f7", 
        "success": "#238636", 
        "error": "#da3633", 
        "border_window": "#da3633",  # <-- CHANGED FROM "#87CEEB"
        "git_clean": "#238636", 
        "git_dirty": "#f0b429"
    }
    
    # --- EDIT THE LIGHT THEME HERE ---
    LIGHT_THEME = {
        "background": "#f6f8fa", 
        "primary": "#ffffff", 
        "border": "#d0d7de", 
        "text": "#24292f", 
        "text_header": "#24292f", 
        "text_secondary": "#57606a", 
        "accent": "#0969da", 
        "success": "#1a7f37", 
        "error": "#cf222e", 
        "border_window": "#cf222e",  # <-- CHANGED FROM "#0969da"
        "git_clean": "#1a7f37", 
        "git_dirty": "#d99800"
    }
    
# --- Global State for Exception Handling ---
LAST_ACTION = "Application startup"

# --- Global Exception Handler ---
def global_exception_hook(exctype, value, tb):
    """Catches unhandled exceptions, logs them, and shows a critical error dialog."""
    global LAST_ACTION
    error_message = f"An unexpected error occurred:\n\n{value}"
    traceback_details = "".join(traceback.format_tb(tb))
    try:
        with open("error_log.txt", "a", encoding='utf-8') as f:
            f.write(f"--- {time.ctime()} ---\n")
            f.write(f"Last Action: {LAST_ACTION}\n")
            f.write(f"{error_message}\n")
            f.write(f"{traceback_details}\n\n")
    except Exception as e:
        print(f"CRITICAL: Error logging failed: {e}")

    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle("Unhandled Application Error")
    error_box.setText("A critical error occurred and the application must close.")
    error_box.setInformativeText("Details have been saved to error_log.txt.")
    error_box.setDetailedText(traceback_details)
    error_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    error_box.exec()
    sys.__excepthook__(exctype, value, tb)
    sys.exit(1)

# --- Worker & Helper Classes ---
class CommandThread(QThread):
    finished = pyqtSignal(bool, str, str)
    process_started = pyqtSignal()
    output_received = pyqtSignal(str)

    def __init__(self, base_path, selected_env=None, env_type="venv", command_type="jupyter", **kwargs):
        super().__init__()
        self.base_path = Path(base_path)
        self.selected_env = selected_env
        self.env_type = env_type
        self.command_type = command_type
        self.kwargs = kwargs
        self.process = None
        self._is_running = True

    def run(self):
        command_output = ""
        try:
            full_cmd, shell = self._build_command()

            if not self._is_running: return
            if full_cmd is None:
                self.finished.emit(True, "Process launched in new terminal.", "")
                return

            self.process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' and not shell else 0,
                shell=shell,
                cwd=self.base_path
            )
            self.process_started.emit()

            for line in iter(self.process.stdout.readline, ''):
                if not self._is_running: break
                stripped_line = line.strip()
                self.output_received.emit(stripped_line)
                command_output += stripped_line + "\n"
            self.process.stdout.close()

            stderr_output = self.process.stderr.read().strip()
            if stderr_output: self.output_received.emit(f"ERROR: {stderr_output}")

            return_code = self.process.wait()

            if not self._is_running:
                self.finished.emit(False, f"Command '{self.command_type}' was terminated.", "")
            elif return_code == 0:
                self.finished.emit(True, f"Command '{self.command_type}' completed successfully.", command_output)
            else:
                error_msg = f"Command '{self.command_type}' failed with exit code {return_code}."
                if stderr_output: error_msg += f"\nDetails: {stderr_output}"
                self.finished.emit(False, error_msg, stderr_output)

        except FileNotFoundError as e:
            self.finished.emit(False, f"Error: Command not found. Is it in your PATH? {str(e)}", "")
        except Exception as e:
            self.finished.emit(False, f"An unexpected error occurred in command thread: {str(e)}", "")
        finally:
            self.process = None

    def _build_command(self):
        shell = True
        # --- This is the main if/elif chain. All elifs must align with this first 'if'. ---
        if self.command_type == "create_venv":
            new_env_name = self.kwargs.get("new_env_name")
            return [sys.executable, '-m', 'venv', new_env_name], False
        elif self.command_type == "git_branch":
            return ['git', 'rev-parse', '--abbrev-ref', 'HEAD'], False
        elif self.command_type == "git_status":
            return ['git', 'status', '--porcelain'], False
        elif self.command_type == "git_pull":
            return ['git', 'pull'], False
        elif self.command_type == "git_add":
            return ['git', 'add', '.'], False
        elif self.command_type == "git_commit":
            msg = self.kwargs.get("commit_message", "Automated commit")
            return ['git', 'commit', '-m', msg], False
        elif self.command_type == "poetry_install":
            return ['poetry', 'install'], True
        elif self.command_type == "pdm_sync":
            return ['pdm', 'sync'], True
        elif self.command_type == "list_conda_envs":
             return ['conda', 'env', 'list', '--json'], True
        
        # --- CORRECTLY INDENTED NEW BLOCKS ---
        # Notice how these elifs are at the same level as the ones above.
        elif self.command_type == "pip_outdated":
            return ['pip', 'list', '--outdated', '--format=json'], True
        elif self.command_type == "pip_upgrade":
            package_name = self.kwargs.get("package_name")
            if not package_name: raise ValueError("Package name is required for upgrade.")
            return ['pip', 'install', '--upgrade', package_name], True
        elif self.command_type == "pip_uninstall":
            package_name = self.kwargs.get("package_name")
            if not package_name: raise ValueError("Package name is required for uninstall.")
            return ['pip', 'uninstall', '-y', package_name], True
        # --- END OF CORRECTED BLOCKS ---

        if not self.selected_env:
            raise ValueError("An environment must be selected for this action.")

        cmd_map = {
            "get_env_details": ['python', '--version'], "freeze": ['pip', 'freeze'],
            "pip_list": ['pip', 'list', '--format=json'],
            "launch": (self.kwargs.get("tool", "jupyter notebook")).split(), "activate": []
        }
        if self.command_type in cmd_map:
            cmd_list = cmd_map[self.command_type]
        elif self.command_type == "install_requirements":
            req_path = Path(self.kwargs.get("requirements_path"))
            if req_path.name == "packages.json":
                with open(req_path, 'r', encoding='utf-8') as f: data = json.load(f)
                packages = data.get("packages", [])
                if not packages: raise ValueError("JSON file contains no packages.")
                cmd_list = ['pip', 'install'] + packages
            else:
                cmd_list = ['pip', 'install', '-r', f'"{req_path}"']
        else:
            self.finished.emit(False, f"Unsupported command type: {self.command_type}", "")
            return None, False

        return self._get_activated_command(cmd_list, new_console=(self.command_type in ["launch", "activate"]))

    def _get_activated_command(self, cmd_list, new_console=False):
        command_str = ' '.join(cmd_list)
        if self.env_type == 'conda':
            activation_cmd = f'conda activate "{self.selected_env}"'
        else:
            script_folder = "Scripts" if sys.platform == "win32" else "bin"
            activate_script = self.base_path / self.selected_env / script_folder / "activate"
            if not activate_script.exists():
                raise FileNotFoundError(f"Activation script not found for {self.selected_env}")
            activation_cmd = f'call "{activate_script}"' if sys.platform == "win32" else f'. "{activate_script}"'


        if new_console:
            ext, shell_cmd = ('.bat', 'cmd.exe /k') if sys.platform == 'win32' else ('.sh', 'bash')
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=ext, newline='\n') as tf:
                if sys.platform == 'win32':
                    tf.write(f'@echo off\ncd /d "{self.base_path}"\ntitle PyEnv Launcher - {self.selected_env}\n{activation_cmd}\n')
                    if command_str: tf.write(f'@echo Running: {command_str}\n{command_str}\n')
                    else: tf.write('echo Environment is now active in this terminal.\ncmd.exe /k\n')
                else:
                    tf.write(f'#!/bin/bash\ncd "{self.base_path}"\n{activation_cmd}\n')
                    if command_str: tf.write(f'echo "Running: {command_str}"\n{command_str}\n')
                    else: tf.write('echo "Environment is now active in this terminal."\nexec bash\n')

            if sys.platform != 'win32': os.chmod(tf.name, 0o755)
            subprocess.Popen(f'start "{self.selected_env}" {tf.name}', shell=True) if sys.platform == 'win32' else subprocess.Popen(['gnome-terminal', '--', tf.name])
            QTimer.singleShot(5000, lambda: Path(tf.name).unlink(missing_ok=True))
            return None, True

        return f'{activation_cmd} && {command_str}', True

    def stop_process(self):
        self._is_running = False
        if self.process and self.process.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(f"taskkill /F /T /PID {self.process.pid}", check=True)
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except Exception as e:
                self.process.kill()
                self._is_running = False


class FileChangeHandler(FileSystemEventHandler, QObject):
    file_changed = pyqtSignal()
    def __init__(self):
        FileSystemEventHandler.__init__(self)
        QObject.__init__(self)
    def on_any_event(self, event):
        if event.event_type in ['created', 'deleted', 'moved']:
            self.file_changed.emit()

# --- Dialog Windows ---
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("About PyEnv Launcher")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel("PyEnv Launcher - Jay Swaminarayan")
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        terms_text = QTextEdit()
        terms_text.setReadOnly(True)
        terms_text.setText(
             """**End-User License Agreement for PyEnv Launcher**

Copyright (c) 2025 Chakhdi.local. All Rights Reserved.

**NOTICE TO USER:** 
This End-User License Agreement (EULA) is a legally binding contract between you and Chakhdi.local for the software product "PyEnv Launcher," which includes the computer software and any associated documentation (the "Software").

By installing, copying, or otherwise using the Software, you agree to be bound by the terms of this EULA. If you do not agree to the terms of this EULA, do not install or use the Software.

**1. LICENSE GRANT**
Chakhdi.local grants you a personal, non-transferable, and non-exclusive right to use one copy of the Software on a single computer for your personal or internal business purposes.

**2. RESTRICTIONS ON USE**
You are expressly forbidden from the following actions:
   a) You may not sell, rent, lease, sublicense, or otherwise transfer rights to the Software to any third party.
   b) You may not modify, translate, reverse engineer, decompile, disassemble, or create derivative works based on the Software.
   c) You may not copy the Software, except for one backup copy for archival purposes only.
   d) You may not remove any proprietary notices or labels on the Software.

**3. COPYRIGHT AND INTELLECTUAL PROPERTY**
The Software is the intellectual property of and is owned by Chakhdi.local. Its structure, organization, and code are the valuable trade secrets and confidential information of Chakhdi.local. The Software is protected by copyright law and international treaty provisions.

**4. DISCLAIMER OF WARRANTY**
THE SOFTWARE IS PROVIDED "AS IS" WITHOUT ANY WARRANTY OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE ENTIRE RISK AS TO THE QUALITY AND PERFORMANCE OF THE SOFTWARE IS WITH YOU. SHOULD THE SOFTWARE PROVE DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING, REPAIR, OR CORRECTION.

**5. LIMITATION OF LIABILITY**
IN NO EVENT SHALL CHAKHDI.LOCAL OR ITS SUPPLIERS BE LIABLE FOR ANY DAMAGES WHATSOEVER (INCLUDING, WITHOUT LIMITATION, DAMAGES FOR LOSS OF BUSINESS PROFITS, BUSINESS INTERRUPTION, LOSS OF BUSINESS INFORMATION, OR ANY OTHER PECUNIARY LOSS) ARISING OUT OF THE USE OF OR INABILITY TO USE THIS SOFTWARE, EVEN IF CHAKHDI.LOCAL HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

For permissions and licensing inquiries
Please contact: Sahaj Saliya
"""
        )
        terms_text.setFixedHeight(200)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bbox.accepted.connect(self.accept)

        widgets_to_add = [
            title,
            QLabel("<b>Company:</b> Chakhdi.local"),
            QLabel("<b>Year:</b> 2025"),
            QLabel("Copyright © 2025 Chakhdi.local - All Rights Reserved"),
            self._create_separator(),
            QLabel("<b>Terms and Conditions (MIT License):</b>"),
            terms_text,  # Add the populated QTextEdit here
            bbox
        ]
        for widget in widgets_to_add:
            layout.addWidget(widget)

        if parent and hasattr(parent, 'current_theme'):
            c = parent.current_theme
            self.setStyleSheet(f"""
                QDialog {{ background-color: {c['primary']}; }}
                QLabel, QTextEdit {{ color: {c['text']}; }}
                #aboutTitle {{ font-size: 14pt; font-weight: bold; }}
                QPushButton {{ padding: 8px; }}
            """)

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Settings"); self.setMinimumWidth(400)
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["Dark", "Light"])
        layout.addWidget(self.theme_combo)
        layout.addWidget(QLabel("Default Project Directory:"))
        path_layout = QHBoxLayout(); self.default_path_input = QLineEdit()
        self.browse_btn = QPushButton("Browse..."); path_layout.addWidget(self.default_path_input); path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); layout.addWidget(bbox)
        bbox.accepted.connect(self.accept); bbox.rejected.connect(self.reject); self.browse_btn.clicked.connect(self._browse)
        self._load()
    def _load(self): self.theme_combo.setCurrentText(self.settings.value("theme", "Dark")); self.default_path_input.setText(self.settings.value("default_path", os.path.expanduser("~")))
    def _browse(self): path = QFileDialog.getExistingDirectory(self, "Select Dir", self.default_path_input.text()); self.default_path_input.setText(path) if path else None
    def accept(self): self.settings.setValue("theme", self.theme_combo.currentText()); self.settings.setValue("default_path", self.default_path_input.text()); super().accept()

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Create New Project"); self.setMinimumWidth(450)
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.parent_dir = self.settings.value("default_path", os.path.expanduser("~"))
        layout = QVBoxLayout(self); layout.addWidget(QLabel("Parent Directory:"))
        path_layout = QHBoxLayout(); self.parent_dir_label = QLineEdit(self.parent_dir); self.parent_dir_label.setReadOnly(True)
        browse_btn = QPushButton("Browse..."); browse_btn.clicked.connect(self._browse); path_layout.addWidget(self.parent_dir_label); path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout); layout.addWidget(QLabel("Project Name:"))
        self.project_name_input = QLineEdit(); self.project_name_input.setPlaceholderText("e.g., customer-churn-analysis")
        layout.addWidget(self.project_name_input)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self.accept); bbox.rejected.connect(self.reject); layout.addWidget(bbox)
    def _browse(self): path = QFileDialog.getExistingDirectory(self, "Select Parent", self.parent_dir); self.parent_dir = path if path else self.parent_dir; self.parent_dir_label.setText(self.parent_dir)
    def get_details(self): return self.parent_dir, self.project_name_input.text().strip()

class GitCommitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Git Commit"); self.setMinimumWidth(400)
        layout = QVBoxLayout(self); layout.addWidget(QLabel("Enter commit message:"))
        self.commit_message_input = QTextEdit(); self.commit_message_input.setPlaceholderText("A brief summary of the changes...")
        self.commit_message_input.setMinimumHeight(100); layout.addWidget(self.commit_message_input)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self.accept); bbox.rejected.connect(self.reject); layout.addWidget(bbox)
    def get_commit_message(self): return self.commit_message_input.toPlainText().strip()


# --- UI Manager ---
class UIManager:
    """Handles the creation and layout of all UI widgets."""
    def __init__(self, main_window):
        self.main_window = main_window
        self._setup_main_layout()
        self._setup_ui_components()
        self.collect_interactive_widgets()

    def _setup_main_layout(self):
        self.main_window.main_layout = QVBoxLayout(self.main_window)
        self.main_window.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_window.container = QWidget(self.main_window)
        self.main_window.container.setObjectName("container")
        self.main_window.main_layout.addWidget(self.main_window.container)
        self.container_layout = QVBoxLayout(self.main_window.container)
        self.container_layout.setContentsMargins(2, 2, 2, 2)
        self.container_layout.setSpacing(0)

    def _setup_ui_components(self):
        # The main top-to-bottom layout for the entire app content area
        self.container_layout.addWidget(self._create_title_bar())
        
        # --- NEW TWO-COLUMN STRUCTURE ---
        # 1. Create a container widget for our columns
        columns_container = QWidget()
        columns_layout = QHBoxLayout(columns_container) # Main horizontal layout
        columns_layout.setContentsMargins(15, 10, 15, 15)
        columns_layout.setSpacing(15)

        # 2. Create the Left Column (for controls)
        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(15)
        
        # 3. Create the Right Column (for lists)
        right_column_widget = QWidget()
        right_column_layout = QVBoxLayout(right_column_widget)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(15)
        
        # 4. Add the column widgets to the main horizontal layout
        # We give the right column slightly more space (3 parts vs 2)
        columns_layout.addWidget(left_column_widget, 1)
        columns_layout.addWidget(right_column_widget, 1)

        # --- POPULATE THE LEFT COLUMN ---
        left_column_layout.addLayout(self._create_path_section())
        left_column_layout.addWidget(self._create_git_section())
        left_column_layout.addLayout(self._create_new_venv_section())
        left_column_layout.addWidget(AboutDialog(self.main_window)._create_separator())
        left_column_layout.addLayout(self._create_manage_venv_section())
        left_column_layout.addWidget(self._create_poetry_pdm_section())
        left_column_layout.addStretch() # Pushes everything up

        # --- POPULATE THE RIGHT COLUMN ---
        right_column_layout.addLayout(self._create_files_section())
        right_column_layout.addLayout(self._create_log_section())

        # Set the main content of the container
        self.container_layout.addWidget(columns_container)
        
        # --- FOOTER REMAINS AT THE BOTTOM ---
        footer_container = QWidget() # Put footer in its own container
        footer_layout = self._create_footer_section()
        footer_container.setLayout(footer_layout)
        footer_container.setContentsMargins(15, 0, 0, 5) # Adjust margins
        self.container_layout.addWidget(footer_container)

    def collect_interactive_widgets(self):
        self.main_window.interactive_widgets = self.main_window.container.findChildren(QPushButton) + \
                                           self.main_window.container.findChildren(QComboBox) + \
                                           self.main_window.container.findChildren(QLineEdit)

    def _create_title_bar(self):
        title_bar = QWidget(); title_bar.setObjectName("titleBar"); title_bar.setFixedHeight(40)
        layout = QHBoxLayout(title_bar); layout.setContentsMargins(10, 0, 5, 0)
        self.title_label = QLabel("📘 PyEnv Launcher"); self.title_label.setObjectName("titleLabel")
        self.about_btn = QPushButton("?"); self.about_btn.setObjectName("controlBtn"); self.about_btn.setToolTip("About PyEnv Launcher"); self.about_btn.setFixedSize(30, 30)
        self.settings_btn = QPushButton(); self.settings_btn.setIcon(self.main_window.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)); self.settings_btn.setObjectName("controlBtn"); self.settings_btn.setToolTip("Open Settings")
        self.running_indicator = QLabel("●"); self.running_indicator.setObjectName("runningIndicator"); self.running_indicator.setVisible(False); self.running_indicator.setToolTip("A command process is currently active.")
        self.minimize_btn = QPushButton("—"); self.close_btn = QPushButton("✕")
        for btn, tip in [(self.minimize_btn, "Minimize"), (self.close_btn, "Close")]:
            btn.setObjectName("controlBtn"); btn.setFixedSize(30, 30); btn.setToolTip(tip)
        layout.addWidget(self.title_label); layout.addStretch()
        layout.addWidget(self.about_btn); layout.addWidget(self.settings_btn); layout.addWidget(self.running_indicator)
        layout.addWidget(self.minimize_btn); layout.addWidget(self.close_btn)
        return title_bar

    def _create_path_section(self):
        layout = QVBoxLayout(); layout.setSpacing(8); layout.addWidget(QLabel("Project Directory"))
        path_layout = QHBoxLayout(); self.path_input = QLineEdit(); self.recent_paths_btn = QPushButton("▼"); self.recent_paths_btn.setObjectName("recentBtn"); self.recent_paths_btn.setFixedWidth(30)
        path_layout.addWidget(self.path_input); path_layout.addWidget(self.recent_paths_btn); layout.addLayout(path_layout)
        btn_layout = QHBoxLayout(); self.browse_btn = QPushButton("Select Directory"); self.new_project_btn = QPushButton("New Project"); self.open_btn = QPushButton("Open Path")
        btn_layout.addWidget(self.browse_btn); btn_layout.addWidget(self.new_project_btn); btn_layout.addWidget(self.open_btn); layout.addLayout(btn_layout)
        return layout

    def _create_git_section(self):
        self.git_groupbox = QGroupBox("Git Status"); layout = QHBoxLayout(self.git_groupbox)
        self.git_status_label = QLabel("Not a git repository."); self.git_status_label.setObjectName("detailsLabel")
        self.git_pull_btn = QPushButton("Git Pull"); self.git_commit_btn = QPushButton("Git Commit")
        layout.addWidget(self.git_status_label, 1); layout.addStretch(); layout.addWidget(self.git_pull_btn); layout.addWidget(self.git_commit_btn)
        self.git_groupbox.setVisible(False); return self.git_groupbox

    def _create_new_venv_section(self):
        layout = QVBoxLayout(); layout.setSpacing(8); layout.addWidget(QLabel("Create New Virtual Environment"))
        creation_layout = QHBoxLayout(); self.new_venv_name_input = QLineEdit(); self.new_venv_name_input.setPlaceholderText("Enter new environment name (no spaces)")
        self.create_venv_btn = QPushButton("Create"); self.create_venv_btn.setObjectName("createBtn")
        creation_layout.addWidget(self.new_venv_name_input); creation_layout.addWidget(self.create_venv_btn); layout.addLayout(creation_layout)
        return layout

    # In the UIManager class...
    # In the UIManager class, replace this entire method

    def _create_manage_venv_section(self):
        layout = QVBoxLayout(); layout.setSpacing(8); layout.addWidget(QLabel("Manage Existing Environment"))
        env_layout = QHBoxLayout(); self.venv_dropdown = QComboBox(); self.delete_venv_btn = QPushButton("🗑️"); self.delete_venv_btn.setObjectName("deleteBtn"); self.delete_venv_btn.setFixedWidth(40)
        env_layout.addWidget(self.venv_dropdown); env_layout.addWidget(self.delete_venv_btn); layout.addLayout(env_layout)
        self.env_details_label = QLabel("Select an environment to see details."); self.env_details_label.setObjectName("detailsLabel"); layout.addWidget(self.env_details_label)
        self.package_action_group = QGroupBox("Package Management")
        package_action_layout = QHBoxLayout(self.package_action_group)
        self.check_updates_btn = QPushButton("Check for Updates")
        self.upgrade_package_btn = QPushButton("Upgrade Selected")
        self.uninstall_package_btn = QPushButton("Uninstall Selected")
        package_action_layout.addWidget(self.check_updates_btn)
        package_action_layout.addWidget(self.upgrade_package_btn)
        package_action_layout.addWidget(self.uninstall_package_btn)
        layout.addWidget(self.package_action_group)
        self.package_table = QTableWidget()
        self.package_table.setColumnCount(3)
        self.package_table.setHorizontalHeaderLabels(["Package", "Version", "Latest"])
        self.package_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.package_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.package_table.verticalHeader().setVisible(False)
        self.package_table.setAlternatingRowColors(True)
        self.package_table.setFixedHeight(240) # Give it a taller fixed initial height
        header = self.package_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.package_table)
        self.package_action_group.setVisible(False)
        self.package_table.setVisible(False)
        pkg_layout = QHBoxLayout(); self.install_reqs_btn = QPushButton("Install from File"); self.export_json_btn = QPushButton("Export to packages.json"); self.freeze_btn = QPushButton("Freeze to requirements.txt")
        pkg_layout.addWidget(self.install_reqs_btn); pkg_layout.addWidget(self.export_json_btn); pkg_layout.addWidget(self.freeze_btn); layout.addLayout(pkg_layout)
        launch_layout = QHBoxLayout(); self.activate_btn = QPushButton("Activate Terminal"); self.launch_jupyter_btn = QPushButton("Launch Jupyter"); self.launch_jupyter_btn.setObjectName("launchBtn")
        launch_layout.addWidget(self.activate_btn); launch_layout.addWidget(self.launch_jupyter_btn); layout.addLayout(launch_layout)
        return layout

    def _create_poetry_pdm_section(self):
        self.build_tools_groupbox = QGroupBox("Build Tools"); layout = QHBoxLayout(self.build_tools_groupbox)
        self.poetry_install_btn = QPushButton("Poetry Install"); self.pdm_sync_btn = QPushButton("PDM Sync")
        layout.addWidget(self.poetry_install_btn); layout.addWidget(self.pdm_sync_btn); self.build_tools_groupbox.setVisible(False); return self.build_tools_groupbox

    def _create_files_section(self):
        layout = QVBoxLayout(); layout.setSpacing(8); layout.addWidget(QLabel("Project Directory Contents"))
        self.file_list = QListWidget(); self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); layout.addWidget(self.file_list); return layout

    def _create_log_section(self):
        layout = QVBoxLayout(); layout.setSpacing(4); header = QHBoxLayout(); header.addWidget(QLabel("Activity Log")); header.addStretch()
        self.clear_log_btn = QPushButton("Clear"); header.addWidget(self.clear_log_btn); layout.addLayout(header)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True); self.log_output.setObjectName("logOutput")
        # We've reduced the height here to give more space to the file list above.
        self.log_output.setFixedHeight(250) 
        layout.addWidget(self.log_output)
        return layout
        
    def _create_footer_section(self):
        footer = QHBoxLayout(); footer.setContentsMargins(0, 5, 0, 0); self.status_label = QLabel("Welcome!"); self.status_label.setObjectName("statusLabel")
        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(False); self.progress_bar.setVisible(False); self.progress_bar.setFixedHeight(6)
        status_layout = QVBoxLayout(); status_layout.addWidget(self.status_label); status_layout.addWidget(self.progress_bar); footer.addLayout(status_layout, 1)
        footer.addWidget(QSizeGrip(self.main_window.container)); return footer


if __name__ == "__main__":
    sys.excepthook = global_exception_hook
    app = QApplication(sys.argv)
    app.setFont(QFont(AppConfig.FONT_MAIN, 9))
    window = JupyterLauncher()
    window.show_with_fade()
    sys.exit(app.exec())