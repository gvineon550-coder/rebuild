import json, time
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
