

import os
import sys
import time
import json
import math
import queue
import threading
import datetime
import subprocess
import webbrowser
import re
import unicodedata
from collections import deque

import tkinter as tk
from tkinter import ttk, messagebox

import psutil

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:
    Figure = None
    FigureCanvasTkAgg = None

MIC_INDEX_RAW = os.getenv("NEXUS_MICROPHONE_INDEX", "").strip()
MIC_INDEX = int(MIC_INDEX_RAW) if MIC_INDEX_RAW else None

# Palette
BG = "#070B14"
SIDEBAR = "#090F1D"
PANEL = "#101A2B"
PANEL_ALT = "#142238"
EDGE = "#213653"
WHITE = "#EAF3FF"
MUTED = "#7F96B5"
CYAN = "#48D9FF"
BLUE = "#4C8DFF"
GREEN = "#37E6A5"
AMBER = "#FFCA70"
RED = "#FF627D"
PURPLE = "#9B8CFF"
FONT = ("Segoe UI", 9)


def ps(command, timeout=20):
    if os.name != "nt":
        return None, "Windows-only feature."
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if p.returncode:
            return None, (p.stderr or p.stdout or "Command failed").strip()
        return p.stdout.strip(), None
    except Exception as e:
        return None, str(e)


class NexusUltra:
    def __init__(self, root):
        self.root = root
        self.root.title("NEXUS ULTRA  |  SYSTEM COMMAND CENTER")
        self.root.geometry("1440x900")
        self.root.minsize(1120, 740)
        self.root.configure(bg=BG)

        self.q = queue.Queue()
        self.events = deque(maxlen=350)
        self.cpu_hist = deque([0] * 60, maxlen=60)
        self.ram_hist = deque([0] * 60, maxlen=60)
        self.disk_hist = deque([0] * 60, maxlen=60)
        self.net_hist = deque([0] * 60, maxlen=60)
        self.net_prev = psutil.net_io_counters()
        self.listening = False
        self.audio_state = "IDLE"
        self.anim_phase = 0.0
        self.tts = None
        self.started = time.time()

        if pyttsx3:
            try:
                self.tts = pyttsx3.init()
                self.tts.setProperty("rate", 170)
                self.tts.setProperty("volume", 0.95)
            except Exception:
                self.tts = None

        self._style()
        self._build_layout()
        self.show_page("Overview")
        self.event("CORE", "NEXUS ULTRA initialized successfully.", "OK")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(250, self._poll)
        self.root.after(900, self._telemetry_tick)
        self.root.after(45, self._animate_orb)
        self.root.after(1000, self._clock_tick)

    # ----------------- Styling / shell -----------------
    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Treeview", background=PANEL, foreground=WHITE,
                    fieldbackground=PANEL, rowheight=27, borderwidth=0,
                    font=("Segoe UI", 9))
        s.configure("Treeview.Heading", background=PANEL_ALT, foreground=CYAN,
                    font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", "#1D4160")],
              foreground=[("selected", WHITE)])
        s.configure("TProgressbar", troughcolor="#1B2A40", background=CYAN,
                    bordercolor="#1B2A40", lightcolor=CYAN, darkcolor=CYAN)

    def _build_layout(self):
        self.side = tk.Frame(self.root, bg=SIDEBAR, width=235)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)

        brand = tk.Frame(self.side, bg=SIDEBAR)
        brand.pack(fill="x", padx=22, pady=(27, 26))
        tk.Label(brand, text="NEXUS", bg=SIDEBAR, fg=CYAN,
                 font=("Segoe UI", 25, "bold")).pack(anchor="w")
        tk.Label(brand, text="U L T R A   /   COMMAND CENTER", bg=SIDEBAR,
                 fg=MUTED, font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(1, 0))

        tk.Frame(self.side, bg=EDGE, height=1).pack(fill="x", padx=18, pady=(0, 16))
        self.nav = {}
        for name, glyph in [
            ("Overview", "◈"), ("Security Center", "⬡"),
            ("Live Processes", "▤"), ("Network Monitor", "⌁"),
            ("Voice Assistant", "◉"), ("Event Logs", "≡")
        ]:
            b = tk.Button(self.side, text=f"  {glyph}    {name}", anchor="w",
                          command=lambda n=name: self.show_page(n),
                          bg=SIDEBAR, fg="#AFC2DC", activebackground=PANEL_ALT,
                          activeforeground=CYAN, relief="flat", bd=0,
                          font=("Segoe UI", 9, "bold"), padx=16, pady=14,
                          cursor="hand2")
            b.pack(fill="x", padx=10, pady=2)
            self.nav[name] = b

        bottom = tk.Frame(self.side, bg=SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=20, pady=22)
        tk.Label(bottom, text="LOCAL DEFENSIVE MONITORING", bg=SIDEBAR,
                 fg=GREEN, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        tk.Label(bottom, text="Build 2.0  •  Windows Desktop", bg=SIDEBAR,
                 fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(5, 0))

        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self.topbar = tk.Frame(self.main, bg=BG, height=76)
        self.topbar.pack(fill="x", padx=28, pady=(20, 8))
        self.topbar.pack_propagate(False)
        self.title_label = tk.Label(self.topbar, text="OVERVIEW", bg=BG, fg=WHITE,
                                    font=("Segoe UI", 19, "bold"))
        self.title_label.pack(side="left", anchor="center")
        right = tk.Frame(self.topbar, bg=BG)
        right.pack(side="right", anchor="center")
        self.clock = tk.Label(right, text="", bg=BG, fg=MUTED, font=("Consolas", 10))
        self.clock.pack(anchor="e")
        self.global_status = tk.Label(right, text="● ALL SYSTEMS NOMINAL", bg=BG,
                                      fg=GREEN, font=("Segoe UI", 8, "bold"))
        self.global_status.pack(anchor="e", pady=(5, 0))
        self.page = tk.Frame(self.main, bg=BG)
        self.page.pack(fill="both", expand=True, padx=28, pady=(0, 24))

    def _panel(self, parent, title=None, subtitle=None):
        f = tk.Frame(parent, bg=PANEL, highlightbackground=EDGE, highlightthickness=1)
        if title:
            head = tk.Frame(f, bg=PANEL)
            head.pack(fill="x", padx=15, pady=(13, 4))
            tk.Label(head, text=title.upper(), bg=PANEL, fg=WHITE,
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            if subtitle:
                tk.Label(head, text=subtitle, bg=PANEL, fg=MUTED,
                         font=("Segoe UI", 8)).pack(side="right")
        return f

    def _metric(self, parent, title, value, unit, accent=CYAN):
        f = self._panel(parent)
        tk.Label(f, text=title.upper(), bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(13, 3))
        v = tk.Label(f, text=value, bg=PANEL, fg=accent,
                     font=("Segoe UI", 21, "bold"))
        v.pack(anchor="w", padx=14)
        tk.Label(f, text=unit, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(1, 12))
        return f, v

    def _button(self, parent, text, command, color="#126E9A"):
        return tk.Button(parent, text=text, command=command, bg=color, fg=WHITE,
                         activebackground="#238AB8", activeforeground=WHITE,
                         relief="flat", bd=0, padx=13, pady=9,
                         font=("Segoe UI", 8, "bold"), cursor="hand2")

    def _clear(self):
        for w in self.page.winfo_children():
            w.destroy()

    def show_page(self, name):
        for n, b in self.nav.items():
            b.configure(bg=PANEL_ALT if n == name else SIDEBAR,
                        fg=CYAN if n == name else "#AFC2DC")
        self.title_label.config(text=name.upper())
        self._clear()
        {
            "Overview": self._overview,
            "Security Center": self._security_page,
            "Live Processes": self._process_page,
            "Network Monitor": self._network_page,
            "Voice Assistant": self._assistant_page,
            "Event Logs": self._events_page
        }[name]()

    # ----------------- Overview -----------------
    def _overview(self):
        row = tk.Frame(self.page, bg=BG)
        row.pack(fill="x")
        self.metric_widgets = {}
        specs = [
            ("CPU LOAD", "0", "%", CYAN),
            ("MEMORY", "0", "%", PURPLE),
            ("SYSTEM DISK", "0", "%", AMBER),
            ("NETWORK", "0", "KB/s", GREEN),
        ]
        for title, val, unit, color in specs:
            f, v = self._metric(row, title, val, unit, color)
            f.pack(side="left", fill="both", expand=True, padx=(0, 10))
            self.metric_widgets[title] = v

        mid = tk.Frame(self.page, bg=BG)
        mid.pack(fill="both", expand=True, pady=(14, 0))
        chart_panel = self._panel(mid, "LIVE SYSTEM TELEMETRY", "rolling 60-second window")
        chart_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.chart_host = tk.Frame(chart_panel, bg=PANEL)
        self.chart_host.pack(fill="both", expand=True, padx=10, pady=8)
        self._make_chart(self.chart_host, overview=True)

        right = tk.Frame(mid, bg=BG, width=310)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        orb_panel = self._panel(right, "NEXUS NEURAL INTERFACE", "VOICE STATE")
        orb_panel.pack(fill="x")
        self.orb = tk.Canvas(orb_panel, width=280, height=220, bg=PANEL,
                             highlightthickness=0)
        self.orb.pack(padx=8, pady=5)
        self.state_label = tk.Label(orb_panel, text="SYSTEM IDLE", bg=PANEL,
                                    fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.state_label.pack(pady=(0, 3))
        self.state_hint = tk.Label(orb_panel, text="Awaiting command", bg=PANEL,
                                   fg=MUTED, font=("Segoe UI", 8))
        self.state_hint.pack(pady=(0, 13))
        quick = self._panel(right, "QUICK ACTIONS")
        quick.pack(fill="x", pady=(12, 0))
        for label, fn, color in [
            ("OPEN SECURITY CENTER", lambda: self.show_page("Security Center"), "#185B79"),
            ("START VOICE SESSION", self.listen_voice, "#205B55"),
            ("OPEN WINDOWS SECURITY", self.open_windows_security, "#344B70")
        ]:
            self._button(quick, label, fn, color).pack(fill="x", padx=12, pady=5)
        tk.Label(quick, text="Voice orb is an animated state indicator,\nnot a measured audio waveform.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 7), justify="left").pack(anchor="w", padx=12, pady=(6, 12))

    def _make_chart(self, host, overview=False):
        if Figure is None:
            tk.Label(host, text="Install matplotlib to enable live charts.",
                     bg=PANEL, fg=AMBER).pack(pady=30)
            return
        self.fig = Figure(figsize=(8.0, 5.0), dpi=100, facecolor=PANEL)
        self.ax_cpu = self.fig.add_subplot(221)
        self.ax_mem = self.fig.add_subplot(222)
        self.ax_disk = self.fig.add_subplot(223)
        self.ax_net = self.fig.add_subplot(224)
        self.fig.subplots_adjust(left=0.07, right=0.98, top=0.94,
                                 bottom=0.09, hspace=0.42, wspace=0.25)
        self.canvas = FigureCanvasTkAgg(self.fig, master=host)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_chart()

    def _draw_chart(self):
        if not hasattr(self, "canvas") or Figure is None:
            return
        specs = [
            (self.ax_cpu, list(self.cpu_hist), "CPU LOAD", CYAN, "%", 100),
            (self.ax_mem, list(self.ram_hist), "MEMORY USAGE", PURPLE, "%", 100),
            (self.ax_disk, list(self.disk_hist), "SYSTEM DISK", AMBER, "%", 100),
            (self.ax_net, list(self.net_hist), "NETWORK TRAFFIC", GREEN, "KB/s", None),
        ]
        for ax, values, title, color, unit, ymax in specs:
            ax.clear()
            ax.set_facecolor(PANEL)
            ax.plot(values, color=color, linewidth=1.8)
            ax.fill_between(range(len(values)), values, color=color, alpha=0.10)
            ax.set_title(title, color=WHITE, fontsize=8, fontweight="bold", pad=7)
            ax.set_xlim(0, max(1, len(values)-1))
            if ymax is not None:
                ax.set_ylim(0, ymax)
            elif values:
                ax.set_ylim(0, max(10, max(values)*1.2))
            ax.set_ylabel(unit, color=MUTED, fontsize=7)
            ax.tick_params(colors=MUTED, labelsize=6)
            ax.grid(True, color=EDGE, alpha=0.55, linewidth=0.5)
            for spine in ax.spines.values():
                spine.set_color(EDGE)
        self.canvas.draw_idle()


    # ----------------- Orb animation -----------------
    def set_audio_state(self, state):
        self.audio_state = state
        labels = {
            "IDLE": ("SYSTEM IDLE", GREEN, "Awaiting command"),
            "LISTENING": ("LISTENING", CYAN, "فارسی یا English صحبت کن"),
            "THINKING": ("PROCESSING", AMBER, "Checking predefined commands"),
            "SPEAKING": ("VOICE OUTPUT", PURPLE, "NEXUS is responding")
        }
        if hasattr(self, "state_label") and self.state_label.winfo_exists():
            text, color, hint = labels.get(state, labels["IDLE"])
            self.state_label.config(text=text, fg=color)
            self.state_hint.config(text=hint)

    def _animate_orb(self):
        self.anim_phase += 0.12
        if hasattr(self, "orb") and self.orb.winfo_exists():
            c = self.orb
            c.delete("all")
            cx, cy = 140, 104
            color = {"IDLE": GREEN, "LISTENING": CYAN, "THINKING": AMBER, "SPEAKING": PURPLE}.get(self.audio_state, CYAN)
            amp = 5 if self.audio_state == "IDLE" else 17
            for i in range(5):
                r = 35 + i * 15 + math.sin(self.anim_phase + i * 0.8) * amp
                c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color,
                              width=1 if i else 2, stipple="gray50" if i > 2 else "")
            for i in range(48):
                a = (2 * math.pi * i / 48) + self.anim_phase * (0.25 if self.audio_state == "IDLE" else 1.0)
                r1, r2 = 77, 83 + (5 if self.audio_state != "IDLE" else 1) * math.sin(self.anim_phase * 2 + i)
                x1, y1 = cx + math.cos(a)*r1, cy + math.sin(a)*r1
                x2, y2 = cx + math.cos(a)*r2, cy + math.sin(a)*r2
                c.create_line(x1, y1, x2, y2, fill=color, width=2)
            c.create_oval(cx-22, cy-22, cx+22, cy+22, fill="#142B43", outline=color, width=2)
            c.create_text(cx, cy, text="N", fill=WHITE, font=("Segoe UI", 17, "bold"))
            # Audio activity bars
            for i in range(19):
                h = 3 + (8 if self.audio_state != "IDLE" else 2) * abs(math.sin(self.anim_phase*2 + i*.7))
                x = 45 + i*10
                c.create_rectangle(x, 202-h, x+4, 202+h, fill=color, outline="")
        self.root.after(45, self._animate_orb)

    # ----------------- Live telemetry -----------------
    def _telemetry_tick(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            drive = os.environ.get("SystemDrive", "C:") + "\\"
            disk = psutil.disk_usage(drive).percent
            current = psutil.net_io_counters()
            delta = (current.bytes_sent + current.bytes_recv) - (self.net_prev.bytes_sent + self.net_prev.bytes_recv)
            rate = max(0, delta / 1024 / 1.5)
            self.net_prev = current
            self.cpu_hist.append(cpu)
            self.ram_hist.append(mem)
            self.disk_hist.append(disk)
            self.net_hist.append(rate)
            if hasattr(self, "metric_widgets"):
                self.metric_widgets["CPU LOAD"].config(text=f"{cpu:.0f}")
                self.metric_widgets["MEMORY"].config(text=f"{mem:.0f}")
                self.metric_widgets["SYSTEM DISK"].config(text=f"{disk:.0f}")
                self.metric_widgets["NETWORK"].config(text=f"{rate:.1f}")
            if hasattr(self, "canvas"):
                self._draw_chart()
        except Exception as e:
            self.event("TELEMETRY", str(e), "WARN")
        self.root.after(1500, self._telemetry_tick)

    # ----------------- Security -----------------
    def _security_page(self):
        hero = self._panel(self.page, "DEFENSIVE SECURITY OVERVIEW",
                           "READ-ONLY STATUS + USER-APPROVED SCAN")
        hero.pack(fill="x")
        tk.Label(hero, text="Review your Windows protection posture. NEXUS never disables security controls or deletes files.",
                 bg=PANEL, fg=MUTED, font=FONT).pack(anchor="w", padx=15, pady=(0, 13))
        actions = tk.Frame(self.page, bg=BG)
        actions.pack(fill="x", pady=12)
        self._button(actions, "REFRESH SECURITY STATUS", self.refresh_security).pack(side="left", padx=(0, 8))
        self._button(actions, "RUN QUICK DEFENDER SCAN", self.start_scan, "#80561E").pack(side="left", padx=8)
        self._button(actions, "OPEN WINDOWS SECURITY", self.open_windows_security, "#344B70").pack(side="left", padx=8)
        self.security_box = tk.Text(self.page, bg=PANEL, fg=WHITE, relief="flat",
                                    wrap="word", font=("Consolas", 10), padx=16, pady=14)
        self.security_box.pack(fill="both", expand=True)
        self.security_box.insert("end", "Click REFRESH SECURITY STATUS to inspect Windows Defender and Firewall.\n")
        self.security_box.configure(state="disabled")
        self.refresh_security()

    def refresh_security(self):
        if not hasattr(self, "security_box"):
            return
        self.security_box.configure(state="normal")
        self.security_box.delete("1.0", "end")
        self.security_box.insert("end", "Collecting security status...\n")
        self.security_box.configure(state="disabled")
        threading.Thread(target=self._security_worker, daemon=True).start()

    def _security_worker(self):
        d, de = ps("Get-MpComputerStatus | Select AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated | ConvertTo-Json -Compress")
        f, fe = ps("Get-NetFirewallProfile | Select Name,Enabled | ConvertTo-Json -Compress")
        result = {"d": None, "f": None, "de": de, "fe": fe}
        try:
            if d:
                result["d"] = json.loads(d)
        except Exception:
            result["de"] = "Unable to parse Defender status."
        try:
            if f:
                x = json.loads(f)
                result["f"] = x if isinstance(x, list) else [x]
        except Exception:
            result["fe"] = "Unable to parse Firewall status."
        self.q.put(("security", result))

    def _render_security(self, data):
        if not hasattr(self, "security_box") or not self.security_box.winfo_exists():
            return
        lines = ["NEXUS SECURITY REPORT", "="*54, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""]
        d = data["d"]
        if d:
            for k, label in [
                ("AMServiceEnabled", "Defender Service"),
                ("AntivirusEnabled", "Antivirus Protection"),
                ("RealTimeProtectionEnabled", "Real-time Protection")
            ]:
                val = d.get(k)
                lines.append(f"{label:28} : {'ENABLED' if val is True else 'DISABLED' if val is False else 'UNKNOWN'}")
            lines.append(f"Signature Updated           : {d.get('AntivirusSignatureLastUpdated', 'Unknown')}")
        else:
            lines.append("Windows Defender status unavailable.")
            if data["de"]:
                lines.append("Details: " + str(data["de"]))
        lines += ["", "WINDOWS FIREWALL", "-"*54]
        if data["f"]:
            for profile in data["f"]:
                lines.append(f"{profile.get('Name', 'Profile'):28} : {'ENABLED' if profile.get('Enabled') else 'DISABLED'}")
        else:
            lines.append("Firewall status unavailable.")
            if data["fe"]:
                lines.append("Details: " + str(data["fe"]))
        lines += ["", "SAFETY NOTES",
                  "• A missing value can be caused by permissions or Windows edition.",
                  "• Confirm findings in the Windows Security application.",
                  "• NEXUS does not change security settings or remove files."]
        self.security_box.configure(state="normal")
        self.security_box.delete("1.0", "end")
        self.security_box.insert("end", "\n".join(lines))
        self.security_box.configure(state="disabled")
        self.event("SECURITY", "Defender and Firewall status check completed.", "OK")

    def start_scan(self):
        if not messagebox.askyesno("Confirm Quick Scan", "Start a Microsoft Defender Quick Scan now?"):
            return
        self.event("SECURITY", "User approved a Microsoft Defender Quick Scan.", "WARN")
        threading.Thread(target=self._scan_worker, daemon=True).start()
        messagebox.showinfo("Scan Requested", "The Quick Scan request was sent. Check Windows Security for scan progress and results.")

    def _scan_worker(self):
        out, err = ps("Start-MpScan -ScanType QuickScan", timeout=15)
        self.q.put(("event", ("DEFENDER", out or err or "Quick Scan request submitted.", "INFO")))

    def open_windows_security(self):
        try:
            os.startfile("windowsdefender:")
        except Exception:
            try:
                subprocess.Popen(["explorer.exe", "windowsdefender:"])
            except Exception as e:
                messagebox.showerror("Windows Security", str(e))

    # ----------------- Process / network -----------------
    def _process_page(self):
        bar = tk.Frame(self.page, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        self._button(bar, "REFRESH PROCESS LIST", self.refresh_processes).pack(side="left")
        tk.Label(bar, text="Read-only view • no process termination controls", bg=BG,
                 fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=12)
        cols = ("pid", "name", "cpu", "mem", "user")
        self.proc_tree = ttk.Treeview(self.page, columns=cols, show="headings")
        for c, label, width in [
            ("pid", "PID", 75), ("name", "PROCESS", 300),
            ("cpu", "CPU %", 100), ("mem", "MEMORY %", 110), ("user", "USER", 230)
        ]:
            self.proc_tree.heading(c, text=label)
            self.proc_tree.column(c, width=width, anchor="w")
        self.proc_tree.pack(fill="both", expand=True)
        self.refresh_processes()

    def refresh_processes(self):
        if not hasattr(self, "proc_tree"):
            return
        self.proc_tree.delete(*self.proc_tree.get_children())
        data = []
        for p in psutil.process_iter(["pid", "name", "username", "memory_percent", "cpu_percent"]):
            try:
                info = p.info
                data.append((info.get("memory_percent") or 0, info))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        for _, x in sorted(data, key=lambda a: a[0], reverse=True)[:180]:
            self.proc_tree.insert("", "end", values=(
                x.get("pid"), x.get("name") or "—", f"{x.get('cpu_percent') or 0:.1f}",
                f"{x.get('memory_percent') or 0:.1f}", x.get("username") or "—"
            ))

    def _network_page(self):
        info = self._panel(self.page, "NETWORK INTERFACE", "LIVE CONNECTION SNAPSHOT")
        info.pack(fill="x")
        self.net_summary = tk.Label(info, text="Collecting network information...",
                                    bg=PANEL, fg=WHITE, justify="left",
                                    font=("Consolas", 10), padx=15, pady=13)
        self.net_summary.pack(anchor="w")
        bar = tk.Frame(self.page, bg=BG)
        bar.pack(fill="x", pady=10)
        self._button(bar, "REFRESH CONNECTIONS", self.refresh_connections).pack(side="left")
        tk.Label(bar, text="Connection metadata only. Remote addresses are not automatically classified as malicious.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=12)
        cols = ("local", "remote", "status", "pid", "process")
        self.conn_tree = ttk.Treeview(self.page, columns=cols, show="headings")
        for c, label, width in [
            ("local", "LOCAL ENDPOINT", 210), ("remote", "REMOTE ENDPOINT", 210),
            ("status", "STATE", 120), ("pid", "PID", 80), ("process", "PROCESS", 220)
        ]:
            self.conn_tree.heading(c, text=label)
            self.conn_tree.column(c, width=width, anchor="w")
        self.conn_tree.pack(fill="both", expand=True)
        self.refresh_connections()

    def refresh_connections(self):
        if not hasattr(self, "conn_tree"):
            return
        self.conn_tree.delete(*self.conn_tree.get_children())
        try:
            for c in psutil.net_connections(kind="inet"):
                try:
                    proc = psutil.Process(c.pid).name() if c.pid else "—"
                except Exception:
                    proc = "—"
                local = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "—"
                remote = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "—"
                self.conn_tree.insert("", "end", values=(local, remote, c.status, c.pid or "—", proc))
            self.net_summary.config(text=f"Hostname: {os.environ.get('COMPUTERNAME', 'Unknown')}    |    "
                                         f"Active interfaces: {len(psutil.net_if_addrs())}    |    "
                                         f"Connection records: {len(self.conn_tree.get_children())}")
        except Exception as e:
            self.net_summary.config(text=f"Could not read connections. Try running NEXUS with appropriate permissions.\n{e}")

    # ----------------- Assistant -----------------
    def _assistant_page(self):
        shell = self._panel(self.page, "NEXUS VOICE COMMAND CENTER", "PERSIAN + ENGLISH • PREDEFINED COMMANDS")
        shell.pack(fill="both", expand=True)
        self.chat = tk.Text(shell, bg="#0C1423", fg=WHITE, insertbackground=WHITE,
                            relief="flat", wrap="word", font=("Segoe UI", 10),
                            padx=16, pady=14)
        self.chat.pack(fill="both", expand=True, padx=10, pady=(10, 8))
        self.chat.insert("end", "NEXUS: آماده دریافت فرمان صوتی هستم.\n\n")
        self.chat.configure(state="disabled")
        row = tk.Frame(shell, bg=PANEL)
        row.pack(fill="x", padx=10, pady=(0, 10))
        self._button(row, "START VOICE", self.listen_voice, "#205B55").pack(side="left", padx=4)
        self._button(row, "CLEAR CHAT", self.clear_chat, "#344B70").pack(side="left", padx=4)
        tk.Label(row, text="Say: Bug Bounty • CVE • OWASP • Security News",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(side="right", padx=8)

    def clear_chat(self):
        if hasattr(self, "chat"):
            self.chat.configure(state="normal")
            self.chat.delete("1.0", "end")
            self.chat.configure(state="disabled")

    def _chat_append(self, who, text):
        if hasattr(self, "chat") and self.chat.winfo_exists():
            self.chat.configure(state="normal")
            self.chat.insert("end", f"{who}: {text}\n\n")
            self.chat.see("end")
            self.chat.configure(state="disabled")

    def normalize_fa(self, text):
        text = unicodedata.normalize("NFKC", str(text)).strip().lower()
        text = text.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
        text = text.replace("‌", " ").replace("ـ", " ")
        text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
        return " ".join(text.split())

    def process_command(self, text, source="text"):
        fa = self.normalize_fa(text)
        low = fa

        def has_any(*phrases):
            return any(self.normalize_fa(p) in low for p in phrases)

        def open_sites(urls, message):
            opened = 0
            for url in urls:
                try:
                    webbrowser.open_new_tab(url)
                    opened += 1
                except Exception:
                    pass
            self.respond(message if opened else "باز کردن سایت‌ها ناموفق بود.")

        # Bug bounty
        if has_any("باگ بانتی", "باگبانتی", "bug bounty", "bugbounty", "bounty"):
            open_sites([
                "https://www.hackerone.com/",
                "https://www.bugcrowd.com/",
                "https://www.intigriti.com/",
                "https://yeswehack.com/"
            ], "سایت‌های باگ‌بانتی باز شدند.")
            return

        # CVE
        if has_any("cve", "آسیب پذیری", "آسیبپذیری"):
            open_sites([
                "https://www.cve.org/",
                "https://nvd.nist.gov/vuln/search",
                "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
            ], "منابع CVE باز شدند.")
            return

        # OWASP
        if has_any("owasp"):
            open_sites(["https://owasp.org/", "https://owasp.org/www-project-top-ten/"],
                       "منابع OWASP باز شدند.")
            return

        # Cybersecurity news
        if has_any("اخبار امنیتی", "خبر امنیت", "security news", "cyber news"):
            open_sites([
                "https://thehackernews.com/",
                "https://www.bleepingcomputer.com/",
                "https://www.darkreading.com/"
            ], "سایت‌های اخبار امنیتی باز شدند.")
            return

        # Penetration testing tools
        if has_any("ابزار تست نفوذ", "تست نفوذ", "penetration testing", "pentest", "tools"):
            open_sites([
                "https://www.kali.org/tools/",
                "https://github.com/topics/pentesting",
                "https://www.exploit-db.com/"
            ], "منابع ابزارهای تست نفوذ باز شدند.")
            return

        # Red Team
        if has_any("رد تیم", "ردتیم", "red team", "redteam"):
            open_sites([
                "https://attack.mitre.org/",
                "https://github.com/topics/red-team",
                "https://www.cobaltstrike.com/"
            ], "منابع رد تیم باز شدند.")
            return

        # Blue Team
        if has_any("بلو تیم", "بلوتیم", "blue team", "blueteam"):
            open_sites([
                "https://www.cisa.gov/",
                "https://www.microsoft.com/en-us/security/blog/",
                "https://github.com/topics/blue-team"
            ], "منابع بلو تیم باز شدند.")
            return

        # Phishing
        if has_any("فیشینگ", "phishing"):
            open_sites([
                "https://www.cisa.gov/secure-our-world/recognize-and-report-phishing",
                "https://attack.mitre.org/techniques/T1566/"
            ], "منابع فیشینگ باز شدند.")
            return

        # Malware
        if has_any("بدافزار", "malware"):
            open_sites([
                "https://www.malware-traffic-analysis.net/",
                "https://www.virustotal.com/",
                "https://attack.mitre.org/techniques/T1204/"
            ], "منابع تحلیل بدافزار باز شدند.")
            return

        if has_any("گوگل", "google"):
            open_sites(["https://www.google.com/"], "گوگل باز شد.")
            return
        if has_any("یوتیوب", "youtube"):
            open_sites(["https://www.youtube.com/"], "یوتیوب باز شد.")
            return

        # Local dashboard navigation
        if has_any("داشبورد", "صفحه اصلی", "نمای کلی", "overview", "dashboard"):
            self.show_page("Overview")
            self.respond("داشبورد باز شد.")
            return

        if has_any("مرکز امنیت", "امنیت سیستم", "وضعیت امنیت", "security", "defender"):
            self.show_page("Security Center")
            self.respond("مرکز امنیت باز شد.")
            return

        if has_any("پردازش", "process", "processes"):
            self.show_page("Live Processes")
            self.respond("فهرست پردازش‌ها باز شد.")
            return

        if has_any("شبکه", "network", "connections"):
            self.show_page("Network Monitor")
            self.respond("مانیتور شبکه باز شد.")
            return

        if has_any("دستیار صوتی", "voice assistant"):
            self.show_page("Voice Assistant")
            self.respond("بخش فرمان صوتی باز شد.")
            return

        if has_any("گزارش رویداد", "رویدادها", "event logs"):
            self.show_page("Event Logs")
            self.respond("گزارش رویدادها باز شد.")
            return

        if has_any("ساعت", "time"):
            self.respond("ساعت فعلی " + datetime.datetime.now().strftime("%H:%M") + " است.")
            return

        if has_any("تاریخ", "date"):
            self.respond("تاریخ امروز " + datetime.datetime.now().strftime("%Y-%m-%d") + " است.")
            return

        if has_any("خروج", "exit nexus", "quit nexus"):
            if messagebox.askyesno("تأیید خروج", "آیا مطمئن هستید که می‌خواهید NEXUS بسته شود؟"):
                self.close()
            else:
                self.respond("عملیات خروج لغو شد.")
            return

        if has_any("خاموش", "shutdown computer"):
            if messagebox.askyesno("تأیید خاموش کردن", "آیا مطمئن هستید که می‌خواهید ویندوز خاموش شود؟"):
                subprocess.Popen(["shutdown", "/s", "/t", "30"])
                self.respond("فرمان خاموش شدن سیستم ثبت شد.")
            else:
                self.respond("فرمان خاموش کردن لغو شد.")
            return

        self.respond("این دستور تعریف نشده است.")

    def respond(self, text):
        self._chat_append("NEXUS", text)
        self.event("ASSISTANT", text, "INFO")
        if self.tts:
            self.set_audio_state("SPEAKING")
            threading.Thread(target=self._speak, args=(text,), daemon=True).start()
        else:
            self.set_audio_state("IDLE")

    def _speak(self, text):
        try:
            self.tts.say(text)
            self.tts.runAndWait()
        except Exception as e:
            self.q.put(("event", ("VOICE", f"Text-to-speech error: {e}", "WARN")))
        finally:
            self.q.put(("audio_state", "IDLE"))

    # ----------------- Voice -----------------
    def listen_voice(self):
        if self.listening:
            return
        if not sr:
            messagebox.showerror("Voice Input", "SpeechRecognition is not installed.")
            return
        self.listening = True
        self.set_audio_state("LISTENING")
        self.event("VOICE", "Microphone listening started.", "INFO")
        threading.Thread(target=self._voice_worker, daemon=True).start()

    def _voice_worker(self):
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.55
        try:
            with sr.Microphone(device_index=MIC_INDEX) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=5)

            candidates = []
            for language in ("fa-IR", "en-US"):
                try:
                    result = recognizer.recognize_google(audio, language=language)
                    if result:
                        candidates.append(result)
                except sr.UnknownValueError:
                    pass

            if candidates:
                command_terms = (
                    "باگ بانتی", "باگبانتی", "bug bounty", "bounty", "cve",
                    "owasp", "اخبار امنیتی", "security news", "pentest",
                    "تست نفوذ", "red team", "رد تیم", "blue team", "بلو تیم",
                    "phishing", "فیشینگ", "malware", "بدافزار", "google", "گوگل"
                )

                def score(candidate):
                    normalized = self.normalize_fa(candidate)
                    return sum(
                        1 for term in command_terms
                        if self.normalize_fa(term) in normalized
                    )

                recognized = max(candidates, key=score)
                self.q.put(("voice", recognized))
            else:
                self.q.put(("event", ("VOICE", "Speech was not recognized. Try a shorter command.", "WARN")))

        except sr.WaitTimeoutError:
            self.q.put(("event", ("VOICE", "No speech detected. Check microphone permissions.", "WARN")))
        except Exception as e:
            self.q.put(("event", ("VOICE", f"Microphone / network error: {e}", "WARN")))
        finally:
            self.q.put(("listening_done", None))

    # ----------------- Event log / queue -----------------
    def event(self, category, message, level="INFO"):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.events.appendleft((stamp, level, category, str(message)))
        if hasattr(self, "events_text") and self.events_text.winfo_exists():
            self._render_events()

    def _events_page(self):
        self.events_text = tk.Text(self.page, bg=PANEL, fg=WHITE, relief="flat",
                                   wrap="word", font=("Consolas", 9), padx=14, pady=12)
        self.events_text.pack(fill="both", expand=True)
        self._render_events()
        self._button(self.page, "CLEAR EVENT VIEW", self.clear_events, "#66364B").pack(anchor="e", pady=9)

    def _render_events(self):
        if not hasattr(self, "events_text") or not self.events_text.winfo_exists():
            return
        self.events_text.configure(state="normal")
        self.events_text.delete("1.0", "end")
        for stamp, level, cat, msg in self.events:
            self.events_text.insert("end", f"[{stamp}] [{level:4}] {cat}: {msg}\n")
        self.events_text.configure(state="disabled")

    def clear_events(self):
        self.events.clear()
        self._render_events()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "security":
                    self._render_security(payload)
                elif kind == "voice":
                    self.set_audio_state("THINKING")
                    self.process_command(payload, source="voice")
                elif kind == "listening_done":
                    self.listening = False
                    if self.audio_state == "LISTENING":
                        self.set_audio_state("IDLE")
                elif kind == "event":
                    self.event(*payload)
                elif kind == "audio_state":
                    self.set_audio_state(payload)
        except queue.Empty:
            pass
        self.root.after(250, self._poll)

    def _clock_tick(self):
        self.clock.config(text=datetime.datetime.now().strftime("%A, %d %b %Y    %H:%M:%S"))
        self.root.after(1000, self._clock_tick)

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = NexusUltra(root)
    root.mainloop()
