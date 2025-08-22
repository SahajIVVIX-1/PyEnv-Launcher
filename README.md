# UniShare: Seamless Cross-Platform File Transfer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Platform Support](https://img.shields.io/badge/Platforms-Windows%7CMacOS%7CLinux%7CAndroid%7CiOS-blue.svg?style=flat-square)](https://github.com/SahajIVVIX-1/UniShare)

UniShare is an open-source, cross-platform application designed for fast, secure, and seamless file sharing between devices on a local network. Inspired by applications like LocalSend, UniShare aims to provide a user-friendly experience for transferring files, text, and other data without requiring an internet connection or external servers. It's built with Flutter and Dart, ensuring compatibility across a wide range of operating systems including Windows, macOS, Linux, Android, and iOS.

---

## ✨ Key Features

*   **Cross-Platform Compatibility:** Works natively on Windows, macOS, Linux, Android, and iOS.
*   **Local Network Transfer:** No internet connection or external servers needed. All transfers happen directly on your local network.
*   **Fast & Efficient:** Optimized for quick file transfers, handling large files with ease.
*   **Secure:** Implements end-to-end encryption (e.g., HTTPS) for all data transfers, ensuring your data is private.
*   **Device Discovery:** Automatically discovers nearby devices running UniShare using mDNS (Multicast DNS).
*   **File & Folder Sharing:** Send any type of file or entire folders with a simple drag-and-drop or selection.
*   **Text Sharing:** Easily share text snippets directly to the clipboard on the receiving device.
*   **Customizable Device Names:** Personalize your device's name for easy identification among other devices.
*   **Intuitive User Interface:** A clean, modern, and user-friendly interface designed for ease of use.
*   **(Optional) Transfer History:** Keep track of your past file transfers.
*   **(Optional) QR Code Sharing:** Generate QR codes for easy manual connection.

---

## 🚀 Getting Started

To get UniShare up and running on your local machine:

### Prerequisites

*   **Flutter SDK:** Ensure you have the Flutter SDK installed. If not, follow the official installation guide: [https://docs.flutter.dev/get-started/install](https://docs.flutter.dev/get-started/install)
*   **Git:** You'll need Git for cloning the repository. Download it from [https://git-scm.com/downloads](https://git-scm.com/downloads).
*   **(Optional) Desktop Build Tools:** For building desktop applications, ensure you have the necessary build tools for your operating system (e.g., Visual Studio with C++ workload for Windows, Xcode for macOS).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/SahajIVVIX-1/UniShare.git
    cd UniShare
    ```
    *(Note: I've used your provided repository link here. If you change the repository name or your username, update this command accordingly.)*

2.  **Install Flutter dependencies:**
    Open your terminal in the `UniShare` directory and run:
    ```bash
    flutter pub get
    ```

3.  **Run the application:**
    Connect a physical device or start an emulator/simulator, then run:
    ```bash
    flutter run
    ```

---

## 🤝 Contributing

We welcome contributions to UniShare! If you'd like to contribute, please follow these steps:

1.  **Fork the repository:** Click the "Fork" button on the top right of the GitHub page.
2.  **Clone your fork:**
    ```bash
    git clone https://github.com/SahajIVVIX-1/UniShare.git
    cd UniShare
    ```
    *(Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username.)*
3.  **Create a new branch:**
    ```bash
    git checkout -b feature/YourFeatureName
    ```
    *(Replace `YourFeatureName` with a descriptive name for your contribution.)*
4.  **Make your changes:** Add new features, fix bugs, or improve documentation.
5.  **Commit your changes:**
    ```bash
    git add .
    git commit -m "feat: Add YourFeatureName"
    ```
    *(Use conventional commit messages for clarity.)*
6.  **Push to your branch:**
    ```bash
    git push origin feature/YourFeatureName
    ```
7.  **Open a Pull Request:** Go to the original repository (`https://github.com/SahajIVVIX-1/UniShare`) and open a Pull Request from your branch.

Please ensure your code adheres to the project's coding standards and includes tests where appropriate.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
*(Note: You will need to create a `LICENSE.md` file in your repository with the MIT license text or choose another license.)*

---
