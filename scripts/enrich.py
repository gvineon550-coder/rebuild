import asyncio, json, re, time
import aiohttp
from . import config

ATTR_RE = re.compile(r'([A-Za-z0-9_\-]+)="([^"]*)"')

def _split_extinf(line):
    in_q = False
    for i, ch in enumerate(line):
        if ch == '"': in_q = not in_q
        elif ch == ',' and not in_q: return line[:i], line[i+1:].strip()
    return line, ""

def parse_m3u(text):
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith("#EXTINF"):
            m = re.match(r'#EXTINF:-?\d+\s*(.*)$', line)
            if not m: continue
            attrs_str, name = _split_extinf(m.group(1))
            cur = {"name": name, "attrs": dict(ATTR_RE.findall(attrs_str)), "extvlc": {}, "kodiprop": {}, "exthttp": {}, "url": None}
        elif cur is not None and line.startswith("#EXTVLCOPT:"):
            kv = line[len("#EXTVLCOPT:"):].strip()
            if "=" in kv:
                k, v = kv.split("=", 1); cur["extvlc"][k.strip().lower()] = v.strip()
        elif cur is not None and line.startswith("#KODIPROP:"):
            kv = line[len("#KODIPROP:"):].strip()
            if "=" in kv:
                k, v = kv.split("=", 1); cur["kodiprop"][k.strip()] = v.strip()
        elif cur is not None and line.startswith("#EXTHTTP:"):
            try:
                js = line[len("#EXTHTTP:"):].strip()
                cur["exthttp"] = json.loads(js)
            except Exception: pass
        elif line.startswith("#"): continue
        elif cur is not None:
            cur["url"] = line; out.append(cur); cur = None
    return out

def _is_junk(u):
    if not u or not re.match(r'^https?://', u): return True
    low = u.lower()
    if any(x in low for x in config.BAD_URL_PATTERNS): return True
    if any(x in low for x in ("localhost","127.0.0.1","0.0.0.0")): return True
    if re.search(r'^https?://(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)', u): return True
    return False

def _is_forbidden(name, tid, tvg_name, grp):
    text = " ".join([name or "", tid or "", tvg_name or "", grp or ""]).lower()
    for bg in config.BAD_GROUPS:
        if bg in (grp or "").lower(): return True
    for bw in config.BAD_WORDS:
        if bw in text: return True
    return False

async def _get_json(session, url):
    to = aiohttp.ClientTimeout(total=90)
    async with session.get(url, timeout=to) as r: r.raise_for_status(); return await r.json(content_type=None)

async def load_api():
    cp = config.DATA / "api_cats.json"; lp = config.DATA / "api_logos.json"; ttl = 7 * 86400
    cats_c = config.load_json(cp, {}); logos_c = config.load_json(lp, {})
    if cats_c.get("ts") and time.time()-cats_c["ts"] < ttl: cats, names, ru = cats_c["cats"], cats_c["names"], cats_c.get("ru", {})
    else:
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as s: data = await _get_json(s, config.CHANNELS_URL)
        cats, names, ru = {}, {}, {}
        for ch in data:
            cid = ch.get("id")
            if not cid: continue
            for c in (ch.get("categories") or []): cats[cid] = c.lower(); break
            nm = ch.get("name")
            if nm:
                nn = config.norm_name(nm)
                if nn: names.setdefault(nn, cid)
            for alt in (ch.get("alt_names") or []):
                if alt:
                    nn = config.norm_name(alt)
                    if nn: names.setdefault(nn, cid)
            for n in ([nm] if nm else []) + list(ch.get("alt_names") or []):
                if n and config.has_cyr(n): ru[cid] = n.strip(); break
        config.atomic_write(cp, json.dumps({"ts": int(time.time()), "cats": cats, "names": names, "ru": ru}))
    if logos_c.get("ts") and time.time()-logos_c["ts"] < ttl: logos = logos_c["logos"]
    else:
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as s: data = await _get_json(s, config.LOGOS_URL)
        logos = {}
        for rec in data:
            cid, url = rec.get("channel"), rec.get("url")
            if not cid or not url or not url.startswith("https://"): continue
            fmt = (rec.get("format") or "").upper(); ex = logos.get(cid)
            if not ex: logos[cid] = url
            elif ".svg" in ex.lower() and fmt == "PNG": logos[cid] = url
        config.atomic_write(lp, json.dumps({"ts": int(time.time()), "logos": logos}))
    return cats, names, ru, logos

def load_sources():
    out = []
    if not config.SOURCES_PATH.exists(): return out
    try:
        import yaml
        d = yaml.safe_load(config.SOURCES_PATH.read_text("utf-8")) or {}
        for s in d.get("sources", []):
            if s.get("name") and s.get("url"): out.append((s["name"], s["url"], int(s.get("priority", 5))))
        for u in d.get("extra_m3u", []): out.append((f"extra-{len(out)}", u, 9))
    except Exception: pass
    return out

async def _fetch(session, name, url, retries=2):
    for a in range(retries+1):
        try:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=aiohttp.ClientTimeout(total=90), ssl=False) as r:
                if r.status == 429: await asyncio.sleep(5*(a+1)); continue
                if r.status != 200: return name, None
                return name, await r.text(errors="ignore")
        except Exception:
            if a < retries: await asyncio.sleep(3)
    return name, None

def merge_channels(channels):
    def merge(a, b):
        r = dict(a)
        r["urls"] = list({*a.get("urls", [a.get("url")]), *b.get("urls", [b.get("url")])})
        if not r.get("logo") and b.get("logo"): r["logo"] = b["logo"]
        if not r.get("has_epg") and b.get("has_epg"): r["has_epg"] = b["has_epg"]
        if (b.get("confidence", 0) > r.get("confidence", 0)):
            r["category"] = b["category"]; r["confidence"] = b["confidence"]; r["method"] = b["method"]
        if len(b.get("name","")) > len(r.get("name","")): r["name"] = b["name"]
        
        # Слияние заголовков
        for key in ["catchup","catchup-source","catchup-days","timeshift"]:
            if not r.get("attrs", {}).get(key) and b.get("attrs", {}).get(key):
                if "attrs" not in r: r["attrs"] = {}
                r["attrs"][key] = b["attrs"][key]
        if not r.get("extvlc"): r["extvlc"] = {}
        for k, v in b.get("extvlc", {}).items():
            if k not in r["extvlc"]: r["extvlc"][k] = v
        if not r.get("kodiprop"): r["kodiprop"] = {}
        for k, v in b.get("kodiprop", {}).items():
            if k not in r["kodiprop"]: r["kodiprop"][k] = v
        if not r.get("exthttp"): r["exthttp"] = {}
        for k, v in b.get("exthttp", {}).items():
            if k not in r["exthttp"]: r["exthttp"][k] = v
        return r

    by_url, no_url = {}, []
    for c in channels:
        u = (c.get("urls") or [c.get("url","")])[0]
        if not u: no_url.append(c); continue
        k = config.normalize_url(u)
        if k not in by_url: by_url[k] = dict(c)
        else: by_url[k] = merge(by_url[k], c)
    by_tid, no_tid = {}, []
    for c in list(by_url.values()) + no_url:
        tid = (c.get("tvg_id") or "").split("@")[0].strip().lower()
        if not tid: no_tid.append(c); continue
        if tid not in by_tid: by_tid[tid] = dict(c)
        else: by_tid[tid] = merge(by_tid[tid], c)
    result = {}
    for c in list(by_tid.values()) + no_tid:
        nn = config.norm_name(c.get("name","")); host = config.host_of((c.get("urls") or [c.get("url","")])[0]); k = (nn, host)
        if k not in result: result[k] = dict(c)
        else: result[k] = merge(result[k], c)
    return list(result.values())
