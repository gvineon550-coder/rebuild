#!/usr/bin/env python3
import argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parent
FILES = {}

FILES["scripts/__init__.py"] = ""

FILES["scripts/config.py"] = r'''import json, os, re
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)

CHANNELS_URL = "https://iptv-org.github.io/api/channels.json"
LOGOS_URL    = "https://iptv-org.github.io/api/logos.json"

EPG_URLS = [
    "https://iptvx.one/epg/epg_lite.xml.gz",
    "https://epg.one/epg.xml.gz",
    "http://epg.it999.ru/edem.xml.gz",
]
EPG_TTL_HOURS = 168
EPG_TIMEOUT   = 120

CONCURRENCY      = int(os.getenv("IPTV_CONC", "250"))
HOST_CONCURRENCY = 10
HTTP_TIMEOUT     = 4
RANGE_BYTES      = 4096
RETRIES          = 0

WARM_TTL_HOURS         = 6
DEAD_CACHE_MIN_FAILS   = 1
DEAD_CACHE_TTL_DAYS    = 30
HOST_BLOCK_AFTER_FAILS = 3

MIN_ALIVE_ABS  = 20
MIN_ALIVE_PCT  = 0.10
DEEP_CHECK     = os.getenv("DEEP_CHECK") == "1"
TEST_URL       = os.getenv("TEST_URL", "").strip()

PLAYLIST_PATH = ROOT / "playlist.m3u"
README_PATH   = ROOT / "README.md"
REPORT_PATH   = DATA / "report.json"
SOURCES_PATH  = ROOT / "sources.yml"

BAD_URL_PATTERNS = [
    "ads=", "ad=", "adv=", "advert=", "advertisement=",
    "banner=", "promo=", "/ads/", "/ad/",
    "mcquack", "cinerama", "tvstitch", "thestream.cyou", "televizor24.cc"
]

UAS = {
    "Wink": "WINK/RT_(Android_TV/11)_WinkPlayer_AppleWebKit/537.36",
    "HlsWinkPlayer": "HlsWinkPlayer/3.0.2 (Linux; Android 11; Wink) ExoPlayerLib/2.18.1",
    "TiviMate": "TiviMate/4.7.0 (Linux; Android 11; Sony Smart TV)",
    "AndroidTV": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "VLC": "VLC/3.0.20 LibVLC/3.0.20",
    "SmartTV": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/4.0 Chrome/76.0.3809.146 TV Safari/537.36",
    "Kodi": "Kodi/20.5 (Windows NT 10.0; Win64; x64) App_Bitness/64 Version/20.5",
    "OTT": "OTT Navigator/1.7.1.2 (Linux; Android 11)",
    "ExoPlayer": "ExoPlayerLib/2.18.1",
    "Lavf": "Lavf/60.16.100",
    "okhttp": "okhttp/4.9.3",
    "Chrome_Win": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Safari_Mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "MXPlayer": "MXPlayer/1.71.6 (Linux; Android 11)",
}
UA_WEIGHTS = {"Wink":30,"HlsWinkPlayer":25,"TiviMate":12,"AndroidTV":8,"VLC":8,"SmartTV":6,"Kodi":5,"OTT":5,"ExoPlayer":4,"Lavf":3,"okhttp":3,"Chrome_Win":3,"Safari_Mac":2,"Firefox":2,"MXPlayer":2}

BAD_GROUPS = ["kids", "детск", "children", "cartoon", "мульт", "шопинг", "shop", "магазин", "ювелир", "витрина", "adult", "18+", "эротика", "regional", "региональн", "област", "краев", "город", "авто", "auto", "drive", "религ", "церков", "православ", "ислам", "спас", "союз"]

BAD_WORDS = ["детск","kids","child","cartoon","мульт","карусель","disney","nickelodeon","nick jr","boomerang","смешарик","фиксики","малыш","tiji","аниме","мама","солнце","тамыр","супергерои","радость моя","ani","мультимузыка","капитан фантастика","fan","в гостях у сказки","прима","волга","белгород","самара","енисей","горловка","сочи","пермь","волгоград","корабль","миллет","евразия","нтм","нтс","продвижение","афонтово","омск","новосибирск","нижний","красноярск","прим","братск","новокузнецк","север","сургут","симферополь","луганск","тонус","вайнах","арис","рязань","астрахань","толк","алушта","салям","кубань","щелков","дагестан","краснодар","абза","апсуа","таврия","архыз","грозный","истоки","югра","москва","ингушетия","ярославль","курай","тдк","регион","тнв","лентв","qazaq","kazakh","uzbek","moldova","belarus","ukrain","armenia","georgia","kyrgyz","tajik","turkmen","azerb","latvia","lithuania","estonia","abkhaz","ossetia","chechnya","ingushetia","dagestan","rtvi","рада","freeдом","свобода","svoboda","tvrain","kentron","kino 2","tv 21","беларус","украин","молдов","казах","узбек","армени","грузи","азерб","латви","литв","эстон","киргиз","таджик","туркмен","израил","сша","usa","европа","europe","international","world","global","shop","шоппинг","магазин","leomax","top shop","витрина","ювелирочка","moy mir","авто","auto","drive","драйв","auto plus","autogid","вера","церков","православ","ислам","спас","3abn","союз","царьград","huzur","tbn","angel","mana","big asia","сарафан","усадьба","univer","ntv law","просвещение","точка отрыва","вместе","rus","загородная","дача","home 4k","zoopark","insayt","ministerstvo","душевное","city eden","время","наш кинопоказ","киносерия","кинопоказ","kinohit","киносвидание","test","demo","promo"]

CATEGORY_MAP = {"sports":"⚽ Спорт","sport":"⚽ Спорт","news":"📰 Новостные","movies":"🎬 Кино","movie":"🎬 Кино","cinema":"🎬 Кино","series":"📺 Сериалы","music":"🎵 Музыкальные","documentary":"🎥 Документальные","history":"🎥 Документальные","science":"🌍 Познавательные","education":"🌍 Познавательные","entertainment":"🎭 Развлекательные","comedy":"🎭 Развлекательные","lifestyle":"🎭 Развлекательные","general":"📡 Федеральные","cooking":"🍳 Кулинарные","food":"🍳 Кулинарные","travel":"🌍 Путешествия","culture":"🎭 Культура","business":"📰 Бизнес","weather":"📰 Погода","classic":"🎭 Классика","outdoor":"🌍 Природа","undefined":"📦 Разное","other":"📦 Разное","misc":"📦 Разное","разное":"📦 Разное"}

KEYWORD_RULES = {"⚽ Спорт": ["спорт","sport","футбол","football","матч","хокке","hockey","теннис","бокс","ufc","mma","арена","биатлон"],"📰 Новостные": ["новост","news","известия","рбк","вести","360","дождь","тасс","lenta","информ"],"🎬 Кино": ["кино","cinema","movie","фильм","film","боевик","комедия","ужас","детектив","премьера","tv1000","кинопоказ","иллюзион","победа"],"📺 Сериалы": ["сериал","series","дорам","драма","мелодрам"],"🎵 Музыкальные": ["music","музык","муз","mtv","vh1","ru.tv","шансон","europa plus","bridge","top hit"],"🎭 Развлекательные": ["развлек","юмор","comedy","шоу","тнт","пятница","суббота","перец"],"🌍 Познавательные": ["science","наука","discovery","nat geo","history","истор","viasat","nano","животн","природа","охота","путешеств"],"🎥 Документальные": ["документ","documental","tlc","dmax","военн","биограф","катастроф"],"🍳 Кулинарные": ["кухня","еда","food","cooking","кулинар"],"🎭 Культура": ["культур","culture","искусств","театр"],"📰 Бизнес": ["бизнес","business","деньги"],"📰 Погода": ["погода","weather"]}

NOISE = {"тв","tv","hd","uhd","fhd","sd","4k","1080p","720p","full","канал","channel","online","live","stream"}
TRANSLIT = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya","ї":"i","є":"e","і":"i","ґ":"g"}

def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

def load_json(path: Path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def host_of(url: str) -> str:
    try: return urlparse(url).netloc.lower().split(":")[0]
    except Exception: return "unknown"

def has_cyr(s: str) -> bool: return bool(re.search(r'[а-яА-ЯёЁ]', s or ''))

def norm_name(s: str) -> str:
    n = (s or "").lower().replace("ё","е").replace("й","и")
    n = re.sub(r'\(.*?\)|\[.*?\]', ' ', n)
    n = re.sub(r'[^a-zа-я0-9\s]', ' ', n)
    return " ".join(w for w in n.split() if w and w not in NOISE)

def translit(s: str) -> str: return "".join(TRANSLIT.get(c, c) for c in (s or ""))

def extract_suffix(tvg_id: str) -> str:
    if not tvg_id or "@" not in tvg_id: return ""
    sfx = tvg_id.split("@", 1)[1]; low = sfx.lower()
    if low == "sd": return ""
    if low.startswith("plus") and low[4:].isdigit(): return "+" + low[4:]
    if low in ("hd","fhd","uhd","4k","1080p","720p"): return sfx.upper()
    return sfx

def normalize_url(u: str) -> str:
    if not u: return ""
    try:
        p = urlparse(u.strip())
        drop = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","fbclid","gclid","ref","source"}
        q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in drop]
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(q), ""))
    except Exception: return u.strip()
'''

FILES["scripts/ui.py"] = r'''from datetime import datetime, timezone, timedelta
def msk_now(): return datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M MSK")
def info(msg): print(f"[*] {msg}", flush=True)
def ok(msg): print(f"[+] {msg}", flush=True)
def warn(msg): print(f"[!] {msg}", flush=True)
def err(msg): print(f"[-] {msg}", flush=True)
class Progress:
    def __init__(self, total, step=5):
        self.total = total; self.step = step; self.done = 0; self.alive = 0; self._last_pct = -1
    def bump(self, alive=False):
        self.done += 1
        if alive: self.alive += 1
        pct = int(self.done * 100 / self.total) if self.total else 100
        if pct >= self._last_pct + self.step or self.done == self.total:
            self._last_pct = pct; self._render()
    def _render(self):
        dead = self.done - self.alive
        w = 40; f = int(w * self.done / self.total) if self.total else w
        bar = "█" * f + "░" * (w - f)
        pct = self.done * 100 // self.total if self.total else 100
        print(f"[{bar}] {pct}% ({self.done}/{self.total}) | Живых: {self.alive} | Упало: {dead}", flush=True)
'''

FILES["scripts/knowledge.py"] = r'''import json, random, time
from . import config
class Knowledge:
    def __init__(self):
        self.warm = config.load_json(config.DATA/"warm.json", {})
        self.dead = config.load_json(config.DATA/"dead.json", {})
        self.ua_cache = config.load_json(config.DATA/"ua_cache.json", {})
        self.ua_scores = config.load_json(config.DATA/"ua_scores.json", {})
        self.tmo = config.load_json(config.DATA/"tmo.json", {})
        self.hosts = config.load_json(config.DATA/"hosts.json", {})
    def is_warm(self, url):
        r = self.warm.get(url)
        return bool(r) and time.time() - r.get("ts", 0) < config.WARM_TTL_HOURS*3600
    def get_warm(self, url): return self.warm.get(url)
    def mark_warm(self, url, ua_key, height=0, bandwidth=0): self.warm[url] = {"ts": int(time.time()), "ua_key": ua_key, "height": height, "bandwidth": bandwidth}
    def is_dead(self, url):
        r = self.dead.get(url)
        if not r: return False
        if r.get("fails", 0) < config.DEAD_CACHE_MIN_FAILS: return False
        if time.time() - r.get("ts", 0) > config.DEAD_CACHE_TTL_DAYS*86400: return False
        return True
    def mark_dead(self, url, ok):
        if ok: self.dead.pop(url, None); return
        r = self.dead.get(url, {"fails": 0, "ts": 0}); r["fails"] = r.get("fails", 0) + 1; r["ts"] = int(time.time()); self.dead[url] = r
    def pick_ua_order(self, host, deep=False):
        saved = self.ua_cache.get(host); scores = self.ua_scores.get(host, {}); global_scores = {}
        for h, s in self.ua_scores.items():
            for ua, sc in s.items(): global_scores[ua] = global_scores.get(ua, 0) + sc
        samples = {}
        for k in config.UAS.keys():
            ok = max(0, scores.get(k, 0)) + max(0, global_scores.get(k, 0)) * 0.1
            fail = max(0, -scores.get(k, 0)); samples[k] = random.betavariate(ok + 1, fail + 1)
        keys = sorted(samples.keys(), key=lambda k: -samples[k])
        if deep: return keys
        top = keys[:4]
        if saved and saved in config.UAS:
            if saved in top: top.remove(saved)
            return [saved] + top
        return top
    def upd_ua_score(self, host, ua_key, ok):
        s = self.ua_scores.setdefault(host, {}); s[ua_key] = s.get(ua_key, 0) + (2 if ok else -1)
    def set_best_ua(self, host, ua_key): self.ua_cache[host] = ua_key
    def get_timeout(self, url):
        h = config.host_of(url); med = self.tmo.get(h, {}).get("med", 0)
        if med: return max(3, min(10, int(med/1000*2 + 2)))
        return config.HTTP_TIMEOUT
    def upd_timeout(self, url, ms):
        h = config.host_of(url); r = self.tmo.setdefault(h, {"v": []}); v = (r.get("v", [])[-20:] + [int(ms)])[-20:]
        r["v"] = v; r["med"] = sorted(v)[len(v)//2]
    def upd_host(self, host, ok):
        r = self.hosts.setdefault(host, {"ok": 0, "fail": 0}); k = "ok" if ok else "fail"; r[k] = r.get(k, 0) + 1
    def host_blocked(self, host):
        r = self.hosts.get(host, {}); return r.get("ok", 0) == 0 and r.get("fail", 0) >= config.HOST_BLOCK_AFTER_FAILS
    def save_all(self):
        cw = time.time() - 7*86400; warm = {k: v for k, v in self.warm.items() if v.get("ts", 0) > cw}
        cd = time.time() - config.DEAD_CACHE_TTL_DAYS*86400; dead = {k: v for k, v in self.dead.items() if v.get("ts", 0) > cd}
        for name, data in [("warm.json", warm), ("dead.json", dead), ("ua_cache.json", self.ua_cache), ("ua_scores.json", self.ua_scores), ("tmo.json", self.tmo), ("hosts.json", self.hosts)]:
            config.atomic_write(config.DATA/name, json.dumps(data, ensure_ascii=False, indent=1))
'''

FILES["scripts/checker.py"] = r'''import asyncio, random, re, time
from urllib.parse import urljoin, urlparse
import aiohttp
from . import config, ui

RU_IPS = ["95.108.213.1", "77.88.8.8", "87.250.250.242", "5.255.255.5"]
PATHS = ["/live/", "/hls/", "/play/", "/stream/", "/index/"]

def _hdr(ua, ref=None, xff=False):
    h = {"User-Agent": ua, "Accept": "*/*", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8", "Accept-Encoding": "identity", "Connection": "keep-alive"}
    if ref:
        h["Referer"] = ref
        if "wink.ru" in ref: h["Origin"] = "https://wink.ru"
        elif "rutube.ru" in ref: h["Origin"] = "https://rutube.ru"
    if xff:
        ip = random.choice(RU_IPS); h["X-Forwarded-For"] = ip; h["X-Real-IP"] = ip
    return h

def _ref(url):
    h = config.host_of(url)
    if "wink.ru" in h: return "https://wink.ru/"
    if "rutube.ru" in h: return "https://rutube.ru/"
    return None

def _variants(text, base):
    out, lines = [], [l.strip() for l in text.splitlines()]
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            bw, h = 0, 0
            m = re.search(r"BANDWIDTH=(\d+)", line)
            if m: bw = int(m.group(1))
            r = re.search(r"RESOLUTION=\d+x(\d+)", line)
            if r: h = int(r.group(1))
            for j in range(i+1, len(lines)):
                if lines[j] and not lines[j].startswith("#"):
                    out.append({"url": urljoin(base, lines[j]), "bw": bw, "h": h}); break
    return out

async def _probe(session, url, ua, ref, depth=0, deep=False, timeout=4, use_xff=False):
    if depth > 1: return None
    urls_to_try = [url]
    if url.startswith("https://"): urls_to_try.append(url.replace("https://", "http://", 1))
    for current_url in urls_to_try:
        headers = _hdr(ua, ref, use_xff); to = aiohttp.ClientTimeout(total=timeout)
        try:
            async with session.head(current_url, headers=headers, timeout=to, allow_redirects=True, ssl=False) as r:
                if r.status == 429: await asyncio.sleep(min(int(r.headers.get("Retry-After", "3")), 15)); continue
                if r.status in (403, 404, 410, 451) and current_url == url: continue
        except Exception: pass
        headers["Range"] = f"bytes=0-{config.RANGE_BYTES-1}"; body = b""
        try:
            async with session.get(current_url, headers=headers, timeout=to, allow_redirects=True, ssl=False) as r:
                if r.status in (200, 206):
                    body = await r.content.read(config.RANGE_BYTES); text = body.decode("utf-8", errors="ignore"); final_url = str(r.url)
                else: continue
        except Exception: continue
        if not body: continue
        if "#EXTM3U" not in text and depth == 0 and not deep:
            p = urlparse(current_url)
            for tp in PATHS:
                if tp in p.path: continue
                np = p.path.replace("/live/", tp).replace("/play/", tp)
                if np != p.path:
                    res = await _probe(session, p._replace(path=np).geturl(), ua, ref, depth, deep, timeout, use_xff)
                    if res: return res
        if "#EXTM3U" in text and "#EXT-X-STREAM-INF" in text:
            vs = _variants(text, final_url)
            if not vs: continue
            vs.sort(key=lambda v: (-v["h"], -v["bw"]))
            lim = len(vs) if deep else min(2, len(vs))
            for v in vs[:lim]:
                sub = await _probe(session, v["url"], ua, ref, depth+1, deep, timeout, use_xff)
                if sub: sub["h"] = v["h"] or sub.get("h", 0); sub["bw"] = v["bw"]; return sub
        if "#EXTM3U" in text and text.count("#EXTINF") > 0:
            drm = "#EXT-X-KEY" in text and "METHOD=NONE" not in text
            return {"url": final_url, "h": 0, "bw": 0, "drm": drm}
        if body[:1] in (b"\x47", b"\x00", b"\xff", b"<"): return {"url": final_url, "h": 0, "bw": 0, "drm": False}
    return None

async def _check_url(session, url, kn, deep=False):
    host = config.host_of(url)
    if not deep and kn.is_dead(url): return None
    if not deep and kn.host_blocked(host): return None
    for ua_key in kn.pick_ua_order(host, deep=deep):
        ua = config.UAS[ua_key]; ref = _ref(url); to = kn.get_timeout(url) if not deep else config.HTTP_TIMEOUT
        t0 = time.time(); result = await _probe(session, url, ua, ref, 0, deep, to, False)
        if not result and not deep: result = await _probe(session, url, ua, ref, 0, deep, to, True)
        lat = (time.time()-t0)*1000
        if result:
            kn.mark_warm(url, ua_key, result.get("h", 0), result.get("bw", 0)); kn.set_best_ua(host, ua_key); kn.upd_ua_score(host, ua_key, True)
            kn.upd_host(host, True); kn.mark_dead(url, True); kn.upd_timeout(url, lat)
            return {"url": result["url"], "profile": ua_key, "height": result.get("h", 0), "referer": ref}
        kn.upd_ua_score(host, ua_key, False)
    kn.mark_dead(url, False); kn.upd_host(host, False)
    return None

async def _one(session, ch, kn, deep=False):
    urls = [u for u in (ch.get("urls") or [ch.get("url")]) if u]
    if not urls: return None
    tasks = [_check_url(session, u, kn, deep) for u in urls]; results = await asyncio.gather(*tasks, return_exceptions=True)
    alive_urls, best_profile, best_height, best_referer = [], "", 0, None
    for r in results:
        if isinstance(r, dict) and r:
            if r["url"] not in alive_urls: alive_urls.append(r["url"])
            if not best_profile: best_profile = r["profile"]; best_height = r["height"]; best_referer = r.get("referer")
    if alive_urls: return {"channel": ch, "url": alive_urls[0], "urls": alive_urls, "profile": best_profile, "height": best_height, "referer": best_referer}
    return None

async def check_all(channels, kn, deep=False):
    sem = asyncio.Semaphore(config.CONCURRENCY); hs = {}
    conn = aiohttp.TCPConnector(limit=config.CONCURRENCY*2, ssl=False, ttl_dns_cache=300)
    prog = ui.Progress(len(channels))
    def hsem(h):
        if h not in hs: hs[h] = asyncio.Semaphore(config.HOST_CONCURRENCY)
        return hs[h]
    async with aiohttp.ClientSession(connector=conn) as s:
        async def w(ch):
            h = config.host_of((ch.get("urls") or [ch.get("url","")])[0])
            async with sem:
                async with hsem(h):
                    try: r = await _one(s, ch, kn, deep)
                    except Exception: r = None
                    prog.bump(alive=bool(r)); return r
        tasks = [w(c) for c in channels]; results = []
        for c in asyncio.as_completed(tasks):
            r = await c
            if r: results.append(r)
    return results
'''

def w(rel, c, force):
    p = ROOT / rel; p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not force: print(f"  skip  {rel}"); return
    p.write_text(c, encoding="utf-8"); print(f"  write {rel}")

if __name__ == "__main__":
    for rel, c in FILES.items(): w(rel, c, True)
