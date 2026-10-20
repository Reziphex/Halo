import ctypes
import os
import sys

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from media import SpotifyWatcher
from ui import Halo
from wallpaper import get_palette


def resource_path(rel):
    """Path resource - bekerja saat dijalankan biasa maupun sebagai .exe (PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def single_instance():
    """Cegah Halo berjalan dua kali. Mengembalikan handle mutex (jangan dibuang)."""
    k32 = ctypes.windll.kernel32
    handle = k32.CreateMutexW(None, False, "Local\\HaloNowPlayingPopup")
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)
    return handle


def main():
    _mutex = single_instance()
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Halo.NowPlaying")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # tetap hidup di latar belakang
    icon = QIcon(resource_path(os.path.join("assets", "halo.png")))
    app.setWindowIcon(icon)

    watcher = SpotifyWatcher()
    halo = Halo(watcher, get_palette)

    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Halo")
    menu = QMenu()
    reset = QAction("Reset posisi ke atas tengah")
    reset.triggered.connect(halo.reset_position)
    quit_ = QAction("Keluar")
    quit_.triggered.connect(app.quit)
    menu.addAction(reset)
    menu.addAction(quit_)
    tray.setContextMenu(menu)
    tray.show()

    watcher.start()  # mulai setelah UI terhubung ke sinyal
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
