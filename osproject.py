"""
Hospital Management System — OS Simulation
Real-world application of:
  • CPU Scheduling (FCFS, SJF, Round Robin, Priority)
  • Memory Management (First Fit, Best Fit, Worst Fit)
  • Multiprogramming (multiple patients processed concurrently)

Analogy:
  Patient  →  Process
  Doctor   →  CPU
  Ward     →  Memory Block
  Admit    →  Load into Memory
  Treat    →  Execute on CPU
  Discharge→  Release Memory
"""

import tkinter as tk
from tkinter import ttk, messagebox, font
import threading
import time
import random
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional
import copy

# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────

DEPARTMENTS = ["Emergency", "Surgery", "General", "ICU", "Pediatrics", "Cardiology"]
STATUS_COLORS = {
    "Waiting":    "#f59e0b",
    "Admitted":   "#3b82f6",
    "In Treatment":"#8b5cf6",
    "Discharged": "#10b981",
    "Error":      "#ef4444",
}

pid_counter = 0

@dataclass
class Patient:
    name: str
    department: str
    severity: int          # 1=low … 5=critical  (Priority)
    treatment_time: int    # burst time (seconds of simulation)
    memory_required: int   # MB of memory needed
    pid: int = 0
    arrival_time: float = 0.0
    start_time: float = 0.0
    finish_time: float = 0.0
    remaining_time: int = 0
    status: str = "Waiting"
    memory_block: Optional[int] = None   # index of assigned block
    waiting_time: float = 0.0
    turnaround_time: float = 0.0

    def __post_init__(self):
        global pid_counter
        pid_counter += 1
        self.pid = pid_counter
        self.remaining_time = self.treatment_time

@dataclass
class MemoryBlock:
    block_id: int
    total_size: int    # MB
    used: int = 0
    patient: Optional[Patient] = None

    @property
    def free(self):
        return self.total_size - self.used

    @property
    def status(self):
        return "Occupied" if self.patient else "Free"

# ─────────────────────────────────────────────
# SCHEDULING ALGORITHMS
# ─────────────────────────────────────────────

def schedule_fcfs(queue: List[Patient]) -> List[Patient]:
    return sorted(queue, key=lambda p: p.arrival_time)

def schedule_sjf(queue: List[Patient]) -> List[Patient]:
    return sorted(queue, key=lambda p: p.treatment_time)

def schedule_priority(queue: List[Patient]) -> List[Patient]:
    return sorted(queue, key=lambda p: -p.severity)

# Round Robin handled in simulation loop

# ─────────────────────────────────────────────
# MEMORY ALLOCATION
# ─────────────────────────────────────────────

def allocate_first_fit(blocks: List[MemoryBlock], patient: Patient) -> Optional[int]:
    for i, b in enumerate(blocks):
        if b.patient is None and b.free >= patient.memory_required:
            return i
    return None

def allocate_best_fit(blocks: List[MemoryBlock], patient: Patient) -> Optional[int]:
    best = None
    best_free = float('inf')
    for i, b in enumerate(blocks):
        if b.patient is None and b.free >= patient.memory_required:
            if b.free < best_free:
                best_free = b.free
                best = i
    return best

def allocate_worst_fit(blocks: List[MemoryBlock], patient: Patient) -> Optional[int]:
    worst = None
    worst_free = -1
    for i, b in enumerate(blocks):
        if b.patient is None and b.free >= patient.memory_required:
            if b.free > worst_free:
                worst_free = b.free
                worst = i
    return worst

# ─────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────

class HospitalOSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🏥 Hospital OS Simulator — CPU Scheduling & Memory Management")
        self.geometry("1400x850")
        self.configure(bg="#0f172a")
        self.resizable(True, True)

        # State
        self.patients: List[Patient] = []
        self.memory_blocks: List[MemoryBlock] = [
            MemoryBlock(1, 200),
            MemoryBlock(2, 150),
            MemoryBlock(3, 300),
            MemoryBlock(4, 100),
            MemoryBlock(5, 250),
        ]
        self.sim_running = False
        self.sim_thread = None
        self.sim_time = 0.0
        self.log_lines = []
        self.completed_patients: List[Patient] = []

        self._setup_styles()
        self._build_ui()
        self._add_sample_patients()

    # ── Styles ──────────────────────────────────
    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TNotebook", background="#0f172a", borderwidth=0)
        style.configure("TNotebook.Tab",
                        background="#1e293b", foreground="#94a3b8",
                        padding=[16, 8], font=("Consolas", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", "#3b82f6")],
                  foreground=[("selected", "white")])

        style.configure("Treeview",
                        background="#1e293b", foreground="#e2e8f0",
                        fieldbackground="#1e293b", rowheight=28,
                        font=("Consolas", 9))
        style.configure("Treeview.Heading",
                        background="#0f172a", foreground="#64748b",
                        font=("Consolas", 9, "bold"))
        style.map("Treeview", background=[("selected", "#3b82f6")])

        style.configure("TCombobox",
                        fieldbackground="#1e293b", background="#1e293b",
                        foreground="white", selectbackground="#3b82f6")

        style.configure("TEntry",
                        fieldbackground="#1e293b", foreground="white",
                        insertcolor="white")

        style.configure("TLabelframe",
                        background="#0f172a", foreground="#64748b",
                        bordercolor="#1e293b")
        style.configure("TLabelframe.Label",
                        background="#0f172a", foreground="#64748b",
                        font=("Consolas", 9, "bold"))

    # ── UI Layout ────────────────────────────────
    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg="#0f172a")
        header.pack(fill=tk.X, padx=20, pady=(15, 5))

        tk.Label(header, text="🏥 HOSPITAL OS SIMULATOR",
                 font=("Consolas", 18, "bold"),
                 bg="#0f172a", fg="#f1f5f9").pack(side=tk.LEFT)

        self.sim_time_lbl = tk.Label(header, text="⏱ Sim Time: 0.0s",
                                     font=("Consolas", 11),
                                     bg="#0f172a", fg="#64748b")
        self.sim_time_lbl.pack(side=tk.RIGHT, padx=10)

        self.status_dot = tk.Label(header, text="● IDLE",
                                   font=("Consolas", 11, "bold"),
                                   bg="#0f172a", fg="#64748b")
        self.status_dot.pack(side=tk.RIGHT, padx=10)

        # Algorithm selectors
        ctrl_bar = tk.Frame(self, bg="#1e293b")
        ctrl_bar.pack(fill=tk.X, padx=20, pady=5)

        tk.Label(ctrl_bar, text="  CPU Scheduling:",
                 font=("Consolas", 10, "bold"),
                 bg="#1e293b", fg="#94a3b8").pack(side=tk.LEFT, pady=8)
        self.sched_var = tk.StringVar(value="FCFS")
        sched_cb = ttk.Combobox(ctrl_bar, textvariable=self.sched_var,
                                values=["FCFS", "SJF", "Priority", "Round Robin"],
                                width=14, state="readonly")
        sched_cb.pack(side=tk.LEFT, padx=8, pady=8)

        self.quantum_lbl = tk.Label(ctrl_bar, text="  Quantum (s):",
                                    font=("Consolas", 10, "bold"),
                                    bg="#1e293b", fg="#94a3b8")
        self.quantum_var = tk.StringVar(value="3")
        self.quantum_entry = tk.Entry(ctrl_bar, textvariable=self.quantum_var,
                                      width=4, bg="#0f172a", fg="white",
                                      font=("Consolas", 10),
                                      insertbackground="white",
                                      relief="flat", bd=4)

        tk.Label(ctrl_bar, text="  Memory Alloc:",
                 font=("Consolas", 10, "bold"),
                 bg="#1e293b", fg="#94a3b8").pack(side=tk.LEFT, padx=(20,0), pady=8)
        self.mem_var = tk.StringVar(value="First Fit")
        mem_cb = ttk.Combobox(ctrl_bar, textvariable=self.mem_var,
                              values=["First Fit", "Best Fit", "Worst Fit"],
                              width=12, state="readonly")
        mem_cb.pack(side=tk.LEFT, padx=8, pady=8)

        sched_cb.bind("<<ComboboxSelected>>", self._on_sched_change)
        self._on_sched_change(None)

        # Buttons
        btn_cfg = dict(font=("Consolas", 10, "bold"), relief="flat",
                       cursor="hand2", padx=14, pady=6)
        self.run_btn = tk.Button(ctrl_bar, text="▶  RUN SIMULATION",
                                 bg="#3b82f6", fg="white",
                                 command=self._start_sim, **btn_cfg)
        self.run_btn.pack(side=tk.RIGHT, padx=8, pady=8)

        self.stop_btn = tk.Button(ctrl_bar, text="■  STOP",
                                  bg="#ef4444", fg="white",
                                  command=self._stop_sim,
                                  state=tk.DISABLED, **btn_cfg)
        self.stop_btn.pack(side=tk.RIGHT, padx=4, pady=8)

        tk.Button(ctrl_bar, text="+ Add Patient",
                  bg="#10b981", fg="white",
                  command=self._open_add_patient, **btn_cfg).pack(side=tk.RIGHT, padx=8, pady=8)

        tk.Button(ctrl_bar, text="↺ Reset",
                  bg="#64748b", fg="white",
                  command=self._reset, **btn_cfg).pack(side=tk.RIGHT, padx=4, pady=8)

        # Notebook tabs
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.tab_main   = tk.Frame(nb, bg="#0f172a")
        self.tab_memory = tk.Frame(nb, bg="#0f172a")
        self.tab_gantt  = tk.Frame(nb, bg="#0f172a")
        self.tab_stats  = tk.Frame(nb, bg="#0f172a")

        nb.add(self.tab_main,   text="  📋 Patient Queue  ")
        nb.add(self.tab_memory, text="  🧠 Memory Map  ")
        nb.add(self.tab_gantt,  text="  📊 Gantt Chart  ")
        nb.add(self.tab_stats,  text="  📈 Statistics  ")

        self._build_tab_main()
        self._build_tab_memory()
        self._build_tab_gantt()
        self._build_tab_stats()

    def _on_sched_change(self, _):
        if self.sched_var.get() == "Round Robin":
            self.quantum_lbl.pack(side=tk.LEFT, padx=(20, 0), pady=8)
            self.quantum_entry.pack(side=tk.LEFT, padx=4, pady=8)
        else:
            self.quantum_lbl.pack_forget()
            self.quantum_entry.pack_forget()

    # ── Tab: Patient Queue ────────────────────────
    def _build_tab_main(self):
        paned = tk.PanedWindow(self.tab_main, orient=tk.HORIZONTAL,
                               bg="#0f172a", sashwidth=4, sashrelief="flat")
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: patient table
        left = tk.Frame(paned, bg="#0f172a")
        paned.add(left, width=850)

        tk.Label(left, text="PATIENT PROCESS TABLE",
                 font=("Consolas", 10, "bold"),
                 bg="#0f172a", fg="#64748b").pack(anchor=tk.W, padx=5, pady=(0,5))

        cols = ("PID", "Name", "Department", "Severity", "Burst(s)", "Mem(MB)",
                "Status", "Wait(s)", "TAT(s)")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=22)
        widths = [50, 120, 110, 70, 70, 70, 100, 70, 70]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right: log
        right = tk.Frame(paned, bg="#0f172a")
        paned.add(right, width=300)

        tk.Label(right, text="SYSTEM LOG",
                 font=("Consolas", 10, "bold"),
                 bg="#0f172a", fg="#64748b").pack(anchor=tk.W, padx=5, pady=(0,5))

        self.log_text = tk.Text(right, bg="#0a0f1e", fg="#4ade80",
                                font=("Consolas", 8), state=tk.DISABLED,
                                relief="flat", bd=0, insertbackground="white")
        log_scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ── Tab: Memory Map ───────────────────────────
    def _build_tab_memory(self):
        tk.Label(self.tab_memory, text="MEMORY WARD MAP  (Each block = a hospital ward)",
                 font=("Consolas", 11, "bold"),
                 bg="#0f172a", fg="#64748b").pack(pady=(10,5))

        self.mem_canvas = tk.Canvas(self.tab_memory, bg="#0a0f1e",
                                    height=340, relief="flat", bd=0)
        self.mem_canvas.pack(fill=tk.X, padx=20, pady=10)

        # Legend
        leg = tk.Frame(self.tab_memory, bg="#0f172a")
        leg.pack(pady=5)
        for label, color in [("Free", "#1e3a2f"), ("Occupied", "#1e3a8a"), ("Allocated Now", "#7c3aed")]:
            tk.Frame(leg, bg=color, width=18, height=18).pack(side=tk.LEFT, padx=4)
            tk.Label(leg, text=label, bg="#0f172a", fg="#94a3b8",
                     font=("Consolas", 9)).pack(side=tk.LEFT, padx=(0, 12))

        # Memory stats table
        tk.Label(self.tab_memory, text="MEMORY BLOCK DETAILS",
                 font=("Consolas", 10, "bold"),
                 bg="#0f172a", fg="#64748b").pack(pady=(10,5))

        mem_cols = ("Block", "Total(MB)", "Used(MB)", "Free(MB)", "Patient", "Status")
        self.mem_tree = ttk.Treeview(self.tab_memory, columns=mem_cols,
                                     show="headings", height=7)
        for col in mem_cols:
            self.mem_tree.heading(col, text=col)
            self.mem_tree.column(col, width=140, anchor=tk.CENTER)
        self.mem_tree.pack(padx=20, pady=5, fill=tk.X)

        self._draw_memory()

    def _draw_memory(self):
        self.mem_canvas.delete("all")
        c = self.mem_canvas
        w = self.winfo_width() - 60 if self.winfo_width() > 200 else 1340
        total_mem = sum(b.total_size for b in self.memory_blocks)
        x = 10
        y1, y2 = 60, 240

        for b in self.memory_blocks:
            block_w = max(int((b.total_size / total_mem) * (w - 20)), 60)
            color = "#7c3aed" if b.patient else "#1e3a2f"
            outline = "#a78bfa" if b.patient else "#166534"

            c.create_rectangle(x, y1, x+block_w, y2,
                                fill=color, outline=outline, width=2)

            # Size bar inside
            if b.used > 0:
                used_h = int((b.used / b.total_size) * (y2 - y1 - 20))
                c.create_rectangle(x+4, y2-10-used_h, x+block_w-4, y2-10,
                                   fill="#4f46e5", outline="")

            # Labels
            c.create_text(x + block_w//2, y1 - 20,
                          text=f"Ward {b.block_id}",
                          fill="#94a3b8", font=("Consolas", 9, "bold"))
            c.create_text(x + block_w//2, y1 + 20,
                          text=f"{b.total_size} MB",
                          fill="white", font=("Consolas", 9))
            if b.patient:
                c.create_text(x + block_w//2, y1 + 50,
                              text=f"P{b.patient.pid}", fill="#a78bfa",
                              font=("Consolas", 9, "bold"))
                c.create_text(x + block_w//2, y1 + 70,
                              text=f"{b.used}MB used",
                              fill="#c4b5fd", font=("Consolas", 8))
            else:
                c.create_text(x + block_w//2, y1 + 50,
                              text="FREE", fill="#4ade80",
                              font=("Consolas", 9, "bold"))

            x += block_w + 8

        # Update memory table
        self.mem_tree.delete(*self.mem_tree.get_children())
        for b in self.memory_blocks:
            pname = b.patient.name if b.patient else "—"
            self.mem_tree.insert("", tk.END, values=(
                f"Ward {b.block_id}",
                b.total_size,
                b.used,
                b.free,
                pname,
                b.status,
            ))

    # ── Tab: Gantt Chart ──────────────────────────
    def _build_tab_gantt(self):
        tk.Label(self.tab_gantt, text="GANTT CHART  (CPU Treatment Timeline)",
                 font=("Consolas", 11, "bold"),
                 bg="#0f172a", fg="#64748b").pack(pady=(10,5))

        self.gantt_canvas = tk.Canvas(self.tab_gantt, bg="#0a0f1e",
                                      height=400, relief="flat", bd=0,
                                      scrollregion=(0, 0, 3000, 400))
        hscroll = ttk.Scrollbar(self.tab_gantt, orient=tk.HORIZONTAL,
                                 command=self.gantt_canvas.xview)
        self.gantt_canvas.configure(xscrollcommand=hscroll.set)
        self.gantt_canvas.pack(fill=tk.BOTH, expand=True, padx=20)
        hscroll.pack(fill=tk.X, padx=20)

        self.gantt_events = []  # list of (pid, name, start, end, color)
        self.gantt_colors = {}
        palette = ["#3b82f6","#8b5cf6","#ec4899","#f59e0b",
                   "#10b981","#06b6d4","#f97316","#a3e635",
                   "#e879f9","#fb7185"]
        self._palette = palette
        self._palette_idx = 0

    def _gantt_color(self, pid):
        if pid not in self.gantt_colors:
            self.gantt_colors[pid] = self._palette[self._palette_idx % len(self._palette)]
            self._palette_idx += 1
        return self.gantt_colors[pid]

    def _draw_gantt(self):
        c = self.gantt_canvas
        c.delete("all")
        if not self.gantt_events:
            return

        PX_PER_SEC = 40
        ROW_H = 40
        LABEL_W = 100
        TOP = 40

        # Axis
        max_t = max(e[3] for e in self.gantt_events)
        for t in range(0, int(max_t)+2):
            x = LABEL_W + t * PX_PER_SEC
            c.create_line(x, TOP-10, x, TOP + len(set(e[0] for e in self.gantt_events))*ROW_H + 10,
                          fill="#1e293b", width=1)
            c.create_text(x, TOP-18, text=str(t), fill="#475569",
                          font=("Consolas", 8))

        # Group by PID row
        pids = []
        for e in self.gantt_events:
            if e[0] not in pids:
                pids.append(e[0])

        for row, pid in enumerate(pids):
            y1 = TOP + row * ROW_H + 4
            y2 = y1 + ROW_H - 8
            # row label
            name = next((e[1] for e in self.gantt_events if e[0]==pid), "")
            c.create_text(LABEL_W - 5, (y1+y2)//2,
                          text=f"P{pid}: {name[:8]}", anchor=tk.E,
                          fill="#94a3b8", font=("Consolas", 8))
            for pid2, name2, start, end, color in self.gantt_events:
                if pid2 != pid:
                    continue
                x1 = LABEL_W + start * PX_PER_SEC
                x2 = LABEL_W + end   * PX_PER_SEC
                c.create_rectangle(x1, y1, x2, y2, fill=color, outline="#0f172a", width=2)
                if x2 - x1 > 20:
                    c.create_text((x1+x2)//2, (y1+y2)//2,
                                  text=f"{end-start:.0f}s",
                                  fill="white", font=("Consolas", 8, "bold"))

        c.configure(scrollregion=(0, 0, LABEL_W + (max_t+2)*PX_PER_SEC,
                                  TOP + len(pids)*ROW_H + 30))

    # ── Tab: Stats ────────────────────────────────
    def _build_tab_stats(self):
        tk.Label(self.tab_stats, text="PERFORMANCE METRICS",
                 font=("Consolas", 13, "bold"),
                 bg="#0f172a", fg="#64748b").pack(pady=(15,10))

        self.stats_frame = tk.Frame(self.tab_stats, bg="#0f172a")
        self.stats_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        self.stat_labels = {}
        metrics = [
            ("avg_waiting",     "Avg Waiting Time",     "#f59e0b"),
            ("avg_tat",         "Avg Turnaround Time",  "#3b82f6"),
            ("throughput",      "Throughput",            "#10b981"),
            ("cpu_util",        "CPU Utilization",       "#8b5cf6"),
            ("mem_util",        "Memory Utilization",    "#ec4899"),
            ("total_patients",  "Total Patients",        "#06b6d4"),
            ("completed",       "Completed",             "#4ade80"),
            ("algorithm",       "Algorithm Used",        "#a3e635"),
        ]
        row_f = None
        for i, (key, label, color) in enumerate(metrics):
            if i % 4 == 0:
                row_f = tk.Frame(self.stats_frame, bg="#0f172a")
                row_f.pack(fill=tk.X, pady=6)
            card = tk.Frame(row_f, bg="#1e293b", bd=0, relief="flat")
            card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=6, pady=6, ipadx=12, ipady=12)
            tk.Label(card, text=label,
                     font=("Consolas", 9), bg="#1e293b", fg="#64748b").pack()
            lbl = tk.Label(card, text="—",
                           font=("Consolas", 16, "bold"),
                           bg="#1e293b", fg=color)
            lbl.pack(pady=4)
            self.stat_labels[key] = lbl

        self._update_stats()

    def _update_stats(self):
        done = [p for p in self.patients if p.status == "Discharged"]
        total = len(self.patients)
        total_mem = sum(b.total_size for b in self.memory_blocks)
        used_mem  = sum(b.used for b in self.memory_blocks)

        avg_w = (sum(p.waiting_time for p in done) / len(done)) if done else 0
        avg_t = (sum(p.turnaround_time for p in done) / len(done)) if done else 0
        tp    = f"{len(done) / max(self.sim_time, 1):.2f}/s" if self.sim_time else "—"
        cpu   = f"{(sum(p.treatment_time for p in done)/max(self.sim_time,1)*100):.1f}%" if self.sim_time else "—"
        mem_u = f"{used_mem}/{total_mem} MB  ({100*used_mem//total_mem if total_mem else 0}%)"

        self.stat_labels["avg_waiting"].config(text=f"{avg_w:.2f}s")
        self.stat_labels["avg_tat"].config(text=f"{avg_t:.2f}s")
        self.stat_labels["throughput"].config(text=tp)
        self.stat_labels["cpu_util"].config(text=cpu)
        self.stat_labels["mem_util"].config(text=mem_u)
        self.stat_labels["total_patients"].config(text=str(total))
        self.stat_labels["completed"].config(text=str(len(done)))
        self.stat_labels["algorithm"].config(text=self.sched_var.get())

    # ── Patient Table Refresh ─────────────────────
    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.patients:
            wait = f"{p.waiting_time:.1f}" if p.waiting_time else "—"
            tat  = f"{p.turnaround_time:.1f}" if p.turnaround_time else "—"
            iid = self.tree.insert("", tk.END, values=(
                f"P{p.pid}", p.name, p.department, p.severity,
                p.treatment_time, p.memory_required,
                p.status, wait, tat
            ))
            # Color by status
            color = STATUS_COLORS.get(p.status, "#e2e8f0")
            self.tree.tag_configure(p.status, foreground=color)
            self.tree.item(iid, tags=(p.status,))

    # ── Logging ───────────────────────────────────
    def _log(self, msg):
        t = f"[{self.sim_time:.1f}s] {msg}"
        self.log_lines.append(t)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, t + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ── Add Patient Dialog ────────────────────────
    def _open_add_patient(self):
        dlg = tk.Toplevel(self)
        dlg.title("Admit New Patient")
        dlg.geometry("360x380")
        dlg.configure(bg="#0f172a")
        dlg.grab_set()

        fields = {}
        rows = [
            ("Name",            "entry",    "John Doe"),
            ("Department",      "combo",    DEPARTMENTS),
            ("Severity (1-5)",  "entry",    "3"),
            ("Treatment Time (s)","entry",  "10"),
            ("Memory Required (MB)","entry","80"),
        ]

        for label, kind, default in rows:
            tk.Label(dlg, text=label, bg="#0f172a", fg="#94a3b8",
                     font=("Consolas", 10)).pack(anchor=tk.W, padx=20, pady=(8,2))
            if kind == "entry":
                var = tk.StringVar(value=default)
                tk.Entry(dlg, textvariable=var, bg="#1e293b", fg="white",
                         font=("Consolas", 10), insertbackground="white",
                         relief="flat", bd=6).pack(fill=tk.X, padx=20)
                fields[label] = var
            else:
                var = tk.StringVar(value=default[0])
                ttk.Combobox(dlg, textvariable=var, values=default,
                             state="readonly").pack(fill=tk.X, padx=20)
                fields[label] = var

        def admit():
            try:
                p = Patient(
                    name=fields["Name"].get(),
                    department=fields["Department"].get(),
                    severity=int(fields["Severity (1-5)"].get()),
                    treatment_time=int(fields["Treatment Time (s)"].get()),
                    memory_required=int(fields["Memory Required (MB)"].get()),
                    arrival_time=self.sim_time,
                )
                self.patients.append(p)
                self._refresh_table()
                self._log(f"ADMIT  P{p.pid} {p.name} → {p.department}")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Input Error", str(e))

        tk.Button(dlg, text="Admit Patient", bg="#3b82f6", fg="white",
                  font=("Consolas", 11, "bold"), relief="flat",
                  command=admit).pack(pady=20, padx=20, fill=tk.X)

    # ── Sample Data ───────────────────────────────
    def _add_sample_patients(self):
        samples = [
            ("Ali Khan",      "Emergency",   5, 8,  120),
            ("Sara Ahmed",    "Surgery",     4, 15, 200),
            ("Hamza Malik",   "General",     2, 5,  60),
            ("Zara Siddiqui", "ICU",         5, 20, 280),
            ("Usman Raza",    "Pediatrics",  3, 7,  90),
            ("Fatima Noor",   "Cardiology",  4, 12, 150),
            ("Omar Sheikh",   "General",     1, 4,  50),
        ]
        for name, dept, sev, tt, mem in samples:
            p = Patient(name=name, department=dept, severity=sev,
                        treatment_time=tt, memory_required=mem,
                        arrival_time=0.0)
            self.patients.append(p)
        self._refresh_table()

    # ── Simulation Core ───────────────────────────
    def _start_sim(self):
        if self.sim_running:
            return
        waiting = [p for p in self.patients if p.status == "Waiting"]
        if not waiting:
            messagebox.showinfo("No Patients", "No waiting patients to simulate.")
            return
        self.sim_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_dot.config(text="● RUNNING", fg="#4ade80")
        self.sim_thread = threading.Thread(target=self._run_simulation, daemon=True)
        self.sim_thread.start()

    def _stop_sim(self):
        self.sim_running = False
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_dot.config(text="● STOPPED", fg="#f59e0b")

    def _run_simulation(self):
        algo = self.sched_var.get()
        mem_algo = self.mem_var.get()
        quantum = int(self.quantum_var.get()) if algo == "Round Robin" else None

        alloc_fn = {
            "First Fit": allocate_first_fit,
            "Best Fit":  allocate_best_fit,
            "Worst Fit": allocate_worst_fit,
        }[mem_algo]

        # Get waiting patients, sort by chosen algo
        queue = [p for p in self.patients if p.status == "Waiting"]
        if algo == "FCFS":
            queue = schedule_fcfs(queue)
        elif algo == "SJF":
            queue = schedule_sjf(queue)
        elif algo == "Priority":
            queue = schedule_priority(queue)
        # Round Robin uses deque
        rr_queue = deque(queue) if algo == "Round Robin" else None

        self._log(f"=== Simulation START ({algo} | {mem_algo}) ===")

        if algo == "Round Robin":
            self._simulate_rr(rr_queue, alloc_fn, quantum)
        else:
            self._simulate_sequential(queue, alloc_fn)

        self.sim_running = False
        self.after(0, lambda: self.run_btn.config(state=tk.NORMAL))
        self.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        self.after(0, lambda: self.status_dot.config(text="● DONE", fg="#4ade80"))
        self.after(0, lambda: self._log("=== Simulation COMPLETE ==="))
        self.after(0, self._update_stats)
        self.after(0, self._draw_gantt)

    def _simulate_sequential(self, queue, alloc_fn):
        for p in queue:
            if not self.sim_running:
                break

            # Memory allocation
            blk_idx = alloc_fn(self.memory_blocks, p)
            if blk_idx is None:
                p.status = "Error"
                self._log(f"❌ P{p.pid} {p.name}: No memory available ({p.memory_required}MB needed)")
                self.after(0, self._refresh_table)
                continue

            blk = self.memory_blocks[blk_idx]
            blk.patient = p
            blk.used = p.memory_required
            p.memory_block = blk_idx
            p.status = "Admitted"
            p.waiting_time = self.sim_time - p.arrival_time
            self._log(f"🏥 P{p.pid} {p.name} → Ward {blk.block_id} ({p.memory_required}MB)")
            self.after(0, self._refresh_table)
            self.after(0, self._draw_memory)
            time.sleep(0.3)

            # CPU treatment
            p.status = "In Treatment"
            p.start_time = self.sim_time
            color = self._gantt_color(p.pid)
            t_start = self.sim_time
            self._log(f"💊 P{p.pid} treating... ({p.treatment_time}s)")
            self.after(0, self._refresh_table)

            for tick in range(p.treatment_time):
                if not self.sim_running:
                    break
                time.sleep(0.12)
                self.sim_time += 1
                self.after(0, lambda t=self.sim_time:
                           self.sim_time_lbl.config(text=f"⏱ Sim Time: {t:.0f}s"))

            t_end = self.sim_time
            self.gantt_events.append((p.pid, p.name, t_start, t_end, color))

            # Discharge
            p.status = "Discharged"
            p.finish_time = self.sim_time
            p.turnaround_time = p.finish_time - p.arrival_time
            blk.patient = None
            blk.used = 0
            self._log(f"✅ P{p.pid} {p.name} discharged. TAT={p.turnaround_time:.0f}s")
            self.after(0, self._refresh_table)
            self.after(0, self._draw_memory)
            self.after(0, self._update_stats)
            self.after(0, self._draw_gantt)
            time.sleep(0.2)

    def _simulate_rr(self, rr_queue, alloc_fn, quantum):
        # Allocate all memory first
        admitted = []
        for p in list(rr_queue):
            blk_idx = alloc_fn(self.memory_blocks, p)
            if blk_idx is None:
                p.status = "Error"
                self._log(f"❌ P{p.pid} {p.name}: No memory")
                rr_queue.remove(p)
                continue
            blk = self.memory_blocks[blk_idx]
            blk.patient = p
            blk.used = p.memory_required
            p.memory_block = blk_idx
            p.status = "Admitted"
            p.waiting_time = self.sim_time - p.arrival_time
            admitted.append(p)
            self._log(f"🏥 P{p.pid} {p.name} → Ward {blk.block_id} ({p.memory_required}MB)")

        self.after(0, self._refresh_table)
        self.after(0, self._draw_memory)
        time.sleep(0.4)

        current_queue = deque(admitted)
        while current_queue and self.sim_running:
            p = current_queue.popleft()
            if p.status == "Discharged":
                continue
            p.status = "In Treatment"
            if p.start_time == 0.0:
                p.start_time = self.sim_time
            run_for = min(quantum, p.remaining_time)
            color = self._gantt_color(p.pid)
            t_start = self.sim_time
            self._log(f"💊 P{p.pid} {p.name} running {run_for}s (remaining {p.remaining_time}s)")
            self.after(0, self._refresh_table)

            for _ in range(run_for):
                if not self.sim_running:
                    return
                time.sleep(0.10)
                self.sim_time += 1
                p.remaining_time -= 1
                self.after(0, lambda t=self.sim_time:
                           self.sim_time_lbl.config(text=f"⏱ Sim Time: {t:.0f}s"))

            t_end = self.sim_time
            self.gantt_events.append((p.pid, p.name, t_start, t_end, color))

            if p.remaining_time > 0:
                p.status = "Waiting"
                current_queue.append(p)
                self._log(f"⏩ P{p.pid} preempted, {p.remaining_time}s left")
            else:
                p.status = "Discharged"
                p.finish_time = self.sim_time
                p.turnaround_time = p.finish_time - p.arrival_time
                if p.memory_block is not None:
                    b = self.memory_blocks[p.memory_block]
                    b.patient = None
                    b.used = 0
                self._log(f"✅ P{p.pid} {p.name} discharged. TAT={p.turnaround_time:.0f}s")
                self.after(0, self._draw_memory)

            self.after(0, self._refresh_table)
            self.after(0, self._update_stats)
            self.after(0, self._draw_gantt)
            time.sleep(0.1)

    # ── Reset ─────────────────────────────────────
    def _reset(self):
        global pid_counter
        if self.sim_running:
            self._stop_sim()
            time.sleep(0.2)
        pid_counter = 0
        self.patients.clear()
        self.gantt_events.clear()
        self.gantt_colors.clear()
        self._palette_idx = 0
        self.sim_time = 0.0
        for b in self.memory_blocks:
            b.patient = None
            b.used = 0
        self.log_lines.clear()
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.sim_time_lbl.config(text="⏱ Sim Time: 0.0s")
        self.status_dot.config(text="● IDLE", fg="#64748b")
        self._add_sample_patients()
        self._draw_memory()
        self.gantt_canvas.delete("all")
        self._update_stats()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = HospitalOSApp()
    app.mainloop()