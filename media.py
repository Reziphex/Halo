"""Pemantau Spotify via Windows SMTC (System Media Transport Controls)."""
import asyncio
import threading
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as Manager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)
from winrt.windows.storage.streams import Buffer, DataReader, InputStreamOptions

# Aplikasi yang dipantau. Tambah/kurangi sesuai kebutuhan (cocok jika nama ada di AUMID sesi).
# Browser dipakai untuk YouTube / YouTube Music.
SOURCES = ("spotify", "chrome", "msedge", "firefox", "brave", "opera", "vivaldi")


def _app_id(session):
    return (session.source_app_user_model_id or "").lower()


def _is_playing(session):
    info = session.get_playback_info()
    return bool(info) and info.playback_status == PlaybackStatus.PLAYING


COMMANDS = {
    "play_pause": "try_toggle_play_pause_async",
    "next": "try_skip_next_async",
    "prev": "try_skip_previous_async",
}


class SpotifyWatcher(QObject):
    # {"active", "playing", "title", "artist", "pos" (detik), "dur" (detik)}
    changed = Signal(dict)
    cover = Signal(object)  # bytes gambar cover (jpeg/png)

    def __init__(self):
        super().__init__()
        self._loop = asyncio.new_event_loop()
        self._session = None
        self._session_id = None
        self._last = None
        self._cover_key = None
        self._cover_tries = 0
        self._cover_hash = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._poll())

    async def _poll(self):
        manager = await Manager.request_async()
        while True:
            try:
                state = await self._read(manager)
            except Exception:
                self._session = None
                state = {"active": False}
            if not state.get("active"):
                self._cover_key = self._cover_hash = None
            if state != self._last:
                self._last = state
                self.changed.emit(state)
            await asyncio.sleep(1)

    def _choose(self, manager):
        """Pilih sesi: yang sedang diputar (Spotify diutamakan), atau tetap di sesi terakhir."""
        sessions = [s for s in manager.get_sessions() if any(k in _app_id(s) for k in SOURCES)]
        playing = [s for s in sessions if _is_playing(s)]
        if playing:
            keep = next((s for s in playing if _app_id(s) == self._session_id), None)
            return keep or next((s for s in playing if "spotify" in _app_id(s)), playing[0])
        keep = next((s for s in sessions if _app_id(s) == self._session_id), None)
        return keep or next((s for s in sessions if "spotify" in _app_id(s)), None)

    async def _read(self, manager):
        self._session = self._choose(manager)
        if self._session is None:
            self._session_id = None
            return {"active": False}
        self._session_id = _app_id(self._session)

        props = await self._session.try_get_media_properties_async()
        playing = _is_playing(self._session)
        title = props.title or "Tanpa judul"
        artist = props.artist or "Artis tidak diketahui"

        pos, dur = 0.0, 0.0
        try:
            tl = self._session.get_timeline_properties()
            pos = tl.position.total_seconds()
            dur = (tl.end_time - tl.start_time).total_seconds()
            if playing:  # posisi di SMTC adalah snapshot pada last_updated_time
                lu = tl.last_updated_time
                if lu.tzinfo is None:
                    lu = lu.replace(tzinfo=timezone.utc)
                pos += max(0.0, (datetime.now(timezone.utc) - lu).total_seconds())
            if dur > 0:
                pos = min(pos, dur)
            pos = max(pos, 0.0)
        except Exception:
            pass

        await self._maybe_cover(props, (title, artist))
        return {"active": True, "playing": playing, "title": title,
                "artist": artist, "pos": round(pos, 1), "dur": round(dur, 1)}

    async def _maybe_cover(self, props, key):
        if key != self._cover_key:
            self._cover_key, self._cover_tries = key, 3
        if self._cover_tries <= 0:
            return
        self._cover_tries -= 1
        data = await self._thumb(props)
        if data and hash(data) != self._cover_hash:
            self._cover_hash, self._cover_tries = hash(data), 0
            self.cover.emit(data)
        elif not data and self._cover_tries == 0 and self._cover_hash is not None:
            self._cover_hash = None  # lagu/video ini tanpa cover: hapus cover lama
            self.cover.emit(b"")

    @staticmethod
    async def _thumb(props):
        try:
            ref = props.thumbnail
            if ref is None:
                return None
            stream = await ref.open_read_async()
            buf = Buffer(int(stream.size) or 5_000_000)
            await stream.read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD)
            reader = DataReader.from_buffer(buf)
            data = reader.read_buffer(reader.unconsumed_buffer_length)
            return bytes(bytearray(data))
        except Exception:
            return None

    def seek(self, seconds):
        asyncio.run_coroutine_threadsafe(self._seek(seconds), self._loop)

    async def _seek(self, seconds):
        s = self._session
        if s is not None:
            try:  # satuan SMTC: 100 nanodetik
                await s.try_change_playback_position_async(int(seconds * 10_000_000))
            except Exception:
                pass

    def command(self, name):
        asyncio.run_coroutine_threadsafe(self._cmd(name), self._loop)

    async def _cmd(self, name):
        s = self._session
        if s is not None:
            try:
                await getattr(s, COMMANDS[name])()
            except Exception:
                pass
