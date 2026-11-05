import asyncio, random, re, time
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
