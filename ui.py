"""Pop-up ala Dynamic Island: jam + cover, progres yang bisa digeser, dan lirik."""
import html
import time
from bisect import bisect_right
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter,
                           QFontDatabase, QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMenu,
                               QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from lyrics import LyricsFetcher
from wallpaper import palette_from_bytes

OPACITY = 0.72          # 0.0 = tembus total, 1.0 = solid. Ubah sesuai selera.
COL = QSize(124, 40)    # collapsed: cover + jam
EXP = QSize(460, 108)   # expanded: cover, judul, kontrol, progres
LYR = QSize(460, 270)   # expanded + lirik
SIZES = {"col": COL, "exp": EXP, "lyr": LYR}
COVER, COVER_SMALL = 64, 28
TEXT_W = 170
AUTO_COLLAPSE_MS = 6000


# Font ala Apple Music: Inter (open source, paling mirip SF Pro) dimuat dari assets/fonts.
# Jika gagal dimuat, dipakai SF Pro / Segoe UI Variable / Segoe UI.
FALLBACK_FAMILIES = ["SF Pro Display", "Segoe UI Variable Display", "Segoe UI"]
WEIGHTS = {"regular": (400, QFont.Normal), "semibold": (600, QFont.DemiBold),
           "bold": (700, QFont.Bold)}
_FAMILIES = []


def load_fonts(folder):
    import glob
    import os
    for path in sorted(glob.glob(os.path.join(folder, "*.[ot]tf"))):
        fid = QFontDatabase.addApplicationFont(path)
        if fid >= 0:
            for fam in QFontDatabase.applicationFontFamilies(fid):
                if fam not in _FAMILIES:
                    _FAMILIES.append(fam)


def make_font(role, size):
    want, qt_weight = WEIGHTS[role]
    best = None
    for fam in _FAMILIES:
        for st in QFontDatabase.styles(fam):
            key = (abs(QFontDatabase.weight(fam, st) - want), len(fam))
            if best is None or key < best[0]:
                best = (key, fam, st)
    if best:
        return QFontDatabase.font(best[1], best[2], size)
    f = QFont()
    f.setFamilies(FALLBACK_FAMILIES)
    f.setPointSize(size)
    f.setWeight(qt_weight)
    return f


def mix(a, b, t):
    ca, cb = QColor(a), QColor(b)
    return QColor(int(ca.red() * (1 - t) + cb.red() * t),
                  int(ca.green() * (1 - t) + cb.green() * t),
                  int(ca.blue() * (1 - t) + cb.blue() * t)).name()


def fmt(sec):
    m, s = divmod(int(max(sec, 0)), 60)
    return f"{m}:{s:02d}"


def round_pixmap(src, size, radius):
    s = size * 2  # render 2x agar tajam di layar HiDPI
    pm = src.scaled(s, s, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    out = QPixmap(s, s)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(0, 0, s, s, radius * 2, radius * 2)
    p.setClipPath(path)
    p.drawPixmap((s - pm.width()) // 2, (s - pm.height()) // 2, pm)
    p.end()
    out.setDevicePixelRatio(2)
    return out


class SeekBar(QWidget):
    """Bar progres yang bisa diklik/digeser untuk pindah menit lagu."""
    moved = Signal(float)      # rasio 0..1 selama digeser
    scrubbed = Signal(float)   # rasio 0..1 saat dilepas

    def __init__(self):
        super().__init__()
        self.setFixedHeight(16)
        self.setCursor(Qt.PointingHandCursor)
        self.ratio, self.dragging, self.hover = 0.0, False, False
        self.fill = QColor("#ffffff")

    def set_ratio(self, r):
        if not self.dragging:
            self.ratio = min(max(r, 0.0), 1.0)
            self.update()

    def _at(self, x):
        return min(max((x - 6) / max(self.width() - 12, 1), 0.0), 1.0)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.ratio = self._at(e.position().x())
            self.moved.emit(self.ratio)
            self.update()

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.ratio = self._at(e.position().x())
            self.moved.emit(self.ratio)
            self.update()

    def mouseReleaseEvent(self, e):
        if self.dragging and e.button() == Qt.LeftButton:
            self.dragging = False
            self.scrubbed.emit(self.ratio)
            self.update()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, cy = self.width() - 12, self.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 55))
        p.drawRoundedRect(QRectF(6, cy - 2, w, 4), 2, 2)
        fw = w * self.ratio
        p.setBrush(self.fill)
        p.drawRoundedRect(QRectF(6, cy - 2, fw, 4), 2, 2)
        if self.hover or self.dragging:
            p.drawEllipse(QPointF(6 + fw, cy), 6, 6)


class IconButton(QPushButton):
    """Tombol dengan ikon vektor (tajam di semua DPI), pengganti glyph font."""

    def __init__(self, kind, tip, size, fn):
        super().__init__()
        self.kind, self.active, self._hover = kind, False, False
        self.filled = kind in ("play", "pause")
        self.fg, self.accent, self.dark = QColor("#ffffff"), QColor("#ffffff"), QColor("#111111")
        self.setToolTip(tip)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.clicked.connect(fn)

    def set_kind(self, kind):
        self.kind, self.filled = kind, kind in ("play", "pause")
        self.update()

    def set_active(self, on):
        self.active = on
        self.update()

    def set_colors(self, fg, accent, dark):
        self.fg, self.accent, self.dark = fg, accent, dark
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        k, cx, cy = w / 30.0, w / 2.0, h / 2.0
        p.setPen(Qt.NoPen)
        if self.filled:  # tombol utama: lingkaran terang, ikon gelap
            bg = QColor(self.fg)
            bg.setAlpha(255 if self._hover else 238)
            p.setBrush(bg)
            p.drawEllipse(QRectF(0.5, 0.5, w - 1, h - 1))
            col = self.dark
        else:
            if self._hover or self.active:
                bg = QColor(self.accent) if self.active else QColor(255, 255, 255)
                bg.setAlpha(46 if self.active else 38)
                p.setBrush(bg)
                p.drawEllipse(QRectF(1, 1, w - 2, h - 2))
            col = self.accent if self.active else self.fg

        kd, path, solid = self.kind, QPainterPath(), True
        if kd in ("prev", "next"):
            d = -1 if kd == "prev" else 1
            path.moveTo(cx - d * 5.5 * k, cy - 5.2 * k)
            path.lineTo(cx - d * 5.5 * k, cy + 5.2 * k)
            path.lineTo(cx + d * 3.5 * k, cy)
            path.closeSubpath()
            path.addRoundedRect(QRectF(cx + d * 6 * k - 1.0 * k, cy - 5.2 * k, 2.0 * k, 10.4 * k),
                                1.0 * k, 1.0 * k)
            width = 1.6 * k
        elif kd == "play":
            path.moveTo(cx - 3.8 * k, cy - 6.5 * k)
            path.lineTo(cx - 3.8 * k, cy + 6.5 * k)
            path.lineTo(cx + 6.6 * k, cy)
            path.closeSubpath()
            width = 1.4 * k
        elif kd == "pause":
            path.addRoundedRect(QRectF(cx - 5.4 * k, cy - 5.8 * k, 3.4 * k, 11.6 * k), 1.2 * k, 1.2 * k)
            path.addRoundedRect(QRectF(cx + 2.0 * k, cy - 5.8 * k, 3.4 * k, 11.6 * k), 1.2 * k, 1.2 * k)
            width = 1.0 * k
        elif kd == "lyrics":  # tiga baris teks
            solid = False
            for y, x1 in ((-5, 7), (0, 2), (5, 5)):
                path.moveTo(cx - 7 * k, cy + y * k)
                path.lineTo(cx + x1 * k, cy + y * k)
            width = 1.8 * k
        else:  # close: chevron ke atas
            solid = False
            path.moveTo(cx - 5 * k, cy + 2.5 * k)
            path.lineTo(cx, cy - 2.5 * k)
            path.lineTo(cx + 5 * k, cy + 2.5 * k)
            width = 1.8 * k
        p.setPen(QPen(col, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(col if solid else Qt.NoBrush)
        p.drawPath(path)


class Halo(QWidget):
    def __init__(self, watcher, get_palette):
        super().__init__()
        self.watcher, self.get_palette = watcher, get_palette
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.mode = "col"
        self.playing = False
        self._track, self._was_playing = None, False
        self._press = self._origin = None
        self._moved = False
        self._cover_pm, self._cover_pal = None, None
        self._dur, self._anchor = 0.0, (0.0, time.monotonic())
        self._seek_hold = 0.0
        self._ly, self._ly_times, self._plain = [], [], None
        self._ly_state, self._ly_key, self._ly_last = "loading", None, None
        self.pal = get_palette()

        self.lyr_fetch = LyricsFetcher()
        self.lyr_fetch.ready.connect(self.on_lyrics)

        self._build()
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self._anim.finished.connect(self._on_anim_done)

        self._auto = QTimer(self, singleShot=True)
        self._auto.timeout.connect(self._auto_collapse)
        self._clock = QTimer(self, timeout=self._tick)
        self._clock.start(1000)
        self._prog = QTimer(self, timeout=self._progress)
        self._prog.start(250)
        self._wp = QTimer(self, timeout=self.refresh_palette)
        self._wp.start(60_000)

        self._collapsed_state()
        self.reset_position()
        self.apply_palette()
        self._tick()
        watcher.changed.connect(self.on_state)
        watcher.cover.connect(self.on_cover)

    # ---------- UI ----------
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # --- collapsed: cover di samping jam ---
        self.col = QWidget()
        cl = QHBoxLayout(self.col)
        cl.setContentsMargins(6, 6, 16, 6)
        cl.setSpacing(8)
        self.col_cover = QLabel(alignment=Qt.AlignCenter)
        self.col_cover.setFixedSize(COVER_SMALL, COVER_SMALL)
        self.col_clock = QLabel(alignment=Qt.AlignCenter)
        self.col_clock.setFont(make_font("semibold", 11))
        for l in (self.col_cover, self.col_clock):
            l.setAttribute(Qt.WA_TransparentForMouseEvents)
        cl.addWidget(self.col_cover)
        cl.addWidget(self.col_clock, 1)
        lay.addWidget(self.col)

        # --- expanded ---
        self.exp = QWidget()
        ev = QVBoxLayout(self.exp)
        ev.setContentsMargins(14, 12, 14, 12)
        ev.setSpacing(8)

        self.top = QWidget()
        self.top.setFixedHeight(84)
        tv = QVBoxLayout(self.top)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(6)

        r1 = QHBoxLayout()
        r1.setSpacing(10)
        self.cover_lbl = QLabel(alignment=Qt.AlignCenter)
        self.cover_lbl.setFixedSize(COVER, COVER)
        self.cover_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        r1.addWidget(self.cover_lbl)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title, self.artist = QLabel(), QLabel()
        self.title.setFont(make_font("semibold", 11))
        self.artist.setFont(make_font("regular", 9))
        for l in (self.title, self.artist):
            l.setAttribute(Qt.WA_TransparentForMouseEvents)
        text.addStretch()
        text.addWidget(self.title)
        text.addWidget(self.artist)
        text.addStretch()
        r1.addLayout(text, 1)

        btns = QHBoxLayout()
        btns.setSpacing(4)
        self.btn_prev = IconButton("prev", "Sebelumnya", 30, lambda: self.watcher.command("prev"))
        self.btn_play = IconButton("pause", "Putar/Jeda", 38, lambda: self.watcher.command("play_pause"))
        self.btn_next = IconButton("next", "Berikutnya", 30, lambda: self.watcher.command("next"))
        self.btn_lyr = IconButton("lyrics", "Lirik", 30, self._toggle_lyrics)
        self.btn_close = IconButton("close", "Tutup", 30, self._close_clicked)
        for b in (self.btn_prev, self.btn_play, self.btn_next, self.btn_lyr, self.btn_close):
            btns.addWidget(b)
        r1.addLayout(btns)
        tv.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(8)
        self.t_cur, self.t_tot = QLabel("0:00"), QLabel("0:00")
        self.t_cur.setFixedWidth(36)
        self.t_tot.setFixedWidth(36)
        self.t_tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for l in (self.t_cur, self.t_tot):
            l.setFont(make_font("semibold", 8))
            l.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.bar = SeekBar()
        self.bar.moved.connect(lambda r: self.t_cur.setText(fmt(r * self._dur)))
        self.bar.scrubbed.connect(self._on_seek)
        r2.addWidget(self.t_cur)
        r2.addWidget(self.bar, 1)
        r2.addWidget(self.t_tot)
        tv.addLayout(r2)
        ev.addWidget(self.top, 0, Qt.AlignTop)

        self.lyr = QTextBrowser()
        self.lyr.setFrameShape(QTextBrowser.NoFrame)
        self.lyr.setFont(make_font("bold", 10))
        self.lyr.viewport().setAutoFillBackground(False)
        self.lyr.setContextMenuPolicy(Qt.NoContextMenu)  # klik kanan diteruskan ke menu Halo
        self.lyr.hide()
        ev.addWidget(self.lyr, 1)

        self.exp.hide()
        lay.addWidget(self.exp)

    def apply_palette(self):
        p = self.pal
        self.setStyleSheet(f"""
            QLabel {{ color: {p['fg']}; }}
            QTextBrowser {{ background: transparent; border: none; }}""")
        self.artist.setStyleSheet(f"color: {p['muted']};")
        self.t_cur.setStyleSheet(f"color: {p['muted']};")
        self.t_tot.setStyleSheet(f"color: {p['muted']};")
        self.bar.fill = QColor(p["accent"])
        self.bar.update()
        for b in (self.btn_prev, self.btn_play, self.btn_next, self.btn_lyr, self.btn_close):
            b.set_colors(QColor(p["fg"]), QColor(p["accent"]), QColor(p["bg2"]))
        self._render_covers()
        self._ly_last = None
        self._render_lyrics()
        self.update()
        self._tick()

    def _render_covers(self):
        if self._cover_pm is not None:
            for lbl, size, rad in ((self.cover_lbl, COVER, 10),
                                   (self.col_cover, COVER_SMALL, COVER_SMALL // 2)):
                lbl.setStyleSheet("background: transparent;")
                lbl.setText("")
                lbl.setPixmap(round_pixmap(self._cover_pm, size, rad))
        else:
            for lbl, rad, fs in ((self.cover_lbl, 10, 26), (self.col_cover, 14, 14)):
                lbl.clear()
                lbl.setText("♪")
                lbl.setStyleSheet(f"background: rgba(255,255,255,0.10); border-radius: {rad}px;"
                                  f"color: {self.pal['accent']}; font-size: {fs}px;")

    def refresh_palette(self):
        new = self._cover_pal or self.get_palette()
        if new != self.pal:
            self.pal = new
            self.apply_palette()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        rad = min(22.0, r.height() / 2)
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)

        alpha = int(255 * OPACITY)
        c1, c2 = QColor(self.pal["bg1"]), QColor(self.pal["bg2"])
        c1.setAlpha(alpha)
        c2.setAlpha(alpha)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, c1)
        g.setColorAt(1, c2)
        p.fillPath(path, g)

        # ambient: cahaya warna cover yang memancar dari sisi cover
        glow = QColor(self.pal["accent"])
        glow.setAlpha(int(110 * OPACITY + 30))
        if self.mode == "col":
            center, radius = QPointF(20, r.height() / 2), 80
        else:
            center, radius = QPointF(14 + COVER / 2, 12 + COVER / 2), 240
        rg = QRadialGradient(center, radius)
        rg.setColorAt(0, glow)
        glow.setAlpha(0)
        rg.setColorAt(1, glow)
        p.setClipPath(path)
        p.fillRect(self.rect(), QBrush(rg))
        p.setClipping(False)

        border = QColor(self.pal["accent"])
        border.setAlpha(90)
        p.setPen(QPen(border, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

    # ---------- mode, ukuran & posisi ----------
    def _collapsed_state(self):
        self.mode = "col"
        self.btn_lyr.set_active(False)
        self.setFixedSize(COL)
        self.exp.hide()
        self.lyr.hide()
        self.col.show()

    def reset_position(self):
        g = QApplication.primaryScreen().geometry()
        self._cx, self._top = g.center().x(), g.top() + 8
        self.move(self._cx - self.width() // 2, self._top)

    def set_mode(self, mode):
        if mode == self.mode:
            return
        prev, self.mode = self.mode, mode
        self.btn_lyr.set_active(mode == "lyr")
        self._anim.stop()
        if mode == "col":
            self.exp.hide()
        else:
            self.col.hide()
            if prev == "col":
                self.exp.hide()  # tampil setelah animasi selesai
        self.lyr.hide()
        self._anim.setStartValue(self.size())
        self._anim.setEndValue(SIZES[mode])
        self._anim.start()

    def _on_anim(self, size):
        self.setFixedSize(size)
        self.move(self._cx - size.width() // 2, self._top)  # jaga pusat horizontal

    def _on_anim_done(self):
        if self.mode == "col":
            self.col.show()
        else:
            self.exp.show()
            if self.mode == "lyr":
                self.lyr.show()
                self._ly_last = None
                self._render_lyrics()
        self.update()

    def _auto_collapse(self):
        if self.mode == "exp":
            self.set_mode("col")

    def _close_clicked(self):
        self._auto.stop()
        self.set_mode("col")

    def _toggle_lyrics(self):
        self._auto.stop()
        self.set_mode("exp" if self.mode == "lyr" else "lyr")

    # ---------- drag & klik ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._origin = self.pos()
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._press is None:
            return
        d = e.globalPosition().toPoint() - self._press
        if self._moved or d.manhattanLength() > 5:
            self._moved = True
            self.move(self._origin + d)
            self._cx, self._top = self.x() + self.width() // 2, self.y()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._press is not None:
            if not self._moved and self.mode == "col":
                self._auto.stop()
                self.set_mode("exp")
            self._press = None

    def contextMenuEvent(self, e):
        p = self.pal
        m = QMenu(self)
        m.setStyleSheet(
            f"QMenu {{ background: {p['bg2']}; color: {p['fg']}; padding: 4px;"
            f" border: 1px solid {p['accent']}; }}"
            f"QMenu::item {{ padding: 6px 20px; }}"
            f"QMenu::item:selected {{ background: rgba(255,255,255,0.14); }}"
            f"QMenu::separator {{ height: 1px; background: rgba(255,255,255,0.15);"
            f" margin: 4px 8px; }}")
        m.addAction("Reset posisi ke atas tengah").triggered.connect(self.reset_position)
        m.addSeparator()
        m.addAction("Keluar dari Halo").triggered.connect(QApplication.quit)
        m.exec(e.globalPos())

    # ---------- jam, progres, seek ----------
    def _tick(self):
        color = self.pal["fg"] if self.playing else self.pal["muted"]
        self.col_clock.setStyleSheet(f"color: {color};")
        self.col_clock.setText(f"{datetime.now():%H:%M}")

    def _cur_pos(self):
        pos, t0 = self._anchor
        if self.playing:
            pos += time.monotonic() - t0
        if self._dur > 0:
            pos = min(pos, self._dur)
        return max(pos, 0.0)

    def _progress(self):
        if self.mode == "col" or not self.isVisible():
            return
        pos = self._cur_pos()
        if not self.bar.dragging:
            self.t_cur.setText(fmt(pos))
            self.bar.set_ratio(pos / self._dur if self._dur > 0 else 0.0)
        self.t_tot.setText(fmt(self._dur))
        if self.mode == "lyr" and self._ly_state == "synced":
            self._render_lyrics()

    def _on_seek(self, ratio):
        if self._dur <= 0:
            return
        pos = ratio * self._dur
        self.watcher.seek(pos)
        self._anchor = (pos, time.monotonic())
        self._seek_hold = time.monotonic() + 1.5  # abaikan posisi lama dari Spotify sesaat
        self._render_lyrics()

    # ---------- lirik ----------
    def _render_lyrics(self):
        if self.mode != "lyr":
            return
        p, st = self.pal, self._ly_state
        msgs = {"loading": "Mencari lirik…", "none": "Lirik tidak ditemukan",
                "error": "Gagal memuat lirik (periksa koneksi internet)"}
        policy = Qt.ScrollBarAlwaysOff
        if st in msgs:
            body = (f"<p align='center' style='margin-top:60px; color:{p['muted']};'>"
                    f"{msgs[st]}</p>")
        elif st == "synced":
            idx = bisect_right(self._ly_times, self._cur_pos() + 0.2) - 1
            dim = mix(p["fg"], p["bg2"], 0.58)
            rows = []
            for i in range(idx - 2, idx + 3):
                if 0 <= i < len(self._ly):
                    raw = html.escape(self._ly[i][1])
                    t = f"“{raw}”" if raw else "♪"
                    color = p["fg"] if i == idx else dim
                    rows.append(f"<p align='left' style='margin:5px 0;'><span style="
                                f"'color:{color}; font-size:15px;'>{t}</span></p>")
                else:
                    rows.append("<p style='margin:5px 0;'>&nbsp;</p>")
            body = "".join(rows)
        else:  # plain (tanpa timestamp): bisa di-scroll
            policy = Qt.ScrollBarAsNeeded
            lines = [f"“{html.escape(l.strip())}”" if l.strip() else ""
                     for l in (self._plain or "").splitlines()]
            body = (f"<p align='left' style='color:{p['fg']}; font-size:13px;'>"
                    f"{'<br>'.join(lines)}</p>")
        if body == self._ly_last:
            return
        self._ly_last = body
        self.lyr.setVerticalScrollBarPolicy(policy)
        self.lyr.setHtml(body)

    def _reset_lyrics(self):
        self._ly, self._ly_times, self._plain = [], [], None
        self._ly_state, self._ly_key, self._ly_last = "loading", None, None
        self._render_lyrics()

    def on_lyrics(self, res):
        if res["key"] != self._ly_key:
            return  # hasil untuk lagu sebelumnya
        if res.get("error"):
            self._ly_state = "error"
        elif res["synced"]:
            self._ly, self._ly_state = res["synced"], "synced"
            self._ly_times = [t for t, _ in self._ly]
        elif res["plain"]:
            self._plain, self._ly_state = res["plain"], "plain"
        else:
            self._ly_state = "none"
        self._ly_last = None
        self._render_lyrics()

    # ---------- cover & state Spotify ----------
    def on_cover(self, data):
        if not data:  # tanpa cover: kembali ke placeholder dan palet wallpaper
            self._cover_pm, self._cover_pal = None, None
            self.pal = self.get_palette()
            self.apply_palette()
            return
        pm = QPixmap()
        if pm.loadFromData(data) and not pm.isNull():
            self._cover_pm = pm
            pal = palette_from_bytes(data)
            if pal:
                self._cover_pal, self.pal = pal, pal
            self.apply_palette()

    @staticmethod
    def _elide(label, text):
        label.setText(QFontMetrics(label.font()).elidedText(text, Qt.ElideRight, TEXT_W))

    def on_state(self, s):
        if not s.get("active"):
            self._auto.stop()
            self._track, self._was_playing, self.playing = None, False, False
            self.hide()
            return
        self.playing = s["playing"]
        key = (s["title"], s["artist"])
        self._elide(self.title, s["title"])
        self._elide(self.artist, s["artist"])
        self.btn_play.set_kind("pause" if s["playing"] else "play")
        self._dur = s["dur"]
        if time.monotonic() >= self._seek_hold:
            self._anchor = (s["pos"], time.monotonic())

        if key != self._track:
            self._reset_lyrics()
        if self._ly_key != key and s["dur"] > 0:  # tunggu durasi agar lirik cocok
            self._ly_key = key
            self.lyr_fetch.fetch(s["title"], s["artist"], s["dur"])

        first = not self.isVisible()
        if first:
            self.refresh_palette()
            self._anim.stop()
            self._collapsed_state()
            self.move(self._cx - self.width() // 2, self._top)
            self.show()
        if s["playing"] and (first or not self._was_playing or key != self._track):
            if self.mode == "col":
                self.set_mode("exp")
                self._auto.start(AUTO_COLLAPSE_MS)
        self._track, self._was_playing = key, s["playing"]
        self._tick()
