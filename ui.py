"""Pop-up ala Dynamic Island: jam, cover, progres lagu, dan lirik."""
import html
import time
from bisect import bisect_right
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QSize, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from lyrics import LyricsFetcher

COL = QSize(150, 38)    # collapsed: jam
EXP = QSize(460, 108)   # expanded: cover, judul, kontrol, progres
LYR = QSize(460, 270)   # expanded + lirik
SIZES = {"col": COL, "exp": EXP, "lyr": LYR}
COVER = 64
TEXT_W = 185
AUTO_COLLAPSE_MS = 6000


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
        self._has_cover = False
        self._dur, self._anchor = 0.0, (0.0, time.monotonic())
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
    def _btn(self, text, tip, fn):
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setFixedSize(30, 30)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(fn)
        return b

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # --- collapsed: jam ---
        self.col = QLabel(alignment=Qt.AlignCenter)
        self.col.setTextFormat(Qt.RichText)
        self.col.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.col.setAttribute(Qt.WA_TransparentForMouseEvents)
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
        self.title.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self.artist.setFont(QFont("Segoe UI", 9))
        for l in (self.title, self.artist):
            l.setAttribute(Qt.WA_TransparentForMouseEvents)
        text.addStretch()
        text.addWidget(self.title)
        text.addWidget(self.artist)
        text.addStretch()
        r1.addLayout(text, 1)

        btns = QHBoxLayout()
        btns.setSpacing(2)
        self.btn_prev = self._btn("⏮", "Sebelumnya", lambda: self.watcher.command("prev"))
        self.btn_play = self._btn("⏸", "Putar/Jeda", lambda: self.watcher.command("play_pause"))
        self.btn_next = self._btn("⏭", "Berikutnya", lambda: self.watcher.command("next"))
        self.btn_lyr = self._btn("♫", "Lirik", self._toggle_lyrics)
        self.btn_close = self._btn("⌃", "Tutup", self._close_clicked)
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
            l.setFont(QFont("Segoe UI", 8))
            l.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setAttribute(Qt.WA_TransparentForMouseEvents)
        r2.addWidget(self.t_cur)
        r2.addWidget(self.bar, 1, Qt.AlignVCenter)
        r2.addWidget(self.t_tot)
        tv.addLayout(r2)
        ev.addWidget(self.top, 0, Qt.AlignTop)

        self.lyr = QTextBrowser()
        self.lyr.setFrameShape(QTextBrowser.NoFrame)
        self.lyr.setFont(QFont("Segoe UI", 10))
        self.lyr.hide()
        ev.addWidget(self.lyr, 1)

        self.exp.hide()
        lay.addWidget(self.exp)

    def apply_palette(self):
        p = self.pal
        self.setStyleSheet(f"""
            QLabel {{ color: {p['fg']}; }}
            QPushButton {{ background: transparent; color: {p['fg']}; border: none;
                           border-radius: 15px; font-size: 14px;
                           font-family: 'Segoe UI Symbol'; }}
            QPushButton:hover {{ background: rgba(255,255,255,0.16); }}
            QProgressBar {{ background: rgba(255,255,255,0.18); border: none;
                            border-radius: 2px; }}
            QProgressBar::chunk {{ background: {p['accent']}; border-radius: 2px; }}
            QTextBrowser {{ background: transparent; border: none; }}""")
        self.artist.setStyleSheet(f"color: {p['muted']};")
        self.t_cur.setStyleSheet(f"color: {p['muted']};")
        self.t_tot.setStyleSheet(f"color: {p['muted']};")
        if not self._has_cover:
            self._placeholder_cover()
        self._ly_last = None
        self._render_lyrics()
        self.update()
        self._tick()

    def _placeholder_cover(self):
        self.cover_lbl.clear()
        self.cover_lbl.setText("♪")
        self.cover_lbl.setStyleSheet(
            f"background: rgba(255,255,255,0.10); border-radius: 10px;"
            f"color: {self.pal['accent']}; font-size: 26px;")

    def refresh_palette(self):
        new = self.get_palette()
        if new != self.pal:
            self.pal = new
            self.apply_palette()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(self.pal["bg1"]))
        g.setColorAt(1, QColor(self.pal["bg2"]))
        border = QColor(self.pal["accent"])
        border.setAlpha(90)
        p.setBrush(g)
        p.setPen(QPen(border, 1))
        rad = min(22, r.height() / 2)
        p.drawRoundedRect(r, rad, rad)

    # ---------- mode, ukuran & posisi ----------
    def _collapsed_state(self):
        self.mode = "col"
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

    # ---------- jam, progres, lirik ----------
    def _tick(self):
        color = self.pal["accent"] if self.playing else self.pal["muted"]
        self.col.setText(f"<span style='color:{color}'>♪</span>&nbsp;&nbsp;"
                         f"{datetime.now():%H:%M}")

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
        self.t_cur.setText(fmt(pos))
        self.t_tot.setText(fmt(self._dur))
        self.bar.setValue(int(pos / self._dur * 1000) if self._dur > 0 else 0)
        if self.mode == "lyr" and self._ly_state == "synced":
            self._render_lyrics()

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
            rows = []
            for i in range(idx - 2, idx + 3):
                if 0 <= i < len(self._ly):
                    t = html.escape(self._ly[i][1]) or "♪"
                    if i == idx:
                        rows.append(f"<p align='center' style='margin:5px 0;'><span style="
                                    f"'color:{p['accent']}; font-size:16px; font-weight:600;'>"
                                    f"{t}</span></p>")
                    else:
                        rows.append(f"<p align='center' style='margin:5px 0;'><span style="
                                    f"'color:{p['muted']}; font-size:12px;'>{t}</span></p>")
                else:
                    rows.append("<p style='margin:5px 0;'>&nbsp;</p>")
            body = "".join(rows)
        else:  # plain (tanpa timestamp): bisa di-scroll
            policy = Qt.ScrollBarAsNeeded
            txt = html.escape(self._plain or "").replace("\n", "<br>")
            body = (f"<p align='center' style='color:{p['fg']}; font-size:12px;'>"
                    f"{txt}</p>")
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

    def on_cover(self, data):
        pm = QPixmap()
        if pm.loadFromData(data) and not pm.isNull():
            self._has_cover = True
            self.cover_lbl.setStyleSheet("background: transparent;")
            self.cover_lbl.setText("")
            self.cover_lbl.setPixmap(round_pixmap(pm, COVER, 10))

    # ---------- state Spotify ----------
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
        self.btn_play.setText("⏸" if s["playing"] else "▶")
        self._dur = s["dur"]
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
