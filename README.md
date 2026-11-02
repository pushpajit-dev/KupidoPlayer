# Kupido Player 4.5 🎬✨

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-007ACC?style=flat)](https://github.com/TomSchimansky/CustomTkinter)
[![VLC](https://img.shields.io/badge/Engine-libVLC-FF8800?style=flat&logo=vlc&logoColor=white)](https://www.videolan.org/vlc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Version-4.5.0-success.svg)]()

> A sleek, high-performance multimedia player and offline AI transcription studio crafted with Python, CustomTkinter, and libVLC. Designed with a modern dark navy and electric blue aesthetic, zero-terminal silent execution, and rich playback intelligence.

---

## 🌟 Key Features

### 🎥 High-Fidelity Multimedia Engine
* **VLC & PyTorch Powered:** Native sub-second hardware-accelerated playback for MP4, MKV, WebM, MP3, WAV, and live internet streams.
* **YouTube & Streaming Support:** Instant streaming extraction powered by `yt-dlp` with dynamic quality switching (1080p, 720p, 480p, Audio Only).
* **Direct Local File Play:** Drag, drop, or open any local video/audio without external network requirements.

### 🪟 Picture-in-Picture Mini Player
* **Draggable & Frameless:** Minimalist floating PiP window with smooth titlebar dragging.
* **Complete Controls:** Symmetrical 10-second skip forward/backward, play/pause, loop, mute/unmute, and volume slider.
* **Right-Click Context Menu:** Compact context menu with Copy URL, Paste, Cut, and Main Window triggers.
* **Independent Playback Tracking:** Track time and seek progress completely independently from the main player window.

### 🎚️ Interactive Scrubbing Progress Bars
* **Smooth Drag-and-Seek:** Custom interactive canvas progress bar supporting single-click jumps and smooth mouse drag scrubbing.
* **Pinpoint Time Synchronization:** Real-time elapsed and total duration indicators with zero lag.
* **Automatic Progress Reset:** Seamlessly resets progress and timestamps to `0:00` upon loading new tracks or URLs.

### 🎙️ Offline AI Transcription & Intelligence
* **OpenAI Whisper Integration:** Dynamic on-demand loading of Whisper (`tiny`, `base`, `small`, `medium`) with local weight caching.
* **Hugging Face Model Manager:** One-click model downloader with progress tracking dialog and custom weight folder persistence.
* **Subtitle Multi-Format Export:** Export transcribed speech to `.srt`, `.vtt`, `.txt`, and `.json`.
* **Subtitle Player Injection:** Load generated SRT subtitles directly onto the active video stream with a single click.

### 📥 Bulk Downloader & Offline Cache
* **Single & Bulk Downloads:** Queue multiple video/audio URLs simultaneously with real-time download speed and ETA.
* **Smart Explorer Integration:** One-click "Open Folder" button to immediately reveal downloaded files in Windows File Explorer.
* **Offline Library:** Offline video manager with metadata badges (format, size, upload date, views, likes).

### 📑 Playlist Studio
* **Named Playlists & Group Tags:** Organize tracks into custom collections (e.g. `[ MUSIC ]`, `[ FAVORITES ]`, `[ LECTURES ]`).
* **Offline JSON Storage:** Export and import playlist collections with full metadata preservation.
* **Group Filtering:** Filter displayed items dynamically by group categories.

---

## ⌨️ Keyboard Shortcuts Reference

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| <kbd>Space</kbd> | Play / Pause | Toggle media playback |
| <kbd>F</kbd> / Double Click | Fullscreen | Toggle fullscreen mode |
| <kbd>M</kbd> | Mute / Unmute | Toggle audio mute |
| <kbd>L</kbd> | Loop | Toggle single-track repeat |
| <kbd>←</kbd> / <kbd>→</kbd> | Seek ±10s | Skip backward or forward by 10 seconds |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Volume ±5% | Increase or decrease audio volume |
| <kbd>P</kbd> | Mini Player | Toggle floating Picture-in-Picture window |
| <kbd>Ctrl</kbd> + <kbd>O</kbd> | Open File | Open local media file dialog |
| <kbd>Ctrl</kbd> + <kbd>D</kbd> | Downloader | Open single/bulk download dialog |
| <kbd>Ctrl</kbd> + <kbd>T</kbd> | Transcriber | Switch to AI Transcription Studio tab |
| <kbd>Esc</kbd> | Exit | Exit fullscreen or dismiss floating overlays |

---

## 🚀 Installation & Quick Start

### Option 1: Windows Installer (Recommended)
Download and run `Kupido_Player_4.5_Setup.exe` from the [Releases](https://github.com/kupido-player/releases) tab.
* Complete license agreement page and destination folder selector.
* Creates Desktop and Start Menu shortcuts.
* Automatically verifies Python environment and dependencies silently.
* Launches with zero terminal flash.

### Option 2: Portable Silent Launch
If running directly from source on Windows:
```cmd
# Double click to launch with NO console window:
run_kupido_silent.vbs
```

### Option 3: Manual Developer Setup
```bash
# Clone repository
git clone https://github.com/kupido-player/kupido.git
cd kupido

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install required dependencies
pip install -r requirements.txt

# Run application
python kupido_player.py
```

---

## 🛠️ Building Installers & Standalone Executables

### Compiling Inno Setup 6 Installer
```cmd
iscc installer\setup.iss
```
The resulting installer is generated at `installer\output\Kupido_Player_4.5_Setup.exe`.

### Compiling NSIS Installer
```cmd
makensis installer\setup.nsi
```
The resulting installer is generated at `installer\output\Kupido_Player_4.5_NSIS_Setup.exe`.

### Automated One-Click Build
Run the included pipeline script:
```cmd
build_exe.bat
```

---

## 📂 Project Architecture

```
kupido/
├── kupido_player.py         # Main application architecture & UI
├── requirements.txt         # Core dependencies
├── kupido.ico               # Multi-resolution brand icon (16x16 to 256x256)
├── run_kupido_silent.vbs    # Zero-console Windows launcher
├── launch_kupido.bat        # Windows diagnostics console launcher
├── build_exe.bat            # Automated PyInstaller & Inno build script
├── LICENSE                  # MIT License
├── README.md                # Documentation
├── assets/                  # High-DPI SVG icons & pre-rendered PNGs
│   ├── play.svg
│   ├── pause.svg
│   ├── forward.svg
│   ├── backward.svg
│   ├── volume-up.svg
│   ├── volume-down.svg
│   ├── loop.svg
│   ├── folder.svg
│   ├── download.svg
│   ├── copy.svg
│   ├── full screen.svg
│   ├── float player.svg
│   └── transcription icon.svg
└── installer/
    ├── setup.iss            # Inno Setup 6 configuration
    ├── setup.nsi            # Nullsoft NSIS configuration
    ├── kupido.ico           # Installer branding icon
    └── LICENSE.txt          # Installer agreement text
```

---

## 📜 License
This project is open-source and licensed under the [MIT License](LICENSE).
Copyright (c) 2026 Kupido Media Lab & Contributors.
