"""nexus_netmon.py - Network Monitor plugin for NEXUS ULTRA (single file, stdlib only).

Usage:
    from nexus_netmon import open_window, NetworkMonitorFrame
    open_window(root, lang="fa")
Author: ArrowDeveloper
"""
from __future__ import annotations

import csv
import json
import os
import platform
import queue
import re
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime

__all__ = [
    "Config", "Storage", "Monitor",
    "compute_stats", "aggregate", "fmt_duration",
    "ping_icmp", "ping_tcp", "measure_download", "measure_upload",
]

_IS_WIN = platform.system() == "Windows"
_PING_RE = re.compile(r"time\s*[=<]\s*([\d.,]+)\s*ms", re.I)
_USER_AGENT = "NetworkMonitor/1.0"

DEFAULT_TARGETS = [["Google", "8.8.8.8"], ["Cloudflare", "1.1.1.1"], ["Quad9", "9.9.9.9"]]


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    targets: list = field(default_factory=lambda: [list(t) for t in DEFAULT_TARGETS])
    interval: float = 2.0          # seconds between ping rounds
    timeout: float = 1.5           # per-ping timeout (seconds)
    method: str = "icmp"           # "icmp" (system ping) or "tcp" (connect time)
    tcp_port: int = 443
    window: int = 90               # samples shown on the chart
    outage_threshold: int = 3      # consecutive full-failure rounds = outage
    keep_days: int = 14            # raw samples older than this are pruned
    ping_alert_ms: float = 150.0   # "High ping" threshold
    download_urls: list = field(default_factory=lambda: [
        "https://speed.cloudflare.com/__down?bytes=50000000",
        "https://proof.ovh.net/files/10Mb.dat",
    ])
    upload_url: str = "https://speed.cloudflare.com/__up"
    upload_bytes: int = 4_000_000
    test_seconds: float = 8.0
    db_path: str = "netmon.db"

    def normalize(self) -> "Config":
        fixed = []
        for t in self.targets:
            if isinstance(t, str):
                t = [t, t]
            t = list(t)
            if len(t) == 1:
                t = [t[0], t[0]]
            fixed.append([str(t[0]), str(t[1])])
        self.targets = fixed or [list(x) for x in DEFAULT_TARGETS]
        self.interval = max(0.5, float(self.interval))
        self.timeout = max(0.3, float(self.timeout))
        self.window = max(10, int(self.window))
        self.outage_threshold = max(1, int(self.outage_threshold))
        self.keep_days = max(1, int(self.keep_days))
        self.tcp_port = int(self.tcp_port)
        if self.method not in ("icmp", "tcp"):
            self.method = "icmp"
        return self

    def save(self, path: str) -> None:
        data = asdict(self)
        data.pop("db_path", None)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, data_dir: str) -> "Config":
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, "config.json")
        cfg = cls()
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
                for key, value in raw.items():
                    if key in cls.__dataclass_fields__ and key != "db_path":
                        setattr(cfg, key, value)
                cfg.normalize()
            except (OSError, ValueError, TypeError):
                cfg = cls().normalize()
        else:
            cfg.normalize()
            try:
                cfg.save(path)
            except OSError:
                pass
        cfg.db_path = os.path.join(data_dir, "netmon.db")
        return cfg


# --------------------------------------------------------------------------- #
# Ping
# --------------------------------------------------------------------------- #
def ping_tcp(host: str, port: int = 443, timeout: float = 1.5):
    """Return connect time in ms, or None on failure."""
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return None
    return (time.perf_counter() - t0) * 1000.0


def ping_icmp(host: str, timeout: float = 1.5, tcp_port: int = 443):
    """Use the system `ping` command. Returns ms or None.

    Falls back to a TCP connect if `ping` is not available.
    """
    if _IS_WIN:
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
        extra = {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(round(timeout)))), host]
        extra = {}
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="ignore",
            timeout=timeout + 1.5, **extra,
        )
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return ping_tcp(host, tcp_port, timeout)
    out = proc.stdout or ""
    match = _PING_RE.search(out)
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None
    # localized output: trust a zero exit code together with a TTL marker
    if proc.returncode == 0 and "ttl" in out.lower():
        return (time.perf_counter() - t0) * 1000.0
    return None


# --------------------------------------------------------------------------- #
# Stats helpers
# --------------------------------------------------------------------------- #
def compute_stats(samples):
    """samples: list of ms values or None (lost)."""
    ok = [s for s in samples if s is not None]
    loss = 100.0 * (len(samples) - len(ok)) / len(samples) if samples else 0.0
    jitter = (sum(abs(a - b) for a, b in zip(ok, ok[1:])) / (len(ok) - 1)) if len(ok) > 1 else 0.0
    return {
        "last": samples[-1] if samples else None,
        "avg": sum(ok) / len(ok) if ok else None,
        "min": min(ok) if ok else None,
        "max": max(ok) if ok else None,
        "jitter": jitter,
        "loss": loss,
    }


def aggregate(snapshot):
    """Combine per-target series into the numbers shown on the dashboard."""
    everything = [v for s in snapshot.values() for v in s]
    ok = [v for v in everything if v is not None]
    latest = [s[-1] for s in snapshot.values() if s and s[-1] is not None]
    jitters = [compute_stats(s)["jitter"] for s in snapshot.values()
               if sum(1 for v in s if v is not None) > 1]
    return {
        "latest": sum(latest) / len(latest) if latest else None,
        "avg": sum(ok) / len(ok) if ok else None,
        "jitter": sum(jitters) / len(jitters) if jitters else None,
        "loss": 100.0 * (len(everything) - len(ok)) / len(everything) if everything else 0.0,
    }


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


# --------------------------------------------------------------------------- #
# Storage (SQLite)
# --------------------------------------------------------------------------- #
class Storage:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS samples(ts REAL NOT NULL, target TEXT NOT NULL, ms REAL);
    CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
    CREATE TABLE IF NOT EXISTS outages(
        id INTEGER PRIMARY KEY AUTOINCREMENT, start REAL NOT NULL, end REAL);
    CREATE TABLE IF NOT EXISTS speed_tests(ts REAL NOT NULL, download REAL, upload REAL);
    """

    def __init__(self, path: str):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        with self._lock:
            self._db.executescript(self.SCHEMA)
            self._db.commit()
        self.close_dangling()

    def close(self) -> None:
        with self._lock:
            try:
                self._db.commit()
                self._db.close()
            except sqlite3.Error:
                pass

    # -- writes
    def add_samples(self, ts, rows):
        with self._lock:
            self._db.executemany(
                "INSERT INTO samples(ts, target, ms) VALUES (?,?,?)",
                [(ts, name, ms) for name, ms in rows])
            self._db.commit()

    def start_outage(self, start) -> int:
        with self._lock:
            cur = self._db.execute("INSERT INTO outages(start) VALUES (?)", (start,))
            self._db.commit()
            return cur.lastrowid

    def end_outage(self, outage_id, end) -> None:
        with self._lock:
            self._db.execute("UPDATE outages SET end=? WHERE id=?", (end, outage_id))
            self._db.commit()

    def close_dangling(self) -> None:
        """Close outages left open by a crash or forced exit."""
        with self._lock:
            last = self._db.execute("SELECT MAX(ts) FROM samples").fetchone()[0]
            rows = self._db.execute("SELECT id, start FROM outages WHERE end IS NULL").fetchall()
            for oid, start in rows:
                self._db.execute("UPDATE outages SET end=? WHERE id=?",
                                 (max(start, last or start), oid))
            self._db.commit()

    def add_speed(self, ts, download, upload) -> None:
        with self._lock:
            self._db.execute("INSERT INTO speed_tests(ts, download, upload) VALUES (?,?,?)",
                             (ts, download, upload))
            self._db.commit()

    def prune(self, keep_days: int) -> None:
        with self._lock:
            self._db.execute("DELETE FROM samples WHERE ts < ?", (time.time() - keep_days * 86400,))
            self._db.commit()

    # -- reads
    def outages(self, limit: int = 30):
        with self._lock:
            return self._db.execute(
                "SELECT start, end FROM outages ORDER BY start DESC LIMIT ?", (limit,)).fetchall()

    def last_speed(self):
        with self._lock:
            return self._db.execute(
                "SELECT download, upload FROM speed_tests ORDER BY ts DESC LIMIT 1").fetchone()

    def daily_summary(self, days: int = 7):
        cutoff = time.time() - days * 86400
        with self._lock:
            rows = self._db.execute(
                "SELECT date(ts,'unixepoch','localtime') AS d, AVG(ms), "
                "100.0*SUM(CASE WHEN ms IS NULL THEN 1 ELSE 0 END)/COUNT(*), COUNT(*) "
                "FROM samples WHERE ts >= ? GROUP BY d ORDER BY d DESC", (cutoff,)).fetchall()
            outs = self._db.execute(
                "SELECT start, end FROM outages WHERE start >= ?", (cutoff,)).fetchall()
        per_day = {}
        now = time.time()
        for start, end in outs:
            key = datetime.fromtimestamp(start).strftime("%Y-%m-%d")
            count, down = per_day.get(key, (0, 0.0))
            per_day[key] = (count + 1, down + ((end if end is not None else now) - start))
        result = []
        for day, avg, loss, n in rows:
            count, down = per_day.get(day, (0, 0.0))
            result.append({"day": day, "avg": avg, "loss": loss, "samples": n,
                           "outages": count, "downtime": down})
        return result

    def export_csv(self, directory: str):
        """Write samples.csv, outages.csv, speed_tests.csv. Returns the file paths."""
        def iso(ts):
            return "" if ts is None else datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")

        paths = []
        with self._lock:
            samples = self._db.execute("SELECT ts, target, ms FROM samples ORDER BY ts").fetchall()
            outs = self._db.execute("SELECT start, end FROM outages ORDER BY start").fetchall()
            speeds = self._db.execute("SELECT ts, download, upload FROM speed_tests ORDER BY ts").fetchall()
        jobs = [
            ("samples.csv", ["time", "target", "ping_ms"],
             [(iso(t), n, "" if m is None else round(m, 2)) for t, n, m in samples]),
            ("outages.csv", ["start", "end", "duration_seconds"],
             [(iso(s), iso(e), "" if e is None else int(e - s)) for s, e in outs]),
            ("speed_tests.csv", ["time", "download_mbps", "upload_mbps"],
             [(iso(t), "" if d is None else round(d, 2), "" if u is None else round(u, 2))
              for t, d, u in speeds]),
        ]
        for name, header, rows in jobs:
            path = os.path.join(directory, name)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel-friendly
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
            paths.append(path)
        return paths


# --------------------------------------------------------------------------- #
# Speed test
# --------------------------------------------------------------------------- #
def measure_download(cfg: Config, progress=None) -> float:
    """Download for up to cfg.test_seconds. Returns Mbps."""
    last = None
    for url in cfg.download_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            total = 0
            with urllib.request.urlopen(req, timeout=10) as resp:
                t0 = time.perf_counter()          # start timing after headers arrive
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    elapsed = time.perf_counter() - t0
                    if progress and elapsed > 0.25:
                        progress(total * 8 / elapsed / 1e6)
                    if elapsed >= cfg.test_seconds:
                        break
            elapsed = time.perf_counter() - t0
            if total > 0 and elapsed > 0:
                return total * 8 / elapsed / 1e6
            last = RuntimeError("empty response")
        except Exception as exc:  # noqa: BLE001 - try the next URL
            last = exc
    raise RuntimeError(f"download test failed: {last}")


def measure_upload(cfg: Config) -> float:
    """Upload cfg.upload_bytes once. Returns Mbps (approximate, includes handshake)."""
    if not cfg.upload_url:
        raise RuntimeError("no upload url configured")
    data = bytes(cfg.upload_bytes)
    req = urllib.request.Request(
        cfg.upload_url, data=data, method="POST",
        headers={"User-Agent": _USER_AGENT, "Content-Type": "application/octet-stream"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()
    elapsed = time.perf_counter() - t0
    if elapsed <= 0:
        raise RuntimeError("upload timing failed")
    return len(data) * 8 / elapsed / 1e6


# --------------------------------------------------------------------------- #
# Monitor
# --------------------------------------------------------------------------- #
class Monitor:
    """Background pinger. Push events to `events`: ("tick", ts), ("outage_start", ts),
    ("outage_end", seconds), ("error", message)."""

    def __init__(self, cfg: Config, storage: Storage | None = None, ping_fn=None):
        self.cfg = cfg
        self.storage = storage or Storage(cfg.db_path)
        self._ping_fn = ping_fn
        self.history = {name: deque(maxlen=cfg.window) for name, _ in cfg.targets}
        self.events: "queue.Queue" = queue.Queue()
        self.online = None            # None = unknown yet
        self._lock = threading.Lock()         # guards history
        self._state = threading.Lock()        # guards outage state
        self._active = False
        self._stop = threading.Event()
        self._streak = 0
        self._streak_start = None
        self._outage_id = None
        self._outage_start = None
        self._cycles = 0

    # -- control
    @property
    def running(self) -> bool:
        return self._active

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        self._stop = threading.Event()
        pool = ThreadPoolExecutor(max_workers=max(1, len(self.cfg.targets)))
        threading.Thread(target=self._run, args=(self._stop, pool),
                         daemon=True, name="netmon-worker").start()

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        self._stop.set()
        with self._state:
            self._close_outage(time.time())
            self._streak = 0
            self._streak_start = None
            self.online = None

    # -- internals
    def _ping(self, host: str):
        try:
            if self._ping_fn:
                return self._ping_fn(host)
            if self.cfg.method == "tcp":
                return ping_tcp(host, self.cfg.tcp_port, self.cfg.timeout)
            return ping_icmp(host, self.cfg.timeout, self.cfg.tcp_port)
        except Exception:  # noqa: BLE001
            return None

    def _close_outage(self, ts: float) -> None:
        if self._outage_id is not None:
            self.storage.end_outage(self._outage_id, ts)
            self.events.put(("outage_end", ts - self._outage_start))
            self._outage_id = None
            self._outage_start = None

    def _track(self, ts: float, results) -> None:
        with self._state:
            if any(r is not None for r in results):
                self._streak = 0
                self._streak_start = None
                self._close_outage(ts)
                self.online = True
                return
            if self._streak == 0:
                self._streak_start = ts
            self._streak += 1
            if self._streak >= self.cfg.outage_threshold:
                if self._outage_id is None:
                    self._outage_start = self._streak_start
                    self._outage_id = self.storage.start_outage(self._streak_start)
                    self.events.put(("outage_start", self._streak_start))
                self.online = False

    def _cycle(self, stop: threading.Event, pool) -> None:
        ts = time.time()
        targets = self.cfg.targets
        results = list(pool.map(lambda t: self._ping(t[1]), targets))
        if stop.is_set():
            return
        with self._lock:
            for (name, _), ms in zip(targets, results):
                self.history[name].append(ms)
        self.storage.add_samples(ts, [(t[0], ms) for t, ms in zip(targets, results)])
        self._track(ts, results)
        self.events.put(("tick", ts))

    def _run(self, stop: threading.Event, pool) -> None:
        try:
            while not stop.is_set():
                t0 = time.monotonic()
                try:
                    self._cycle(stop, pool)
                except Exception as exc:  # noqa: BLE001
                    self.events.put(("error", str(exc)))
                self._cycles += 1
                if self._cycles % 60 == 0:
                    try:
                        self.storage.prune(self.cfg.keep_days)
                    except Exception:  # noqa: BLE001
                        pass
                stop.wait(max(0.0, self.cfg.interval - (time.monotonic() - t0)))
        finally:
            pool.shutdown(wait=False)

    # -- public helpers
    def poll_once(self) -> None:
        """Run one synchronous round (used by tests)."""
        with ThreadPoolExecutor(max_workers=max(1, len(self.cfg.targets))) as pool:
            self._cycle(threading.Event(), pool)

    def snapshot(self):
        with self._lock:
            return {name: list(values) for name, values in self.history.items()}


"""Network Monitor - Tkinter UI.

`NetworkMonitorFrame` is a normal tk.Frame, so it can be used as the main window
content, inside a Notebook tab, or in a Toplevel (see `open_window`).
Author: ArrowDeveloper
"""

import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox


DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "netmon_data")

DARK = {
    "bg": "#0f1115", "panel": "#171a21", "fg": "#e6e9ef", "muted": "#8b93a7",
    "accent": "#4f8cff", "ok": "#2ecc71", "bad": "#ff4d5e", "warn": "#f5a524", "grid": "#262b36",
}
LIGHT = {
    "bg": "#f3f5f9", "panel": "#ffffff", "fg": "#1b2030", "muted": "#6b7385",
    "accent": "#2f6df6", "ok": "#1faa59", "bad": "#e5384b", "warn": "#d98a00", "grid": "#e3e7ef",
}
SERIES = ["#4f8cff", "#2ecc71", "#f5a524", "#c77dff", "#ff6b9d"]

FONT = "Segoe UI"
F_TITLE = (FONT, 15, "bold")
F_BIG = (FONT, 17, "bold")
F_BOLD = (FONT, 10, "bold")
F_BASE = (FONT, 10)
F_SMALL = (FONT, 9)
F_TINY = (FONT, 8)
F_MONO = ("Consolas", 10)

STRINGS = {
    "en": {
        "title": "Network Monitor", "online": "Online", "offline": "Offline",
        "checking": "Checking…", "stopped": "Stopped", "high": "High ping",
        "ping": "Ping", "avg": "Average", "jitter": "Jitter", "loss": "Packet loss",
        "download": "Download", "upload": "Upload",
        "speed_test": "Speed test", "testing": "Testing…",
        "start": "Start", "stop": "Stop", "export": "Export CSV", "report": "7-day report",
        "theme": "Theme", "outages": "Outages", "no_outages": "No outages recorded",
        "ongoing": "ongoing", "exported": "Files saved:", "speed_failed": "Speed test failed",
        "no_data": "No data yet", "alert_outage": "Internet connection lost",
        "alert_back": "Internet connection restored",
    },
    "fa": {
        "title": "مانیتور شبکه", "online": "آنلاین", "offline": "آفلاین",
        "checking": "در حال بررسی…", "stopped": "متوقف", "high": "پینگ بالا",
        "ping": "پینگ", "avg": "میانگین", "jitter": "جیتر", "loss": "افت بسته",
        "download": "دانلود", "upload": "آپلود",
        "speed_test": "تست سرعت", "testing": "در حال تست…",
        "start": "شروع", "stop": "توقف", "export": "خروجی CSV", "report": "گزارش ۷ روزه",
        "theme": "تم", "outages": "قطعی‌ها", "no_outages": "قطعی‌ای ثبت نشده",
        "ongoing": "در جریان", "exported": "فایل‌ها ذخیره شد:", "speed_failed": "تست سرعت ناموفق بود",
        "no_data": "هنوز داده‌ای نیست", "alert_outage": "اینترنت قطع شد",
        "alert_back": "اینترنت وصل شد",
    },
}


def _roles(P):
    return {
        "bg": {"bg": P["bg"]},
        "panel": {"bg": P["panel"]},
        "title": {"bg": P["bg"], "fg": P["fg"]},
        "muted_bg": {"bg": P["bg"], "fg": P["muted"]},
        "muted_panel": {"bg": P["panel"], "fg": P["muted"]},
        "value": {"bg": P["panel"], "fg": P["fg"]},
        "button": {"bg": P["grid"], "fg": P["fg"], "activebackground": P["accent"],
                   "activeforeground": "#ffffff", "disabledforeground": P["muted"]},
        "accent_button": {"bg": P["accent"], "fg": "#ffffff", "activebackground": P["fg"],
                          "activeforeground": P["bg"], "disabledforeground": "#cfd8ee"},
        "canvas": {"bg": P["panel"]},
        "list": {"bg": P["panel"], "fg": P["fg"], "selectbackground": P["accent"],
                 "selectforeground": "#ffffff"},
    }


def _nice_ceil(value: float) -> float:
    for step in (50, 100, 200, 250, 500, 1000, 2000, 5000):
        if value <= step:
            return step
    return float(int(value) + 1)


class NetworkMonitorFrame(tk.Frame):
    """Dashboard widget.

    Parameters
    ----------
    parent     : any Tk container
    data_dir   : where config.json and netmon.db live
    theme      : "dark" | "light" | dict of colors (keys of DARK) to match a host app
    lang       : "en" | "fa"
    autostart  : start pinging immediately
    on_alert   : optional callback(kind, message) for outage start/end
    """

    def __init__(self, parent, data_dir=None, theme="dark", lang="en",
                 autostart=True, on_alert=None, cfg=None, ping_fn=None):
        super().__init__(parent)
        self.cfg = cfg or Config.load(data_dir or DEFAULT_DATA_DIR)
        self.monitor = Monitor(self.cfg, ping_fn=ping_fn)
        self.lang = lang if lang in STRINGS else "en"
        self.on_alert = on_alert
        self._custom = theme if isinstance(theme, dict) else None
        self._light = (theme == "light")
        self.P = self._palette()
        self._themed = []
        self._i18n = []
        self._speed = {"dl": None, "ul": None}
        self._speed_busy = False
        self._speed_q: "queue.Queue" = queue.Queue()
        self._after_id = None
        self._closed = False

        self._build()
        self._apply_theme()
        last = self.monitor.storage.last_speed()
        if last:
            self._speed = {"dl": last[0], "ul": last[1]}
        if autostart:
            self.monitor.start()
        self._apply_text()
        self.bind("<Destroy>", self._on_destroy)
        self._after_id = self.after(400, self._poll)

    # ------------------------------------------------------------------ theme
    def _palette(self):
        if self._custom:
            merged = dict(DARK)
            merged.update(self._custom)
            return merged
        return LIGHT if self._light else DARK

    def _reg(self, widget, role):
        self._themed.append((widget, role))
        return widget

    def _apply_theme(self):
        roles = _roles(self.P)
        self.configure(bg=self.P["bg"])
        for widget, role in self._themed:
            widget.configure(**roles[role])
        for btn in (self.run_btn, self.speed_btn, self.export_btn, self.report_btn,
                    self.theme_btn, self.lang_btn):
            btn.configure(relief="flat", bd=0, highlightthickness=0)
        self._refresh_stats()
        self._draw_chart()

    def _toggle_theme(self):
        self._custom = None
        self._light = not self._light
        self.P = self._palette()
        self._apply_theme()

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "fa" else "fa"
        self._apply_text()
        self._draw_chart()

    # ------------------------------------------------------------------ build
    def _btn(self, parent, key, command, accent=False):
        btn = tk.Button(parent, command=command, font=F_SMALL, padx=12, pady=5, cursor="hand2")
        self._reg(btn, "accent_button" if accent else "button")
        if key:
            self._i18n.append((btn, key))
        return btn

    def _build(self):
        self.configure(padx=14, pady=12)

        header = self._reg(tk.Frame(self), "bg")
        header.pack(fill="x")
        title = self._reg(tk.Label(header, font=F_TITLE, anchor="w"), "title")
        title.pack(side="left")
        self._i18n.append((title, "title"))
        self.status_lbl = tk.Label(header, font=F_BOLD, padx=12, pady=3)
        self.status_lbl.pack(side="right")

        cards = self._reg(tk.Frame(self), "bg")
        cards.pack(fill="x", pady=(10, 0))
        self.card_vals = {}
        for i, key in enumerate(("ping", "avg", "jitter", "loss")):
            card = self._reg(tk.Frame(cards, padx=12, pady=8), "panel")
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            cards.grid_columnconfigure(i, weight=1, uniform="cards")
            lbl = self._reg(tk.Label(card, anchor="w", font=F_SMALL), "muted_panel")
            lbl.pack(fill="x")
            self._i18n.append((lbl, key))
            val = self._reg(tk.Label(card, text="–", anchor="w", font=F_BIG), "value")
            val.pack(fill="x")
            self.card_vals[key] = val

        self.canvas = self._reg(tk.Canvas(self, height=230, highlightthickness=0), "canvas")
        self.canvas.pack(fill="both", expand=True, pady=(10, 0))
        self.canvas.bind("<Configure>", lambda _e: self._draw_chart())

        speed = self._reg(tk.Frame(self, padx=12, pady=8), "panel")
        speed.pack(fill="x", pady=(10, 0))
        self.dl_lbl = self._reg(tk.Label(speed, anchor="w", font=F_BASE), "value")
        self.dl_lbl.pack(side="left")
        self.ul_lbl = self._reg(tk.Label(speed, anchor="w", font=F_BASE), "value")
        self.ul_lbl.pack(side="left", padx=(18, 0))
        self.speed_btn = self._btn(speed, None, self._start_speed, accent=True)
        self.speed_btn.pack(side="right")

        controls = self._reg(tk.Frame(self), "bg")
        controls.pack(fill="x", pady=(10, 0))
        self.run_btn = self._btn(controls, None, self._toggle_run, accent=True)
        self.export_btn = self._btn(controls, "export", self._export)
        self.report_btn = self._btn(controls, "report", self._show_report)
        self.theme_btn = self._btn(controls, "theme", self._toggle_theme)
        self.lang_btn = self._btn(controls, None, self._toggle_lang)
        for i, btn in enumerate((self.run_btn, self.export_btn, self.report_btn)):
            btn.pack(side="left", padx=(0 if i == 0 else 6, 0))
        self.lang_btn.pack(side="right")
        self.theme_btn.pack(side="right", padx=(0, 6))

        out_title = self._reg(tk.Label(self, anchor="w", font=F_BOLD), "muted_bg")
        out_title.pack(fill="x", pady=(12, 4))
        self._i18n.append((out_title, "outages"))
        self.out_list = self._reg(
            tk.Listbox(self, height=5, font=F_MONO, bd=0, highlightthickness=0,
                       activestyle="none"), "list")
        self.out_list.pack(fill="x")

    def _apply_text(self):
        S = STRINGS[self.lang]
        for widget, key in self._i18n:
            widget.configure(text=S[key])
        self.run_btn.configure(text=S["stop"] if self.monitor.running else S["start"])
        self.speed_btn.configure(text=S["testing"] if self._speed_busy else S["speed_test"],
                                 state="disabled" if self._speed_busy else "normal")
        self.lang_btn.configure(text="EN" if self.lang == "fa" else "فا")
        self._update_speed_labels()
        self._refresh_outages()
        self._refresh_stats()

    # --------------------------------------------------------------- refreshes
    def _refresh_stats(self):
        S, P = STRINGS[self.lang], self.P
        agg = aggregate(self.monitor.snapshot())
        self.card_vals["ping"].configure(
            text="–" if agg["latest"] is None else f"{agg['latest']:.0f} ms")
        self.card_vals["avg"].configure(
            text="–" if agg["avg"] is None else f"{agg['avg']:.0f} ms")
        self.card_vals["jitter"].configure(
            text="–" if agg["jitter"] is None else f"{agg['jitter']:.1f} ms")
        self.card_vals["loss"].configure(text=f"{agg['loss']:.1f}%")

        if not self.monitor.running:
            key, color = "stopped", P["muted"]
        elif self.monitor.online is False:
            key, color = "offline", P["bad"]
        elif self.monitor.online is None:
            key, color = "checking", P["muted"]
        elif agg["latest"] is not None and agg["latest"] > self.cfg.ping_alert_ms:
            key, color = "high", P["warn"]
        else:
            key, color = "online", P["ok"]
        self.status_lbl.configure(text=S[key], bg=color, fg="#ffffff")

    def _refresh_outages(self):
        S = STRINGS[self.lang]
        rows = self.monitor.storage.outages(30)
        self.out_list.delete(0, "end")
        if not rows:
            self.out_list.insert("end", S["no_outages"])
            return
        for start, end in rows:
            when = datetime.fromtimestamp(start).strftime("%m-%d %H:%M:%S")
            if end is None:
                length = f"{S['ongoing']} ({fmt_duration(time.time() - start)})"
            else:
                length = fmt_duration(end - start)
            self.out_list.insert("end", f"{when}   {length}")

    def _update_speed_labels(self):
        S = STRINGS[self.lang]

        def fmt(v):
            return "–" if v is None else f"{v:.1f} Mbps"

        self.dl_lbl.configure(text=f"{S['download']}: {fmt(self._speed['dl'])}")
        self.ul_lbl.configure(text=f"{S['upload']}: {fmt(self._speed['ul'])}")

    # ------------------------------------------------------------------- chart
    @staticmethod
    def _flush(canvas, run, color):
        if len(run) >= 4:
            canvas.create_line(*run, fill=color, width=2, joinstyle="round")
        elif len(run) == 2:
            x, y = run
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline=color)

    def _draw_chart(self):
        c, P = self.canvas, self.P
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 80 or h < 80:
            return
        pl, pr, pt, pb = 42, 12, 26, 18
        pw, ph = w - pl - pr, h - pt - pb
        snap = self.monitor.snapshot()
        series_list = list(snap.items())
        vals = [v for _, s in series_list for v in s if v is not None]
        ymax = _nice_ceil(max(vals) * 1.15) if vals else 100

        for i in range(5):
            y = pt + ph * (1 - i / 4)
            c.create_line(pl, y, w - pr, y, fill=P["grid"])
            c.create_text(pl - 6, y, text=f"{ymax * i / 4:g}", fill=P["muted"],
                          anchor="e", font=F_TINY)
        c.create_text(w - pr, 12, text="ms", fill=P["muted"], anchor="e", font=F_TINY)

        n = self.cfg.window

        def xy(i, v):
            return pl + pw * i / (n - 1), pt + ph * (1 - min(v, ymax) / ymax)

        if self.cfg.ping_alert_ms < ymax:
            _, ya = xy(0, self.cfg.ping_alert_ms)
            c.create_line(pl, ya, w - pr, ya, fill=P["warn"], dash=(4, 4))

        length = min((len(s) for _, s in series_list), default=0)
        for i in range(length):
            if all(s[len(s) - length + i] is None for _, s in series_list):
                x = pl + pw * (n - length + i) / (n - 1)
                c.create_line(x, pt, x, pt + ph, fill=P["bad"], dash=(2, 3))

        for idx, (_, s) in enumerate(series_list):
            color = SERIES[idx % len(SERIES)]
            offset = n - len(s)
            run = []
            for i, v in enumerate(s):
                if v is None:
                    self._flush(c, run, color)
                    run = []
                else:
                    run.extend(xy(offset + i, v))
            self._flush(c, run, color)

        lx = pl
        for idx, (name, _) in enumerate(series_list):
            color = SERIES[idx % len(SERIES)]
            c.create_rectangle(lx, 8, lx + 8, 16, fill=color, outline=color)
            c.create_text(lx + 12, 12, text=name, fill=P["muted"], anchor="w", font=F_TINY)
            lx += 12 + len(name) * 6 + 16

    # ------------------------------------------------------------------ events
    def _poll(self):
        if self._closed:
            return
        dirty = False
        try:
            while True:
                ev = self.monitor.events.get_nowait()
                if ev[0] == "tick":
                    dirty = True
                elif ev[0] in ("outage_start", "outage_end"):
                    dirty = True
                    self._alert(ev[0])
        except queue.Empty:
            pass
        try:
            while True:
                self._handle_speed(self._speed_q.get_nowait())
        except queue.Empty:
            pass
        if dirty:
            self._refresh_stats()
            self._refresh_outages()
            self._draw_chart()
        self._after_id = self.after(400, self._poll)

    def _alert(self, kind):
        S = STRINGS[self.lang]
        message = S["alert_outage"] if kind == "outage_start" else S["alert_back"]
        if kind == "outage_start":
            try:
                self.bell()
            except tk.TclError:
                pass
        if self.on_alert:
            try:
                self.on_alert(kind, message)
            except Exception:  # noqa: BLE001 - never let a host callback break the UI
                pass

    # -------------------------------------------------------------- user actions
    def _toggle_run(self):
        if self.monitor.running:
            self.monitor.stop()
        else:
            self.monitor.start()
        self._apply_text()

    def _start_speed(self):
        if self._speed_busy:
            return
        self._speed_busy = True
        self._speed = {"dl": None, "ul": None}
        self._apply_text()
        cfg, q, storage = self.cfg, self._speed_q, self.monitor.storage

        def work():
            dl = ul = err = None
            try:
                dl = measure_download(cfg, progress=lambda v: q.put(("live_dl", v)))
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
            try:
                ul = measure_upload(cfg)
            except Exception as exc:  # noqa: BLE001
                err = err or str(exc)
            if dl is not None or ul is not None:
                try:
                    storage.add_speed(time.time(), dl, ul)
                except Exception:  # noqa: BLE001
                    pass
            q.put(("done", dl, ul, err))

        threading.Thread(target=work, daemon=True, name="netmon-speed").start()

    def _handle_speed(self, ev):
        kind = ev[0]
        if kind == "live_dl":
            self._speed["dl"] = ev[1]
        elif kind == "done":
            _, dl, ul, err = ev
            self._speed_busy = False
            self._speed = {"dl": dl, "ul": ul}
            self._apply_text()
            if dl is None and ul is None:
                S = STRINGS[self.lang]
                messagebox.showwarning(S["title"], f"{S['speed_failed']}\n{(err or '')[:200]}",
                                       parent=self)
            return
        self._update_speed_labels()

    def _export(self):
        S = STRINGS[self.lang]
        directory = filedialog.askdirectory(parent=self)
        if not directory:
            return
        try:
            files = self.monitor.storage.export_csv(directory)
        except OSError as exc:
            messagebox.showerror(S["title"], str(exc), parent=self)
            return
        messagebox.showinfo(S["title"], S["exported"] + "\n" + "\n".join(
            os.path.basename(f) for f in files), parent=self)

    def _show_report(self):
        S, P = STRINGS[self.lang], self.P
        rows = self.monitor.storage.daily_summary(7)
        top = tk.Toplevel(self)
        top.title(S["report"])
        top.configure(bg=P["bg"])
        top.geometry("560x300")
        text = tk.Text(top, font=F_MONO, bg=P["panel"], fg=P["fg"], bd=0,
                       highlightthickness=0, padx=14, pady=12)
        text.pack(fill="both", expand=True, padx=10, pady=10)
        if not rows:
            text.insert("end", S["no_data"])
        else:
            text.insert("end", f"{'Day':<12}{'Avg ms':>8}{'Loss %':>9}{'Outages':>9}{'Downtime':>14}\n")
            text.insert("end", "-" * 52 + "\n")
            for r in rows:
                avg = "-" if r["avg"] is None else f"{r['avg']:.0f}"
                text.insert("end", f"{r['day']:<12}{avg:>8}{r['loss']:>9.1f}"
                                   f"{r['outages']:>9}{fmt_duration(r['downtime']):>14}\n")
        text.configure(state="disabled")

    # ---------------------------------------------------------------- lifecycle
    def _on_destroy(self, event):
        if event.widget is self:
            self.shutdown()

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self.monitor.stop()
        self.monitor.storage.close()


# ---------------------------------------------------------------------- helpers
def open_window(root, title=None, geometry="840x660", **kwargs):
    """Open the monitor in its own Toplevel. Returns (window, frame)."""
    top = tk.Toplevel(root)
    top.title(title or "Network Monitor")
    top.geometry(geometry)
    top.minsize(680, 560)
    frame = NetworkMonitorFrame(top, **kwargs)
    frame.pack(fill="both", expand=True)

    def close():
        frame.shutdown()
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", close)
    return top, frame

if __name__ == "__main__":
    _root = tk.Tk()
    _root.withdraw()
    _top, _f = open_window(_root, lang="fa")
    _top.protocol("WM_DELETE_WINDOW", lambda: (_f.shutdown(), _top.destroy(), _root.destroy()))
    _root.mainloop()
