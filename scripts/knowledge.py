import json, random, time
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
