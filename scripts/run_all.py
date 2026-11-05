import asyncio, os, time
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
