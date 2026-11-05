#!/usr/bin/env python3
import argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parent
FILES = {}

FILES["sources.yml"] = """sources:
  - name: RU-Streams
    url: https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ru.m3u
    priority: 0
  - name: RU-Language
    url: https://iptv-org.github.io/iptv/languages/rus.m3u
    priority: 1
extra_m3u: []
"""

FILES["README.md"] = """# 📺 IPTV Ultimate
<!-- STATS:START -->
Отчёт появится после первого запуска.
<!-- STATS:END -->
"""

FILES["scripts/classify.py"] = r'''import json, time
from rapidfuzz import fuzz, process
from . import config
LEARNED_FILE = config.DATA / "learned_categories.json"
def load_learned():
    d = config.load_json(LEARNED_FILE, {}); return {k: v for k, v in d.items() if v.get("ts", 0) > time.time() - 60*86400}
def save_learned(l): config.atomic_write(LEARNED_FILE, json.dumps(l, ensure_ascii=False, indent=1))
def _norm_api(r):
    if not r: return None
    g = r.strip().lower()
    if ";" in g: g = g.split(";")[0].strip()
    return config.CATEGORY_MAP.get(g)
def classify(ch, cats, names, learned):
    name = ch.get("name","").strip(); tid = (ch.get("tvg_id") or "").split("@")[0].strip().lower(); grp = ch.get("group","").strip(); nn = config.norm_name(name)
    if nn and nn in learned: return learned[nn]["cat"], 0.95, "learned"
    if tid and tid in cats:
        n = _norm_api(cats[tid])
        if n: return n, 1.0, "api_id"
    if nn and nn in names:
        cid = names[nn]
        if cid in cats:
            n = _norm_api(cats[cid])
            if n: return n, 0.95, "api_name"
    if names and name and len(name) >= 3:
        try: best = process.extractOne(name.lower(), list(names.keys()), scorer=fuzz.ratio, score_cutoff=82)
        except Exception: best = None
        if best:
            cid = names.get(best[0])
            if cid and cid in cats:
                n = _norm_api(cats[cid])
                if n: return n, 0.8, "fuzzy"
    if grp:
        g = grp.strip().lower()
        for k, v in config.CATEGORY_MAP.items():
            if g == k: return v, 0.7, "group"
    text = f"{name} {grp}".lower()
    for cat, kws in config.KEYWORD_RULES.items():
        for kw in kws:
            if kw in text: return cat, 0.6, "keyword"
    return "📦 Разное", 0.0, "none"
def maybe_learn(l, ch, cat, conf, m):
    if m != "fuzzy" or conf < 0.8: return
    nn = config.norm_name(ch.get("name",""))
    if nn and len(nn) >= 2: l[nn] = {"cat": cat, "conf": conf, "ts": int(time.time())}
'''

FILES["scripts/epg.py"] = r'''import gzip, io, json, time, urllib.request, ssl
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
from . import config
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
CACHE = config.DATA / "epg.json"
def _dl_parse(url, bn, bt, bp, ic, ru, prog_ids):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=config.EPG_TIMEOUT, context=ctx) as r:
            f = gzip.GzipFile(fileobj=r) if url.endswith(".gz") else r
            for _, el in ET.iterparse(f, events=("end",)):
                if el.tag == "channel":
                    cid = el.get("id")
                    if cid:
                        icon = el.find("icon")
                        if icon is not None and icon.get("src"): ic[cid] = icon.get("src")
                        for dn in el.findall("display-name"):
                            if dn.text:
                                orig = dn.text.strip()
                                if orig and cid not in ru and config.has_cyr(orig): ru[cid] = orig
                                nn = config.norm_name(orig)
                                if nn and len(nn) >= 2:
                                    bn.setdefault(nn, cid); tr = config.translit(nn)
                                    if tr: bt.setdefault(tr, cid)
                                    if len(nn[:6]) >= 3: bp.setdefault(nn[:6], []).append((nn, cid))
                    el.clear()
                elif el.tag == "programme":
                    cid = el.get("channel")
                    if cid: prog_ids.add(cid)
                    el.clear()
    except Exception: pass
def load():
    if CACHE.exists():
        try:
            d = json.loads(CACHE.read_text("utf-8"))
            if time.time() - d.get("ts", 0) < config.EPG_TTL_HOURS*3600:
                return (d.get("bn",{}), d.get("bt",{}), {k: [tuple(x) for x in v] for k, v in d.get("bp",{}).items()}, d.get("ic",{}), d.get("ru",{}), set(d.get("prog_ids",[])))
        except Exception: pass
    bn, bt, bp, ic, ru, prog_ids = {}, {}, {}, {}, {}, set()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for url in config.EPG_URLS: ex.submit(_dl_parse, url, bn, bt, bp, ic, ru, prog_ids)
    if bn and prog_ids: config.atomic_write(CACHE, json.dumps({"ts": int(time.time()), "bn": bn, "bt": bt, "bp": {k: list(v) for k, v in bp.items()}, "ic": ic, "ru": ru, "prog_ids": list(prog_ids)}, ensure_ascii=False))
    return bn, bt, bp, ic, ru, prog_ids
def _resolve(name, bn, bt, bp):
    nn = config.norm_name(name)
    if not nn: return ""
    if nn in bn: return bn[nn]
    tr = config.translit(nn)
    if tr and tr in bt: return bt[tr]
    if len(nn[:6]) >= 3 and nn[:6] in bp:
        c = bp[nn[:6]]
        if len(c) <= 3: return c[0][1]
    for key in (" ".join(nn.split()[:2]), nn[:4]):
        if len(key) < 3: continue
        best, br = None, 0
        for nm, cid in bp.get(key, []):
            r = SequenceMatcher(None, nn, nm).ratio() * 100
            if r > br: br, best = r, cid
        if best and br >= 88: return best
    return ""
def match_channel(ch, idx):
    bn, bt, bp, ic, ru, prog_ids = idx
    if not prog_ids: return None, None
    tid = ch.get("tvg_id",""); base = tid.split("@")[0] if tid else ""; sfx = config.extract_suffix(tid)
    if (tid in prog_ids) or (base and base in prog_ids):
        name_ru = (ru.get(base,"") + " " + sfx).strip() if base in ru else None
        return tid, name_ru
    cid = _resolve(ch.get("name",""), bn, bt, bp)
    if cid and (cid in prog_ids or cid.split("@")[0] in prog_ids):
        name_ru = (ru.get(cid,"") + " " + sfx).strip() if cid in ru else None
        return cid, name_ru
    return None, None
'''

FILES["scripts/epg_trim.py"] = r'''import gzip, io, time, urllib.request, ssl
import xml.etree.ElementTree as ET
from . import config
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
def _process(url, matched, seen_c, seen_p, out):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=config.EPG_TIMEOUT, context=ctx) as r:
            f = gzip.GzipFile(fileobj=r) if url.endswith(".gz") else r
            for _, el in ET.iterparse(f, events=("end",)):
                if el.tag == "channel" and el.get("id") in matched:
                    if el.get("id") not in seen_c: out.write(ET.tostring(el, encoding="utf-8")); seen_c.add(el.get("id"))
                elif el.tag == "programme" and el.get("channel") in matched:
                    k = (el.get("channel"), el.get("start"))
                    if k not in seen_p: out.write(ET.tostring(el, encoding="utf-8")); seen_p.add(k)
                el.clear()
    except Exception: pass
def build(matched_ids):
    out_path = config.ROOT / "epg.xml.gz"; tmp = config.ROOT / "epg.xml.gz.tmp"; sc, sp = set(), set()
    with gzip.GzipFile(filename=str(tmp), mode="wb", mtime=0, compresslevel=9) as out:
        out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n')
        for url in config.EPG_URLS: _process(url, matched_ids, sc, sp, out)
        out.write(b'</tv>\n')
    if not sc: return None
    if not out_path.exists() or out_path.read_bytes() != tmp.read_bytes(): tmp.replace(out_path); print(f"  trimmed epg: {len(sc)} каналов, {len(sp)} программ, {out_path.stat().st_size//1024} KB")
    else: tmp.unlink(); print(f"  trimmed epg: без изменений ({out_path.stat().st_size//1024} KB)")
    return out_path
'''

FILES["scripts/enrich.py"] = r'''import asyncio, json, re, time
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
            cur = {"name": name, "attrs": dict(ATTR_RE.findall(attrs_str)), "extvlc": {}, "url": None}
        elif cur is not None and line.startswith("#EXTVLCOPT:"):
            kv = line[len("#EXTVLCOPT:"):].strip()
            if "=" in kv:
                k, v = kv.split("=", 1); cur["extvlc"][k.strip().lower()] = v.strip()
        elif line.startswith("#"): continue
        elif cur is not None: cur["url"] = line; out.append(cur); cur = None
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
        r = dict(a); r["urls"] = list({*a.get("urls", [a.get("url")]), *b.get("urls", [b.get("url")])})
        if not r.get("logo") and b.get("logo"): r["logo"] = b["logo"]
        if not r.get("has_epg") and b.get("has_epg"): r["has_epg"] = b["has_epg"]
        if (b.get("confidence", 0) > r.get("confidence", 0)): r["category"] = b["category"]; r["confidence"] = b["confidence"]; r["method"] = b["method"]
        if len(b.get("name","")) > len(r.get("name","")): r["name"] = b["name"]
        for key in ["catchup","catchup-source","catchup-days","timeshift"]:
            if not r.get("attrs", {}).get(key) and b.get("attrs", {}).get(key):
                if "attrs" not in r: r["attrs"] = {}
                r["attrs"][key] = b["attrs"][key]
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
'''

FILES["scripts/build_output.py"] = r'''import json, time
from datetime import datetime, timezone, timedelta
from collections import Counter
from . import config
def write_playlist(channels, epg_url):
    lines = [f'#EXTM3U url-tvg="{epg_url}" tvg-shift="0"']
    for c in channels:
        urls = c.get("urls") or [c.get("url")]; urls = [c["url"]] + [u for u in urls if u != c["url"]]
        for i, u in enumerate(urls):
            attrs = []
            if c.get("tvg_id"): attrs.append(f'tvg-id="{c["tvg_id"]}"')
            if c.get("tvg_name"): attrs.append(f'tvg-name="{c["tvg_name"]}"')
            if c.get("logo"): attrs.append(f'tvg-logo="{c["logo"]}"')
            attrs.append(f'group-title="{c.get("category") or "📦 Разное"}"')
            for key in ["catchup","catchup-source","catchup-days","timeshift"]:
                v = c.get("attrs", {}).get(key)
                if v: attrs.append(f'{key}="{v}"')
            name = c["name"] + (f" [Зеркало {i+1}]" if i > 0 else "")
            lines.append(f'#EXTINF:-1 {" ".join(attrs)},{name}')
            if c.get("extvlc", {}).get("http-user-agent"): lines.append(f'#EXTVLCOPT:http-user-agent={c["extvlc"]["http-user-agent"]}')
            if c.get("extvlc", {}).get("http-referrer"): lines.append(f'#EXTVLCOPT:http-referrer={c["extvlc"]["http-referrer"]}')
            lines.append(u)
    config.atomic_write(config.PLAYLIST_PATH, "\n".join(lines) + "\n")
def write_report(channels, total, elapsed, filtered):
    grp = Counter(c.get("category","📦 Разное") for c in channels)
    rep = {"total": total, "alive": len(channels), "dead": total - len(channels), "with_epg": sum(1 for c in channels if c.get("has_epg")), "with_logo": sum(1 for c in channels if c.get("logo")), "with_archive": sum(1 for c in channels if c.get("attrs", {}).get("catchup")), "elapsed": round(elapsed, 1), "categories": dict(grp), "mode": "DEEP" if config.DEEP_CHECK else "normal", "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "channels": [{"name": c["name"], "url": c["url"], "urls": c.get("urls", []), "ua": c.get("profile",""), "group": c.get("category",""), "tvg_id": c.get("tvg_id",""), "logo": c.get("logo","")} for c in channels]}
    config.atomic_write(config.REPORT_PATH, json.dumps(rep, ensure_ascii=False, indent=2)); return rep
def update_readme(rep):
    if not config.README_PATH.exists(): return
    text = config.README_PATH.read_text("utf-8"); s, e = "<!-- STATS:START -->", "<!-- STATS:END -->"
    if s not in text or e not in text: return
    pre, _, rest = text.partition(s); _, _, post = rest.partition(e)
    block = f"**Обновлено:** `{datetime.now(timezone(timedelta(hours=3))).strftime('%Y-%m-%d %H:%M MSK')}`\n\n| Метрика | Значение |\n|---|---|\n| Проверено | `{rep['total']}` |\n| Живых | **`{rep['alive']}`** |\n| С EPG | `{rep['with_epg']}` |\n| С лого | `{rep['with_logo']}` |\n| С архивом | `{rep['with_archive']}` |\n| Время | `{rep['elapsed']} с` |\n"
    config.atomic_write(config.README_PATH, pre + s + "\n" + block + "\n" + e + post)
'''

FILES["scripts/run_all.py"] = r'''import asyncio, os, time
from . import config, ui, checker, enrich, epg, epg_trim, classify, build_output
from .knowledge import Knowledge
async def main():
    start = time.time(); print("=== Stream Audit ==="); ui.info(f"Старт: {ui.msk_now()}")
    api_cats, api_names, api_ru, api_logos = await enrich.load_api(); ui.info(f"API: {len(api_cats)} категорий, {len(api_logos)} логотипов")
    epg_idx = epg.load(); ui.info(f"EPG: {len(epg_idx[0])} имён, {len(epg_idx[3])} иконок")
    ui.info("Загрузка источников...")
    sources = enrich.load_sources(); import aiohttp
    conn = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=conn) as session: results = await asyncio.gather(*[enrich._fetch(session, n, u) for n, u, _ in sources])
    raw_channels = []; learned = classify.load_learned()
    for (sname, _, _), (_, text) in zip(sources, results):
        if not text: continue
        parsed = enrich.parse_m3u(text); kept = 0
        for ch in parsed:
            n, u, a = ch["name"], ch["url"], ch["attrs"]
            if enrich._is_junk(u): continue
            tid = a.get("tvg-id","")
            if enrich._is_forbidden(n, tid, a.get("tvg-name",""), a.get("group-title","")): continue
            chan = {"name": n, "url": u, "urls": [u], "tvg_id": tid, "tvg_name": a.get("tvg-name",""), "logo": a.get("tvg-logo",""), "group": a.get("group-title",""), "extvlc": ch["extvlc"], "has_epg": False, "attrs": a}
            cat, conf, method = classify.classify(chan, api_cats, api_names, learned)
            chan["category"] = cat; chan["confidence"] = conf; chan["method"] = method; classify.maybe_learn(learned, chan, cat, conf, method)
            if not chan["logo"]:
                base = tid.split("@")[0] if tid else ""
                if base in api_logos: chan["logo"] = api_logos[base]
            new_tid, name_ru = epg.match_channel(chan, epg_idx)
            if new_tid:
                chan["tvg_id"] = new_tid; chan["has_epg"] = True
                if name_ru and config.has_cyr(name_ru): chan["name"] = name_ru
            raw_channels.append(chan); kept += 1
        ui.ok(f"{sname}: {kept}")
    classify.save_learned(learned); merged = enrich.merge_channels(raw_channels); ui.info(f"Всего каналов после дедупа: {len(merged)}")
    matched_ids = set(c["tvg_id"] for c in merged if c.get("tvg_id")); ui.info(f"Матчинг EPG: {len(matched_ids)} ID")
    trimmed = epg_trim.build(matched_ids); ui.info(f"Проверка ({len(merged)} шт.)...")
    kn = Knowledge(); alive_raw = await checker.check_all(merged, kn, config.DEEP_CHECK); kn.save_all()
    alive = []
    for r in alive_raw:
        c = dict(r["channel"]); c["url"] = r["url"]; c["urls"] = r["urls"]; c["profile"] = r["profile"]; c["height"] = r["height"]
        if r.get("referer"):
            if "extvlc" not in c: c["extvlc"] = {}
            c["extvlc"]["http-referrer"] = r["referer"]
        alive.append(c)
    threshold = max(config.MIN_ALIVE_ABS, int(len(merged) * config.MIN_ALIVE_PCT))
    if len(alive) < threshold: ui.err(f"Sanity: {len(alive)} < {threshold}. Публикация отменена."); return
    repo = os.getenv("GITHUB_REPOSITORY", ""); branch = os.getenv("GITHUB_REF_NAME", "main")
    epg_url = f"https://raw.githubusercontent.com/{repo}/{branch}/epg.xml.gz" if (trimmed and repo) else config.EPG_URLS[0]
    build_output.write_playlist(alive, epg_url); report = build_output.write_report(alive, len(merged), time.time()-start, {}); build_output.update_readme(report)
    print("=========================================")
    ui.ok(f"Готово за {time.time()-start:.1f}s"); ui.ok(f"Всего:   {len(merged)}"); ui.ok(f"Рабочих: {len(alive)}"); ui.ok(f"Мёртвых: {len(merged) - len(alive)}"); ui.ok(f"С EPG:   {report['with_epg']}")
if __name__ == "__main__": asyncio.run(main())
'''

def w(rel, c):
    p = ROOT / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(c, encoding="utf-8"); print(f"  write {rel}")

if __name__ == "__main__":
    for rel, c in FILES.items(): w(rel, c)
