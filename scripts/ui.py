from datetime import datetime, timezone, timedelta
def msk_now(): return datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M MSK")
def info(msg): print(f"[*] {msg}", flush=True)
def ok(msg): print(f"[+] {msg}", flush=True)
def warn(msg): print(f"[!] {msg}", flush=True)
def err(msg): print(f"[-] {msg}", flush=True)
class Progress:
    def __init__(self, total, step=5):
        self.total = total; self.step = step; self.done = 0; self.alive = 0; self._last_pct = -1
    def bump(self, alive=False):
        self.done += 1
        if alive: self.alive += 1
        pct = int(self.done * 100 / self.total) if self.total else 100
        if pct >= self._last_pct + self.step or self.done == self.total:
            self._last_pct = pct; self._render()
    def _render(self):
        dead = self.done - self.alive
        w = 40; f = int(w * self.done / self.total) if self.total else w
        bar = "█" * f + "░" * (w - f)
        pct = self.done * 100 // self.total if self.total else 100
        print(f"[{bar}] {pct}% ({self.done}/{self.total}) | Живых: {self.alive} | Упало: {dead}", flush=True)
