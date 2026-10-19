"""Ambil lirik dari LRCLIB (https://lrclib.net) - gratis, tanpa API key."""
import json
import re
import threading
import urllib.parse
import urllib.request

from PySide6.QtCore import QObject, Signal

LRC_STAMP = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
UA = {"User-Agent": "Halo/1.0 (desktop now-playing popup)"}


def parse_lrc(text):
    out = []
    for line in text.splitlines():
        stamps = LRC_STAMP.findall(line)
        if not stamps:
            continue
        content = LRC_STAMP.sub("", line).strip()
        for m, s in stamps:
            out.append((int(m) * 60 + float(s), content))
    out.sort(key=lambda x: x[0])
    return out


def _clean_title(title):
    return re.sub(r"\s*[-–(\[].*$", "", title).strip() or title


def _pick(items, duration):
    cands = [i for i in items if i.get("syncedLyrics") or i.get("plainLyrics")]
    if duration > 0:
        cands = [i for i in cands if abs((i.get("duration") or 0) - duration) <= 5]
    if not cands:
        return None
    cands.sort(key=lambda i: (not i.get("syncedLyrics"),
                              abs((i.get("duration") or 0) - duration)))
    return cands[0]


class LyricsFetcher(QObject):
    # {"key": (title, artist), "synced": [(detik, teks)], "plain": str|None, "error": bool}
    ready = Signal(object)

    def __init__(self):
        super().__init__()
        self._cache = {}

    def fetch(self, title, artist, duration):
        key = (title, artist)
        if key in self._cache:
            self.ready.emit(self._cache[key])
            return
        threading.Thread(target=self._work, args=(key, duration), daemon=True).start()

    def _work(self, key, duration):
        title, artist = key
        res = {"key": key, "synced": [], "plain": None, "error": False}
        try:
            queries = [
                {"track_name": title, "artist_name": artist},
                {"q": f"{_clean_title(title)} {artist}"},
            ]
            for params in queries:
                url = "https://lrclib.net/api/search?" + urllib.parse.urlencode(params)
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=8) as r:
                    items = json.loads(r.read().decode("utf-8"))
                best = _pick(items, duration)
                if best:
                    if best.get("syncedLyrics"):
                        res["synced"] = parse_lrc(best["syncedLyrics"])
                    if not res["synced"]:
                        res["plain"] = best.get("plainLyrics")
                    break
            self._cache[key] = res
        except Exception:
            res["error"] = True  # jangan di-cache, coba lagi lain kali
        self.ready.emit(res)
