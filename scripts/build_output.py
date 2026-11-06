import json, os, time
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
            
            # Выводим все заголовки (UA, Referer, Cookie, Kodi, HTTP)
            ev = c.get("extvlc", {})
            if ev.get("http-user-agent"): lines.append(f'#EXTVLCOPT:http-user-agent={ev["http-user-agent"]}')
            if ev.get("http-referrer"): lines.append(f'#EXTVLCOPT:http-referrer={ev["http-referrer"]}')
            if ev.get("http-cookie"): lines.append(f'#EXTVLCOPT:http-cookie={ev["http-cookie"]}')
            for k, v in c.get("kodiprop", {}).items():
                lines.append(f'#KODIPROP:{k}={v}')
            if c.get("exthttp"):
                lines.append(f'#EXTHTTP:{json.dumps(c["exthttp"])}')
                
            lines.append(u)
    config.atomic_write(config.PLAYLIST_PATH, "\n".join(lines) + "\n")

def write_report(channels, total, elapsed, filtered):
    grp = Counter(c.get("category","📦 Разное") for c in channels)
    rep = {
        "total": total, 
        "alive": len(channels), 
        "dead": total - len(channels), 
        "with_epg": sum(1 for c in channels if c.get("has_epg")), 
        "with_logo": sum(1 for c in channels if c.get("logo")), 
        "with_archive": sum(1 for c in channels if c.get("attrs", {}).get("catchup")), 
        "elapsed": round(elapsed, 1), 
        "categories": dict(grp), 
        "mode": "DEEP" if config.DEEP_CHECK else "normal", 
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), 
        "channels": [
            {"name": c["name"], "url": c["url"], "urls": c.get("urls", []), 
             "ua": c.get("profile",""), "group": c.get("category",""), 
             "tvg_id": c.get("tvg_id",""), "logo": c.get("logo","")} 
            for c in channels
        ]
    }
    config.atomic_write(config.REPORT_PATH, json.dumps(rep, ensure_ascii=False, indent=2))
    return rep

def update_readme(rep):
    repo = os.getenv("GITHUB_REPOSITORY", "user/repo")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}"
    
    epg_file = "epg.xml" if (config.ROOT / "epg.xml").exists() else "epg.xml.gz"
    playlist_url = f"{raw_url}/playlist.m3u"
    epg_url = f"{raw_url}/{epg_file}"
    
    total = rep["total"]; alive = rep["alive"]; dead = rep["dead"]
    pct = (alive / total * 100) if total else 0
    with_epg = rep["with_epg"]; with_logo = rep["with_logo"]
    elapsed = rep["elapsed"]; mode = rep["mode"]
    date_str = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M MSK")
    
    badge_alive = f"![живых](https://img.shields.io/badge/живых-{alive}-brightgreen?style=flat-square)"
    badge_total = f"![всего](https://img.shields.io/badge/всего-{total}-blue?style=flat-square)"
    badge_epg = f"![EPG](https://img.shields.io/badge/EPG-{with_epg}-cyan?style=flat-square)"
    badge_logo = f"![лого](https://img.shields.io/badge/лого-{with_logo}-purple?style=flat-square)"
    
    cats = rep.get("categories", {})
    top_cats = sorted(cats.items(), key=lambda x: -x[1])[:10]
    cat_rows = "\n".join(f"| {k} | {v} |" for k, v in top_cats)
    
    bar_len = 20
    filled = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    content = f"""# 📺 IPTV Ultimate Checker

> Автономный, самообучающийся чекер публичных IPTV-потоков на GitHub Actions.
> Проверяет тысячи каналов, отсекает мертвое и рекламу, склеивает EPG и собирает чистый плейлист.

{badge_alive} {badge_total} {badge_epg} {badge_logo}

---

## 🔗 Ссылки

**Плейлист (M3U):**
```text
{playlist_url}
