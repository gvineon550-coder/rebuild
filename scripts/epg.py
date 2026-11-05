import gzip, io, json, time, urllib.request, ssl
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
