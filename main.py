import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from media import SpotifyWatcher
from ui import Halo
from wallpaper import get_palette


def make_icon(color):
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 20, 56, 24, 12, 12)
    p.end()
    return QIcon(pm)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # tetap hidup di latar belakang

    watcher = SpotifyWatcher()
    halo = Halo(watcher, get_palette)

    tray = QSystemTrayIcon(make_icon(halo.pal["accent"]), app)
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
