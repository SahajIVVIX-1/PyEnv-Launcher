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
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QAction, QColor

# --- Global Constants ---
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
        "border_window": "#da3633",
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
        "border_window": "#cf222e",
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
            if full_cmd is None: # This indicates a new console was launched by the _get_activated_command
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
        if self.command_type == "create_venv":
            new_env_name = self.kwargs.get("new_env_name")
            python_version = self.kwargs.get("python_version")
            if sys.platform == 'win32' and python_version:
                # Use py.exe launcher for specific Python version on Windows
                return ['py', f'-{python_version}', '-m', 'venv', new_env_name], False
            else:
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
        elif self.command_type == "check_pipx":
            return ['pipx', '--version'], True # Simple check if pipx exists
        elif self.command_type == "pipx_list":
            return ['pipx', 'list', '--json'], True
        elif self.command_type == "pipx_install":
            package = self.kwargs.get("package")
            return ['pipx', 'install', package], True
        elif self.command_type == "pipx_upgrade":
            package = self.kwargs.get("package")
            return ['pipx', 'upgrade', package], True
        elif self.command_type == "pipx_uninstall":
            package = self.kwargs.get("package")
            return ['pipx', 'uninstall', package], True
        elif self.command_type == "pipx_ensurepath":
            return ['pipx', 'ensurepath'], True

        if not self.selected_env and self.command_type not in ["get_env_details", "list_conda_envs", "pipx_list", "pipx_install", "pipx_upgrade", "pipx_uninstall", "pipx_ensurepath", "check_pipx"]:
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
            if sys.platform == 'win32':
                # For Windows, launch cmd.exe /k to keep the console open
                full_command = f'start cmd.exe /k "{activation_cmd} && {command_str}"'
                subprocess.Popen(full_command, shell=True)
                return None, True # Indicate a new console was launched
            else:
                # For Linux/macOS, use a temporary script and terminal emulator
                ext, shell_cmd = ('.bat', 'cmd.exe /k') if sys.platform == 'win32' else ('.sh', 'bash')
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=ext, newline='\n') as tf:
                    tf.write(f'#!/bin/bash\ncd "{self.base_path}"\n{activation_cmd}\n')
                    if command_str: tf.write(f'echo "Running: {command_str}"\n{command_str}\n')
                    else: tf.write('echo "Environment is now active in this terminal."\nexec bash\n')

                os.chmod(tf.name, 0o755)
                # This subprocess.Popen needs to be non-blocking
                subprocess.Popen(['gnome-terminal', '--', tf.name] if sys.platform != 'win32' else ['cmd.exe', '/C', f'start "" "{tf.name}"'], shell=False)
                # Removed the QTimer.singleShot for deleting the file on Windows since cmd.exe /k keeps it open.
                # For non-Windows, we might still want this, but for simplicity, let's keep it consistent for now.
                # If a persistent console is intended on non-Windows, we'd also remove the deletion there.
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
    def _load(self): self.theme_combo.setCurrentText(self.settings.value("theme", "Dark")); self.default_path_input.setText(self.settings.value("default_path", str(Path.home()))) # Changed here
    def _browse(self): path = QFileDialog.getExistingDirectory(self, "Select Dir", self.default_path_input.text()); self.default_path_input.setText(path) if path else None
    def accept(self): self.settings.setValue("theme", self.theme_combo.currentText()); self.settings.setValue("default_path", self.default_path_input.text()); super().accept()

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Create New Project"); self.setMinimumWidth(450)
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.parent_dir = self.settings.value("default_path", str(Path.home())) # Changed here
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
        columns_layout.addWidget(left_column_widget, 1)
        columns_layout.addWidget(right_column_widget, 1)

        # --- POPULATE THE LEFT COLUMN ---
        left_column_layout.addLayout(self._create_path_section())
        left_column_layout.addWidget(self._create_git_section())
        left_column_layout.addLayout(self._create_new_venv_section())
        left_column_layout.addWidget(AboutDialog(self.main_window)._create_separator())
        left_column_layout.addLayout(self._create_manage_venv_section())
        left_column_layout.addWidget(self._create_poetry_pdm_section())
        left_column_layout.addWidget(self._create_pipx_section()) # ADDED PIPX SECTION
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
                                           self.main_window.container.findChildren(QLineEdit) + \
                                           self.main_window.container.findChildren(QTextEdit) # Added QTextEdit for pipx_output

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
        
        # New: Python Version Input
        python_ver_layout = QHBoxLayout()
        python_ver_layout.addWidget(QLabel("Python Version (optional):"))
        self.new_venv_python_version_input = QLineEdit()
        self.new_venv_python_version_input.setPlaceholderText("e.g., 3.9, 3.10 (uses py.exe on Win)")
        python_ver_layout.addWidget(self.new_venv_python_version_input)
        layout.addLayout(python_ver_layout)

        creation_layout = QHBoxLayout(); self.new_venv_name_input = QLineEdit(); self.new_venv_name_input.setPlaceholderText("Enter new environment name (no spaces)")
        self.create_venv_btn = QPushButton("Create"); self.create_venv_btn.setObjectName("createBtn")
        creation_layout.addWidget(self.new_venv_name_input); creation_layout.addWidget(self.create_venv_btn); layout.addLayout(creation_layout)
        return layout

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

    def _create_pipx_section(self):
        self.pipx_groupbox = QGroupBox("Global Python Tools (pipx)");
        layout = QVBoxLayout(self.pipx_groupbox); layout.setSpacing(8)

        layout.addWidget(QLabel("Manage pipx installed applications:"));

        # Install/Upgrade/Uninstall
        pkg_action_layout = QHBoxLayout()
        self.pipx_package_input = QLineEdit()
        self.pipx_package_input.setPlaceholderText("Enter package name (e.g., black, rich-cli)")
        self.pipx_install_btn = QPushButton("Install")
        self.pipx_upgrade_btn = QPushButton("Upgrade")
        self.pipx_uninstall_btn = QPushButton("Uninstall")

        pkg_action_layout.addWidget(self.pipx_package_input)
        pkg_action_layout.addWidget(self.pipx_install_btn)
        pkg_action_layout.addWidget(self.pipx_upgrade_btn)
        pkg_action_layout.addWidget(self.pipx_uninstall_btn)
        layout.addLayout(pkg_action_layout)

        # List/Ensure Path
        other_actions_layout = QHBoxLayout()
        self.pipx_list_btn = QPushButton("List Installed Tools")
        self.pipx_ensurepath_btn = QPushButton("Ensure Path")
        other_actions_layout.addWidget(self.pipx_list_btn)
        other_actions_layout.addWidget(self.pipx_ensurepath_btn)
        layout.addLayout(other_actions_layout)

        # Output area for pipx commands
        layout.addWidget(QLabel("pipx Output:"))
        self.pipx_output = QTextEdit()
        self.pipx_output.setReadOnly(True)
        self.pipx_output.setFixedHeight(120)
        self.pipx_output.setObjectName("pipxOutput")
        layout.addWidget(self.pipx_output)

        self.pipx_groupbox.setVisible(False)
        return self.pipx_groupbox

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


# --- Main Application Window ---
class JupyterLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.current_theme = AppConfig.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else AppConfig.LIGHT_THEME
        self.setWindowTitle("PyEnv Launcher"); self.setObjectName("JupyterLauncher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(1100, 850)

        self.observer = None
        self.old_pos = None
        self.command_thread = None
        self.pipx_thread = None # Added for pipx commands
        self.interactive_widgets = []
        self.package_data = {}
        self.pipx_data = {} # Added for pipx list

        self.ui = UIManager(self)
        self._apply_stylesheet()
        self._connect_signals()
        self._setup_animations()
        self._load_app_settings()
        self._on_path_changed()

    def _connect_signals(self):
        # Title Bar
        self.ui.about_btn.clicked.connect(self._open_about_dialog)
        self.ui.settings_btn.clicked.connect(self._open_settings)
        self.ui.close_btn.clicked.connect(self._initiate_close)
        self.ui.minimize_btn.clicked.connect(self.showMinimized)
        # Path Section
        self.ui.path_input.textChanged.connect(self._on_path_changed)
        self.ui.recent_paths_btn.clicked.connect(self._show_recent_paths_menu)
        self.ui.browse_btn.clicked.connect(self._browse_path)
        self.ui.new_project_btn.clicked.connect(self._create_new_project)
        self.ui.open_btn.clicked.connect(self._open_in_explorer)
        # Git Section
        self.ui.git_pull_btn.clicked.connect(self._git_pull)
        self.ui.git_commit_btn.clicked.connect(self._git_commit_stage_1_check_status)
        # New Venv Section
        self.ui.create_venv_btn.clicked.connect(self._create_environment)
        # Manage Venv Section
        self.ui.venv_dropdown.currentTextChanged.connect(self._on_venv_selection_changed)
        self.ui.delete_venv_btn.clicked.connect(self._delete_environment)
        self.ui.install_reqs_btn.clicked.connect(self._install_requirements)
        self.ui.freeze_btn.clicked.connect(self._freeze_requirements)
        self.ui.export_json_btn.clicked.connect(self._export_to_json)
        self.ui.activate_btn.clicked.connect(self._activate_environment)
        self.ui.launch_jupyter_btn.clicked.connect(self._launch_jupyter)
        # Build Tools Section
        self.ui.poetry_install_btn.clicked.connect(self._poetry_install)
        self.ui.pdm_sync_btn.clicked.connect(self._pdm_sync)
        # File List & Log
        self.ui.file_list.customContextMenuRequested.connect(self._show_file_context_menu)
        self.ui.clear_log_btn.clicked.connect(self.ui.log_output.clear)
        self.ui.check_updates_btn.clicked.connect(self._check_for_package_updates)
        self.ui.upgrade_package_btn.clicked.connect(self._upgrade_package)
        self.ui.uninstall_package_btn.clicked.connect(self._uninstall_package)
        # pipx Section
        self.ui.pipx_list_btn.clicked.connect(self._pipx_list)
        self.ui.pipx_install_btn.clicked.connect(self._pipx_install)
        self.ui.pipx_upgrade_btn.clicked.connect(self._pipx_upgrade)
        self.ui.pipx_uninstall_btn.clicked.connect(self._pipx_uninstall)
        self.ui.pipx_ensurepath_btn.clicked.connect(self._pipx_ensurepath)

    def _apply_stylesheet(self):
        c = self.current_theme
        self.setStyleSheet(f"""
            #JupyterLauncher{{background:transparent;}}
            #container{{background-color:{c['primary']};border:2px solid {c['border_window']};border-radius:15px;}}
            QWidget{{font-family:"{AppConfig.FONT_MAIN}";color:{c['text']};font-size:9pt;}}
            #titleBar{{background-color:{c['background']};border-top-left-radius:13px;border-top-right-radius:13px;}}
            #titleLabel{{color:{c['text_header']};font-weight:bold;font-size:11pt;padding-left:5px;}}
            #controlBtn,#recentBtn,#deleteBtn{{background:transparent;border:none;font-size:12pt;font-weight:bold;}}
            #controlBtn:hover,#recentBtn:hover,#deleteBtn:hover{{background:{c['border']};border-radius:4px;}}
            QScrollArea,QScrollArea>QWidget>QWidget{{background:transparent;border:none;}}
            QLabel{{font-weight:bold;background:transparent;}}
            #detailsLabel{{font-weight:normal;color:{c['text_secondary']};}}
            QLineEdit,QComboBox,QTextEdit{{background-color:{c['background']};border:1px solid {c['border']};border-radius:6px;padding:7px;}}
            QLineEdit:focus,QComboBox:focus,QTextEdit:focus{{border-color:{c['accent']};}}
            QComboBox QAbstractItemView{{background-color:{c['background']};border:1px solid {c['border']};selection-background-color:{c['accent']};color:{c['text']};outline:0px;}}
            QComboBox QAbstractItemView::item{{padding:10px 6px;}}
            QPushButton{{background-color:{c['border']};border:1px solid {c['border']};border-radius:6px;padding:8px;font-weight:bold;}}
            QPushButton:hover{{border-color:#8b949e;}}
            QPushButton:pressed{{background-color:#21262d;}}
            QPushButton:disabled{{background-color:{c['border']};color:{c['text_secondary']};border-color:{c['border']};}}
            #createBtn{{background-color:{c['error']};border-color:{c['error']};}} #createBtn:hover{{background-color:#b82c2a;}}
            #statusLabel{{font-weight:normal;background-color:transparent;}}
            #runningIndicator{{color:{c['success']};font-size:16pt;font-weight:bold;padding-bottom:4px;}}
            QProgressBar{{border-radius:3px;background-color:{c['border']};text-align:center;}}
            QProgressBar::chunk{{background-color:{c['accent']};border-radius:3px;}}
            QListWidget,#logOutput,#pipxOutput{{background-color:{c['background']};border:1px solid {c['border']};border-radius:6px;padding:4px;}}
            QListWidget::item{{padding:6px;border-radius:4px;}} QListWidget::item:hover{{background-color:{c['border']};}}
            QListWidget::item:selected{{background-color:{c['accent']};color:white;}}
            QMenu{{background-color:{c['primary']};border:1px solid {c['border']};}} QMenu::item:selected{{background-color:{c['accent']};}}
            QGroupBox{{font-weight:bold;border:1px solid {c['border']};border-radius:6px;margin-top:10px;}}
            QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;padding:0 5px;left:10px;}}
            QTableWidget {{
                background-color: {c['background']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                gridline-color: {c['border']};
                alternate-background-color: {c['background']};
            }}
            QTableWidget::item {{
                padding: 6px;
                color: {c['text']};
            }}
            QTableWidget::item:selected {{
                background-color: {c['accent']};
                color: #ffffff;
            }}
            QHeaderView::section {{
                background-color: {c['background']};
                border-bottom: 2px solid {c['border']};
                padding: 6px;
                font-weight: bold;
            }}

            /* === STYLE THE MAIN SCROLLBARS === */
            QScrollBar:vertical {{
                border: none;
                background: {c['primary']};
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {c['border']};
                min-height: 25px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {c['accent']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {c['primary']};
                height: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {c['border']};
                min-width: 25px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {c['accent']};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background: none;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
        """)

    def _set_ui_enabled(self, enabled):
        for widget in self.interactive_widgets:
            if widget != self.ui.clear_log_btn: # Always allow clear log
                widget.setEnabled(enabled)

    def _run_command(self, command_type, on_finish=None, **kwargs):
        global LAST_ACTION
        LAST_ACTION = f"Running command '{command_type}' with args {kwargs}"
        
        # Check if the command is pipx-related
        is_pipx_command = command_type.startswith("pipx_") or command_type == "check_pipx"

        if self.command_thread and self.command_thread.isRunning():
            self._update_status("A project command is already running. Please wait.", "error")
            return
        if self.pipx_thread and self.pipx_thread.isRunning() and is_pipx_command:
            self._update_status("A pipx command is already running. Please wait.", "error")
            return
        
        base_path = self.ui.path_input.text().strip()
        if not Path(base_path).is_dir() and command_type not in ['list_conda_envs', 'check_pipx', 'pipx_list', 'pipx_install', 'pipx_upgrade', 'pipx_uninstall', 'pipx_ensurepath']:
            self._update_status("Invalid project directory specified.", "error")
            return
        
        env_text = self.ui.venv_dropdown.currentText()
        env_data = self.ui.venv_dropdown.currentData()
        env_name = env_text.split(' (')[0] if env_text else None
        env_type = env_data or "venv"

        required_env_commands = ["get_env_details", "freeze", "pip_list", "launch", "activate", "install_requirements", "pip_outdated", "pip_upgrade", "pip_uninstall"]
        if command_type in required_env_commands and (not env_name or "found" in env_name):
            self._update_status("A valid environment must be selected for this action.", "error")
            return
            
        self._set_ui_enabled(False)
        
        thread_to_use = self.command_thread
        if is_pipx_command:
            self.pipx_thread = CommandThread(base_path, env_name, env_type, command_type, **kwargs)
            thread_to_use = self.pipx_thread
        else:
            self.command_thread = CommandThread(base_path, env_name, env_type, command_type, **kwargs)
            thread_to_use = self.command_thread
            
        thread_to_use.output_received.connect(self._log_message if not is_pipx_command else self._pipx_log_message)
        thread_to_use.process_started.connect(lambda: self._set_progress_bar_active(True))
        thread_to_use.finished.connect(lambda s, m, o: self._on_command_finished(s, m, o, on_finish, is_pipx_command))
        thread_to_use.start()
        self._log_message(f"Starting: {command_type}...")

    def _on_command_finished(self, success, message, command_output, on_finish_callback, is_pipx_command):
        self._set_progress_bar_active(False)
        self._set_ui_enabled(True)
        self._update_status(message, "success" if success else "error")
        (self._log_message if not is_pipx_command else self._pipx_log_message)(f"Finished: {message}")
        if success and on_finish_callback:
            on_finish_callback(command_output)
        if self.command_thread and self.command_thread.command_type in ['git_pull', 'git_commit']:
            self._update_git_status()
        if is_pipx_command:
            self.pipx_thread = None # Clear pipx thread
            self._check_pipx_availability(auto_list=False) # Re-check status without listing immediately

    def _open_about_dialog(self): AboutDialog(self).exec()
    def _open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.settings.sync()
            self.current_theme = AppConfig.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else AppConfig.LIGHT_THEME
            self._apply_stylesheet()
            self._update_status("Settings saved and theme updated.", "info")

    def _load_app_settings(self):
        self.current_theme = AppConfig.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else AppConfig.LIGHT_THEME
        default_path = self.settings.value("default_path", str(Path.home())) # Changed here
        self.ui.path_input.setText(default_path)
        self._add_to_recent_paths(default_path)

    def _on_path_changed(self):
        if not hasattr(self, '_path_change_timer'):
            self._path_change_timer = QTimer()
            self._path_change_timer.setSingleShot(True)
            self._path_change_timer.timeout.connect(self.discover_resources)
        self._path_change_timer.start(500)

    def discover_resources(self):
        """High-level method to discover all resources for the current path."""
        path = Path(self.ui.path_input.text().strip())
        if path.is_dir():
            self._populate_file_list(path)
            self._update_file_observer(path)
            self._add_to_recent_paths(str(path))
            self._update_git_status()
            self._update_build_tool_visibility()
            self._find_and_populate_venvs(path)
            self._check_pipx_availability() # Check pipx status
        else:
            self.ui.git_groupbox.setVisible(False)
            self.ui.build_tools_groupbox.setVisible(False)
            self.ui.pipx_groupbox.setVisible(False) # Hide pipx if path invalid
            self.ui.file_list.clear()

    def _add_to_recent_paths(self, path):
        if not path or not os.path.isdir(path): return
        recent = self.settings.value("recent_paths", [], type=list)
        if path in recent: recent.remove(path)
        recent.insert(0, path)
        self.settings.setValue("recent_paths", recent[:10])

    def _clear_recent_paths(self):
        reply = QMessageBox.question(self, 'Confirm Clear History',
                                     "Are you sure you want to clear all recent project history?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.remove("recent_paths")
            self._update_status("Recent project history cleared.", "success")
            self._log_message("Recent project history cleared by user.")

    def _show_recent_paths_menu(self):
        recent = self.settings.value("recent_paths", [], type=list)
        menu = QMenu(self)

        icon_pixmap = self.style().standardPixmap(QStyle.StandardPixmap.SP_DirIcon)
        small_icon = QIcon(icon_pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        if recent:
            for path_str in recent:
                display_path = Path(path_str).as_posix()
                action = QAction(small_icon, display_path, self)
                action.triggered.connect(lambda checked, p=path_str: self.ui.path_input.setText(p))
                menu.addAction(action)
            menu.addSeparator()
        else:
            empty_action = QAction("No recent paths", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)

        trash_pixmap = self.style().standardPixmap(QStyle.StandardPixmap.SP_TrashIcon)
        small_trash_icon = QIcon(trash_pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        clear_action = QAction(small_trash_icon, "Clear Recent History", self)
        clear_action.setEnabled(bool(recent))
        clear_action.triggered.connect(self._clear_recent_paths)
        menu.addAction(clear_action)

        menu.exec(self.ui.recent_paths_btn.mapToGlobal(QPoint(0, self.ui.recent_paths_btn.height())))

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.ui.path_input.text())
        if path: self.ui.path_input.setText(path)

    def _open_in_explorer(self):
        path = self.ui.path_input.text().strip()
        if os.path.isdir(path):
            os.startfile(path)
        else:
            self._update_status("Directory not found.", "error")

    def _create_environment(self):
        name = self.ui.new_venv_name_input.text().strip()
        python_version = self.ui.new_venv_python_version_input.text().strip()
        
        if not name or ' ' in name:
            self._update_status("Invalid environment name. No spaces allowed.", "error"); return
        if (Path(self.ui.path_input.text().strip()) / name).exists():
            self._update_status(f"Directory or file '{name}' already exists.", "error"); return
        
        # Pass python_version if provided
        self._run_command("create_venv", new_env_name=name, python_version=python_version, on_finish=lambda _: self.discover_resources())
        self.ui.new_venv_name_input.clear()
        # Optionally, clear python version input if it's meant for single use
        # self.ui.new_venv_python_version_input.clear()

    def _delete_environment(self):
        env_text = self.ui.venv_dropdown.currentText()
        if not env_text or "found" in env_text: return
        env_name = env_text.split(' (')[0]
        env_path = Path(self.ui.path_input.text().strip()) / env_name
        
        reply = QMessageBox.question(self, 'Confirm Deletion', f"Are you sure you want to permanently delete the environment '{env_name}'?\n\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # For conda envs, we'd need to run `conda env remove -n env_name`
                # For now, this assumes local venvs
                shutil.rmtree(env_path)
                QTimer.singleShot(250, self.discover_resources)
                self._update_status(f"Environment '{env_name}' deleted successfully.", "success")
            except Exception as e:
                self._update_status(f"Error deleting environment: {e}", "error")

    def _on_venv_selection_changed(self, name):
        self.ui.package_action_group.setVisible(False)
        self.ui.package_table.setVisible(False)
        self.ui.package_table.clearContents()
        self.package_data = {}  
        if name and "found" not in name:
            self.ui.package_action_group.setVisible(True)
            self.ui.package_table.setVisible(True)
            # We only start the FIRST command. Its callback will start the next one.
            self._run_command("get_env_details", on_finish=self._update_env_details)
        else:
            self.ui.env_details_label.setText("Select an environment to see details.")

    def _update_env_details(self, py_ver):
        name = self.ui.venv_dropdown.currentText().split(' (')[0]
        path = Path(self.ui.path_input.text().strip()) / name
        try:
            self.ui.env_details_label.setText(f"Version: {py_ver.strip()} | Created: {time.ctime(os.path.getctime(path))}")
        except FileNotFoundError:
            self.ui.env_details_label.setText("Details unavailable (environment may be remote or deleted).")
        
        # NOW, after the first command is done, we start the second one.
        self._fetch_package_list()

    def _install_requirements(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Requirements File", self.ui.path_input.text(), "Package Files (*.txt *.json)")
        if path: self._run_command("install_requirements", requirements_path=path)
     
    def _fetch_package_list(self):
        """Initiates the command to get all installed packages."""
        self.ui.package_table.clearContents()
        self.ui.package_table.setRowCount(0)
        self._update_status("Fetching installed packages...", "info")
        self._run_command("pip_list", on_finish=self._populate_package_table)

    def _populate_package_table(self, json_output):
        """Parses the 'pip list' output and populates the package table."""
        try:
            packages = json.loads(json_output)
            self.package_data = {pkg['name']: pkg for pkg in packages}
            self.ui.package_table.setRowCount(len(packages))
            
            for row, pkg in enumerate(packages):
                name_item = QTableWidgetItem(pkg['name'])
                version_item = QTableWidgetItem(pkg['version'])
                latest_item = QTableWidgetItem("N/A") # Placeholder for outdated check
                
                self.ui.package_table.setItem(row, 0, name_item)
                self.ui.package_table.setItem(row, 1, version_item)
                self.ui.package_table.setItem(row, 2, latest_item)
                
            self.ui.package_table.resizeColumnsToContents()
            self._update_status(f"Found {len(packages)} packages.", "success")
            
            # Automatically check for updates after populating
            self._check_for_package_updates()
        except json.JSONDecodeError:
            self._update_status("Failed to parse package list.", "error")
            self._log_message(f"Error decoding JSON from pip list: {json_output}")

    def _check_for_package_updates(self):
        """Runs the 'pip list --outdated' command."""
        self._update_status("Checking for outdated packages...", "info")
        self._run_command("pip_outdated", on_finish=self._highlight_outdated_packages)

    def _highlight_outdated_packages(self, json_output):
        """Parses the outdated list and updates the table UI."""
        try:
            outdated_packages = json.loads(json_output)
            if not outdated_packages:
                self._update_status("All packages are up-to-date.", "success")
                return

            outdated_map = {pkg['name']: pkg['latest_version'] for pkg in outdated_packages}

            # Define the QColor object once outside the loop for efficiency
            dirty_color = QColor(self.current_theme['git_dirty']) # <--- CHANGE HERE

            for row in range(self.ui.package_table.rowCount()):
                name_item = self.ui.package_table.item(row, 0)
                if name_item and name_item.text() in outdated_map:
                    latest_version = outdated_map[name_item.text()]
                    self.ui.package_table.item(row, 2).setText(latest_version)
                    # Highlight the entire row for visibility
                    for col in range(3):
                        item = self.ui.package_table.item(row, col)
                        if item: # Ensure item exists before setting background
                            item.setBackground(dirty_color) # <--- USE QColor OBJECT HERE

            self._update_status(f"Found {len(outdated_packages)} outdated packages.", "info")
        except json.JSONDecodeError:
            self._update_status("Failed to parse outdated package list.", "error")

    def _get_selected_package_name(self):
        """Helper to get the name of the currently selected package in the table."""
        selected_items = self.ui.package_table.selectedItems()
        if not selected_items:
            self._update_status("No package selected.", "error")
            return None
        # The first item in the selected row is the package name
        return self.ui.package_table.item(selected_items[0].row(), 0).text()

    def _upgrade_package(self):
        """Upgrades the selected package."""
        package_name = self._get_selected_package_name()
        if package_name:
            self._update_status(f"Upgrading {package_name}...", "info")
            self._run_command("pip_upgrade",
                              package_name=package_name,
                              on_finish=lambda _: self._fetch_package_list()) # Refresh list on success

    def _uninstall_package(self):
        """Uninstalls the selected package."""
        package_name = self._get_selected_package_name()
        if package_name:
            reply = QMessageBox.question(self, 'Confirm Uninstall',
                                         f"Are you sure you want to uninstall '{package_name}'?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Yes:
                self._update_status(f"Uninstalling {package_name}...", "info")
                self._run_command("pip_uninstall",
                                  package_name=package_name,
                                  on_finish=lambda _: self._fetch_package_list()) # Refresh list on success

    def _freeze_requirements(self): self._run_command("freeze", on_finish=self._save_freeze_output)
    def _save_freeze_output(self, output):
        try:
            (Path(self.ui.path_input.text().strip()) / "requirements.txt").write_text(output.strip())
            self._update_status("requirements.txt generated successfully.", "success")
            self.discover_resources()
        except Exception as e: self._update_status(f"Failed to write requirements.txt: {e}", "error")

    def _export_to_json(self): self._run_command("pip_list", on_finish=self._save_json_output)
    def _save_json_output(self, output):
        try:
            packages = json.loads(output)
            filtered = sorted([f"{p['name']}=={p['version']}" for p in packages if p['name'] not in ['pip', 'setuptools', 'wheel']], key=str.lower)
            (Path(self.ui.path_input.text().strip()) / "packages.json").write_text(json.dumps({"packages": filtered}, indent=4))
            self._update_status("packages.json exported successfully.", "success")
            self.discover_resources()
        except Exception as e:
            self._update_status(f"Failed to export to JSON: {e}", "error")
            self._log_message(f"JSON export error details: {output}")

    def _git_pull(self): self._run_command("git_pull")
    def _git_commit_stage_1_check_status(self): self._run_command("git_status", on_finish=self._git_commit_stage_2_show_dialog)
    def _git_commit_stage_2_show_dialog(self, status):
        if not status.strip():
            self._update_status("No changes to commit (working tree is clean).", "info")
            return
        dialog = GitCommitDialog(self)
        if dialog.exec():
            msg = dialog.get_commit_message()
            if not msg:
                self._update_status("Commit cancelled: message cannot be empty.", "error")
                return
            self._run_command("git_add", on_finish=lambda _: self._git_commit_stage_3_run_commit(msg))
    def _git_commit_stage_3_run_commit(self, message): self._run_command("git_commit", commit_message=message)

    def _poetry_install(self): self._run_command("poetry_install")
    def _pdm_sync(self): self._run_command("pdm_sync")
    def _activate_environment(self): self._run_command("activate")
    def _launch_jupyter(self): self._run_command("launch", tool="jupyter notebook")

    def _show_file_context_menu(self, pos):
        item = self.ui.file_list.itemAt(pos)
        if not item: return
        path = Path(self.ui.path_input.text().strip()) / item.text()
        if not path.exists(): return
        menu = QMenu()
        open_act = menu.addAction("📂 Open")
        copy_act = menu.addAction("🔗 Copy Path")

        if path.is_dir() and sys.platform == "win32": # Windows specific actions for directories
            menu.addSeparator()
            cmd_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon) # A generic icon for console
            powershell_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon) # Another generic icon
            
            cmd_here_act = menu.addAction(cmd_icon, "CMD Here")
            powershell_here_act = menu.addAction(powershell_icon, "PowerShell Here")

        menu.addSeparator()
        del_act = menu.addAction("🗑️ Delete")
        
        action = menu.exec(self.ui.file_list.mapToGlobal(pos))
        if action == open_act:
            os.startfile(path)
        elif action == copy_act:
            QGuiApplication.clipboard().setText(str(path))
            self._update_status("Path copied to clipboard.", "info")
        elif sys.platform == "win32" and action == cmd_here_act:
            subprocess.Popen(f'start cmd.exe /k "cd /d "{path}""', shell=True)
            self._update_status(f"Opened CMD at {path}", "info")
        elif sys.platform == "win32" and action == powershell_here_act:
            subprocess.Popen(f'start powershell.exe -NoExit -Command "Set-Location -LiteralPath \'{path}\'"', shell=True)
            self._update_status(f"Opened PowerShell at {path}", "info")
        elif action == del_act:
            if QMessageBox.question(self, 'Confirm Deletion', f"Are you sure you want to delete '{item.text()}'?") == QMessageBox.StandardButton.Yes:
                try:
                    if path.is_dir(): shutil.rmtree(path)
                    else: os.remove(path)
                    self.discover_resources()
                except Exception as e:
                    self._update_status(f"Error deleting file/folder: {e}", "error")

    def _populate_file_list(self, base_path):
        self.ui.file_list.clear()
        try:
            folders = sorted([p.name for p in base_path.iterdir() if p.is_dir()])
            files = sorted([p.name for p in base_path.iterdir() if p.is_file()])
            for name in folders + files:
                item = QListWidgetItem(name)
                icon_type = QStyle.StandardPixmap.SP_DirIcon if (base_path / name).is_dir() else QStyle.StandardPixmap.SP_FileIcon
                item.setIcon(self.style().standardIcon(icon_type))
                self.ui.file_list.addItem(item)
        except PermissionError:
            self._update_status("Permission denied to read directory.", "error")

    def _find_and_populate_venvs(self, base_path):
        self.ui.venv_dropdown.clear()
        # Find local venvs
        script_folder = "Scripts" if sys.platform == "win32" else "bin"
        venvs = [d.name for d in base_path.iterdir() if d.is_dir() and (d / script_folder / "activate").exists()]
        for venv in sorted(venvs):
            self.ui.venv_dropdown.addItem(venv)
            self.ui.venv_dropdown.setItemData(self.ui.venv_dropdown.count() - 1, "venv")
        # Find conda envs (asynchronously)
        self._run_command("list_conda_envs", on_finish=self._on_conda_envs_listed)

    def _on_conda_envs_listed(self, output):
        try:
            data = json.loads(output)
            conda_envs = [Path(p).name for p in data.get('envs', [])]
            existing_items = {self.ui.venv_dropdown.itemText(i).split(' (')[0] for i in range(self.ui.venv_dropdown.count())}
            for env in sorted(conda_envs):
                if env and env not in existing_items: # Avoid duplicates if env name matches venv
                    self.ui.venv_dropdown.addItem(f"{env} (conda)")
                    self.ui.venv_dropdown.setItemData(self.ui.venv_dropdown.count() - 1, "conda")
        except json.JSONDecodeError:
            self._log_message("Could not parse conda envs. Is conda installed and in PATH?")
        
        if self.ui.venv_dropdown.count() == 0:
            self.ui.venv_dropdown.addItem("No environments found")
            self.ui.venv_dropdown.setEnabled(False)
        else:
            self.ui.venv_dropdown.setEnabled(True)

    # --- pipx Management Methods ---
    def _check_pipx_availability(self, auto_list=True):
        self._run_command("check_pipx", on_finish=lambda out: self._on_pipx_checked(out, auto_list), base_path=".") # base_path can be arbitrary for global tools

    def _on_pipx_checked(self, output, auto_list):
        if "pipx" in output.lower(): # Simple check for pipx version output
            self.ui.pipx_groupbox.setVisible(True)
            self._update_status("pipx is available.", "success")
            if auto_list:
                self._pipx_list() # Automatically list tools if pipx is found
        else:
            self.ui.pipx_groupbox.setVisible(False)
            self._update_status("pipx not found. Install it for global tool management.", "info")

    def _pipx_log_message(self, message):
        self.ui.pipx_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.ui.pipx_output.verticalScrollBar().setValue(self.ui.pipx_output.verticalScrollBar().maximum())

    def _pipx_list(self):
        self._pipx_log_message("Fetching pipx installed tools...")
        self._run_command("pipx_list", on_finish=self._display_pipx_list_output, base_path=".")

    def _display_pipx_list_output(self, json_output):
        self.ui.pipx_output.clear()
        self.pipx_data = {}
        try:
            data = json.loads(json_output)
            if data and "venvs" in data:
                for venv_name, venv_info in data["venvs"].items():
                    self.pipx_data[venv_name] = venv_info
                    app_name = venv_info.get('metadata', {}).get('main_package', {}).get('app_paths_by_name', {}).keys()
                    version = venv_info.get('metadata', {}).get('main_package', {}).get('version', 'N/A')
                    location = venv_info.get('root', 'N/A')
                    apps = ', '.join(app_name) if app_name else "No apps"
                    self._pipx_log_message(f"  <b>{venv_name}</b> (v{version}) - Apps: {apps} (Path: {location})")
                self._update_status(f"Found {len(self.pipx_data)} pipx tools.", "success")
            else:
                self._pipx_log_message("No pipx tools found.")
                self._update_status("No pipx tools found.", "info")
        except json.JSONDecodeError:
            self._pipx_log_message(f"Failed to parse pipx list output: {json_output}")
            self._update_status("Failed to parse pipx list output.", "error")
        
    def _pipx_install(self):
        package = self.ui.pipx_package_input.text().strip()
        if not package:
            self._update_status("Enter a package name to install with pipx.", "error"); return
        self._pipx_log_message(f"Installing {package} with pipx...")
        self._run_command("pipx_install", package=package, on_finish=lambda _: self._pipx_list(), base_path=".")
        self.ui.pipx_package_input.clear()

    def _pipx_upgrade(self):
        package = self.ui.pipx_package_input.text().strip()
        if not package:
            self._update_status("Enter a package name to upgrade with pipx.", "error"); return
        self._pipx_log_message(f"Upgrading {package} with pipx...")
        self._run_command("pipx_upgrade", package=package, on_finish=lambda _: self._pipx_list(), base_path=".")
        self.ui.pipx_package_input.clear()

    def _pipx_uninstall(self):
        package = self.ui.pipx_package_input.text().strip()
        if not package:
            self._update_status("Enter a package name to uninstall with pipx.", "error"); return
        reply = QMessageBox.question(self, 'Confirm pipx Uninstall',
                                         f"Are you sure you want to uninstall '{package}' using pipx?\n\nThis will remove the tool and its associated virtual environment.",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            self._pipx_log_message(f"Uninstalling {package} with pipx...")
            self._run_command("pipx_uninstall", package=package, on_finish=lambda _: self._pipx_list(), base_path=".")
            self.ui.pipx_package_input.clear()

    def _pipx_ensurepath(self):
        self._pipx_log_message("Running 'pipx ensurepath' to update system PATH...")
        self._run_command("pipx_ensurepath", on_finish=lambda _: self._pipx_log_message("pipx ensurepath completed. Restarting terminal might be required."), base_path=".")

    def _update_file_observer(self, path):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        if os.path.isdir(path):
            self.observer = Observer()
            event_handler = FileChangeHandler()
            event_handler.file_changed.connect(self.discover_resources)
            self.observer.schedule(event_handler, str(path), recursive=False)
            self.observer.start()

    def _update_status(self, message, msg_type):
        c = self.current_theme
        colors = {"success": c['success'], "error": c['error'], "info": c['accent']}
        bg_color = colors.get(msg_type, 'transparent')
        self.ui.status_label.setText(message)
        # Apply the background color if it's not transparent, otherwise clear it fully.
        if bg_color != 'transparent':
            self.ui.status_label.setStyleSheet(f"background-color:{bg_color}; color:white; border-radius:4px; padding:4px; qproperty-alignment: 'AlignCenter';")
        else:
            self.ui.status_label.setStyleSheet(f"background-color:transparent; color:{c['text']}; border-radius:4px; padding:4px; qproperty-alignment: 'AlignCenter';")

        if msg_type in colors and bg_color != 'transparent':
            QTimer.singleShot(5000, lambda: self.ui.status_label.setStyleSheet(f"background-color:transparent; color:{c['text']};"))


    def _log_message(self, message):
        self.ui.log_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.ui.log_output.verticalScrollBar().setValue(self.ui.log_output.verticalScrollBar().maximum())

    def _set_progress_bar_active(self, active):
        self.ui.progress_bar.setVisible(active)
        self.ui.running_indicator.setVisible(active)
        self.ui.progress_bar.setRange(0, 0 if active else 100)

    def _initiate_close(self): self.close()
    def closeEvent(self, event):
        if hasattr(self, '_is_closing') and self._is_closing:
            super().closeEvent(event)
            return
        if self.observer:
            self.observer.stop()
            self.observer.join()
        if self.command_thread and self.command_thread.isRunning():
            self.command_thread.stop_process()
            self.command_thread.wait()
        if self.pipx_thread and self.pipx_thread.isRunning(): # Stop pipx thread too
            self.pipx_thread.stop_process()
            self.pipx_thread.wait()
        self._is_closing = True
        event.ignore()
        self.fade_out_animation.start()

    def _setup_animations(self):
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity", self); self.fade_in_animation.setDuration(400); self.fade_in_animation.setStartValue(0.0); self.fade_in_animation.setEndValue(1.0)
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity", self); self.fade_out_animation.setDuration(300); self.fade_out_animation.setStartValue(1.0); self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.finished.connect(self.close)
    def show_with_fade(self):
        self.setWindowOpacity(0.0)
        self.show()
        self.fade_in_animation.start()

    def _create_new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec():
            parent_dir, name = dialog.get_details()
            if not parent_dir or not name:
                self._update_status("Parent directory and project name are required.", "error"); return
            path = Path(parent_dir) / name
            if path.exists():
                self._update_status(f"Project directory '{name}' already exists.", "error"); return
            try:
                self._log_message(f"Creating new project at: {path}")
                path.mkdir(parents=True)
                for d in ["data", "notebooks", "scripts", "src"]: (path / d).mkdir()
                (path / ".gitignore").write_text("# Environments\n.env\n.venv\nenv/\nvenv/\n\n# Python cache\n__pycache__/\n*.py[cod]\n\n# IDEs\n.vscode/\n.idea/\n\n# Other\n.DS_Store")
                self._update_status(f"Project '{name}' created successfully.", "success")
                self.ui.path_input.setText(str(path))
            except Exception as e:
                self._update_status(f"Failed to create project: {e}", "error")

    def _update_git_status(self):
        if not (Path(self.ui.path_input.text().strip()) / ".git").is_dir():
            self.ui.git_groupbox.setVisible(False)
            return
        self.ui.git_groupbox.setVisible(True)
        self.ui.git_status_label.setText("<i>Checking Git status...</i>")
        self._run_command("git_branch", on_finish=self._on_git_branch_finish)
    def _on_git_branch_finish(self, branch):
        self._run_command("git_status", on_finish=lambda status: self._on_git_status_finish(branch.strip(), status))
    def _on_git_status_finish(self, branch, status):
        c = self.current_theme
        if status.strip():
            text = f"Branch: <b>{branch}</b> <font color='{c['git_dirty']}'> (dirty)</font>"
            tip = "Working directory has uncommitted changes."
        else:
            text = f"Branch: <b>{branch}</b> <font color='{c['git_clean']}'> (clean)</font>"
            tip = "Working directory is clean."
        self.ui.git_status_label.setText(text)
        self.ui.git_status_label.setToolTip(tip)

    def _update_build_tool_visibility(self):
        self.ui.build_tools_groupbox.setVisible((Path(self.ui.path_input.text().strip()) / "pyproject.toml").exists())
    
    # --- Window Movement ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.ui.container_layout.itemAt(0).widget().geometry().contains(event.pos()):
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.old_pos:
            self.move(self.pos() + event.globalPosition().toPoint() - self.old_pos)
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event):
        self.old_pos = None

if __name__ == "__main__":
    sys.excepthook = global_exception_hook
    app = QApplication(sys.argv)
    app.setFont(QFont(AppConfig.FONT_MAIN, 9))
    window = JupyterLauncher()
    window.show_with_fade()
    sys.exit(app.exec())