import json, time
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
