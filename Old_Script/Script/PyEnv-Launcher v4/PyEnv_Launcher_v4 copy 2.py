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
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QAction, QColor, QCursor, QBrush # QBrush added for table items

# --- Global Constants ---
class AppConfig:
    """Stores global application constants."""
    FONT_MAIN = "Inter" # Changed to a modern sans-serif font
    FONT_CODE = "Consolas" # For log output, etc.

    # --- EDITED DARK THEME ---
    DARK_THEME = {
        "background": "#0c0d11",  # Darker primary background
        "primary": "#1a1b26",     # Main widget background (e.g., cards, panels)
        "secondary": "#24283b",   # Used for subtle separation, e.g., alternates
        "border": "#414868",      # Subtle border color
        "text": "#c0caf5",        # Primary text color
        "text_header": "#f7768e", # Highlighted text/titles, a soft red
        "text_secondary": "#a9b1d6", # Secondary text, descriptions
        "accent": "#7aa2f7",      # Accent color, a vibrant blue
        "success": "#9ece6a",     # Success color, a soft green
        "error": "#f7768e",       # Error color, matches header text color
        "border_window": "#7aa2f7", # Accent for window border
        "git_clean": "#9ece6a",   # Git clean status
        "git_dirty": "#e0af68"    # Git dirty status, a warm orange
    }

    # --- EDITED LIGHT THEME ---
    LIGHT_THEME = {
        "background": "#f8f9fa",
        "primary": "#ffffff",
        "secondary": "#f0f2f5",
        "border": "#e0e2e6",
        "text": "#343a40",
        "text_header": "#007bff",
        "text_secondary": "#6c757d",
        "accent": "#007bff",
        "success": "#28a745",
        "error": "#dc3545",
        "border_window": "#007bff",
        "git_clean": "#28a745",
        "git_dirty": "#ffc107"
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

            # When shell=True, command needs to be a single string for Windows and Linux.
            # When shell=False, command needs to be a list of arguments.
            # subprocess.CREATE_NO_WINDOW is for Windows only.
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' and not shell else 0

            # Ensure full_cmd is a list if shell is False, string if shell is True
            if not shell and isinstance(full_cmd, str):
                full_cmd = full_cmd.split() # Simple split might not handle quoted args correctly.
                                           # Better to ensure _build_command returns list for shell=False.
                                           # The current _build_command already does this for most shell=False cases.

            self.process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=creation_flags,
                shell=shell,
                cwd=self.base_path,
                preexec_fn=os.setsid if 'linux' in sys.platform or 'darwin' in sys.platform else None # For process group on Unix
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
            "launch": (self.kwargs.get("tool", "jupyter notebook")).split(), # tool can be 'jupyter notebook' or 'python script.py'
            "activate": []
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
                # Ensure the path to the temp file is correctly quoted for 'start' command.
                # 'start' command takes the title as the first argument in quotes.
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
                    # Use os.kill for Windows process termination as well, if we use preexec_fn=os.setsid.
                    # If process was started without new process group, taskkill /T /PID might be needed.
                    # For a process started with preexec_fn=os.setsid, os.kill(pid, SIGTERM) is better.
                    # Assuming we create new process group.
                    os.kill(self.process.pid, signal.SIGTERM)
                else:
                    # Use os.killpg to kill the process group for cleaner termination
                    # Ensure the Popen call creates a new process group: preexec_fn=os.setsid
                    pgid = os.getpgid(self.process.pid)
                    os.killpg(pgid, signal.SIGTERM)
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
        # Filter events to avoid excessive updates.
        # Only care about creation, deletion, or renaming/moving within the monitored directory.
        # Modifications to file content are often less critical for the file list itself.
        if event.is_directory:
            # For directories, only consider creation/deletion
            if event.event_type in ['created', 'deleted']:
                self.file_changed.emit()
        else:
            # For files, consider creation/deletion/moving
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
        title.setToolTip("Python Environment Manager and Project Launcher") # Tooltip added
        
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
        terms_text.setToolTip("End-User License Agreement details") # Tooltip added

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bbox.accepted.connect(self.accept)
        bbox.setToolTip("Close this dialog") # Tooltip added for button box

        widgets_to_add = [
            title,
            QLabel("<b>Company:</b> Chakhdi.local").setToolTip("Software developer company"), # Tooltip added
            QLabel("<b>Year:</b> 2025").setToolTip("Year of software release"), # Tooltip added
            QLabel("Copyright © 2025 Chakhdi.local - All Rights Reserved").setToolTip("Copyright information"), # Tooltip added
            self._create_separator(),
            QLabel("<b>Terms and Conditions (MIT License):</b>"),
            terms_text,  # Add the populated QTextEdit here
            bbox
        ]
        for widget in widgets_to_add:
            if isinstance(widget, QLabel) and not widget.toolTip(): # Set default tooltip for labels if not already set
                widget.setToolTip("Information about the application.")
            layout.addWidget(widget)

        # Apply specific styling for the dialog itself, ensuring consistency with parent theme
        if parent and hasattr(parent, 'current_theme'):
            c = parent.current_theme
            self.setStyleSheet(parent._get_dialog_stylesheet(c) + f"""
                #aboutTitle {{ font-size: 14pt; font-weight: bold; color: {c['text_header']}; }}
                QTextEdit {{ background-color: {c['background']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 8px; }}
                QDialogButtonBox QPushButton {{ background-color: {c['accent']}; color: white; border: none; border-radius: 5px; padding: 8px 15px; font-weight: bold; }}
                QDialogButtonBox QPushButton:hover {{ background-color: {c['accent']}CC; }}
            """)
        else:
            # Fallback styling if parent theme is not available (shouldn't happen with proper init)
            self.setStyleSheet(f"""
                QDialog {{ background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }}
                QLabel, QTextEdit {{ color: #333333; font-family: "{AppConfig.FONT_MAIN}"; }}
                #aboutTitle {{ font-size: 14pt; font-weight: bold; color: #007bff; }}
                QTextEdit {{ background-color: #f8f8f8; border: 1px solid #cccccc; border-radius: 5px; padding: 8px; }}
                QPushButton {{ background-color: #007bff; color: white; border: none; border-radius: 5px; padding: 8px 15px; font-weight: bold; }}
                QPushButton:hover {{ background-color: #0056b3; }}
                QDialogButtonBox QPushButton {{ background-color: #007bff; color: white; border: none; border-radius: 5px; padding: 8px 15px; font-weight: bold; }}
                QDialogButtonBox QPushButton:hover {{ background-color: #0056b3; }}
            """)

    def _create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setToolTip("A visual separator") # Tooltip added
        separator.setObjectName("dialogSeparator") # Add object name for styling
        return separator

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Settings"); self.setMinimumWidth(400)
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        
        layout = QVBoxLayout(self)
        
        # Theme selection
        theme_group = QGroupBox("Appearance")
        theme_layout = QVBoxLayout(theme_group)
        theme_layout.addWidget(QLabel("Theme:").setToolTip("Choose between dark and light application theme"))
        self.theme_combo = QComboBox(); self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setToolTip("Select the application's visual theme")
        theme_layout.addWidget(self.theme_combo)
        layout.addWidget(theme_group)

        # Default Project Directory
        dir_group = QGroupBox("Project Settings")
        dir_layout = QVBoxLayout(dir_group)
        dir_layout.addWidget(QLabel("Default Project Directory:").setToolTip("Set the default directory for new projects"))
        path_layout = QHBoxLayout(); self.default_path_input = QLineEdit()
        self.default_path_input.setToolTip("The default directory where new projects will be created")
        self.browse_btn = QPushButton("Browse..."); self.browse_btn.setToolTip("Select a default project directory")
        path_layout.addWidget(self.default_path_input); path_layout.addWidget(self.browse_btn)
        dir_layout.addLayout(path_layout)
        layout.addWidget(dir_group)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); layout.addWidget(bbox)
        bbox.setToolTip("Accept or cancel settings changes")
        bbox.accepted.connect(self.accept); bbox.rejected.connect(self.reject); self.browse_btn.clicked.connect(self._browse)
        self._load()

        # Apply styling
        if parent and hasattr(parent, 'current_theme'):
            c = parent.current_theme
            self.setStyleSheet(parent._get_dialog_stylesheet(c) + f"""
                QGroupBox {{
                    font-weight: bold;
                    border: 1px solid {c['border']};
                    border-radius: 6px;
                    margin-top: 10px;
                    padding-top: 15px; /* Adjust padding to make space for title */
                    color: {c['text_header']};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 5px;
                    left: 10px;
                    color: {c['text_header']};
                }}
                QDialogButtonBox QPushButton[text="Cancel"] {{
                    background-color: {c['secondary']};
                    color: {c['text']};
                }}
                QDialogButtonBox QPushButton[text="Cancel"]:hover {{
                    background-color: {c['border']};
                }}
            """)
        else:
            # Fallback styling
            self.setStyleSheet(f"""
                QDialog {{ background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }}
                QLabel {{ color: #333333; font-family: "{AppConfig.FONT_MAIN}"; font-weight: bold; }}
                QGroupBox {{ font-weight: bold; border: 1px solid #cccccc; border-radius: 6px; margin-top: 10px; padding-top: 15px; color: #007bff; }}
                QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; color: #007bff; }}
                QLineEdit, QComboBox {{ background-color: #f8f8f8; border: 1px solid #cccccc; border-radius: 6px; padding: 7px; color: #333333; }}
                QLineEdit:focus, QComboBox:focus {{ border-color: #007bff; }}
                QComboBox QAbstractItemView {{ background-color: #f8f8f8; border: 1px solid #cccccc; selection-background-color: #007bff; color: #333333; outline: 0px; }}
                QPushButton {{ background-color: #e0e0e0; color: #333333; border: 1px solid #cccccc; border-radius: 6px; padding: 8px 15px; font-weight: bold; }}
                QPushButton:hover {{ background-color: #cccccc; }}
                QDialogButtonBox QPushButton {{ background-color: #007bff; color: white; border: none; border-radius: 6px; padding: 8px 15px; font-weight: bold; }}
                QDialogButtonBox QPushButton[text="Cancel"] {{ background-color: #e0e0e0; color: #333333; }}
                QDialogButtonBox QPushButton[text="Cancel"]:hover {{ background-color: #cccccc; }}
                QDialogButtonBox QPushButton:hover {{ background-color: #0056b3; }}
            """)

    def _load(self): self.theme_combo.setCurrentText(self.settings.value("theme", "Dark")); self.default_path_input.setText(self.settings.value("default_path", str(Path.home())))
    def _browse(self): path = QFileDialog.getExistingDirectory(self, "Select Dir", self.default_path_input.text()); self.default_path_input.setText(path) if path else None
    def accept(self): self.settings.setValue("theme", self.theme_combo.currentText()); self.settings.setValue("default_path", self.default_path_input.text()); super().accept()

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Create New Project"); self.setMinimumWidth(450)
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.parent_dir = self.settings.value("default_path", str(Path.home()))
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Parent Directory:").setToolTip("The directory where the new project folder will be created"))
        path_layout = QHBoxLayout(); self.parent_dir_label = QLineEdit(self.parent_dir); self.parent_dir_label.setReadOnly(True)
        self.parent_dir_label.setToolTip("The parent directory for the new project")
        browse_btn = QPushButton("Browse..."); browse_btn.clicked.connect(self._browse); browse_btn.setToolTip("Select the parent directory for the new project")
        path_layout.addWidget(self.parent_dir_label); path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        layout.addWidget(QLabel("Project Name:").setToolTip("Enter a name for your new project (e.g., my-data-project)"))
        self.project_name_input = QLineEdit(); self.project_name_input.setPlaceholderText("e.g., customer-churn-analysis")
        self.project_name_input.setToolTip("Enter a descriptive name for your new project")
        layout.addWidget(self.project_name_input)
        
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.setToolTip("Create the new project or cancel")
        bbox.accepted.connect(self.accept); bbox.rejected.connect(self.reject); layout.addWidget(bbox)

        # Apply styling
        if parent and hasattr(parent, 'current_theme'):
            c = parent.current_theme
            self.setStyleSheet(parent._get_dialog_stylesheet(c) + f"""
                QDialogButtonBox QPushButton[text="Cancel"] {{
                    background-color: {c['secondary']};
                    color: {c['text']};
                }}
                QDialogButtonBox QPushButton[text="Cancel"]:hover {{
                    background-color: {c['border']};
                }}
            """)
        else:
            # Fallback styling
            self.setStyleSheet(f"""
                QDialog {{ background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }}
                QLabel {{ color: #333333; font-family: "{AppConfig.FONT_MAIN}"; font-weight: bold; }}
                QLineEdit {{ background-color: #f8f8f8; border: 1px solid #cccccc; border-radius: 6px; padding: 7px; color: #333333; }}
                QLineEdit:focus {{ border-color: #007bff; }}
                QPushButton {{ background-color: #e0e0e0; color: #333333; border: 1px solid #cccccc; border-radius: 6px; padding: 8px 15px; font-weight: bold; }}
                QPushButton:hover {{ background-color: #cccccc; }}
                QDialogButtonBox QPushButton {{ background-color: #007bff; color: white; border: none; border-radius: 6px; padding: 8px 15px; font-weight: bold; }}
                QDialogButtonBox QPushButton[text="Cancel"] {{ background-color: #e0e0e0; color: #333333; }}
                QDialogButtonBox QPushButton[text="Cancel"]:hover {{ background-color: #cccccc; }}
                QDialogButtonBox QPushButton:hover {{ background-color: #0056b3; }}
            """)


    def _browse(self): path = QFileDialog.getExistingDirectory(self, "Select Parent", self.parent_dir); self.parent_dir = path if path else self.parent_dir; self.parent_dir_label.setText(self.parent_dir)
    def get_details(self): return self.parent_dir, self.project_name_input.text().strip()

class GitCommitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Git Commit"); self.setMinimumWidth(400)
        layout = QVBoxLayout(self); layout.addWidget(QLabel("Enter commit message:").setToolTip("Provide a clear and concise message for your commit")) # Tooltip added
        self.commit_message_input = QTextEdit(); self.commit_message_input.setPlaceholderText("A brief summary of the changes...")
        self.commit_message_input.setToolTip("Enter the commit message here. Start with a short summary, then add more details if needed.") # Tooltip added
        self.commit_message_input.setMinimumHeight(100); layout.addWidget(self.commit_message_input)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.setToolTip("Commit changes with the provided message or cancel") # Tooltip added
        bbox.accepted.connect(self.accept); bbox.rejected.connect(self.reject); layout.addWidget(bbox)

        # Apply styling
        if parent and hasattr(parent, 'current_theme'):
            c = parent.current_theme
            self.setStyleSheet(parent._get_dialog_stylesheet(c) + f"""
                QTextEdit {{
                    background-color: {c['background']};
                    border: 1px solid {c['border']};
                    border-radius: 6px;
                    padding: 7px;
                    color: {c['text']};
                    font-family: "{AppConfig.FONT_MAIN}";
                }}
                QTextEdit:focus {{ border-color: {c['accent']}; }}
                QDialogButtonBox QPushButton[text="Cancel"] {{
                    background-color: {c['secondary']};
                    color: {c['text']};
                }}
                QDialogButtonBox QPushButton[text="Cancel"]:hover {{
                    background-color: {c['border']};
                }}
            """)
        else:
            # Fallback styling
            self.setStyleSheet(f"""
                QDialog {{ background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }}
                QLabel {{ color: #333333; font-family: "{AppConfig.FONT_MAIN}"; font-weight: bold; }}
                QTextEdit {{ background-color: #f8f8f8; border: 1px solid #cccccc; border-radius: 6px; padding: 7px; color: #333333; font-family: "{AppConfig.FONT_MAIN}"; }}
                QTextEdit:focus {{ border-color: #007bff; }}
                QDialogButtonBox QPushButton {{ background-color: #007bff; color: white; border: none; border-radius: 6px; padding: 8px 15px; font-weight: bold; }}
                QDialogButtonBox QPushButton[text="Cancel"] {{ background-color: #e0e0e0; color: #333333; }}
                QDialogButtonBox QPushButton[text="Cancel"]:hover {{ background-color: #cccccc; }}
                QDialogButtonBox QPushButton:hover {{ background-color: #0056b3; }}
            """)

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
        # The main layout is now directly on the main_window, which has a standard frame.
        self.main_window.main_layout = QVBoxLayout(self.main_window)
        self.main_window.main_layout.setContentsMargins(2, 2, 2, 2) # Margins for the inner container
        self.main_window.main_layout.setSpacing(0)

        # The container widget is used for visual styling (e.g., rounded corners, background)
        self.main_window.container = QWidget(self.main_window)
        self.main_window.container.setObjectName("container")
        self.main_window.main_layout.addWidget(self.main_window.container)
        
        self.container_layout = QVBoxLayout(self.main_window.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0) # Container takes up all space within the margins set on main_layout
        self.container_layout.setSpacing(0)

    def _setup_ui_components(self):
        # No custom title bar, rely on system title bar
        # self.container_layout.addWidget(self._create_title_bar()) # REMOVED

        # --- NEW TWO-COLUMN STRUCTURE ---
        # 1. Create a container widget for our columns
        columns_container = QWidget()
        columns_layout = QHBoxLayout(columns_container) # Main horizontal layout
        columns_layout.setContentsMargins(15, 10, 15, 15) # Adjusted padding
        columns_layout.setSpacing(20) # Increased spacing between columns
        columns_container.setToolTip("Main content area with controls on the left and project details on the right") # Tooltip added

        # 2. Create the Left Column (for controls)
        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(15)
        left_column_widget.setToolTip("Controls for project management and environment creation") # Tooltip added

        # 3. Create the Right Column (for lists)
        right_column_widget = QWidget()
        right_column_layout = QVBoxLayout(right_column_widget)
        right_column_layout.setContentsMargins(0, 0, 0, 0)
        right_column_layout.setSpacing(15)
        right_column_widget.setToolTip("Project directory contents and activity log") # Tooltip added

        # 4. Add the column widgets to the main horizontal layout
        columns_layout.addWidget(left_column_widget, 1) # Left column takes 1 part of width
        columns_layout.addWidget(right_column_widget, 1) # Right column takes 1 part of width

        # --- POPULATE THE LEFT COLUMN ---
        left_column_layout.addWidget(self._create_section_title("Project Workspace", "fa5s.folder-open"))
        left_column_layout.addLayout(self._create_path_section())
        left_column_layout.addWidget(self._create_separator_full_width())

        left_column_layout.addWidget(self._create_section_title("Version Control", "fa5s.code-branch"))
        left_column_layout.addWidget(self._create_git_section())
        left_column_layout.addWidget(self._create_separator_full_width())

        left_column_layout.addWidget(self._create_section_title("Python Environments", "fa5s.terminal"))
        left_column_layout.addLayout(self._create_new_venv_section())
        left_column_layout.addLayout(self._create_manage_venv_section())
        left_column_layout.addWidget(self._create_separator_full_width())

        left_column_layout.addWidget(self._create_section_title("Build & Global Tools", "fa5s.tools"))
        left_column_layout.addWidget(self._create_poetry_pdm_section())
        left_column_layout.addWidget(self._create_pipx_section()) # ADDED PIPX SECTION
        left_column_layout.addStretch() # Pushes everything up

        # --- POPULATE THE RIGHT COLUMN ---
        right_column_layout.addWidget(self._create_section_title("Directory & Files", "fa5s.folder"))
        right_column_layout.addLayout(self._create_file_actions_bar())
        right_column_layout.addLayout(self._create_files_section(), stretch=2)  # Give files more space but constrain
        right_column_layout.addWidget(self._create_separator_full_width())

        right_column_layout.addWidget(self._create_section_title("Activity & Logs", "fa5s.clipboard-list"))
        right_column_layout.addLayout(self._create_log_section(), stretch=1)  # Logs take remaining space
        right_column_layout.addStretch(1)  # Push up but allow flexibility

        # Set the main content of the container
        self.container_layout.addWidget(columns_container)

        # --- FOOTER REMAINS AT THE BOTTOM ---
        footer_container = QWidget() # Put footer in its own container
        footer_layout = self._create_footer_section()
        footer_container.setLayout(footer_layout)
        footer_container.setContentsMargins(15, 0, 0, 5) # Adjust margins
        footer_container.setObjectName("footerContainer") # For styling
        self.container_layout.addWidget(footer_container)

    def collect_interactive_widgets(self):
        self.main_window.interactive_widgets = self.main_window.container.findChildren(QPushButton) + \
                                           self.main_window.container.findChildren(QComboBox) + \
                                           self.main_window.container.findChildren(QLineEdit) + \
                                           self.main_window.container.findChildren(QTextEdit) + \
                                           self.main_window.container.findChildren(QToolButton) # Added QToolButton

    def _create_section_title(self, text, icon_name):
        c = self.main_window.current_theme
        label_widget = QWidget()
        label_layout = QHBoxLayout(label_widget)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(5)

        icon_label = QLabel()
        icon_label.setPixmap(fa.icon(icon_name, color=c['text_header'], options=[{'scale_factor': 1.1}]).pixmap(16, 16))
        
        text_label = QLabel(text)
        text_label.setObjectName("sectionHeaderLabel")
        text_label.setToolTip(f"Section: {text}")

        label_layout.addWidget(icon_label)
        label_layout.addWidget(text_label)
        label_layout.addStretch()
        return label_widget

    def _create_separator_full_width(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("fullWidthSeparator") # For styling
        return separator

    # Removed _create_title_bar as it's no longer needed for a standard window.
    # The title label is handled by setWindowTitle, and control buttons are moved to footer.

    def _create_path_section(self):
        c = self.main_window.current_theme
        layout = QVBoxLayout(); layout.setSpacing(8) # No direct QLabel here, using section title
        
        path_layout = QHBoxLayout(); 
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter or select project directory")
        self.path_input.setToolTip("Enter or select the path to your project directory")
        self.path_input.setObjectName("pathInput") # For specific styling
        
        # Smart Path Suggestions (Autocomplete)
        self.path_completer_model = QStringListModel(self.main_window)
        self.path_completer = QCompleter(self.path_completer_model, self.main_window)
        self.path_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.path_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.path_input.setCompleter(self.path_completer)

        self.recent_paths_btn = QToolButton(); 
        self.recent_paths_btn.setIcon(fa.icon('fa5s.history', color=c['text_secondary'])); 
        self.recent_paths_btn.setObjectName("iconOnlyToolButton"); 
        self.recent_paths_btn.setToolTip("Show recent project directories") # Tooltip added
        
        path_layout.addWidget(self.path_input); path_layout.addWidget(self.recent_paths_btn); 
        layout.addLayout(path_layout)

        btn_layout = QHBoxLayout()
        self.browse_btn = QPushButton(fa.icon('fa5s.folder-open', color=c['text']), "Select Directory"); self.browse_btn.setToolTip("Browse to select an existing project directory") # Tooltip added
        self.new_project_btn = QPushButton(fa.icon('fa5s.plus-circle', color=c['text']), "New Project"); self.new_project_btn.setToolTip("Create a new project with a standard folder structure") # Tooltip added
        self.open_btn = QPushButton(fa.icon('fa5s.external-link-alt', color=c['text']), "Open in Explorer"); self.open_btn.setToolTip("Open the current project directory in your system's file explorer") # Tooltip added
        
        btn_layout.addWidget(self.browse_btn); btn_layout.addWidget(self.new_project_btn); btn_layout.addWidget(self.open_btn); 
        layout.addLayout(btn_layout)
        return layout

    def _create_git_section(self):
        c = self.main_window.current_theme
        self.git_groupbox = QGroupBox(""); # No title here, using section title
        self.git_groupbox.setObjectName("gitGroupBox") # For styling
        self.git_groupbox.setToolTip("Displays information about the Git repository in the current project directory")
        layout = QVBoxLayout(self.git_groupbox) 
        
        self.git_status_label = QLabel("Not a git repository."); 
        self.git_status_label.setObjectName("gitStatusLabel")
        self.git_status_label.setWordWrap(True) # Allow text wrapping
        layout.addWidget(self.git_status_label)

        # Visual Git Timeline (QTextEdit for formatted output)
        self.git_timeline_text_edit = QTextEdit()
        self.git_timeline_text_edit.setReadOnly(True)
        self.git_timeline_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.git_timeline_text_edit.setMinimumHeight(60) # Changed from setFixedHeight
        self.git_timeline_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # No scrollbar, just show latest 3-5
        self.git_timeline_text_edit.setToolTip("Shows the last 5 Git commits in the current repository")
        self.git_timeline_text_edit.setObjectName("gitTimeline") # For specific styling
        layout.addWidget(self.git_timeline_text_edit)

        git_btn_layout = QHBoxLayout()
        self.git_pull_btn = QPushButton(fa.icon('fa5s.cloud-download-alt', color=c['text']), "Pull"); 
        self.git_pull_btn.setToolTip("Fetch and integrate changes from the remote Git repository")
        
        self.git_commit_btn = QPushButton(fa.icon('fa5s.save', color=c['text']), "Commit");
        self.git_commit_btn.setToolTip("Stage all current changes and commit them to the Git repository")
        
        git_btn_layout.addStretch(); 
        git_btn_layout.addWidget(self.git_pull_btn); 
        git_btn_layout.addWidget(self.git_commit_btn)
        layout.addLayout(git_btn_layout)
        self.git_groupbox.setVisible(False); return self.git_groupbox

    def _create_new_venv_section(self):
        c = self.main_window.current_theme
        layout = QVBoxLayout(); layout.setSpacing(8); # No direct QLabel here
        
        # New: Python Version Input
        python_ver_layout = QHBoxLayout()
        python_ver_label = QLabel("Python Version (optional):")
        python_ver_label.setToolTip("Specify a Python version (e.g., 3.9, 3.10). Uses 'py.exe' on Windows. Leave blank for system default.")
        python_ver_layout.addWidget(python_ver_label)
        self.new_venv_python_version_input = QLineEdit()
        self.new_venv_python_version_input.setPlaceholderText("e.g., 3.9, 3.10 (uses py.exe on Win)")
        self.new_venv_python_version_input.setToolTip("Enter a specific Python version for the new environment (e.g., 3.9).")
        python_ver_layout.addWidget(self.new_venv_python_version_input)
        layout.addLayout(python_ver_layout)

        # New: One-Click Env Templates
        template_layout = QHBoxLayout()
        template_label = QLabel("Env Template (optional):")
        template_label.setToolTip("Select a template to pre-install common packages into the new environment.")
        template_layout.addWidget(template_label)
        self.template_combo = QComboBox()
        self.template_combo.addItem("None", None) # Default "None" option
        self.template_combo.setToolTip("Choose a set of packages to install automatically after environment creation")
        # Templates will be populated dynamically from JupyterLauncher
        template_layout.addWidget(self.template_combo)
        layout.addLayout(template_layout)

        creation_layout = QHBoxLayout()
        self.new_venv_name_input = QLineEdit()
        self.new_venv_name_input.setPlaceholderText("Enter new environment name (no spaces)")
        self.new_venv_name_input.setToolTip("Enter a unique name for your new virtual environment (no spaces allowed)")
        self.create_venv_btn = QPushButton(fa.icon('fa5s.plus-square', color='white'), "Create Environment")
        self.create_venv_btn.setObjectName("createBtn")
        self.create_venv_btn.setToolTip("Create the new virtual environment in the current project directory")
        creation_layout.addWidget(self.new_venv_name_input); creation_layout.addWidget(self.create_venv_btn); layout.addLayout(creation_layout)
        return layout

    def _create_manage_venv_section(self):
        c = self.main_window.current_theme # Define c here for icon color
        layout = QVBoxLayout(); layout.setSpacing(8) # No direct QLabel here
        
        env_selection_layout = QHBoxLayout()
        env_selection_layout.addWidget(QLabel("Active Environment:").setToolTip("Select an existing virtual environment (local venv or Conda) to manage"))
        self.venv_dropdown = QComboBox()
        self.venv_dropdown.setToolTip("Select an existing virtual environment (local venv or Conda) to manage")
        
        self.delete_venv_btn = QPushButton() 
        self.delete_venv_btn.setIcon(fa.icon('fa5s.trash-alt', color=c['error'])) # Set icon with theme color
        self.delete_venv_btn.setObjectName("iconOnlyButton") # Custom object name for icon-only button styling
        self.delete_venv_btn.setFixedSize(30, 30) # Fixed size for icon only
        self.delete_venv_btn.setToolTip("Delete Selected Environment")

        env_selection_layout.addWidget(self.venv_dropdown)
        env_selection_layout.addWidget(self.delete_venv_btn)
        layout.addLayout(env_selection_layout)

        self.env_details_label = QLabel("Select an environment to see details."); self.env_details_label.setObjectName("detailsLabel")
        self.env_details_label.setWordWrap(True)
        self.env_details_label.setToolTip("Displays details like Python version and creation time for the selected environment")
        layout.addWidget(self.env_details_label)

        # Package Management Group Box (Visible in the image)
        self.package_action_group = QGroupBox("Package Management"); self.package_action_group.setObjectName("packageManagementGroup")
        self.package_action_group.setToolTip("Tools for managing installed packages within the selected environment")
        package_action_layout = QHBoxLayout(self.package_action_group)
        
        # Refined buttons for Package Management - Applying QSizePolicy for better rendering
        self.check_updates_btn = QPushButton(fa.icon('fa5s.sync-alt', color=c['text']), "Check Updates")
        self.check_updates_btn.setToolTip("Scan for outdated packages in the selected environment")
        self.check_updates_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)

        self.upgrade_package_btn = QPushButton(fa.icon('fa5s.arrow-up', color=c['text']), "Upgrade Selected")
        self.upgrade_package_btn.setToolTip("Upgrade the selected package in the table to its latest version")
        self.upgrade_package_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)

        self.uninstall_package_btn = QPushButton(fa.icon('fa5s.minus-circle', color=c['error']), "Uninstall Selected")
        self.uninstall_package_btn.setToolTip("Uninstall the selected package from the environment") # Use error color for uninstall
        self.uninstall_package_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)

        package_action_layout.addWidget(self.check_updates_btn)
        package_action_layout.addWidget(self.upgrade_package_btn)
        package_action_layout.addWidget(self.uninstall_package_btn)
        package_action_layout.addStretch() # Add stretch to push buttons to the left if space allows

        layout.addWidget(self.package_action_group)

        # Package Table (Visible in the image)
        self.package_table = QTableWidget()
        self.package_table.setColumnCount(3)
        self.package_table.setHorizontalHeaderLabels(["Package", "Version", "Latest"])
        self.package_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.package_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.package_table.verticalHeader().setVisible(False)
        self.package_table.setAlternatingRowColors(True)
        self.package_table.setMinimumHeight(80)  # Reduced min height
        self.package_table.setMaximumHeight(200)  # Cap max height to prevent takeover
        self.package_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)  # Expand horizontally, max vertically
        self.package_table.setToolTip("Lists installed packages. Outdated packages will be highlighted after checking for updates.")
        self.package_table.setObjectName("packageTable")
        # Limit row heights for compactness
        self.package_table.verticalHeader().setDefaultSectionSize(20)  # Shorter rows
        self.package_table.verticalHeader().setMaximumSectionSize(25)

        header = self.package_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(60)  # Prevent squished columns
        header.setStretchLastSection(False)  # Don't auto-stretch last column
        layout.addWidget(self.package_table)
        self.package_action_group.setVisible(False)
        self.package_table.setVisible(False)
        layout.insertStretch(-1, 1)

        # Package Operations Layout (Install, Export, Freeze)
        pkg_ops_layout = QHBoxLayout()
        self.install_reqs_btn = QPushButton(fa.icon('fa5s.file-import', color=c['text']), "Install from File"); self.install_reqs_btn.setToolTip("Install packages from a requirements.txt or packages.json file into the selected environment")
        self.export_json_btn = QPushButton(fa.icon('fa5s.file-export', color=c['text']), "Export to JSON"); self.export_json_btn.setToolTip("Export a list of non-core installed packages to a packages.json file")
        self.freeze_btn = QPushButton(fa.icon('fa5s.lock', color=c['text']), "Freeze to TXT"); self.freeze_btn.setToolTip("Generate a requirements.txt file with all installed packages and their versions")
        pkg_ops_layout.addWidget(self.install_reqs_btn); pkg_ops_layout.addWidget(self.export_json_btn); pkg_ops_layout.addWidget(self.freeze_btn); layout.addLayout(pkg_ops_layout)
        
        # Launch Layout (Activate Terminal, Launch Jupyter)
        launch_layout = QHBoxLayout()
        self.activate_btn = QPushButton(fa.icon('fa5s.terminal', color=c['text']), "Activate Terminal"); self.activate_btn.setToolTip("Open a new terminal with the selected virtual environment activated")
        self.launch_jupyter_btn = QPushButton(fa.icon('fa5s.book-open', color='white'), "Launch Jupyter"); self.launch_jupyter_btn.setObjectName("launchBtn"); self.launch_jupyter_btn.setToolTip("Launch Jupyter Notebook in the activated environment (requires Jupyter to be installed)")
        launch_layout.addWidget(self.activate_btn); launch_layout.addWidget(self.launch_jupyter_btn); layout.addLayout(launch_layout)

        layout.addStretch() # Ensure elements are pushed to the top in this section

        return layout

    def _create_poetry_pdm_section(self):
        c = self.main_window.current_theme
        self.build_tools_groupbox = QGroupBox(""); # No title
        self.build_tools_groupbox.setObjectName("buildToolsGroupBox")
        self.build_tools_groupbox.setToolTip("Actions for project-specific build tools like Poetry or PDM (only visible if pyproject.toml exists)")
        layout = QHBoxLayout(self.build_tools_groupbox)
        self.poetry_install_btn = QPushButton(fa.icon('fa5s.flask', color=c['text']), "Poetry Install"); self.poetry_install_btn.setToolTip("Install project dependencies defined in pyproject.toml using Poetry")
        self.pdm_sync_btn = QPushButton(fa.icon('fa5s.box-open', color=c['text']), "PDM Sync"); self.pdm_sync_btn.setToolTip("Synchronize project dependencies defined in pyproject.toml using PDM")
        layout.addWidget(self.poetry_install_btn); layout.addWidget(self.pdm_sync_btn); self.build_tools_groupbox.setVisible(False); return self.build_tools_groupbox

    def _create_pipx_section(self):
        c = self.main_window.current_theme
        self.pipx_groupbox = QGroupBox(""); # No title
        self.pipx_groupbox.setObjectName("pipxGroupBox")
        self.pipx_groupbox.setToolTip("Manage globally installed Python applications using pipx (e.g., Black, Rich-cli)")
        layout = QVBoxLayout(self.pipx_groupbox); layout.setSpacing(8)

        # Instruction label
        layout.addWidget(QLabel("Manage pipx installed applications:").setToolTip("Install, upgrade, or uninstall Python applications globally without affecting project environments."))

        # Install/Upgrade/Uninstall
        pkg_action_layout = QHBoxLayout()
        self.pipx_package_input = QLineEdit()
        self.pipx_package_input.setPlaceholderText("package name (e.g., black, rich-cli)")
        self.pipx_package_input.setToolTip("Enter the name of the Python application to install, upgrade, or uninstall with pipx")
        self.pipx_install_btn = QPushButton(fa.icon('fa5s.plus', color=c['text']), "Install"); self.pipx_install_btn.setToolTip("Install a Python application globally using pipx")
        self.pipx_upgrade_btn = QPushButton(fa.icon('fa5s.arrow-up', color=c['text']), "Upgrade"); self.pipx_upgrade_btn.setToolTip("Upgrade an existing pipx-installed application")
        self.pipx_uninstall_btn = QPushButton(fa.icon('fa5s.trash-alt', color=c['error']), "Uninstall"); self.pipx_uninstall_btn.setToolTip("Uninstall a pipx-installed application")

        pkg_action_layout.addWidget(self.pipx_package_input)
        pkg_action_layout.addWidget(self.pipx_install_btn)
        pkg_action_layout.addWidget(self.pipx_upgrade_btn)
        pkg_action_layout.addWidget(self.pipx_uninstall_btn)
        layout.addLayout(pkg_action_layout)

        # List/Ensure Path
        other_actions_layout = QHBoxLayout()
        self.pipx_list_btn = QPushButton(fa.icon('fa5s.list-ul', color=c['text']), "List Tools"); self.pipx_list_btn.setToolTip("Display a list of all Python applications installed via pipx")
        self.pipx_ensurepath_btn = QPushButton(fa.icon('fa5s.route', color=c['text']), "Ensure Path"); self.pipx_ensurepath_btn.setToolTip("Run 'pipx ensurepath' to verify and update your system's PATH variable to include pipx executables. (Restart terminal for changes to take effect)")
        other_actions_layout.addWidget(self.pipx_list_btn)
        other_actions_layout.addWidget(self.pipx_ensurepath_btn)
        layout.addLayout(other_actions_layout)

        # Output area for pipx commands
        layout.addWidget(QLabel("pipx Output:").setToolTip("Command output from pipx operations"))
        self.pipx_output = QTextEdit()
        self.pipx_output.setReadOnly(True)
        self.pipx_output.setMinimumHeight(60) # Changed from setFixedHeight
        self.pipx_output.setObjectName("pipxOutput")
        self.pipx_output.setToolTip("Shows the output and logs of pipx commands")
        self.pipx_output.setFont(QFont(AppConfig.FONT_CODE, 9)) # Use code font
        layout.addWidget(self.pipx_output)

        self.pipx_groupbox.setVisible(False)
        return self.pipx_groupbox

    # NEW: Quick File Actions Bar
    def _create_file_actions_bar(self):
        c = self.main_window.current_theme
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8) # Increased spacing

        # Use QToolButton with ToolButtonTextBesideIcon
        self.new_file_btn = QToolButton(); self.new_file_btn.setIcon(fa.icon('fa5s.file-medical', color=c['accent'])); self.new_file_btn.setText("New File"); self.new_file_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.new_file_btn.setToolTip("Create a new empty file")
        self.new_folder_btn = QToolButton(); self.new_folder_btn.setIcon(fa.icon('fa5s.folder-plus', color=c['accent'])); self.new_folder_btn.setText("New Folder"); self.new_folder_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.new_folder_btn.setToolTip("Create a new empty folder") # Tooltip added
        
        self.run_script_btn = QToolButton(); self.run_script_btn.setIcon(fa.icon('fa5s.play', color=c['success'])); self.run_script_btn.setText("Run Script"); self.run_script_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.run_script_btn.setToolTip("Run the selected Python script in the active environment")
        self.open_terminal_btn = QToolButton(); self.open_terminal_btn.setIcon(fa.icon('fa5s.terminal', color=c['accent'])); self.open_terminal_btn.setText("Open Terminal"); self.open_terminal_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.open_terminal_btn.setToolTip("Open a new terminal in the current directory (or parent of selected file)")
        
        self.delete_file_btn = QToolButton(); self.delete_file_btn.setIcon(fa.icon('fa5s.trash', color=c['error'])); self.delete_file_btn.setText("Delete"); self.delete_file_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.delete_file_btn.setToolTip("Delete the selected file or folder permanently")

        layout.addWidget(self.new_file_btn)
        layout.addWidget(self.new_folder_btn)
        layout.addSpacing(10) # Visual separator spacing
        layout.addWidget(self.run_script_btn)
        layout.addWidget(self.open_terminal_btn)
        layout.addSpacing(10) # Visual separator spacing
        layout.addWidget(self.delete_file_btn)
        layout.addStretch()

        return layout

    def _create_files_section(self):
        layout = QVBoxLayout(); layout.setSpacing(8); # No direct QLabel here
        self.file_list = QListWidget(); self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); layout.addWidget(self.file_list);
        self.file_list.setToolTip("Double-click to open files or navigate folders. Right-click for more actions.")
        self.file_list.setObjectName("fileListWidget") # For styling
        self.file_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # Allow it to expand vertically
        return layout

    def _create_log_section(self):
        c = self.main_window.current_theme
        layout = QVBoxLayout(); layout.setSpacing(4); 
        header = QHBoxLayout(); 
        
        log_label = QLabel("Activity Log")
        log_label.setToolTip("Log of all application activities and command outputs")
        header.addWidget(log_label)
        header.addStretch() 

        self.clear_log_btn = QPushButton(fa.icon('fa5s.broom', color=c['text_secondary']), "Clear"); self.clear_log_btn.setToolTip("Clear all messages from the activity log")
        self.clear_log_btn.setObjectName("smallIconButton") # For specific styling
        self.clear_log_btn.setFixedSize(60, 25) # Smaller button
        header.addWidget(self.clear_log_btn); 
        layout.addLayout(header)

        self.log_output = QTextEdit(); self.log_output.setReadOnly(True); self.log_output.setObjectName("logOutput")
        self.log_output.setMinimumHeight(100) # Changed from setFixedHeight
        self.log_output.setToolTip("Displays real-time output from commands and application messages")
        self.log_output.setFont(QFont(AppConfig.FONT_CODE, 9)) # Use code font
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) # Allow it to expand vertically
        layout.addWidget(self.log_output)
        return layout

    def _create_footer_section(self):
        footer = QHBoxLayout(); footer.setContentsMargins(0, 5, 0, 0)
        
        # Status Bar Tips: Use ClickableLabel
        self.status_label = ClickableLabel("Welcome! Click for tips."); 
        self.status_label.setObjectName("statusLabel")
        self.status_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor)) # Indicate it's clickable
        self.status_label.setToolTip("Click to see recent activity and a 'Did You Know?' tip.")

        self.progress_bar = QProgressBar(); self.progress_bar.setTextVisible(False); self.progress_bar.setVisible(False); self.progress_bar.setFixedHeight(5) # Thinner progress bar
        self.progress_bar.setToolTip("Indicates that a background command process is currently running.")
        
        status_layout = QVBoxLayout(); 
        status_layout.addWidget(self.status_label); 
        status_layout.addWidget(self.progress_bar); 
        footer.addLayout(status_layout, 1)
        
        # Added About and Settings buttons to the footer
        footer.addStretch() # Push buttons to the right
        self.running_indicator = QLabel("●") # Moved from title bar
        self.running_indicator.setObjectName("runningIndicator")
        self.running_indicator.setVisible(False)
        self.running_indicator.setToolTip("A command process is currently active.")
        footer.addWidget(self.running_indicator)

        self.about_btn = QPushButton()
        self.about_btn.setIcon(fa.icon('fa5s.info-circle', color=self.main_window.current_theme['text_secondary']))
        self.about_btn.setObjectName("controlBtn")
        self.about_btn.setToolTip("About PyEnv Launcher")
        self.about_btn.setFixedSize(30, 30)
        footer.addWidget(self.about_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(fa.icon('fa5s.cog', color=self.main_window.current_theme['text_secondary']))
        self.settings_btn.setObjectName("controlBtn")
        self.settings_btn.setToolTip("Open Settings")
        self.settings_btn.setFixedSize(30, 30)
        footer.addWidget(self.settings_btn)

        # footer.addWidget(QSizeGrip(self.main_window)); # QSizeGrip is on the main_window now
        return footer


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
        "The running indicator (●) tells you if a background command is currently active.",
        "You can specify a Python version when creating a new environment (e.g., 3.9) to use a specific interpreter.",
        "Use the 'Export to JSON' button to save your installed non-core packages to a `packages.json` file for easy reinstallation."
    ]

    def __init__(self):
        super().__init__()
        self.settings = QSettings("ChakhdiLocal", "PyEnvLauncher")
        self.current_theme = AppConfig.DARK_THEME if self.settings.value("theme", "Dark") == "Dark" else AppConfig.LIGHT_THEME
        self.setWindowTitle("PyEnv Launcher"); self.setObjectName("JupyterLauncher")
        # self.setWindowFlags(Qt.WindowType.FramelessWindowHint) # REMOVED for standard window
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # REMOVED for standard window
        
        # --- CODE TO CENTER THE WINDOW ---
        self._center_on_screen()
        # ------------------------------------

        self.observer = None
        # self.old_pos = None # REMOVED as custom dragging is no longer needed
        self.command_thread = None
        self.pipx_thread = None # Added for pipx commands
        self.interactive_widgets = []
        self.package_data = {}
        self.pipx_data = {} # Added for pipx list

        self.log_history = deque(maxlen=10) # Increased history for status bar tips

        self.ui = UIManager(self)
        self._apply_stylesheet()
        self._connect_signals()
        self._setup_animations()
        self._load_app_settings()
        self._populate_env_templates() # Populate template dropdown
        self._on_path_changed() # Trigger initial discovery and completer update

    def _connect_signals(self):
        # Title Bar (now footer buttons)
        self.ui.about_btn.clicked.connect(self._open_about_dialog)
        self.ui.settings_btn.clicked.connect(self._open_settings)
        # self.ui.close_btn.clicked.connect(self._initiate_close) # REMOVED - use system close
        # self.ui.minimize_btn.clicked.connect(self.showMinimized) # REMOVED - use system minimize
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

    def _get_dialog_stylesheet(self, c):
        """Generates a common stylesheet string for QDialogs."""
        return f"""
            QDialog {{ background-color: {c['primary']}; border: 1px solid {c['border']}; border-radius: 8px; }}
            QLabel {{ color: {c['text']}; font-family: "{AppConfig.FONT_MAIN}"; }}
            QLineEdit, QComboBox, QTextEdit {{
                background-color: {c['background']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 7px;
                color: {c['text']};
                font-family: "{AppConfig.FONT_MAIN}"; /* Ensure font consistency */
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border-color: {c['accent']}; }}
            QComboBox QAbstractItemView {{
                background-color: {c['background']};
                border: 1px solid {c['border']};
                selection-background-color: {c['accent']};
                color: {c['text']};
                outline: 0px;
            }}
            QPushButton {{
                background-color: {c['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {c['accent']}CC; }}
            QDialogButtonBox QPushButton {{ /* Specific for buttons in QDialogButtonBox */
                background-color: {c['accent']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }}
            QDialogButtonBox QPushButton:hover {{ background-color: {c['accent']}CC; }}
        """

    def _apply_stylesheet(self):
        c = self.current_theme
        
        # Load Inter font, if available. Fallback to Segoe UI or system default.
        font_family_main = f'"{AppConfig.FONT_MAIN}", "Segoe UI", sans-serif'
        font_family_code = f'"{AppConfig.FONT_CODE}", "Cascadia Code", "Consolas", monospace'

        self.setStyleSheet(f"""
            /* General App Styling */
            #container{{
                background-color:{c['primary']};
                border: 0px solid transparent;
                border-radius:10px;
            }}
            QWidget{{
                font-family:{font_family_main};
                color:{c['text']};
                font-size:9.5pt;
            }}
            
            #controlBtn, #iconOnlyToolButton {{
                background:{c['secondary']};
                border:none;
                border-radius:5px;
                font-size:10pt;
            }}
            #controlBtn:hover, #iconOnlyToolButton:hover {{
                background:{c['border']};
            }}
            #controlBtn:pressed, #iconOnlyToolButton:pressed {{
                background:{c['secondary']};
            }}

            /* Section Headers */
            #sectionHeaderLabel {{
                font-weight: bold;
                font-size: 10pt;
                color: {c['text_header']};
                padding-bottom: 2px;
            }}
            #fullWidthSeparator {{
                border: none;
                background-color: {c['border']}60;
                height: 1px;
                margin-top: 10px;
                margin-bottom: 10px;
            }}

            /* Labels and Details */
            QLabel{{font-weight:bold;background:transparent;}}
            #detailsLabel, #gitStatusLabel {{
                font-weight:normal;
                color:{c['text_secondary']};
                padding-left: 2px;
            }}
            
            /* Input Fields (QLineEdit, QComboBox, QTextEdit) */
            QLineEdit, QComboBox, QTextEdit {{
                background-color:{c['secondary']};
                border:1px solid {c['border']};
                border-radius:6px;
                padding:8px 10px;
                color: {c['text']};
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
                border-color:{c['accent']};
                background-color: {c['background']};
            }}
            QComboBox QAbstractItemView{{
                background-color:{c['secondary']};
                border:1px solid {c['border']};
                selection-background-color:{c['accent']};
                color:{c['text']};
                outline:0px;
                border-radius: 6px;
            }}
            QComboBox QAbstractItemView::item{{padding:10px 6px;}}

            /* General Buttons (QPushButton) */
            QPushButton {{
                background-color:{c['secondary']};
                border:1px solid {c['border']};
                border-radius:6px;
                padding:8px 12px;
                font-weight:bold;
                icon-size: 15px;
            }}
            QPushButton:hover{{border-color:{c['accent']}; background-color: {c['border']};}}
            QPushButton:pressed{{background-color:{c['secondary']}; border-color: {c['accent']};}}
            QPushButton:disabled{{background-color:{c['secondary']}80;color:{c['text_secondary']}80;border-color:{c['border']};}}
            
            /* Special Buttons */
            #createBtn{{
                background-color:{c['accent']};
                border-color:{c['accent']};
                color: white;
            }} 
            #createBtn:hover{{background-color:{c['accent']}CC; border-color:{c['accent']};}}
            #launchBtn{{
                background-color:{c['accent']};
                border-color:{c['accent']};
                color: white;
            }} 
            #launchBtn:hover{{background-color:{c['accent']}CC; border-color:{c['accent']};}}
            #iconOnlyButton {{ /* For small icon-only buttons like delete_venv */
                padding: 4px;
                border-radius: 5px;
                background-color: transparent;
                border: 1px solid transparent;
            }}
            #iconOnlyButton:hover {{
                background-color: {c['secondary']};
                border-color: {c['border']};
            }}
            #iconOnlyButton[icon_name="fa5s.trash-alt"]:hover {{
                background-color: {c['error']}40;
                border-color: {c['error']};
            }}
            #smallIconButton {{ /* For buttons like Clear Log */
                padding: 3px 8px;
                font-size: 8.5pt;
                font-weight: normal;
                border-radius: 4px;
                color: {c['text']}; /* Explicitly set text color for readability */
            }}

            /* Tool Buttons (QToolButton) */
            QToolButton {{ 
                background-color: {c['secondary']};
                border:1px solid {c['border']};
                border-radius:6px;
                padding:6px 10px;
                font-weight:bold;
                icon-size: 14px;
            }} 
            QToolButton:hover{{border-color:{c['accent']}; background-color: {c['border']};}}
            QToolButton:pressed{{background-color:{c['secondary']}; border-color: {c['accent']};}}
            QToolButton:disabled{{background-color:{c['secondary']}80;color:{c['text_secondary']}80;border-color:{c['border']};}}
            QToolButton::menu-indicator {{ image: none; }}

            /* Status Bar */
            #statusLabel{{
                font-weight:normal;
                background-color:transparent;
                color:{c['text_secondary']};
                padding: 4px;
                border-radius: 4px;
            }}
            #runningIndicator{{
                color:{c['accent']};
                font-size:16pt;
                font-weight:bold;
                padding-bottom:4px;
            }}
            
            QProgressBar{{
                border-radius:2px;
                background-color:{c['secondary']};
                text-align:center;
                height: 5px;
            }}
            QProgressBar::chunk{{
                background-color:{c['accent']};
                border-radius:2px;
            }}

            /* List Widgets, Text Edits (Output Areas) */
            QListWidget, #logOutput, #pipxOutput, #gitTimeline {{
                background-color:{c['secondary']};
                border:1px solid {c['border']};
                border-radius:6px;
                padding:4px;
                font-family:{font_family_code};
                font-size:9pt;
            }}
            QListWidget::item{{
                padding:6px;
                border-radius:4px;
                margin-bottom: 2px;
            }} 
            QListWidget::item:hover{{background-color:{c['border']};}}
            QListWidget::item:selected{{background-color:{c['accent']};color:white;}}
            
            /* Context Menus - Now inherits from dialog stylesheet, but defining here for clarity if needed for QMenu directly*/
            QMenu{{
                background-color:{c['primary']};
                border:1px solid {c['border']};
                border-radius: 6px;
                padding: 5px;
            }} 
            QMenu::item{{
                padding: 6px 15px 6px 25px;
                color: {c['text']};
            }}
            QMenu::item:selected{{
                background-color:{c['accent']};
                color: white;
                border-radius: 3px;
            }}
            QMenu::icon {{
                padding-left: 5px;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {c['border']}60;
                margin: 5px 0px;
            }}

            /* Group Boxes */
            QGroupBox{{
                font-weight:bold;
                border:1px solid {c['border']};
                border-radius:6px;
                margin-top:10px;
                padding-top:15px;
                color: {c['text_header']};
            }}
            QGroupBox::title{{
                subcontrol-origin:margin;
                subcontrol-position:top left;
                padding:0 5px;
                left:10px;
                color: {c['text_header']};
            }}

            /* Table Widgets */
            QTableWidget {{
                background-color: {c['secondary']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                gridline-color: {c['border']}60;
                alternate-background-color: {c['background']};
            }}
            QTableWidget::item {{
                padding: 4px;
                color: {c['text']};
                border-bottom: 1px solid {c['secondary']};
            }}
            QTableWidget::item:selected {{
                background-color: {c['accent']};
                color: #ffffff;
            }}
            QHeaderView::section {{
                background-color: {c['border']};
                border-bottom: 1px solid {c['border_window']};
                border-right: 1px solid {c['secondary']};
                padding: 6px;
                font-weight: bold;
                color: {c['text']};
                min-height: 20px;
            }}
            QHeaderView::section:hover {{
                background-color: {c['border']}CC;
            }}

            /* Scrollbars */
            QScrollBar:vertical {{
                border: none;
                background: {c['primary']};
                width: 10px;
                margin: 0px;
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
                margin: 0px;
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

        # Also enable/disable the package management buttons based on environment selection.
        # This is particularly relevant when switching to "No environments found" or "Invalid Project Path".
        is_env_selected = self.ui.venv_dropdown.currentData() not in [None, "Invalid Project Path"] and "No environments found" not in self.ui.venv_dropdown.currentText()
        
        self.ui.check_updates_btn.setEnabled(enabled and is_env_selected)
        self.ui.upgrade_package_btn.setEnabled(enabled and is_env_selected and bool(self.ui.package_table.selectedItems()))
        self.ui.uninstall_package_btn.setEnabled(enabled and is_env_selected and bool(self.ui.package_table.selectedItems()))
        self.ui.install_reqs_btn.setEnabled(enabled and is_env_selected)
        self.ui.export_json_btn.setEnabled(enabled and is_env_selected)
        self.ui.freeze_btn.setEnabled(enabled and is_env_selected)
        self.ui.activate_btn.setEnabled(enabled and is_env_selected)
        self.ui.launch_jupyter_btn.setEnabled(enabled and is_env_selected)


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
        current_selected_env = ui_env_text.split(' (')[0] if ui_env_text and "No environments found" not in ui_env_text and "Invalid Project Path" not in ui_env_text else None
        current_env_type = ui_env_data or "venv" # Default to venv if no specific data

        # For commands that require an environment, check if it's valid
        required_env_commands = ["get_env_details", "freeze", "pip_list", "launch", "activate", "install_requirements", "pip_outdated", "pip_upgrade", "pip_uninstall", "install_template_packages"]
        if command_type in required_env_commands and (not current_selected_env or "found" in current_selected_env or "Invalid Project Path" in ui_env_text):
            self._update_status("A valid environment must be selected for this action.", "error")
            return
            
        self._set_ui_enabled(False)

        # Create a new kwargs dictionary for CommandThread to avoid modifying the original
        thread_kwargs = kwargs.copy()

        # Extract 'selected_env' and 'env_type' from thread_kwargs if they were explicitly passed
        # Otherwise, use the values determined from the UI dropdown
        thread_selected_env = thread_kwargs.pop('selected_env', current_selected_env)
        thread_env_type = thread_kwargs.pop('env_type', current_env_type)
        thread_kwargs.pop('base_path', None) # base_path is passed directly to CommandThread init

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
        self._set_ui_enabled(True) # Re-enable UI
        self._update_status(message, "success" if success else "error")
        (self._log_message if not is_pipx_command else self._pipx_log_message)(f"Finished: {message}")
        if success and on_finish_callback:
            on_finish_callback(command_output)
        if self.command_thread and self.command_thread.command_type in ['git_pull', 'git_commit']:
            self._update_git_status()
        if is_pipx_command:
            self.pipx_thread = None # Clear pipx thread
            self._check_pipx_availability(auto_list=False) # Re-check status without listing immediately

    # Helper method to apply theme to QMessageBox
    def _style_message_box(self, message_box):
        c = self.current_theme
        message_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {c['primary']};
                border: 1px solid {c['border']};
                border-radius: 8px;
            }}
            QMessageBox QLabel {{
                color: {c['text']};
                font-family: "{AppConfig.FONT_MAIN}";
            }}
            QMessageBox QPushButton {{
                background-color: {c['accent']};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }}
            QMessageBox QPushButton:hover {{
                background-color: {c['accent']}CC;
            }}
            QMessageBox QPushButton[text="Cancel"], QMessageBox QPushButton[text="No"] {{ /* Specific for Cancel/No buttons */
                background-color: {c['secondary']};
                color: {c['text']};
                border: 1px solid {c['border']};
            }}
            QMessageBox QPushButton[text="Cancel"]:hover, QMessageBox QPushButton[text="No"]:hover {{
                background-color: {c['border']};
            }}
        """)


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
            self.ui.venv_dropdown.clear()
            self.ui.venv_dropdown.addItem("Invalid Project Path")
            self.ui.venv_dropdown.setEnabled(False)
            self.ui.package_action_group.setVisible(False)
            self.ui.package_table.setVisible(False)
            self.ui.env_details_label.setText("Select an environment to see details.")
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
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("Confirm Clear History")
        message_box.setText("Are you sure you want to clear all recent project history?")
        message_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        message_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        self._style_message_box(message_box) # Apply theme
        reply = message_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self.settings.remove("recent_paths")
            self._update_status("Recent project history cleared.", "success")
            self._log_message("Recent project history cleared by user.")
            self._update_path_completer_model() # Update completer after clearing

    def _show_recent_paths_menu(self):
        recent = self.settings.value("recent_paths", [], type=list)
        menu = QMenu(self)
        c = self.current_theme # Define c here

        small_icon_folder = fa.icon('fa5s.folder', color=c['accent'], options=[{'scale_factor': 0.8}])
        small_icon_trash = fa.icon('fa5s.trash-alt', color=c['error'], options=[{'scale_factor': 0.8}])

        if recent:
            for path_str in recent:
                display_path = Path(path_str).as_posix()
                action = QAction(small_icon_folder, display_path, self)
                action.triggered.connect(lambda checked, p=path_str: self.ui.path_input.setText(p))
                menu.addAction(action)
            menu.addSeparator()
        else:
            empty_action = QAction("No recent paths", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)

        clear_action = QAction(small_icon_trash, "Clear Recent History", self)
        clear_action.setEnabled(bool(recent))
        clear_action.triggered.connect(self._clear_recent_paths)
        menu.addAction(clear_action)

        # Apply stylesheet to the context menu using the dialog stylesheet base
        menu.setStyleSheet(self._get_dialog_stylesheet(c) + f"""
            QMenu::item {{
                padding: 6px 15px 6px 25px;
                color: {c['text']};
            }}
            QMenu::item:selected {{
                background-color: {c['accent']};
                color: white;
                border-radius: 3px;
            }}
            QMenu::icon {{
                padding-left: 5px;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {c['border']}60;
                margin: 5px 0px;
            }}
        """)

        # Position the menu below the button
        button_pos = self.ui.recent_paths_btn.mapToGlobal(self.ui.recent_paths_btn.rect().bottomLeft())
        menu.exec(button_pos)

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.ui.path_input.text())
        if path: self.ui.path_input.setText(path)

    def _open_in_explorer(self):
        path = self.ui.path_input.text().strip()
        if os.path.isdir(path):
            try:
                # Using a cross-platform method that should work better
                if sys.platform == "win32":
                    subprocess.Popen(['explorer', path])
                elif sys.platform == "darwin":
                    subprocess.Popen(['open', path])
                else: # Linux
                    subprocess.Popen(['xdg-open', path])
            except Exception as e:
                self._update_status(f"Could not open directory: {e}", "error")
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
        if not env_text or "found" in env_text or "No environments found" in env_text or "Invalid Project Path" in env_text: 
            self._update_status("No valid environment selected for deletion.", "error")
            return
        env_name = env_text.split(' (')[0]
        env_type = self.ui.venv_dropdown.currentData()

        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("Confirm Deletion")
        message_box.setText(f"Are you sure you want to permanently delete the environment '{env_name}'?\n\nThis action cannot be undone.")
        message_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        message_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        self._style_message_box(message_box) # Apply theme
        reply = message_box.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            if env_type == "conda":
                # Conda envs deletion is complex, often requiring explicit `conda env remove -n <name>`
                # This requires a new CommandThread type for `conda_env_remove` or careful command construction.
                # For now, let's log it as unimplemented for clarity.
                self._update_status(f"Conda environment deletion via GUI is not yet implemented. Please use your terminal: `conda env remove -n {env_name}`.", "error")
                self._log_message(f"Attempted to delete Conda environment '{env_name}'. Feature not yet implemented.")
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
        if name and "found" not in name and "No environments found" not in name and "Invalid Project Path" not in name:
            self.ui.package_action_group.setVisible(True)
            self.ui.package_table.setVisible(True)
            # We only start the FIRST command. Its callback will start the next one.
            self._run_command("get_env_details", on_finish=self._update_env_details)
        else:
            self.ui.env_details_label.setText("Select an environment to see details.")
            self.ui.package_action_group.setVisible(False)
            self.ui.package_table.setVisible(False)
        
        # Update button states whenever environment selection changes
        self._set_ui_enabled(True) # This will trigger re-evaluation of specific buttons


    def _update_env_details(self, py_ver):
        name = self.ui.venv_dropdown.currentText().split(' (')[0]
        env_type = self.ui.venv_dropdown.currentData()

        env_path = None
        if env_type == "venv":
            env_path = Path(self.ui.path_input.text().strip()) / name
        # For Conda, we don't have a direct path relative to project root easily,
        # and getting creation time might require `conda env list --json` and parsing.
        # For simplicity, if not a local venv, just show version.

        details_text = f"Python Version: {py_ver.strip()}"
        if env_path and env_path.exists():
            try:
                details_text += f" | Created: {time.strftime('%Y-%m-%d', time.localtime(os.path.getctime(env_path)))}"
            except Exception:
                details_text += " | Creation date unavailable."

        self.ui.env_details_label.setText(details_text)
        
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
            
            for row in range(self.ui.package_table.rowCount()):
                self.ui.package_table.setRowHeight(row, 20)  # Enforce short rows
            
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
            self._update_status("Failed to parse package list. No packages found or pip not installed.", "error")
            self._log_message(f"Error decoding JSON from pip list: {json_output}")
        except Exception as e:
            self._update_status(f"An error occurred while populating package table: {e}", "error")

    def _check_for_package_updates(self):
        """Runs the 'pip list --outdated' command."""
        self._update_status("Checking for outdated packages...", "info")
        self._run_command("pip_outdated", on_finish=self._highlight_outdated_packages)

    def _highlight_outdated_packages(self, json_output):
        """Parses the outdated list and updates the table UI."""
        c = self.current_theme
        try:
            outdated_packages = json.loads(json_output)
            if not outdated_packages:
                self._update_status("All packages are up-to-date.", "success")
                return
                
            outdated_map = {pkg['name']: pkg['latest_version'] for pkg in outdated_packages}
            
            dirty_color = QBrush(QColor(c['git_dirty']).lighter(150)) # Lighter version of dirty color for background

            for row in range(self.ui.package_table.rowCount()):
                name_item = self.ui.package_table.item(row, 0)
                if name_item and name_item.text() in outdated_map:
                    latest_version = outdated_map[name_item.text()]
                    latest_item = self.ui.package_table.item(row, 2)
                    if latest_item: # Check if item exists
                        latest_item.setText(latest_version)
                        latest_item.setForeground(QBrush(QColor(c['git_dirty']))) # Highlight text color
                    
                    # Highlight the entire row for visibility
                    for col in range(3):
                        item = self.ui.package_table.item(row, col)
                        if item: # Ensure item exists before setting background
                            item.setBackground(dirty_color)

            self._update_status(f"Found {len(outdated_packages)} outdated packages.", "info")
        except json.JSONDecodeError:
            self._update_status("Failed to parse outdated package list.", "error")
        except Exception as e:
            self._update_status(f"An error occurred while highlighting outdated packages: {e}", "error")


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
            message_box = QMessageBox()
            message_box.setIcon(QMessageBox.Icon.Question)
            message_box.setWindowTitle("Confirm Uninstall")
            message_box.setText(f"Are you sure you want to uninstall '{package_name}'?")
            message_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            message_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            self._style_message_box(message_box) # Apply theme
            reply = message_box.exec()
            
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
            # Filter out common base packages like pip, setuptools, wheel
            filtered = sorted([f"{p['name']}=={p['version']}" for p in packages if p['name'].lower() not in ['pip', 'setuptools', 'wheel', 'distlib', 'packaging']], key=str.lower)
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
        
        target_path = current_path
        if item and item.text() != "..": # If an actual item is selected (not '..')
             target_path = current_path / item.text()
        
        if not target_path.exists(): return
        
        menu = QMenu()
        c = self.current_theme # Define c here

        open_act = menu.addAction(fa.icon('fa5s.folder-open' if target_path.is_dir() else 'fa5s.file-alt', color=c['text']), "Open")
        copy_act = menu.addAction(fa.icon('fa5s.copy', color=c['text']), "Copy Path")

        menu.addSeparator()

        # New File/Folder actions are relevant to the *current* directory, or the selected directory
        new_file_base = target_path if target_path.is_dir() else current_path
        new_folder_base = target_path if target_path.is_dir() else current_path

        new_file_act = menu.addAction(fa.icon('fa5s.file-medical', color=c['accent']), f"New File in '{new_file_base.name}'")
        new_folder_act = menu.addAction(fa.icon('fa5s.folder-plus', color=c['accent']), f"New Folder in '{new_folder_base.name}'")

        menu.addSeparator()

        run_script_act = None
        if target_path.is_file() and target_path.suffix == '.py':
            run_script_act = menu.addAction(fa.icon('fa5s.play', color=c['success']), "Run Python Script")
        
        open_terminal_target = target_path if target_path.is_dir() else target_path.parent
        open_terminal_act = menu.addAction(fa.icon('fa5s.terminal', color=c['accent']), f"Open Terminal in '{open_terminal_target.name}'")
        
        menu.addSeparator()
        
        # Disable delete for ".." or root path
        del_act = menu.addAction(fa.icon('fa5s.trash', color=c['error']), "Delete")
        if item and item.text() == "..":
            del_act.setEnabled(False) # Cannot delete ".."
        elif target_path == Path(self.ui.path_input.text().strip()): # Cannot delete the root project folder from within its own list
            del_act.setEnabled(False)

        # Apply stylesheet to the context menu using the dialog stylesheet base
        menu.setStyleSheet(self._get_dialog_stylesheet(c) + f"""
            QMenu::item {{
                padding: 6px 15px 6px 25px;
                color: {c['text']};
            }}
            QMenu::item:selected {{
                background-color: {c['accent']};
                color: white;
                border-radius: 3px;
            }}
            QMenu::icon {{
                padding-left: 5px;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {c['border']}60;
                margin: 5px 0px;
            }}
        """)


        action = menu.exec(self.ui.file_list.mapToGlobal(pos))
        
        if action == open_act:
            self._open_file_list_item(item) # Reuse double-click logic
        elif action == copy_act:
            QGuiApplication.clipboard().setText(str(target_path))
            self._update_status("Path copied to clipboard.", "info")
        elif action == new_file_act:
            self._new_file(base_dir=new_file_base)
        elif action == new_folder_act:
            self._new_folder(base_dir=new_folder_base)
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
        
        if path.is_dir():
            self.ui.path_input.setText(str(path)) # Navigate into directory
        else:
            try:
                os.startfile(path) # Works on Windows, MacOS, and some Linux desktops
                self._log_message(f"Opened: {path.name}")
            except Exception as e:
                self._update_status(f"Failed to open file: {e}", "error")

    def _new_file(self, base_dir=None):
        base_dir = base_dir or Path(self.ui.path_input.text().strip())
        if not base_dir.is_dir():
            self._update_status("Invalid directory to create new file.", "error"); return
        
        file_name, ok = QInputDialog.getText(self, "New File", f"Enter new file name in '{base_dir.name}':")
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

        folder_name, ok = QInputDialog.getText(self, "New Folder", f"Enter new folder name in '{base_dir.name}':")
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
            # The base_path for CommandThread should be `str(target_path.parent)`
            # And the tool command would be 'python "<script_name>"'
            # The CommandThread for 'activate' now accepts 'tool' as a command to run after activation.
            self._run_command("activate", tool=f"python \"{target_path.name}\"", new_console=True, base_path=str(target_path.parent))
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
        
        self._run_command("activate", new_console=True, base_path=str(open_dir))

    def _delete_selected_file_or_folder(self, target_path=None):
        if not target_path:
            item = self.ui.file_list.currentItem()
            if not item:
                self._update_status("No item selected for deletion.", "error"); return
            if item.text() == "..": # Prevent deletion of ".."
                self._update_status("Cannot delete parent directory link.", "error"); return

            target_path = Path(self.ui.path_input.text().strip()) / item.text()
        
        if not target_path.exists():
            self._update_status(f"Path '{target_path.name}' does not exist.", "error"); return

        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("Confirm Deletion")
        message_box.setText(f"Are you sure you want to delete '{target_path.name}' permanently?\n\nThis action cannot be undone.")
        message_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        message_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        self._style_message_box(message_box) # Apply theme
        reply = message_box.exec()
        
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
        if not is_path_valid or not current_item or current_item.text() == "..":
            self.ui.run_script_btn.setEnabled(False)
            self.ui.open_terminal_btn.setEnabled(False)
            self.ui.delete_file_btn.setEnabled(False)
            return

        selected_path = Path(self.ui.path_input.text().strip()) / current_item.text()

        self.ui.delete_file_btn.setEnabled(True) # Can delete any selected item (except '..')
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
            # Avoid showing ".." if current_path is the actual file system root (e.g., C:\ on Windows, / on Linux)
            # Or if it's the user's home directory (a common root for projects)
            # Adjusted logic to show ".." unless at the true root or home dir if home is the default starting point.
            if base_path.parent != base_path and base_path != Path.home(): 
                up_item = QListWidgetItem("..")
                up_icon = fa.icon('fa5s.arrow-up', color=c['text_secondary'], options=[{'scale_factor': 0.9}])
                up_item.setIcon(up_icon)
                self.ui.file_list.addItem(up_item)
                up_item.setToolTip("Go up to the parent directory")

            all_items = sorted(base_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())) # Dirs first, then files, case-insensitive

            for p in all_items:
                name = p.name
                item = QListWidgetItem(name)
                
                # Assign icons based on file type
                if p.is_dir():
                    icon_name = 'fa5s.folder'
                elif p.suffix == '.py': # Changed to fa5b.python for brands icon
                    icon_name = 'fa5b.python' 
                elif p.suffix == '.ipynb':
                    icon_name = 'fa5s.book'
                elif p.suffix in ['.txt', '.md', '.json', '.yml', '.yaml', '.toml']:
                    icon_name = 'fa5s.file-alt'
                elif p.suffix in ['.zip', '.tar', '.gz']:
                    icon_name = 'fa5s.file-archive'
                elif p.suffix in ['.png', '.jpg', '.jpeg', '.gif']:
                    icon_name = 'fa5s.image'
                else:
                    icon_name = 'fa5s.file' # Generic file icon

                item.setIcon(fa.icon(icon_name, color=c['text_secondary'], options=[{'scale_factor': 0.9}]))
                item.setToolTip(f"'{name}' (Double-click to open/navigate)")
                self.ui.file_list.addItem(item)
        except PermissionError:
            self._update_status("Permission denied to read directory. Please select another.", "error")
            self.ui.file_list.addItem(QListWidgetItem(f"ERROR: Permission denied for {base_path}"))
        except FileNotFoundError:
            self._update_status("Directory not found. Please select a valid path.", "error")
            self.ui.file_list.addItem(QListWidgetItem(f"ERROR: Directory not found: {base_path}"))
        except Exception as e:
            self._update_status(f"Error populating file list: {e}", "error")
            self.ui.file_list.addItem(QListWidgetItem(f"ERROR: {e}"))
        
        # Reconnect double-click after clearing and repopulating (ensure only one connection)
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
            if parent_dir != current_path: # Ensure we don't go above true root
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
        venvs = [d.name for d in base_path.iterdir() if d.is_dir() and ((d / script_folder / "activate.bat").exists() or (d / script_folder / "activate").exists())]
        for venv in sorted(venvs):
            self.ui.venv_dropdown.addItem(venv, "venv") # Pass type as data
        
        # Find conda envs (asynchronously)
        # It's better to fetch conda envs if conda is installed globally, not necessarily relative to base_path.
        # This command should run from anywhere.
        self._run_command("list_conda_envs", on_finish=self._on_conda_envs_listed, base_path=".")

    def _on_conda_envs_listed(self, output):
        try:
            data = json.loads(output)
            conda_envs = [Path(p).name for p in data.get('envs', [])]
            existing_items = {self.ui.venv_dropdown.itemText(i).split(' (')[0] for i in range(self.ui.venv_dropdown.count())}
            for env in sorted(conda_envs):
                if env and env not in existing_items: # Avoid duplicates if env name matches venv
                    self.ui.venv_dropdown.addItem(f"{env} (conda)", "conda") # Pass type as data
        except json.JSONDecodeError:
            self._log_message("Could not parse conda envs list. Is conda installed and in PATH?")
        except Exception as e:
            self._log_message(f"Error listing conda environments: {e}")
        
        if self.ui.venv_dropdown.count() == 0:
            self.ui.venv_dropdown.addItem("No environments found")
            self.ui.venv_dropdown.setEnabled(False)
        else:
            self.ui.venv_dropdown.setEnabled(True)
            self._on_venv_selection_changed(self.ui.venv_dropdown.currentText()) # Trigger initial update

    # --- pipx Management Methods ---
    def _check_pipx_availability(self, auto_list=True):
        self._run_command("check_pipx", on_finish=lambda out: self._on_pipx_checked(out, auto_list), base_path=".") # base_path can be arbitrary for global tools

    def _on_pipx_checked(self, output, auto_list):
        if "pipx" in output.lower() and "not found" not in output.lower(): # Simple check for pipx version output
            self.ui.pipx_groupbox.setVisible(True)
            self._update_status("pipx is available.", "success")
            if auto_list:
                self._pipx_list() # Automatically list tools if pipx is found
        else:
            self.ui.pipx_groupbox.setVisible(False)
            self._update_status("pipx not found. Install it for global tool management.", "info")
            self._pipx_log_message("pipx command not found. Please install pipx globally (e.g., `pip install pipx`) and ensure it's in your system PATH.")


    def _pipx_log_message(self, message):
        self.ui.pipx_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.ui.pipx_output.verticalScrollBar().setValue(self.ui.pipx_output.verticalScrollBar().maximum())

    def _pipx_list(self):
        self.ui.pipx_output.clear()
        self._pipx_log_message("Fetching pipx installed tools...")
        self._run_command("pipx_list", on_finish=self._display_pipx_list_output, base_path=".")

    def _display_pipx_list_output(self, json_output):
        self.ui.pipx_output.clear()
        self.pipx_data = {}
        try:
            data = json.loads(json_output)
            if data and "venvs" in data:
                count = 0
                for venv_name, venv_info in data["venvs"].items():
                    self.pipx_data[venv_name] = venv_info
                    app_names = venv_info.get('metadata', {}).get('main_package', {}).get('app_paths_by_name', {}).keys()
                    version = venv_info.get('metadata', {}).get('main_package', {}).get('version', 'N/A')
                    apps = ', '.join(app_names) if app_names else "No apps"
                    self._pipx_log_message(f"  • <b>{venv_name}</b> (v{version}) - Apps: {apps}")
                    count += 1
                self._update_status(f"Found {count} pipx tools.", "success")
            else:
                self._pipx_log_message("No pipx tools found.")
                self._update_status("No pipx tools found.", "info")
        except json.JSONDecodeError:
            self._pipx_log_message(f"Failed to parse pipx list output. Raw output: {json_output}")
            self._update_status("Failed to parse pipx list output. See pipx output for details.", "error")
        
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
        
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle("Confirm pipx Uninstall")
        message_box.setText(f"Are you sure you want to uninstall '{package}' using pipx?\n\nThis will remove the tool and its associated virtual environment.")
        message_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        message_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        self._style_message_box(message_box) # Apply theme
        reply = message_box.exec()

        if reply == QMessageBox.StandardButton.Yes:
            self._pipx_log_message(f"Uninstalling {package} with pipx...")
            self._run_command("pipx_uninstall", package=package, on_finish=lambda _: self._pipx_list(), base_path=".")
            self.ui.pipx_package_input.clear()

    def _pipx_ensurepath(self):
        self._pipx_log_message("Running 'pipx ensurepath' to update system PATH...")
        self._run_command("pipx_ensurepath", on_finish=lambda _: self._pipx_log_message("pipx ensurepath completed. Restarting your terminal/shell might be required for changes to take effect."), base_path=".")

    def _update_file_observer(self, path):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None # Reset observer
        
        if os.path.isdir(path):
            self.observer = Observer()
            event_handler = FileChangeHandler()
            event_handler.file_changed.connect(self.discover_resources) # Re-discover on file changes
            self.observer.schedule(event_handler, str(path), recursive=False) # Only watch current dir
            self.observer.start()
            self._log_message(f"Watching '{path.name}' for file changes.")

    def _update_status(self, message, msg_type):
        c = self.current_theme
        colors = {"success": c['success'], "error": c['error'], "info": c['accent']}
        text_color = "white" if msg_type in ["success", "error"] else c['text_secondary'] # White text for high-contrast messages
        bg_color = colors.get(msg_type, 'transparent')

        self.ui.status_label.setText(message)
        self.ui.status_label.setStyleSheet(f"""
            #statusLabel {{
                background-color:{bg_color}; 
                color:{text_color}; 
                border-radius:4px; 
                padding:4px; 
                qproperty-alignment: 'AlignVCenter';
                font-weight: normal;
                border: 1px solid {bg_color}; /* Solid border matching bg */
            }}
        """)
        
        # Fade out status message after 5 seconds if not transparent
        if msg_type in colors and bg_color != 'transparent':
            QTimer.singleShot(5000, lambda: self.ui.status_label.setStyleSheet(f"""
                #statusLabel {{
                    background-color: transparent;
                    color: {c['text_secondary']};
                    border: 1px solid transparent; /* Transparent border */
                }}
            """))

    def _show_status_tip(self):
        """Displays recent log messages and a random 'Did You Know?' tip."""
        log_msgs = "\n".join(self.log_history) if self.log_history else "No recent activity."
        tip = random.choice(self.DID_YOU_KNOW_TIPS)

        message_box = QMessageBox(self)
        message_box.setWindowTitle("Status Information & Tips")
        message_box.setIcon(QMessageBox.Icon.Information)
        message_box.setText("<b>Recent Activity:</b>")
        message_box.setInformativeText(f"<pre style='font-family: {AppConfig.FONT_CODE};'>{log_msgs}</pre><br><b>Did You Know?</b> {tip}")
        message_box.setStandardButtons(QMessageBox.StandardButton.Ok)

        self._style_message_box(message_box) # Apply theme
        message_box.exec()

    def _log_message(self, message):
        self.ui.log_output.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        self.ui.log_output.verticalScrollBar().setValue(self.ui.log_output.verticalScrollBar().maximum())
        self.log_history.append(f"[{time.strftime('%H:%M:%S')}] {message}") # Add to history

    def _set_progress_bar_active(self, active):
        self.ui.progress_bar.setVisible(active)
        self.ui.running_indicator.setVisible(active)
        self.ui.progress_bar.setRange(0, 0 if active else 100) # Indeterminate progress bar when active

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
        event.ignore() # Keep the window open temporarily
        self.fade_out_animation.start() # Start fade out animation

    def _setup_animations(self):
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity", self); self.fade_in_animation.setDuration(400); self.fade_in_animation.setStartValue(0.0); self.fade_in_animation.setEndValue(1.0)
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity", self); self.fade_out_animation.setDuration(300); self.fade_out_animation.setStartValue(1.0); self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.finished.connect(self.close)
    
    def show_with_fade(self):
        self.setWindowOpacity(0.0) # Start fully transparent
        self.show()
        self.fade_in_animation.start()

    def _create_new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec():
            parent_dir, name = dialog.get_details()
            if not parent_dir or not name:
                self._update_status("Parent directory and project name are required.", "error"); return
            
            # Sanitize project name: remove spaces, special chars, make lowercase, replace spaces with hyphens
            safe_name = name.strip().lower().replace(" ", "-")
            safe_name = "".join(c for c in safe_name if c.isalnum() or c == '-')
            if not safe_name:
                self._update_status("Project name is invalid after sanitization. Use alphanumeric characters and hyphens.", "error"); return

            path = Path(parent_dir) / safe_name
            if path.exists():
                self._update_status(f"Project directory '{safe_name}' already exists. Please choose a different name.", "error"); return
            try:
                self._log_message(f"Creating new project at: {path}")
                path.mkdir(parents=True)
                # Create standard subdirectories
                for d in ["data", "notebooks", "scripts", "src", "docs"]: (path / d).mkdir(exist_ok=True)
                # Create a basic .gitignore
                (path / ".gitignore").write_text(
                    "# Environments\n.env\n.venv/\nenv/\n\n# Python cache\n__pycache__/\n*.py[cod]\n\n# IDEs\n.vscode/\n.idea/\n\n# Data\n*.csv\n*.json\n*.parquet\n\n# OS Junk\n.DS_Store\nthumbs.db\n\n# Output\n*.log\n/dist/\n/build/\n"
                )
                # Create a placeholder README.md
                (path / "README.md").write_text(f"# {name}\n\nThis is a new project created with PyEnv Launcher.")
                
                self._update_status(f"Project '{safe_name}' created successfully.", "success")
                self.ui.path_input.setText(str(path)) # Set new project path as current
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
        self.ui.git_status_label.setText(f"<i style='color:{self.current_theme['text_secondary']}'>Checking Git status...</i>")
        self.ui.git_timeline_text_edit.setHtml(f"<i style='color:{self.current_theme['text_secondary']}'>Fetching Git history...</i>")
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
        # Check for pyproject.toml as an indicator for Poetry/PDM projects
        is_build_tool_project = (Path(self.ui.path_input.text().strip()) / "pyproject.toml").exists()
        self.ui.build_tools_groupbox.setVisible(is_build_tool_project)
        # Also adjust visibility of individual buttons if specific tools are detected within pyproject.toml
        # This would require parsing pyproject.toml to check for [tool.poetry] or [tool.pdm] sections.
        # For simplicity, just showing the group if pyproject.toml exists.
        if is_build_tool_project:
            try:
                with open(Path(self.ui.path_input.text().strip()) / "pyproject.toml", 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.ui.poetry_install_btn.setVisible("[tool.poetry]" in content)
                    self.ui.pdm_sync_btn.setVisible("[tool.pdm]" in content)
            except Exception as e:
                self._log_message(f"Error reading pyproject.toml: {e}")
                self.ui.poetry_install_btn.setVisible(False)
                self.ui.pdm_sync_btn.setVisible(False)
        else:
            self.ui.poetry_install_btn.setVisible(False)
            self.ui.pdm_sync_btn.setVisible(False)
    
    # --- Window Movement ---
    # Removed mousePressEvent, mouseMoveEvent, mouseReleaseEvent as system handles moving/resizing

    def _center_on_screen(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        available_width = screen.width()
        available_height = screen.height()
        
        # Dynamically set initial size: 80% of available screen, with mins/maxes
        # init_width = min(max(int(available_width * 0.8), 600), available_width - 100)
        # init_height = min(max(int(available_height * 0.8), 400), available_height - 100)
        self.resize(1000, 970)
        
        # Calculate center
        x = (available_width - self.width()) // 2 + screen.x()
        y = (available_height - self.height()) // 2 + screen.y()
        
        self.move(x, y)

if __name__ == "__main__":
    sys.excepthook = global_exception_hook
    app = QApplication(sys.argv)
    
    # Load custom fonts if available for better control, otherwise rely on system.
    # For 'Inter' font, you might need to install it on your system or provide a .ttf file.
    # For this example, assuming 'Inter' is available or system fallback is acceptable.
    app.setFont(QFont(AppConfig.FONT_MAIN, 9))

    # Initialize QtAwesome (it loads the icon fonts)
    # fa.load_font("fa5s", "fontawesome-webfont.ttf", "fontawesome5_solid.json")
    # This line is usually not needed if qtawesome is installed via pip,
    # as it should handle font loading automatically. If icons don't appear,
    # check if 'fontawesome-webfont.ttf' is accessible in qtawesome's package data.
    
    # Set the application window icon using a QtAwesome icon
    app.setWindowIcon(fa.icon('fa5s.code', color='white')) 

    window = JupyterLauncher()
    window.show_with_fade() # Use the custom fade-in effect
    sys.exit(app.exec())