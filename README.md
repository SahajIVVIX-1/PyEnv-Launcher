<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/PyQt6-v6.x-green?style=for-the-badge&logo=qt" alt="PyQt6 Version">
  <img src="https://img.shields.io/badge/pyenv-managed-orange?style=for-the-badge&logo=conda-forge" alt="PyEnv Managed">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey?style=for-the-badge" alt="License">
</p>

<h1 align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg" width="40" height="40" alt="PyEnv Manager Icon">
  PyEnv Manager
</h1>

<p align="center">
  A sleek, modern, and powerful PyQt6 GUI for effortless PyEnv environment management.
  Launch scripts, Jupyter notebooks, or interactive shells with ease, all from one intuitive interface.
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#development">Development</a> •
  <a href="#contributing">Contributing</a> •
  <a href="#license">License</a>
</p>

---

## ✨ Features

PyEnv Manager is designed to simplify your Python development workflow, offering a comprehensive set of tools wrapped in a user-friendly GUI.

-   **🚀 Environment Management:**
    -   List all installed PyEnv environments with their versions, status (active/inactive), and installation paths.
    -   Create new Python environments for specific versions.
    -   Delete existing environments cleanly.
    -   Auto-detects `PYENV_ROOT` for seamless integration.

-   **📦 Package Management:**
    -   View all installed packages within a selected PyEnv environment.
    -   Install new packages directly into the active environment.
    -   Uninstall packages with a single click.
    -   Refresh package lists to see the latest changes.

-   **▶️ Flexible Launch Modes:**
    -   **Interactive Shell:** Launch an activated shell for the selected Python environment.
    -   **Run Python Script:** Execute any `.py` script with arguments in the chosen environment.
    -   **Jupyter Notebook:** Instantly start a Jupyter Notebook server for data science and interactive computing.

-   **⚙️ Advanced Options:**
    -   Specify a custom **Working Directory** for your launched processes.
    -   Pass **Command-line Arguments** to scripts or Jupyter.
    -   Real-time **Command Logging** to track all operations and outputs.

-   **🎨 Dynamic Theming:**
    -   Toggle between beautiful **Dark** and **Light** themes to suit your preference.
    -   Modern, responsive UI with crisp icons.

-   **👁️ User Experience:**
    -   Intuitive drag-and-drop resizing of panels.
    -   Progress indicators for long-running operations.
    -   Clear and concise error/success messages.
    -   Smooth fade-in animation on application launch.

---

## 🛠️ Installation

### Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python 3.8+**: Download from [python.org](https://www.python.org/downloads/).
2.  **PyEnv**: Follow the official installation guide on [pyenv's GitHub](https://github.com/pyenv/pyenv#installation).
    -   Make sure `pyenv init` is properly configured in your shell's startup files (`.bashrc`, `.zshrc`, etc.).
3.  **Git**: For cloning this repository.

### Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/pyenv-manager.git
    cd pyenv-manager
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install PyQt6 qtawesome
    ```
    (These are the core dependencies for the GUI and icons.)

4.  **Run the Application:**
    ```bash
    python main.py
    ```

---

## 🚀 Usage

1.  **Set PyEnv Root (if not auto-detected):**
    -   The application attempts to auto-detect your `PYENV_ROOT` (typically `~/.pyenv`).
    -   If the path shown is incorrect, you can manually update it in the "PyEnv Root" section on the left panel, or navigate to `File > Settings` from the menu bar to adjust it.

2.  **Manage Environments (Environments Tab):**
    -   Upon launching, the "Environments" tab will display a list of your installed Python versions. If it's empty or outdated, click the "Refresh" button.
    -   To interact with an environment (e.g., manage its packages or launch processes), select it from the table.
    -   To install a new Python version, click "Create" and enter the desired version (e.g., `3.10.0`).
    -   To remove an existing environment, select it and click "Delete". A confirmation dialog will appear.

3.  **Manage Packages (Packages Tab):**
    -   First, ensure you have an environment selected in the "Environments" tab.
    -   Switch to the "Packages" tab and click "Refresh Packages" to view all `pip`-installed packages for the currently selected environment.
    -   To install a new package, click "Install" and enter the package name (e.g., `numpy`, `requests`).
    -   To uninstall a package, select it from the table and click "Uninstall". A confirmation will be requested.

4.  **Launch Operations:**
    -   **Select Launch Mode:** Use the "Launch Mode" dropdown to choose your desired operation:
        -   **Shell:** Opens a new command-line interface with the selected PyEnv environment activated.
        -   **Run Script:** Executes a specified Python script (`.py` file) using the chosen environment.
        -   **Jupyter Notebook:** Starts a Jupyter Notebook server, accessible in your web browser, tied to the selected environment.
    -   **Working Directory:** It's good practice to set a working directory, especially for scripts or Jupyter notebooks. Use the "Browse" button to select one.
    -   **Script Path (for Run Script mode):** If "Run Script" mode is chosen, a new input field appears. Use its "Browse" button to locate and select your Python script.
    -   **Arguments:** Enter any command-line arguments needed for your script or Jupyter launch (e.g., `--port 8889` for Jupyter, or arguments for your Python script).
    -   Click the "Launch" button to initiate the selected process.
    -   If a process is running, the "Stop" button will become active, allowing you to terminate it. A progress bar will also indicate ongoing activity.

5.  **Monitor Activity (Log Tab):**
    -   The "Log" tab provides a detailed output of all commands executed by the application, including their standard output and any errors. This is invaluable for debugging and understanding what the application is doing behind the scenes.

6.  **Settings:**
    -   Click the gear icon (⚙️) in the top-right header or go to `Edit > Settings` in the menu bar.
    -   Here you can switch between the application's "Dark" and "Light" themes.
    -   You can also manually override the "PyEnv Root Path" if the auto-detection is not suitable for your setup.

---

## 🧑‍💻 Development

### Project Structure

The entire application is self-contained within `main.py` for simplicity.

-   **`main.py`**: Contains all classes and logic for the `PyEnvManager` application, including UI management (`UIManager`), dialogs (`AboutDialog`, `SettingsDialog`), and core PyEnv interaction logic.
-   **`AppConfig`**: A static class for managing global application constants like fonts and theme definitions.

### Key Technologies Used

-   **PyQt6**: The robust framework used for constructing the entire graphical user interface.
-   **qtawesome**: Provides a vast library of scalable vector icons (Font Awesome, Material Design) for a professional look and feel.
-   **`subprocess` module**: Employed for direct command-line interaction with `pyenv`, `python`, and `pip` utilities.
-   **`QProcess`**: Utilized for asynchronous execution of external commands, allowing the UI to remain responsive while operations run in the background, and for capturing their real-time output.

### How to Run in Development Mode

To run the application directly from the source code:

1.  Ensure you have followed the "Installation" steps and activated your virtual environment.
2.  Execute the main script:
    ```bash
    python main.py
    ```
    Note that for changes to the Python code to take effect, the application must be restarted.

---

## 🤝 Contributing

We welcome contributions to make PyEnv Manager even better! If you have suggestions, encounter bugs, or wish to implement new features, please consider the following:

1.  **Fork** the repository to your GitHub account.
2.  **Create a new branch** for your feature or bugfix (e.g., `git checkout -b feature/add-new-mode` or `bugfix/resolve-package-issue`).
3.  **Implement your changes**, ensuring they align with the existing code style.
4.  **Commit your changes** with a clear and descriptive message (e.g., `git commit -m 'feat: Implemented new XYZ launch mode'`).
5.  **Push your branch** to your forked repository.
6.  **Open a Pull Request** to the original repository's `main` branch, detailing your changes.

---

## 📄 License

This project is open-source and distributed under the **MIT License**. For full details, please refer to the [LICENSE](LICENSE) file in the repository.

---
