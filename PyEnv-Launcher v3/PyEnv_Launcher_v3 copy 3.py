import sys
import os
import subprocess
import time
import shutil
import traceback
import json
import tempfile
import signal
import random
import qtawesome as fa
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import deque # For status bar tips history

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QPushButton, QComboBox, QFileDialog, QProgressBar,
    QListWidget, QMenu, QScrollArea, QSizePolicy, QSizeGrip,
    QMessageBox, QStyle, QFrame, QTextEdit, QDialog, QListWidgetItem,
    QDialogButtonBox, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QCompleter, QToolButton, QInputDialog
)
from PyQt6.QtCore import (Qt, QTimer, QThread, pyqtSignal, QPoint, pyqtSlot, QSettings,
                          QPropertyAnimation, QEasingCurve, QObject, QStringListModel)
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QAction, QColor, QCursor # QColor and QCursor added here

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
            if full_cmd is None:  # This indicates a new console was launched by the _get_activated_command
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
        shell = True  # Default to shell=True for complex commands or activation
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
        elif self.command_type == "git_log":
            return ['git', 'log', '--pretty=format:%h|%an|%ar|%s', '-n', '5'], False
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
        elif self.command_type == "install_template_packages":
            packages = self.kwargs.get("packages", [])
            if not packages: raise ValueError("No packages specified for template installation.")
            return ['pip', 'install'] + packages, True
        elif self.command_type == "check_pipx":
            return ['pipx', '--version'], True  # Simple check if pipx exists
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
            cmd_list_args = cmd_map[self.command_type]
        elif self.command_type == "install_requirements":
            req_path = Path(self.kwargs.get("requirements_path"))
            if req_path.name == "packages.json":
                with open(req_path, 'r', encoding='utf-8') as f: data = json.load(f)
                packages = data.get("packages", [])
                if not packages: raise ValueError("JSON file contains no packages.")
                cmd_list_args = ['pip', 'install'] + packages
            else:
                # Ensure path is quoted for spaces, especially on Windows
                cmd_list_args = ['pip', 'install', '-r', f'"{req_path}"']
        else:
            self.finished.emit(False, f"Unsupported command type: {self.command_type}", "")
            return None, False

        return self._get_activated_command(cmd_list_args, new_console=(self.command_type in ["launch", "activate"]))

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
            # Use 'start' on Windows with a title, or gnome-terminal on Linux.
            if sys.platform == 'win32':
                subprocess.Popen(f'start "PyEnv Terminal ({self.selected_env})" "{tf.name}"', shell=True)
            else:
                # Fallback for Linux, might need adjustment for specific terminals
                try:
                    subprocess.Popen(['gnome-terminal', '--title', f'PyEnv Terminal ({self.selected_env})', '--', tf.name])
                except FileNotFoundError:
                    # Try xterm or other common terminals
                    try:
                        subprocess.Popen(['xterm', '-title', f'PyEnv Terminal ({self.selected_env})', '-e', f'bash "{tf.name}"'])
                    except FileNotFoundError:
                        QMessageBox.warning(None, "Terminal Error", "Could not find a suitable terminal emulator (gnome-terminal or xterm). Please install one or configure your system PATH.")
                        Path(tf.name).unlink(missing_ok=True) # Clean up temp file
                        self.finished.emit(False, "Failed to launch terminal.", "")
                        return None, True # Indicate a new console was attempted
            QTimer.singleShot(5000, lambda: Path(tf.name).unlink(missing_ok=True))
            return None, True

        return f'{activation_cmd} && {command_str}', True

    def stop_process(self):
        self._is_running = False
        if self.process and self.process.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(f"taskkill /F /T /PID {self.process.pid}", check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    # Use os.killpg to kill the process group for cleaner termination
                    # Ensure the Popen call creates a new process group: preexec_fn=os.setsid
                    # This modification would be needed in the Popen call.
                    # For now, a simple kill might be enough, but less robust.
                    os.kill(self.process.pid, signal.SIGTERM)
                self.process.wait(timeout=2)
            except Exception as e:
                # If graceful termination fails, force kill
                self.process.kill()


class FileChangeHandler(FileSystemEventHandler, QObject):
    file_changed = pyqtSignal()
    def __init__(self):
        FileSystemEventHandler.__init__(self)
        QObject.__init__(self)
    def on_any_event(self, event):
        if event.event_type in ['created', 'deleted', 'moved']:
            self.file_changed.emit()

# --- Custom Clickable Label ---
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

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

        title = QLabel("PyEnv Launcher v3.0")
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
    def _load(self): self.theme_combo.setCurrentText(self.settings.value("theme", "Dark")); self.default_path_input.setText(self.settings.value("default_path", str(Path.home())))
    def _browse(self): path = QFileDialog.getExistingDirectory(self, "Select Dir", self.default_path_input.text()); self.default_path_input.setText(path) if path else None
    def accept(self): self.settings.setValue("theme", self.theme_combo.currentText()); self.settings.setValue("default_path", self.default_path_input.text()); super().accept()

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Create New Project"); self.setMinimumWidth(450)
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.parent_dir = self.settings.value("default_path", str(Path.home()))
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
        right_column_layout.addLayout(self._create_file_actions_bar()) # NEW: Quick File Actions Bar
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
                                           self.main_window.container.findChildren(QTextEdit) + \
                                           self.main_window.container.findChildren(QToolButton) # Added QToolButton

    def _create_title_bar(self):
        title_bar = QWidget(); title_bar.setObjectName("titleBar"); title_bar.setFixedHeight(40)
        layout = QHBoxLayout(title_bar); layout.setContentsMargins(10, 0, 5, 0)
        self.title_label = QLabel("📘 PyEnv Launcher v3.0"); self.title_label.setObjectName("titleLabel")
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
        path_layout = QHBoxLayout(); self.path_input = QLineEdit()
        
        # Smart Path Suggestions (Autocomplete)
        self.path_completer_model = QStringListModel(self.main_window)
        self.path_completer = QCompleter(self.path_completer_model, self.main_window)
        self.path_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.path_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.path_input.setCompleter(self.path_completer)

        self.recent_paths_btn = QPushButton("▼"); self.recent_paths_btn.setObjectName("recentBtn"); self.recent_paths_btn.setFixedWidth(30)
        path_layout.addWidget(self.path_input); path_layout.addWidget(self.recent_paths_btn); layout.addLayout(path_layout)
        btn_layout = QHBoxLayout(); self.browse_btn = QPushButton("Select Directory"); self.new_project_btn = QPushButton("New Project"); self.open_btn = QPushButton("Open Path")
        btn_layout.addWidget(self.browse_btn); btn_layout.addWidget(self.new_project_btn); btn_layout.addWidget(self.open_btn); layout.addLayout(btn_layout)
        return layout

    def _create_git_section(self):
        self.git_groupbox = QGroupBox("Git Status"); layout = QVBoxLayout(self.git_groupbox) # Changed to QVBoxLayout for timeline
        
        # Git Status Label (Still needed for branch name and clean/dirty)
        self.git_status_label = QLabel("Not a git repository."); self.git_status_label.setObjectName("detailsLabel")
        layout.addWidget(self.git_status_label)

        # Visual Git Timeline (QTextEdit for formatted output)
        self.git_timeline_text_edit = QTextEdit()
        self.git_timeline_text_edit.setReadOnly(True)
        self.git_timeline_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.git_timeline_text_edit.setMinimumHeight(60) # Changed from setFixedHeight
        self.git_timeline_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # No scrollbar, just show latest 3-5
        layout.addWidget(self.git_timeline_text_edit)

        git_btn_layout = QHBoxLayout()
        self.git_pull_btn = QPushButton("Git Pull"); self.git_commit_btn = QPushButton("Git Commit")
        git_btn_layout.addStretch(); git_btn_layout.addWidget(self.git_pull_btn); git_btn_layout.addWidget(self.git_commit_btn)
        layout.addLayout(git_btn_layout)
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

        # New: One-Click Env Templates
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Env Template (optional):"))
        self.template_combo = QComboBox()
        self.template_combo.addItem("None", None) # Default "None" option
        # Templates will be populated dynamically from JupyterLauncher
        template_layout.addWidget(self.template_combo)
        layout.addLayout(template_layout)

        creation_layout = QHBoxLayout(); self.new_venv_name_input = QLineEdit(); self.new_venv_name_input.setPlaceholderText("Enter new environment name (no spaces)")
        self.create_venv_btn = QPushButton("Create"); self.create_venv_btn.setObjectName("createBtn")
        creation_layout.addWidget(self.new_venv_name_input); creation_layout.addWidget(self.create_venv_btn); layout.addLayout(creation_layout)
        return layout

    def _create_manage_venv_section(self):
        c = self.main_window.current_theme # Define c here for icon color
        layout = QVBoxLayout(); layout.setSpacing(8); layout.addWidget(QLabel("Manage Existing Environment"))
        env_layout = QHBoxLayout()
        self.venv_dropdown = QComboBox()
        
        # Corrected: Create QPushButton, then set icon
        self.delete_venv_btn = QPushButton() 
        self.delete_venv_btn.setIcon(fa.icon('fa5s.trash-alt', color=c['error'])) # Set icon with theme color
        self.delete_venv_btn.setObjectName("deleteBtn")
        self.delete_venv_btn.setFixedWidth(40)
        self.delete_venv_btn.setToolTip("Delete Selected Environment") # Add tooltip

        env_layout.addWidget(self.venv_dropdown)
        env_layout.addWidget(self.delete_venv_btn)
        layout.addLayout(env_layout)

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
        self.package_table.setMinimumHeight(100) # Changed from setFixedHeight
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
        self.pipx_output.setMinimumHeight(60) # Changed from setFixedHeight
        self.pipx_output.setObjectName("pipxOutput")
        layout.addWidget(self.pipx_output)

        self.pipx_groupbox.setVisible(False)
        return self.pipx_groupbox

    # NEW: Quick File Actions Bar
    def _create_file_actions_bar(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        c = self.main_window.current_theme # Define c here

        self.new_file_btn = QToolButton(); self.new_file_btn.setIcon(fa.icon('fa5s.file-medical', color=c['text'])); self.new_file_btn.setToolTip("Create a new empty file")
        self.new_folder_btn = QToolButton(); self.new_folder_btn.setIcon(fa.icon('fa5s.folder-plus', color=c['text'])); self.new_folder_btn.setToolTip("Create a new empty folder")
        self.run_script_btn = QToolButton(); self.run_script_btn.setIcon(fa.icon('fa5s.play', color=c['text'])); self.run_script_btn.setToolTip("Run selected Python script")
        self.open_terminal_btn = QToolButton(); self.open_terminal_btn.setIcon(fa.icon('fa5s.terminal', color=c['text'])); self.open_terminal_btn.setToolTip("Open Terminal");
        self.delete_file_btn = QToolButton(); self.delete_file_btn.setIcon(fa.icon('fa5s.trash', color='red')); self.delete_file_btn.setToolTip("Delete");

        layout.addWidget(self.new_file_btn)
        layout.addWidget(self.new_folder_btn)
        # layout.addWidget(self._create_separator_widget()) # Corrected: Use QFrame as separator
        layout.addWidget(self.run_script_btn)
        layout.addWidget(self.open_terminal_btn)
        # layout.addWidget(self._create_separator_widget()) # Corrected: Use QFrame as separator
        layout.addWidget(self.delete_file_btn)
        layout.addStretch()

        return layout

    def _create_separator_widget(self):
        """Creates a horizontal QFrame to act as a separator in a layout."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine) # Changed to VLine for horizontal layout separator
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setContentsMargins(5, 0, 5, 0) # Add some padding around it
        return separator

    def _create_files_section(self):
        layout = QVBoxLayout(); layout.setSpacing(8); layout.addWidget(QLabel("Project Directory Contents"))
        self.file_list = QListWidget(); self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); layout.addWidget(self.file_list); return layout

    def _create_log_section(self):
        layout = QVBoxLayout(); layout.setSpacing(4); header = QHBoxLayout(); header.addWidget(QLabel("Activity Log")); header.addStretch()
        self.clear_log_btn = QPushButton("Clear"); header.addWidget(self.clear_log_btn); layout.addLayout(header)
        self.log_output = QTextEdit(); self.log_output.setReadOnly(True); self.log_output.setObjectName("logOutput")
        self.log_output.setMinimumHeight(100) # Changed from setFixedHeight
        layout.addWidget(self.log_output)
        return layout

    def _create_footer_section(self):
        footer = QHBoxLayout(); footer.setContentsMargins(0, 5, 0, 0)
        
        # Status Bar Tips: Use ClickableLabel
        self.status_label = ClickableLabel("Welcome!"); self.status_label.setObjectName("statusLabel")
        self.status_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)) # Indicate it's clickable

        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(False); self.progress_bar.setVisible(False); self.progress_bar.setFixedHeight(6)
        status_layout = QVBoxLayout(); status_layout.addWidget(self.status_label); status_layout.addWidget(self.progress_bar); footer.addLayout(status_layout, 1)
        footer.addWidget(QSizeGrip(self.main_window.container)); return footer


# --- Main Application Window ---
class JupyterLauncher(QWidget):
    # One-Click Env Templates: Hardcoded for simplicity; can be loaded from templates.json
    ENV_TEMPLATES = [
        {
            "name": "Data Science Basic",
            "description": "Installs pandas, numpy, scikit-learn, matplotlib",
            "packages": ["pandas", "numpy", "scikit-learn", "matplotlib"]
        },
        {
            "name": "Web Dev Flask",
            "description": "Installs Flask, requests, python-dotenv",
            "packages": ["flask", "requests", "python-dotenv"]
        },
        {
            "name": "Jupyter Notebook Essentials",
            "description": "Installs jupyter, ipykernel, tqdm",
            "packages": ["jupyter", "ipykernel", "tqdm"]
        }
    ]

    DID_YOU_KNOW_TIPS = [
        "Right-click on any file or folder in the 'Project Directory Contents' to see available actions.",
        "You can clear your recent project history from the dropdown next to the path input.",
        "The Git status shows if your working directory is clean or has uncommitted changes.",
        "Pipx allows you to install Python applications globally without polluting your system Python.",
        "Double-clicking a file in the list will attempt to open it with the default system application.",
        "You can drag the bottom-right corner of the window to resize it.",
        "Use 'New Project' to quickly scaffold a common project structure.",
        "The running indicator (●) tells you if a background command is currently active."
    ]

    def __init__(self):
        super().__init__()
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.current_theme = AppConfig.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else AppConfig.LIGHT_THEME
        self.setWindowTitle("PyEnv Launcher"); self.setObjectName("JupyterLauncher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.resize(950, 700) # Adjusted initial window size for better fit
        
        # --- NEW CODE TO CENTER THE WINDOW ---
        self._center_on_screen()
        # ------------------------------------

        self.observer = None
        self.old_pos = None
        self.command_thread = None
        self.pipx_thread = None # Added for pipx commands
        self.interactive_widgets = []
        self.package_data = {}
        self.pipx_data = {} # Added for pipx list

        self.log_history = deque(maxlen=5) # For status bar tips

        self.ui = UIManager(self)
        self._apply_stylesheet()
        self._connect_signals()
        self._setup_animations()
        self._load_app_settings()
        self._populate_env_templates() # Populate template dropdown
        self._on_path_changed() # Trigger initial discovery and completer update
        
    def _center_on_screen(self):
        # Get the screen geometry
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        
        # Calculate the center point for the window
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        
        # Move the window to the calculated position
        self.move(x, y)

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
        self.ui.file_list.itemDoubleClicked.connect(self._handle_file_list_double_click) # New: Double-click to open/navigate
        self.ui.file_list.currentItemChanged.connect(self._update_file_action_buttons_state) # New: Update quick action buttons
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
        # Quick File Actions Bar
        self.ui.new_file_btn.clicked.connect(self._new_file)
        self.ui.new_folder_btn.clicked.connect(self._new_folder)
        self.ui.run_script_btn.clicked.connect(self._run_selected_script)
        self.ui.open_terminal_btn.clicked.connect(self._open_terminal_in_selected)
        self.ui.delete_file_btn.clicked.connect(self._delete_selected_file_or_folder)
        # Status Bar Tips
        self.ui.status_label.clicked.connect(self._show_status_tip)


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
            QPushButton, QToolButton{{background-color:{c['border']};border:1px solid {c['border']};border-radius:6px;padding:8px;font-weight:bold;}}
            QPushButton:hover, QToolButton:hover{{border-color:#8b949e;}}
            QPushButton:pressed, QToolButton:pressed{{background-color:#21262d;}}
            QPushButton:disabled, QToolButton:disabled{{background-color:{c['border']};color:{c['text_secondary']};border-color:{c['border']};}}
            QToolButton{{ padding: 5px; }} /* Smaller padding for tool buttons */
            QToolButton::menu-indicator {{ image: none; }} /* Remove dropdown arrow from tool buttons if not used */
            #createBtn{{background-color:{c['error']};border-color:{c['error']};}} #createBtn:hover{{background-color:#b82c2a;}}
            #statusLabel{{font-weight:normal;background-color:transparent;}}
            #runningIndicator{{color:{c['success']};font-size:16pt;font-weight:bold;padding-bottom:4px;}}
            QProgressBar{{border-radius:3px;background-color:{c['border']};text-align:center;}}
            QProgressBar::chunk{{background-color:{c['accent']};border-radius:3px;}}
            QListWidget,#logOutput,#pipxOutput,#git_timeline_text_edit{{background-color:{c['background']};border:1px solid {c['border']};border-radius:6px;padding:4px;}}
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
        # Specific handling for the file action buttons, as they have their own logic
        self._update_file_action_buttons_state(self.ui.file_list.currentItem())


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
        
        # Determine selected_env and env_type from UI, these are the defaults
        ui_env_text = self.ui.venv_dropdown.currentText()
        ui_env_data = self.ui.venv_dropdown.currentData()
        current_selected_env = ui_env_text.split(' (')[0] if ui_env_text and "No environments found" not in ui_env_text else None
        current_env_type = ui_env_data or "venv" # Default to venv if no specific data

        # For commands that require an environment, check if it's valid
        required_env_commands = ["get_env_details", "freeze", "pip_list", "launch", "activate", "install_requirements", "pip_outdated", "pip_upgrade", "pip_uninstall", "install_template_packages"]
        if command_type in required_env_commands and (not current_selected_env or "found" in current_selected_env):
            self._update_status("A valid environment must be selected for this action.", "error")
            return
            
        self._set_ui_enabled(False)

        # Create a new kwargs dictionary for CommandThread to avoid modifying the original
        thread_kwargs = kwargs.copy()

        # Extract 'selected_env' and 'env_type' from thread_kwargs if they were explicitly passed
        # Otherwise, use the values determined from the UI dropdown
        thread_selected_env = thread_kwargs.pop('selected_env', current_selected_env)
        thread_env_type = thread_kwargs.pop('env_type', current_env_type)
        thread_kwargs.pop('base_path', None)

        thread_to_use = self.command_thread
        if is_pipx_command:
            # For pipx commands, environment activation from the dropdown is usually not relevant.
            # We set selected_env to None and env_type to 'system' or a placeholder,
            # but still allow the base_path to be specified if needed for context.
            self.pipx_thread = CommandThread(base_path, None, "system", command_type, **thread_kwargs)
            thread_to_use = self.pipx_thread
        else:
            self.command_thread = CommandThread(base_path, thread_selected_env, thread_env_type, command_type, **thread_kwargs)
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
        default_path = self.settings.value("default_path", str(Path.home()))
        self.ui.path_input.setText(default_path)
        self._add_to_recent_paths(default_path)
        self._update_path_completer_model() # Initial update for completer

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
            self._add_to_recent_paths(str(path)) # This will also update completer model
            self._update_git_status()
            self._update_build_tool_visibility()
            self._find_and_populate_venvs(path)
            self._check_pipx_availability() # Check pipx status
            self._update_file_action_buttons_state(None) # Reset buttons
        else:
            self.ui.git_groupbox.setVisible(False)
            self.ui.build_tools_groupbox.setVisible(False)
            self.ui.pipx_groupbox.setVisible(False) # Hide pipx if path invalid
            self.ui.file_list.clear()
            self._update_file_action_buttons_state(None) # Disable all buttons if path invalid


    def _update_path_completer_model(self):
        """Updates the QCompleter with recent paths and common directories."""
        recent_paths = self.settings.value("recent_paths", [], type=list)
        
        # Add common system directories
        common_paths = [
            str(Path.home()),
            str(Path.home() / "Documents"),
            str(Path.home() / "Downloads"),
            str(Path.home() / "Desktop"),
            str(Path.home() / "Projects") # A common pattern
        ]
        
        # Filter out non-existent paths and duplicates, keep only unique and existing
        unique_paths = sorted(list(set(p for p in recent_paths + common_paths if Path(p).is_dir())))
        
        self.ui.path_completer_model.setStringList(unique_paths)

    def _add_to_recent_paths(self, path):
        if not path or not os.path.isdir(path): return
        recent = self.settings.value("recent_paths", [], type=list)
        if path in recent: recent.remove(path)
        recent.insert(0, path)
        self.settings.setValue("recent_paths", recent[:10])
        self._update_path_completer_model() # Update completer after recent paths change

    def _clear_recent_paths(self):
        reply = QMessageBox.question(self, 'Confirm Clear History',
                                     "Are you sure you want to clear all recent project history?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.remove("recent_paths")
            self._update_status("Recent project history cleared.", "success")
            self._log_message("Recent project history cleared by user.")
            self._update_path_completer_model() # Update completer after clearing

    def _show_recent_paths_menu(self):
        recent = self.settings.value("recent_paths", [], type=list)
        menu = QMenu(self)
        c = self.current_theme # Define c here

        # icon_pixmap = self.style().standardPixmap(QStyle.StandardPixmap.SP_DirIcon) # This line is not used.
        small_icon = fa.icon('fa5s.folder', color=c['text_secondary'], options=[{'scale_factor': 0.8}])

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

        # trash_pixmap = self.style().standardPixmap(QStyle.StandardPixmap.SP_TrashIcon) # This line is not used.
        small_trash_icon = fa.icon('fa5s.trash-alt', color=c['error'], options=[{'scale_factor': 0.8}])

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
            os.startfile(path) # Works on Windows, MacOS, and some Linux desktops
        else:
            self._update_status("Directory not found.", "error")

    def _populate_env_templates(self):
        """Populates the environment template dropdown."""
        for template in self.ENV_TEMPLATES:
            self.ui.template_combo.addItem(template["name"], template) # Store the whole dict as user data

    def _create_environment(self):
        name = self.ui.new_venv_name_input.text().strip()
        python_version = self.ui.new_venv_python_version_input.text().strip()
        selected_template_data = self.ui.template_combo.currentData()
        
        if not name or ' ' in name:
            self._update_status("Invalid environment name. No spaces allowed.", "error"); return
        if (Path(self.ui.path_input.text().strip()) / name).exists():
            self._update_status(f"Directory or file '{name}' already exists.", "error"); return
        
        # Pass python_version if provided
        # The on_finish will either just discover resources, or install template packages then discover
        def final_setup_callback(_):
            if selected_template_data and selected_template_data["packages"]:
                self._update_status(f"Installing template packages for '{name}'...", "info")
                self._run_command("install_template_packages", packages=selected_template_data["packages"], on_finish=lambda __: self.discover_resources())
            else:
                self.discover_resources()

        self._run_command("create_venv", new_env_name=name, python_version=python_version, on_finish=final_setup_callback)
        self.ui.new_venv_name_input.clear()
        # Optionally, clear python version input if it's meant for single use
        # self.ui.new_venv_python_version_input.clear()
        self.ui.template_combo.setCurrentIndex(0) # Reset template dropdown

    def _delete_environment(self):
        env_text = self.ui.venv_dropdown.currentText()
        if not env_text or "found" in env_text or "No environments found" in env_text: return
        env_name = env_text.split(' (')[0]
        env_type = self.ui.venv_dropdown.currentData()

        reply = QMessageBox.question(self, 'Confirm Deletion', f"Are you sure you want to permanently delete the environment '{env_name}'?\n\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            if env_type == "conda":
                # Note: `conda_env_remove` is not implemented in CommandThread, would need to be added
                self._update_status(f"Conda environment deletion for '{env_name}' not yet implemented.", "error")
                # self._run_command("conda_env_remove", env_name=env_name, on_finish=lambda _: self.discover_resources())
            else: # Assume local venv
                env_path = Path(self.ui.path_input.text().strip()) / env_name
                try:
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
        if name and "found" not in name and "No environments found" not in name:
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
            dirty_color = QColor(self.current_theme['git_dirty'])

            for row in range(self.ui.package_table.rowCount()):
                name_item = self.ui.package_table.item(row, 0)
                if name_item and name_item.text() in outdated_map:
                    latest_version = outdated_map[name_item.text()]
                    self.ui.package_table.item(row, 2).setText(latest_version)
                    # Highlight the entire row for visibility
                    for col in range(3):
                        item = self.ui.package_table.item(row, col)
                        if item: # Ensure item exists before setting background
                            item.setBackground(dirty_color)

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
        current_path = Path(self.ui.path_input.text().strip())
        target_path = current_path / item.text() if item else current_path

        if not target_path.exists(): return
        
        menu = QMenu()
        c = self.current_theme # Define c here
        open_act = menu.addAction(fa.icon('fa5s.folder-open' if target_path.is_dir() else 'fa5s.file-alt', color=c['text']), "Open")
        copy_act = menu.addAction(fa.icon('fa5s.copy', color=c['text']), "Copy Path")

        menu.addSeparator()

        new_file_act = menu.addAction(fa.icon('fa5s.file-medical', color=c['text']), "New File Here")
        new_folder_act = menu.addAction(fa.icon('fa5s.folder-plus', color=c['text']), "New Folder Here")

        menu.addSeparator()

        run_script_act = None
        if target_path.is_file() and target_path.suffix == '.py':
            run_script_act = menu.addAction(fa.icon('fa5s.play', color=c['text']), "Run Python Script")
        open_terminal_act = menu.addAction(fa.icon('fa5s.terminal', color=c['text']), "Open Terminal Here")
        
        menu.addSeparator()
        del_act = menu.addAction(fa.icon('fa5s.trash', color=c['error']), "Delete") # Use error color for delete
        
        action = menu.exec(self.ui.file_list.mapToGlobal(pos))
        
        if action == open_act:
            self._open_file_list_item(item) # Reuse double-click logic
        elif action == copy_act:
            QGuiApplication.clipboard().setText(str(target_path))
            self._update_status("Path copied to clipboard.", "info")
        elif action == new_file_act:
            self._new_file(base_dir=target_path if target_path.is_dir() else target_path.parent)
        elif action == new_folder_act:
            self._new_folder(base_dir=target_path if target_path.is_dir() else target_path.parent)
        elif action == run_script_act:
            self._run_selected_script(target_path=target_path)
        elif action == open_terminal_act:
            self._open_terminal_in_selected(target_path=target_path)
        elif action == del_act:
            self._delete_selected_file_or_folder(target_path=target_path)

    def _open_file_list_item(self, item):
        if not item: return
        path = Path(self.ui.path_input.text().strip()) / item.text()
        if not path.exists(): return
        os.startfile(path)
        self._log_message(f"Opened: {path.name}")

    def _new_file(self, base_dir=None):
        base_dir = base_dir or Path(self.ui.path_input.text().strip())
        if not base_dir.is_dir():
            self._update_status("Invalid directory to create new file.", "error"); return
        
        file_name, ok = QInputDialog.getText(self, "New File", "Enter new file name:")
        if ok and file_name:
            new_file_path = base_dir / file_name
            if new_file_path.exists():
                self._update_status(f"File '{file_name}' already exists.", "error"); return
            try:
                new_file_path.touch()
                self.discover_resources()
                self._update_status(f"File '{file_name}' created.", "success")
            except Exception as e:
                self._update_status(f"Failed to create file: {e}", "error")

    def _new_folder(self, base_dir=None):
        base_dir = base_dir or Path(self.ui.path_input.text().strip())
        if not base_dir.is_dir():
            self._update_status("Invalid directory to create new folder.", "error"); return

        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter new folder name:")
        if ok and folder_name:
            new_folder_path = base_dir / folder_name
            if new_folder_path.exists():
                self._update_status(f"Folder '{folder_name}' already exists.", "error"); return
            try:
                new_folder_path.mkdir()
                self.discover_resources()
                self._update_status(f"Folder '{folder_name}' created.", "success")
            except Exception as e:
                self._update_status(f"Failed to create folder: {e}", "error")

    def _run_selected_script(self, target_path=None):
        if not target_path:
            item = self.ui.file_list.currentItem()
            if not item: return
            target_path = Path(self.ui.path_input.text().strip()) / item.text()

        if target_path and target_path.is_file() and target_path.suffix == '.py':
            self._log_message(f"Running script: {target_path.name}")
            # This runs in the active environment (if any)
            # No specific 'tool' argument is passed for plain python script, CommandThread expects command in cmd_list_args
            # For running a script, we directly use 'python <script_path>'
            # The 'activate' command type would activate the env and then run cmd_list_args.
            # We want to activate the env THEN run the script. So, CommandThread(..., command_type="activate", kwargs={"tool": "python \"{target_path}\""})
            # However, the CommandThread for 'activate' command type expects kwargs['tool'] as a list, and it is using it as a direct command.
            # Let's adjust CommandThread's _build_command for "activate" slightly, or create a new command_type for "run_script_in_env".
            # For simplicity, let's keep using 'activate' but pass the tool as the 'command' to execute after activation.
            self._run_command("activate", tool=f"python \"{target_path}\"", new_console=True)
        else:
            self._update_status("Please select a Python script (.py file) to run.", "error")

    def _open_terminal_in_selected(self, target_path=None):
        if not target_path:
            item = self.ui.file_list.currentItem()
            current_project_path = Path(self.ui.path_input.text().strip())
            target_path = current_project_path / item.text() if item else current_project_path
        
        if not target_path.exists():
            self._update_status("Invalid path for terminal.", "error"); return

        open_dir = target_path if target_path.is_dir() else target_path.parent
        self._log_message(f"Opening terminal at: {open_dir}")
        
        # Here, we want to activate the environment in the *new* console.
        # The selected_env and env_type from the UI dropdown are relevant.
        # These are handled by _run_command using current_selected_env and current_env_type.
        # The base_path for CommandThread should be `str(open_dir)`.
        self._run_command("activate", new_console=True, base_path=str(open_dir))

    def _delete_selected_file_or_folder(self, target_path=None):
        if not target_path:
            item = self.ui.file_list.currentItem()
            if not item:
                self._update_status("No item selected for deletion.", "error"); return
            target_path = Path(self.ui.path_input.text().strip()) / item.text()
        
        if not target_path.exists():
            self._update_status(f"Path '{target_path.name}' does not exist.", "error"); return

        reply = QMessageBox.question(self, 'Confirm Deletion',
                                     f"Are you sure you want to delete '{target_path.name}'?\n\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if target_path.is_dir(): shutil.rmtree(target_path)
                else: os.remove(target_path)
                self.discover_resources()
                self._update_status(f"Deleted '{target_path.name}'.", "success")
            except Exception as e:
                self._update_status(f"Error deleting file/folder: {e}", "error")

    def _update_file_action_buttons_state(self, current_item):
        is_path_valid = Path(self.ui.path_input.text().strip()).is_dir()
        
        # Always allow New File/Folder if path is valid
        self.ui.new_file_btn.setEnabled(is_path_valid)
        self.ui.new_folder_btn.setEnabled(is_path_valid)
        
        # Rest of the buttons depend on selection
        if not is_path_valid or not current_item:
            self.ui.run_script_btn.setEnabled(False)
            self.ui.open_terminal_btn.setEnabled(False)
            self.ui.delete_file_btn.setEnabled(False)
            return

        selected_path = Path(self.ui.path_input.text().strip()) / current_item.text()

        self.ui.delete_file_btn.setEnabled(True) # Can delete any selected item
        self.ui.open_terminal_btn.setEnabled(True) # Can open terminal at any selected item (dir or parent of file)

        if selected_path.is_file() and selected_path.suffix == '.py':
            self.ui.run_script_btn.setEnabled(True)
        else:
            self.ui.run_script_btn.setEnabled(False)


    def _populate_file_list(self, base_path):
        self.ui.file_list.clear()
        c = self.current_theme # Define c here
        try:
            # First, add ".." to go up one level if not at root
            if base_path.parent != base_path and base_path != Path.home(): # Prevent ".." at root or home, adjust as needed
                up_item = QListWidgetItem("..")
                up_icon = fa.icon('fa5s.arrow-up', color=c['text_secondary']) # Use a subtle color
                up_item.setIcon(up_icon)
                self.ui.file_list.addItem(up_item)

            folders = sorted([p.name for p in base_path.iterdir() if p.is_dir()])
            files = sorted([p.name for p in base_path.iterdir() if p.is_file()])
            for name in folders + files:
                item = QListWidgetItem(name)
                icon_type = 'fa5s.folder' if (base_path / name).is_dir() else 'fa5s.file'
                item.setIcon(fa.icon(icon_type, color=c['text']))
                self.ui.file_list.addItem(item)
        except PermissionError:
            self._update_status("Permission denied to read directory.", "error")
        except FileNotFoundError:
            self._update_status("Directory not found.", "error")
        
        # Reconnect double-click after clearing and repopulating
        try:
            self.ui.file_list.itemDoubleClicked.disconnect()
        except TypeError: # Signal not connected
            pass
        self.ui.file_list.itemDoubleClicked.connect(self._handle_file_list_double_click)


    def _handle_file_list_double_click(self, item):
        current_path = Path(self.ui.path_input.text().strip())
        selected_name = item.text()

        if selected_name == "..":
            # Go up one level
            parent_dir = current_path.parent
            if parent_dir != current_path: # Ensure we don't go above root
                self.ui.path_input.setText(str(parent_dir))
        else:
            # Open file or navigate to folder
            target_path = current_path / selected_name
            if target_path.is_dir():
                self.ui.path_input.setText(str(target_path))
            else:
                self._open_file_list_item(item) # Reuse existing open file logic


    def _find_and_populate_venvs(self, base_path):
        self.ui.venv_dropdown.clear()
        # Find local venvs
        script_folder = "Scripts" if sys.platform == "win32" else "bin"
        venvs = [d.name for d in base_path.iterdir() if d.is_dir() and (d / script_folder / "activate.bat").exists()]
        for venv in sorted(venvs):
            self.ui.venv_dropdown.addItem(venv, "venv") # Pass type as data
        
        # Find conda envs (asynchronously)
        self._run_command("list_conda_envs", on_finish=self._on_conda_envs_listed)

    def _on_conda_envs_listed(self, output):
        try:
            data = json.loads(output)
            conda_envs = [Path(p).name for p in data.get('envs', [])]
            existing_items = {self.ui.venv_dropdown.itemText(i).split(' (')[0] for i in range(self.ui.venv_dropdown.count())}
            for env in sorted(conda_envs):
                if env and env not in existing_items: # Avoid duplicates if env name matches venv
                    self.ui.venv_dropdown.addItem(f"{env} (conda)", "conda") # Pass type as data
        except json.JSONDecodeError:
            self._log_message("Could not parse conda envs. Is conda installed and in PATH?")
        except Exception as e:
            self._log_message(f"Error listing conda environments: {e}")
        
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
                    app_names = venv_info.get('metadata', {}).get('main_package', {}).get('app_paths_by_name', {}).keys()
                    version = venv_info.get('metadata', {}).get('main_package', {}).get('version', 'N/A')
                    # location = venv_info.get('root', 'N/A') # Too verbose for compact list
                    apps = ', '.join(app_names) if app_names else "No apps"
                    self._pipx_log_message(f"  <b>{venv_name}</b> (v{version}) - Apps: {apps}")
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

    def _show_status_tip(self):
        """Displays recent log messages and a random 'Did You Know?' tip."""
        log_msgs = "\n".join(self.log_history) if self.log_history else "No recent activity."
        tip = random.choice(self.DID_YOU_KNOW_TIPS)

        message_box = QMessageBox(self)
        message_box.setWindowTitle("Status Information & Tips")
        message_box.setIcon(QMessageBox.Icon.Information)
        message_box.setText("<b>Recent Activity:</b>")
        message_box.setInformativeText(f"<pre>{log_msgs}</pre><br><b>Did You Know?</b> {tip}")
        message_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        message_box.exec()

    def _log_message(self, message):
        self.ui.log_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.ui.log_output.verticalScrollBar().setValue(self.ui.log_output.verticalScrollBar().maximum())
        self.log_history.append(f"[{time.strftime('%H:%M:%S')}] {message}") # Add to history

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
                (path / ".gitignore").write_text("# Environments\n.env\n.venv\nenv/\venv/\n\n# Python cache\n__pycache__/\n*.py[cod]\n\n# IDEs\n.vscode/\n.idea/\n\n# Other\n.DS_Store")
                self._update_status(f"Project '{name}' created successfully.", "success")
                self.ui.path_input.setText(str(path))
            except Exception as e:
                self._update_status(f"Failed to create project: {e}", "error")

    def _update_git_status(self):
        current_path_str = self.ui.path_input.text().strip()
        if not (Path(current_path_str) / ".git").is_dir():
            self.ui.git_groupbox.setVisible(False)
            self.ui.git_status_label.setText("Not a git repository.")
            self.ui.git_timeline_text_edit.clear()
            return
        self.ui.git_groupbox.setVisible(True)
        self.ui.git_status_label.setText("<i>Checking Git status...</i>")
        self.ui.git_timeline_text_edit.setHtml("<i>Fetching Git history...</i>")
        self._run_command("git_branch", on_finish=self._on_git_branch_finish)

    def _on_git_branch_finish(self, branch):
        # Now get git status for dirty check and git log for timeline
        self._run_command("git_status", on_finish=lambda status: self._on_git_status_and_log_finish(branch.strip(), status))

    def _on_git_status_and_log_finish(self, branch, status):
        c = self.current_theme
        if status.strip():
            status_text = f"Branch: <b>{branch}</b> <font color='{c['git_dirty']}'> (dirty)</font>"
            status_tip = "Working directory has uncommitted changes."
        else:
            status_text = f"Branch: <b>{branch}</b> <font color='{c['git_clean']}'> (clean)</font>"
            status_tip = "Working directory is clean."
        self.ui.git_status_label.setText(status_text)
        self.ui.git_status_label.setToolTip(status_tip)
        
        # Now fetch the git log for the timeline
        self._run_command("git_log", on_finish=self._on_git_log_finish)

    def _on_git_log_finish(self, log_output):
        c = self.current_theme
        html_timeline = []
        for line in log_output.strip().split('\n'):
            parts = line.split('|', 3) # Hash | Author | Relative Date | Subject
            if len(parts) == 4:
                commit_hash, author, relative_date, subject = parts
                html_timeline.append(
                    f"<div style='margin-bottom: 5px;'>"
                    f"<span style='color:{c['accent']}; font-weight:bold;'>{commit_hash[:7]}</span> "
                    f"<span style='color:{c['text_secondary']};'>({relative_date})</span><br>"
                    f"<span style='color:{c['text']};'>{subject}</span> "
                    f"<span style='color:{c['text_secondary']};'>- {author}</span>"
                    f"</div>"
                )
        if not html_timeline:
            self.ui.git_timeline_text_edit.setHtml("<span style='color:grey;'>No recent commits found.</span>")
        else:
            self.ui.git_timeline_text_edit.setHtml("".join(html_timeline))

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

    # Initialize QtAwesome (it loads the icon fonts)
    # fa.load_font("fa5s", "fontawesome-webfont.ttf", "fontawesome5_solid.json") 
    
    # Set the application window icon using a QtAwesome icon
    app.setWindowIcon(fa.icon('fa5s.code', color='blue')) 

    window = JupyterLauncher()
    window.show_with_fade()
    sys.exit(app.exec())