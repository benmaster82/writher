"""Settings window for Writher — dark-themed, borderless, draggable.

Allows the user to configure:
  - Recording mode: hold-to-record vs toggle (press to start/stop)
  - Max recording duration in seconds (toggle mode only)
"""

import tkinter as tk
from logger import log
import config
import database as db
import locales
from brand import make_title_bar_image
from PIL import ImageTk

# ── Palette (matches notes_window.py) ─────────────────────────────────────
_BG        = "#16161a"
_BG2       = "#1e1e24"
_FG        = "#e0e0e8"
_ACCENT    = "#5bcefa"
_DIM       = "#78787f"
_CARD_BG   = "#24242c"
_BORDER    = "#2e2e38"
_TITLE_BG  = "#131316"
_CLOSE_HOV = "#e05555"
_BTN_BG    = "#2a2a32"
_BTN_SEL   = "#5bcefa"
_SLIDER_BG = "#2a2a32"
_SLIDER_FG = "#5bcefa"

_WIN_W, _WIN_H = 400, 300
_TITLE_H = 38


class SettingsWindow:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._win = None
        self._drag_x = 0
        self._drag_y = 0
        self._title_eye_tk = None
        self._hold_btn = None
        self._toggle_btn = None
        self._slider = None
        self._slider_label = None
        self._slider_frame = None

    def show(self):
        if self._win is not None:
            try:
                if self._win.winfo_exists():
                    self._win.lift()
                    self._sync_ui()
                    return
            except Exception:
                pass
        self._build()
        self._sync_ui()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self):
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.configure(bg=_BORDER)
        win.attributes("-topmost", True)

        sx = win.winfo_screenwidth()
        sy = win.winfo_screenheight()
        x = (sx - _WIN_W) // 2
        y = (sy - _WIN_H) // 2
        win.geometry(f"{_WIN_W}x{_WIN_H}+{x}+{y}")
        self._win = win

        outer = tk.Frame(win, bg=_BORDER)
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        # ── Title bar ────────────────────────────────────────────────
        title_bar = tk.Frame(outer, bg=_TITLE_BG, height=_TITLE_H)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        eye_img = make_title_bar_image(size=20)
        self._title_eye_tk = ImageTk.PhotoImage(eye_img)
        eye_lbl = tk.Label(title_bar, image=self._title_eye_tk, bg=_TITLE_BG)
        eye_lbl.pack(side="left", padx=(12, 6))

        title_lbl = tk.Label(title_bar, text=locales.get("settings_title"),
                             bg=_TITLE_BG, fg=_FG,
                             font=("Segoe UI", 10, "bold"))
        title_lbl.pack(side="left")

        close_btn = tk.Label(title_bar, text="✕", bg=_TITLE_BG, fg=_DIM,
                             font=("Segoe UI", 11), padx=14, cursor="hand2")
        close_btn.pack(side="right", fill="y")
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg=_CLOSE_HOV, fg="#fff"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=_TITLE_BG, fg=_DIM))
        close_btn.bind("<Button-1>", lambda e: self._close())

        for w in (title_bar, title_lbl):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        # ── Content ──────────────────────────────────────────────────
        content = tk.Frame(outer, bg=_BG)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        # Recording mode label
        tk.Label(content, text=locales.get("setting_record_mode"),
                 bg=_BG, fg=_FG, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 10))

        # Mode buttons row
        btn_row = tk.Frame(content, bg=_BG)
        btn_row.pack(fill="x", pady=(0, 20))

        self._hold_btn = tk.Label(
            btn_row, text=locales.get("setting_hold"),
            bg=_BTN_BG, fg=_FG, font=("Segoe UI", 9),
            padx=16, pady=8, cursor="hand2",
        )
        self._hold_btn.pack(side="left", padx=(0, 8))
        self._hold_btn.bind("<Button-1>", lambda e: self._set_mode(True))

        self._toggle_btn = tk.Label(
            btn_row, text=locales.get("setting_toggle"),
            bg=_BTN_BG, fg=_FG, font=("Segoe UI", 9),
            padx=16, pady=8, cursor="hand2",
        )
        self._toggle_btn.pack(side="left")
        self._toggle_btn.bind("<Button-1>", lambda e: self._set_mode(False))

        # Separator
        tk.Frame(content, bg=_BORDER, height=1).pack(fill="x", pady=(0, 16))

        # Max duration slider (toggle mode only)
        self._slider_frame = tk.Frame(content, bg=_BG)
        self._slider_frame.pack(fill="x")

        tk.Label(self._slider_frame,
                 text=locales.get("setting_max_duration"),
                 bg=_BG, fg=_FG, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 8))

        slider_row = tk.Frame(self._slider_frame, bg=_BG)
        slider_row.pack(fill="x")

        self._slider = tk.Scale(
            slider_row, from_=30, to=300, orient="horizontal",
            bg=_BG, fg=_FG, troughcolor=_SLIDER_BG,
            highlightthickness=0, bd=0, sliderrelief="flat",
            font=("Segoe UI", 9), length=280,
            command=self._on_slider_change,
        )
        self._slider.pack(side="left", fill="x", expand=True)

        self._slider_label = tk.Label(
            slider_row, text="120s", bg=_BG, fg=_ACCENT,
            font=("Segoe UI", 10, "bold"), width=5,
        )
        self._slider_label.pack(side="right", padx=(8, 0))

    # ── Drag ──────────────────────────────────────────────────────────────

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        if self._win:
            x = self._win.winfo_x() + (event.x - self._drag_x)
            y = self._win.winfo_y() + (event.y - self._drag_y)
            self._win.geometry(f"+{x}+{y}")

    def _close(self):
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None

    # ── UI sync ───────────────────────────────────────────────────────────

    def _sync_ui(self):
        """Update UI elements to reflect current config values."""
        hold = getattr(config, "HOLD_TO_RECORD", True)
        self._update_mode_buttons(hold)
        max_sec = getattr(config, "MAX_RECORD_SECONDS", 120)
        if self._slider:
            self._slider.set(max_sec)
        if self._slider_label:
            self._slider_label.config(text=f"{max_sec}s")
        self._update_slider_visibility(hold)

    def _update_mode_buttons(self, hold: bool):
        if self._hold_btn:
            self._hold_btn.config(
                bg=_BTN_SEL if hold else _BTN_BG,
                fg="#000" if hold else _FG,
            )
        if self._toggle_btn:
            self._toggle_btn.config(
                bg=_BTN_SEL if not hold else _BTN_BG,
                fg="#000" if not hold else _FG,
            )

    def _update_slider_visibility(self, hold: bool):
        """Show slider only in toggle mode."""
        if self._slider_frame:
            if hold:
                self._slider_frame.pack_forget()
            else:
                self._slider_frame.pack(fill="x")

    # ── Callbacks ─────────────────────────────────────────────────────────

    def _set_mode(self, hold: bool):
        config.HOLD_TO_RECORD = hold
        db.save_setting("hold_to_record", "1" if hold else "0")
        self._update_mode_buttons(hold)
        self._update_slider_visibility(hold)
        log.info("Recording mode set to %s", "hold" if hold else "toggle")

    def _on_slider_change(self, value):
        seconds = int(float(value))
        config.MAX_RECORD_SECONDS = seconds
        db.save_setting("max_record_seconds", str(seconds))
        if self._slider_label:
            self._slider_label.config(text=f"{seconds}s")
