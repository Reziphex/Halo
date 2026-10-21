"""Ambil lirik dari LRCLIB (https://lrclib.net) - gratis, tanpa API key."""
import json
import re
import threading
import urllib.parse
import urllib.request

from PySide6.QtCore import QObject, Signal

LRC_STAMP = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
UA = {"User-Agent": "Halo/1.0 (desktop now-playing popup)"}
NOISE_WORDS = re.compile(
    r"(?i)\b(official|lyrics?|lyric video|music video|video|audio|hd|4k|mv|visualizer)\b")


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


def strip_noise(text):
    """Buang (Official Video), [Lyrics], dsb. dari judul YouTube."""
    text = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", "", text)
    text = NOISE_WORDS.sub("", text)
    return re.sub(r"\s+", " ", text).strip(" -|–—·")


def clean_artist(artist):
    return re.sub(r"(?i)\s*(-\s*topic|vevo)$", "", artist).strip()


def build_queries(title, artist):
    """Beberapa variasi pencarian: judul Spotify rapi, judul YouTube 'Artis - Lagu', dll."""
    artist_c = clean_artist(artist)
    noise_free = strip_noise(title)
    queries = [{"track_name": title, "artist_name": artist}]
    if re.search(r"\s[-–—]\s", noise_free):  # YouTube: "Artis - Judul"
        a, t = re.split(r"\s[-–—]\s", noise_free, maxsplit=1)
        queries.append({"track_name": strip_noise(t), "artist_name": strip_noise(a)})
        queries.append({"q": f"{strip_noise(a)} {strip_noise(t)}"})
    head = re.sub(r"\s[-–—].*$", "", title)  # buang sufiks seperti "- Remastered"
    queries.append({"q": f"{strip_noise(head)} {artist_c}"})
    queries.append({"q": f"{noise_free} {artist_c}"})
    seen, out = set(), []
    for q in queries:  # hilangkan duplikat
        key = json.dumps(q, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def _pick(items, duration, tol):
    cands = [i for i in items if i.get("syncedLyrics") or i.get("plainLyrics")]
    if duration > 0:
        cands = [i for i in cands if abs((i.get("duration") or 0) - duration) <= tol]
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

    def _search(self, params):
        url = "https://lrclib.net/api/search?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))

    def _work(self, key, duration):
        title, artist = key
        res = {"key": key, "synced": [], "plain": None, "error": False}
        try:
            best = None
            for tol in (5, 15):  # durasi video YouTube sering sedikit beda dari lagu
                for params in build_queries(title, artist):
                    best = _pick(self._search(params), duration, tol)
                    if best:
                        break
                if best or duration <= 0:
                    break
            if best:
                if best.get("syncedLyrics"):
                    res["synced"] = parse_lrc(best["syncedLyrics"])
                if not res["synced"]:
                    res["plain"] = best.get("plainLyrics")
            self._cache[key] = res
        except Exception:
            res["error"] = True  # jangan di-cache, coba lagi lain kali
        self.ready.emit(res)
