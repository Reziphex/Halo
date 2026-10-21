# 🎵 Halo

## 📖 About Halo
Started from curiosity, ended up as a weekend escape! 🎧 This passion project explores how music apps work under the hood. No deadlines—just a playground for wild ideas, clean UI/UX, and coding experiments. Feel free to explore, fork, or drop a ⭐ if you like it. Stay curious! 🎶

## ✨ Why is this Project Interesting?

*   🧪 **100% Curiosity-Driven:** A completely free playground to test wild ideas, experiment with random features, and learn new things without any strict rules.
*   🎨 **Clean & Comfortable UI:** The interface (including experiments with an iconic logo) is designed to be as clean and elegant as possible so it's easy on the eyes.
*   🛠️ **Open Coding Experiment:** A place to witness the trial & error process of building a music player app from scratch using Python.

## 🚀 What's Inside?

*   **UI/UX Concept:** Minimalist music player layout experiments.
*   **Tech Stack:** Python (Core logic, UI, Media Handling, Lyrics), PySide6 (Qt) for the floating UI, Windows SMTC via `winrt` for media detection, Pillow for color extraction, and PyInstaller for packaging.
*   **Status:** Work in progress & constantly evolving.

## 🌟 Features

*   🏝️ **Dynamic Island–style popup** that floats at the top center of your screen, always on top of other windows.
*   ⏱️ **Collapsed mode** shows a round album cover next to the current time; click it to expand.
*   🎧 **Works with Spotify and YouTube** (YouTube / YouTube Music playing in Chrome, Edge, Brave, Opera, Vivaldi, or Firefox).
*   🖼️ **Album cover + ambient colors** extracted from the cover art (falls back to your wallpaper colors).
*   ⏯️ **Playback controls** (previous, play/pause, next) and a **draggable progress bar** to seek through the song.
*   📝 **Synced lyrics** shown line by line, with the current line highlighted.
*   🪟 **Translucent, draggable, lightweight** — stays out of your way.
*   🖥️ **Runs like real desktop software**: build a `Halo.exe` with your own icon, a Desktop shortcut, and optional auto-start with Windows.

## 📋 Requirements

*   **Windows 10 or 11** (media detection uses Windows System Media Transport Controls).
*   **Python 3.12** (recommended — the `winrt` packages ship ready-made wheels for it). Download it from [python.org](https://www.python.org/downloads/windows/) and tick **"Add python.exe to PATH"** during installation.
*   The **Spotify desktop app** and/or a supported browser for YouTube.
*   Internet connection (only needed for lyrics).

## 🧭 How to Use

### 1. Get the project

```powershell
git clone https://github.com/<your-username>/Halo.git
cd Halo
```

Or click **Code → Download ZIP** on GitHub and extract it (for example to `C:\Halo`).

> ⚠️ Keep the folder named `assets` (all lowercase). It holds the app icon and fonts.

### 2. Choose how to run it

#### Option A — Install as a desktop app (recommended)

Double-click **`build.bat`**. It will:

1.  Create a Python 3.12 virtual environment and install the dependencies.
2.  Build **`Halo.exe`** with your icon using PyInstaller (this can take a few minutes).
3.  Copy it to `%LOCALAPPDATA%\Halo` and create a **Halo shortcut on your Desktop**.
4.  Ask if you want Halo to **start automatically with Windows**.

When it's done, double-click the **Halo** shortcut on your Desktop. In Task Manager it shows up as **Halo** with its own icon.

> If you see **"MODE CADANGAN"** at the end, the `.exe` could not be built and Halo falls back to running through Python (it will appear as "Python" in Task Manager). Open `build.log` to see why — see [Troubleshooting](#-troubleshooting).

#### Option B — Run from source

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Use `pythonw main.py` to run it without a console window.

### 3. Play some music

Start playing a song in **Spotify**, or play a video/song on **YouTube** in your browser. The Halo popup appears at the top center of your screen, expands for a few seconds, then collapses into a small pill showing the cover and the clock.

### 4. Controls

| Action | How |
| --- | --- |
| Expand the popup | Click the collapsed pill |
| Collapse the popup | Click the **⌃** button |
| Previous / Play-Pause / Next | Use the buttons in the expanded popup |
| Seek to another time | Click or drag the progress bar |
| Show or hide lyrics | Click the lyrics button (≡) |
| Move the popup | Drag it anywhere on the screen |
| Reset position | Right-click the popup (or the tray icon) → **Reset posisi ke atas tengah** |

### 5. Quit Halo

Any of these works:

*   **Right-click the popup → "Keluar dari Halo".**
*   **Right-click the Halo tray icon** (look under the **^** arrow near the clock) → **Keluar**.
*   Double-click **`stop_halo.bat`**.
*   Open **Task Manager** (`Ctrl+Shift+Esc`), find **Halo**, and choose **End task**.

### 6. Handy tips

*   🎨 **Colors follow the album cover**, so the popup looks different with every song.
*   📝 **Lyrics** are not available for every song, especially remixes and covers.
*   📺 **Other videos** in your browser (Netflix, Twitch, and so on) can also trigger the popup, because Windows doesn't say which website is playing. Remove the browsers you don't use from `SOURCES` in `media.py` if that bothers you.

## ⚙️ Customization

| What | Where |
| --- | --- |
| Popup transparency | `OPACITY` at the top of `ui.py` (`1.0` = solid, `0.5` = very transparent) |
| Which apps are monitored | `SOURCES` at the top of `media.py` (remove browsers you don't use) |
| Auto-collapse delay | `AUTO_COLLAPSE_MS` in `ui.py` |
| Fonts | Drop `.otf` / `.ttf` files in `assets/fonts` and adjust `make_font()` in `ui.py` |

## 🗂️ Project Structure

```
Halo/
├── assets/
│   ├── halo.ico            # App / shortcut icon
│   ├── halo.png            # Tray and window icon
│   └── fonts/              # Inter font files + license
├── main.py                 # Entry point, tray icon, single-instance guard
├── ui.py                   # Popup UI: clock, cover, controls, seek bar, lyrics
├── media.py                # Reads Spotify / browser playback via Windows SMTC
├── lyrics.py               # Lyrics lookup (LRCLIB) and LRC parsing
├── wallpaper.py            # Color palette from cover art or wallpaper
├── build.bat               # One-click build + Desktop shortcut
├── make_shortcut.ps1       # Creates Desktop / Startup shortcuts
├── stop_halo.bat           # Stops Halo no matter how it was started
├── version_info.txt        # Windows version info (name shown in Task Manager)
└── requirements.txt
```

## 🛟 Troubleshooting

*   **`Python was not found` / `pip is not recognized`** — Install Python 3.12 and tick *Add python.exe to PATH*, then open a **new** PowerShell window.
*   **`Microsoft Visual C++ 14.0 or greater is required`** — You are probably on a very new Python version without ready-made `winrt` wheels. Use **Python 3.12**: `py -3.12 -m venv .venv`.
*   **Build fails with `Unable to find '...\assets'`** — The folder must be named exactly `assets` and contain `halo.ico`, `halo.png`, and `fonts/`.
*   **Build fails for another reason** — Run `Get-Content build.log -Tail 40` and open an issue with the output.
*   **Task Manager shows "Python" instead of "Halo"** — Halo is running in fallback mode. Fix the build error above so `Halo.exe` can be created.
*   **Shortcut icon looks blank** — Re-run `build.bat`, or run `ie4uinit.exe -show` to refresh the Windows icon cache.
*   **The popup doesn't appear** — Make sure the song is actually playing, and that the app is in the `SOURCES` list in `media.py`.
*   **Lyrics not found** — Lyrics come from the community database [LRCLIB](https://lrclib.net), so not every song is available. Remixes and covers are the most likely to be missing.
*   **Seeking does nothing** — Some players don't allow seeking through Windows media controls.
*   **Windows SmartScreen warning** — Normal for a self-built, unsigned `.exe`. Choose *More info → Run anyway*.

## 🤝 Let's Drop By & Contribute

If you happen to stumble upon this repo:
*   Want to fork it and tweak it yourself? **Go ahead!**
*   Have a crazy feature idea to add? **Submit a Pull Request!**
*   Just want to browse the codebase? **Take your time.**

## 🙏 Credits

*   Typeface: [Inter](https://github.com/rsms/inter) by Rasmus Andersson, licensed under the SIL Open Font License (see `assets/fonts/Inter-LICENSE.txt`).
*   Lyrics: [LRCLIB](https://lrclib.net) — a free, community-driven lyrics API.
*   Built with [PySide6](https://doc.qt.io/qtforpython-6/), [Pillow](https://python-pillow.org/), and the [`winrt`](https://github.com/pywinrt/pywinrt) Python projection.
