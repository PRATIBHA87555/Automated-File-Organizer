"""File Organizer - a modern desktop app. Run:  python app.py"""
import queue
import threading
import time
from collections import Counter
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import organizer

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CAT_COLORS = {
    "Images": "#ec4899", "Videos": "#8b5cf6", "Audio": "#f59e0b", "Documents": "#3b82f6",
    "Spreadsheets": "#10b981", "Presentations": "#f97316", "Archives": "#64748b",
    "Code": "#06b6d4", "Installers": "#ef4444", "Others": "#94a3b8",
}
BG = "#0f172a"
CARD = "#1e293b"
ACCENT = "#6366f1"
AUTO_INTERVAL_MS = 10_000


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("File Organizer")
        self.geometry("920x720")
        self.minsize(760, 620)
        self.configure(fg_color=BG)

        self.q = queue.Queue()
        self.busy = False
        self.auto_job = None
        self.total_moved = 0

        self._build_ui()
        self.after(100, self._poll)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Header
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 4))
        ctk.CTkLabel(head, text="File Organizer", font=ctk.CTkFont(size=30, weight="bold"),
                     text_color="#f8fafc").pack(anchor="w")
        ctk.CTkLabel(head, text="Sort messy folders into clean categories in one click.",
                     font=ctk.CTkFont(size=14), text_color="#94a3b8").pack(anchor="w")

        # Folder picker
        picker = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        picker.grid(row=1, column=0, sticky="ew", padx=28, pady=(16, 8))
        picker.grid_columnconfigure(0, weight=1)
        self.folder_var = ctk.StringVar(value=str(Path.home() / "Downloads"))
        ctk.CTkEntry(picker, textvariable=self.folder_var, height=42, corner_radius=10,
                     font=ctk.CTkFont(size=14), border_width=0, fg_color="#0f172a"
                     ).grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=16)
        ctk.CTkButton(picker, text="Browse", width=110, height=42, corner_radius=10,
                      fg_color="#334155", hover_color="#475569", command=self.browse
                      ).grid(row=0, column=1, padx=(0, 16), pady=16)

        # Category badges
        self.badge_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        self.badge_frame.grid(row=2, column=0, sticky="ew", padx=28, pady=8)
        self._render_badges(None)

        # Action row
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=28, pady=8)
        self.btn_preview = ctk.CTkButton(
            actions, text="Preview", height=44, width=130, corner_radius=12,
            fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run(self._do_preview))
        self.btn_preview.pack(side="left")
        self.btn_org = ctk.CTkButton(
            actions, text="Organize Now", height=44, width=170, corner_radius=12,
            fg_color=ACCENT, hover_color="#4f46e5", font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run(self._do_organize))
        self.btn_org.pack(side="left", padx=10)
        self.btn_undo = ctk.CTkButton(
            actions, text="Undo Last", height=44, width=130, corner_radius=12,
            fg_color="transparent", border_width=2, border_color="#475569",
            hover_color="#1e293b", font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._run(self._do_undo))
        self.btn_undo.pack(side="left")

        self.auto_switch = ctk.CTkSwitch(
            actions, text="Auto-organize (every 10s)", progress_color=ACCENT,
            font=ctk.CTkFont(size=13), text_color="#cbd5e1", command=self._toggle_auto)
        self.auto_switch.pack(side="right")

        # Log
        log_card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        log_card.grid(row=4, column=0, sticky="nsew", padx=28, pady=8)
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(log_card, text="Activity", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color="#e2e8f0").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 4))
        self.log = ctk.CTkTextbox(log_card, fg_color="#0f172a", corner_radius=10,
                                  font=ctk.CTkFont(family="Consolas", size=13),
                                  text_color="#cbd5e1", wrap="word")
        self.log.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.log.configure(state="disabled")

        # Footer
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=5, column=0, sticky="ew", padx=28, pady=(4, 20))
        foot.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(foot, height=8, progress_color=ACCENT, fg_color="#334155")
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew")
        self.status = ctk.CTkLabel(foot, text="Ready", text_color="#94a3b8", font=ctk.CTkFont(size=13))
        self.status.grid(row=1, column=0, sticky="w", pady=(6, 0))

        self._log("Welcome! Pick a folder, press Preview to see what will happen, then Organize Now.")

    def _render_badges(self, counts):
        for w in self.badge_frame.winfo_children():
            w.destroy()
        if not counts:
            ctk.CTkLabel(self.badge_frame, text="Press Preview to see what is in your folder.",
                         text_color="#94a3b8", font=ctk.CTkFont(size=13)
                         ).pack(padx=18, pady=18, anchor="w")
            return
        inner = ctk.CTkFrame(self.badge_frame, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=12)
        for i, (cat, n) in enumerate(sorted(counts.items(), key=lambda x: -x[1])):
            inner.grid_columnconfigure(i % 5, weight=1, uniform="b")
            ctk.CTkLabel(inner, text=f"{cat}  {n}", height=34, corner_radius=10,
                         fg_color=CAT_COLORS.get(cat, "#94a3b8"), text_color="white",
                         font=ctk.CTkFont(size=13, weight="bold")
                         ).grid(row=i // 5, column=i % 5, padx=5, pady=5, sticky="ew")

    # ------------------------------------------------------------- helpers
    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def browse(self):
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if chosen:
            self.folder_var.set(chosen)
            self._render_badges(None)

    def _folder(self):
        p = Path(self.folder_var.get().strip())
        if not p.is_dir():
            self.q.put(("log", f"Folder not found: {p}"))
            self.q.put(("status", "Please choose a valid folder"))
            return None
        return p

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_preview, self.btn_org, self.btn_undo):
            b.configure(state=state)

    def _run(self, fn, *args):
        if self.busy:
            return
        self._set_busy(True)
        self.progress.set(0)

        def worker():
            try:
                fn(*args)
            except Exception as e:  # never let a thread die silently
                self.q.put(("log", f"Error: {e}"))
                self.q.put(("status", "Something went wrong"))
            finally:
                self.q.put(("busy", False))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self._log(val)
                elif kind == "status":
                    self.status.configure(text=val)
                elif kind == "progress":
                    self.progress.set(val)
                elif kind == "badges":
                    self._render_badges(val)
                elif kind == "busy":
                    self._set_busy(val)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _progress_cb(self, i, total):
        self.q.put(("progress", i / total if total else 1))

    # ------------------------------------------------------------- actions
    def _do_preview(self):
        folder = self._folder()
        if not folder:
            return
        self.q.put(("status", "Scanning..."))
        moves = organizer.plan(folder)
        if not moves:
            self.q.put(("badges", None))
            self.q.put(("log", "Nothing to organize. This folder is already tidy."))
            self.q.put(("status", "Nothing to do"))
            return
        self.q.put(("badges", Counter(m.category for m in moves)))
        self.q.put(("log", f"Preview: {len(moves)} file(s) would be moved."))
        for m in moves[:40]:
            self.q.put(("log", f"   {m.src.name}  ->  {m.category}/"))
        if len(moves) > 40:
            self.q.put(("log", f"   ...and {len(moves) - 40} more"))
        self.q.put(("progress", 1))
        self.q.put(("status", f"{len(moves)} file(s) ready to organize"))

    def _do_organize(self, quiet=False):
        folder = self._folder()
        if not folder:
            return
        moves = organizer.plan(folder)
        if not moves:
            if not quiet:
                self.q.put(("log", "Nothing to organize. This folder is already tidy."))
                self.q.put(("status", "Nothing to do"))
            return
        self.q.put(("status", f"Organizing {len(moves)} file(s)..."))
        done = organizer.apply(folder, moves, self._progress_cb)
        self.total_moved += len(done)
        self.q.put(("badges", Counter(m.category for m in done)))
        self.q.put(("log", f"Done! Moved {len(done)} of {len(moves)} file(s)."
                           + ("" if len(done) == len(moves) else " Some were in use and skipped.")))
        self.q.put(("status", f"Moved {len(done)} file(s)  |  total this session: {self.total_moved}"))

    def _do_undo(self):
        folder = self._folder()
        if not folder:
            return
        self.q.put(("status", "Undoing..."))
        n = organizer.undo_last(folder, self._progress_cb)
        if n:
            self.q.put(("log", f"Undo complete: restored {n} file(s) to where they were."))
            self.q.put(("status", f"Restored {n} file(s)"))
            self.q.put(("badges", None))
        else:
            self.q.put(("log", "Nothing to undo in this folder."))
            self.q.put(("status", "Nothing to undo"))

    # ---------------------------------------------------------------- auto
    def _toggle_auto(self):
        if self.auto_switch.get():
            self._log(f"Auto-organize ON: watching {self.folder_var.get()}")
            self._auto_tick()
        else:
            if self.auto_job:
                self.after_cancel(self.auto_job)
                self.auto_job = None
            self._log("Auto-organize OFF")

    def _auto_tick(self):
        if not self.auto_switch.get():
            return
        if not self.busy:
            self._run(self._do_organize, True)
        self.auto_job = self.after(AUTO_INTERVAL_MS, self._auto_tick)


if __name__ == "__main__":
    App().mainloop()
