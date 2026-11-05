import time, urllib.request, ssl
import xml.etree.ElementTree as ET
from . import config

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def _process(url, matched, seen_c, seen_p, out):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=config.EPG_TIMEOUT, context=ctx) as r:
            import gzip
            f = gzip.GzipFile(fileobj=r) if url.endswith(".gz") else r
            for _, el in ET.iterparse(f, events=("end",)):
                if el.tag == "channel" and el.get("id") in matched:
                    if el.get("id") not in seen_c:
                        out.write(ET.tostring(el, encoding="utf-8")); seen_c.add(el.get("id"))
                elif el.tag == "programme" and el.get("channel") in matched:
                    k = (el.get("channel"), el.get("start"))
                    if k not in seen_p:
                        out.write(ET.tostring(el, encoding="utf-8")); seen_p.add(k)
                el.clear()
    except Exception: pass

def build(matched_ids):
    out_path = config.ROOT / "epg.xml"
    tmp = config.ROOT / "epg.xml.tmp"
    sc, sp = set(), set()
    
    with open(tmp, "wb") as out:
        out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n')
        for url in config.EPG_URLS:
            _process(url, matched_ids, sc, sp, out)
        out.write(b'</tv>\n')
        
    if not sc: return None
    if not out_path.exists() or out_path.read_bytes() != tmp.read_bytes():
        tmp.replace(out_path)
        print(f"  trimmed epg: {len(sc)} каналов, {len(sp)} программ, {out_path.stat().st_size//1024} KB")
    else:
        tmp.unlink()
        print(f"  trimmed epg: без изменений ({out_path.stat().st_size//1024} KB)")
    return out_path
