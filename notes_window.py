"""Custom borderless window for viewing notes, appointments and reminders."""

import json
import tkinter as tk
from datetime import datetime
from PIL import ImageTk
from logger import log
import database as db
import locales
from brand import make_title_bar_image

# ── Palette ───────────────────────────────────────────────────────────────
_BG        = "#16161a"
_BG2       = "#1e1e24"
_FG        = "#e0e0e8"
_ACCENT    = "#5bcefa"
_CARD_BG   = "#24242c"
_CARD_HOVER = "#2c2c36"
_DIM       = "#78787f"
_RED       = "#e05555"
_RED_HOVER = "#ff6666"
_GREEN     = "#55cc77"
_BORDER    = "#2e2e38"
_TAB_BG    = "#1a1a20"
_TAB_SEL   = "#5bcefa"
_TITLE_BG  = "#131316"
_CLOSE_BG  = "#2a2a32"
_CLOSE_HOV = "#e05555"

_WIN_W, _WIN_H = 500, 580
_TITLE_H   = 38
_TAB_H     = 36


class NotesWindow:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._win = None
        self._current_tab = "notes"
        self._drag_x = 0
        self._drag_y = 0
        self._tab_buttons = {}
        self._tab_indicators = {}
        self._content_frame = None
        self._scroll_canvas = None
        self._inner_frame = None
        self._title_eye_tk = None  # prevent garbage collection of title bar image

    def show(self, tab: str = "notes"):
        if self._win is not None:
            try:
                if self._win.winfo_exists():
                    self._win.lift()
                    self._switch_tab(tab)
                    return
            except Exception:
                pass
        self._build()
        self._switch_tab(tab)

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self):
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.configure(bg=_BORDER)
        win.attributes("-topmost", False)

        # Centre on screen
        sx = win.winfo_screenwidth()
        sy = win.winfo_screenheight()
        x = (sx - _WIN_W) // 2
        y = (sy - _WIN_H) // 2
        win.geometry(f"{_WIN_W}x{_WIN_H}+{x}+{y}")
        self._win = win

        # Outer border frame (1 px border effect)
        outer = tk.Frame(win, bg=_BORDER)
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        # ── Custom title bar ──────────────────────────────────────────────
        title_bar = tk.Frame(outer, bg=_TITLE_BG, height=_TITLE_H)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        # Title icon (Pandora Blackboard eyes rendered via PIL)
        eye_img = make_title_bar_image(size=20)
        self._title_eye_tk = ImageTk.PhotoImage(eye_img)
        eye_lbl = tk.Label(title_bar, image=self._title_eye_tk, bg=_TITLE_BG)
        eye_lbl.pack(side="left", padx=(12, 6))

        title_lbl = tk.Label(title_bar, text="Writher", bg=_TITLE_BG, fg=_FG,
                             font=("Segoe UI", 10, "bold"))
        title_lbl.pack(side="left")

        # Close button
        close_btn = tk.Label(title_bar, text="✕", bg=_TITLE_BG, fg=_DIM,
                             font=("Segoe UI", 11), padx=14, cursor="hand2")
        close_btn.pack(side="right", fill="y")
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg=_CLOSE_HOV, fg="#fff"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=_TITLE_BG, fg=_DIM))
        close_btn.bind("<Button-1>", lambda e: self._close())

        # Drag support
        for w in (title_bar, title_lbl):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        # ── Tab bar ──────────────────────────────────────────────────────
        tab_bar = tk.Frame(outer, bg=_BG, height=_TAB_H)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        tabs = [
            ("notes",        locales.get("tab_notes")),
            ("appointments", locales.get("tab_agenda")),
            ("reminders",    locales.get("tab_reminders")),
        ]

        for key, label in tabs:
            col = tk.Frame(tab_bar, bg=_BG)
            col.pack(side="left", fill="y", padx=(0, 1))

            btn = tk.Label(col, text=label, bg=_BG, fg=_DIM,
                           font=("Segoe UI", 9), padx=16, pady=8,
                           cursor="hand2")
            btn.pack(fill="both", expand=True)

            # Bottom indicator line
            indicator = tk.Frame(col, bg=_BG, height=2)
            indicator.pack(fill="x")

            btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=_FG) if b.cget("fg") != _ACCENT else None)
            btn.bind("<Leave>", lambda e, b=btn, k=key: b.config(fg=_DIM) if k != self._current_tab else None)

            self._tab_buttons[key] = btn
            self._tab_indicators[key] = indicator

        # Separator line under tabs
        tk.Frame(outer, bg=_BORDER, height=1).pack(fill="x")

        # ── Scrollable content area ──────────────────────────────────────
        content = tk.Frame(outer, bg=_BG2)
        content.pack(fill="both", expand=True)
        self._content_frame = content

        canvas = tk.Canvas(content, bg=_BG2, highlightthickness=0, bd=0)
        inner = tk.Frame(canvas, bg=_BG2)

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw",
                                                 width=_WIN_W - 4)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(fill="both", expand=True)

        content.bind("<Configure>",
                     lambda e: canvas.itemconfig(self._canvas_win,
                                                 width=e.width - 4)
                     if canvas.find_all() else None)

        # Custom scrollbar drawn on the canvas
        self._sb_id = canvas.create_rectangle(0, 0, 0, 0,
                                              fill="#3a3a48", outline="")
        self._sb_visible = False

        def _update_scrollbar(*_args):
            first, last = canvas.yview()
            if float(last) - float(first) >= 1.0:
                canvas.coords(self._sb_id, 0, 0, 0, 0)
                self._sb_visible = False
                return
            self._sb_visible = True
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            sb_w = 4
            sb_x = cw - sb_w - 2
            bar_h = max(20, ch * (float(last) - float(first)))
            bar_y = ch * float(first)
            canvas.coords(self._sb_id, sb_x, bar_y + 2,
                          sb_x + sb_w, bar_y + bar_h - 2)
            canvas.tag_raise(self._sb_id)

        canvas.configure(yscrollcommand=_update_scrollbar)

        self._scroll_canvas = canvas
        self._inner_frame = inner

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

    # ── Tabs ──────────────────────────────────────────────────────────────

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        for key, btn in self._tab_buttons.items():
            if key == tab:
                btn.config(fg=_ACCENT)
                self._tab_indicators[key].config(bg=_TAB_SEL)
            else:
                btn.config(fg=_DIM)
                self._tab_indicators[key].config(bg=_BG)
        self._refresh()

    def _refresh(self):
        for w in self._inner_frame.winfo_children():
            w.destroy()
        if self._current_tab == "notes":
            self._populate_notes()
        elif self._current_tab == "appointments":
            self._populate_appointments()
        elif self._current_tab == "reminders":
            self._populate_reminders()

    # ── Card helper ───────────────────────────────────────────────────────

    def _make_card(self, parent) -> tk.Frame:
        card = tk.Frame(parent, bg=_CARD_BG, padx=12, pady=10)
        card.pack(fill="x", padx=8, pady=4)

        def _enter(e):
            card.config(bg=_CARD_HOVER)
            for child in card.winfo_children():
                try:
                    if child.cget("bg") == _CARD_BG:
                        child.config(bg=_CARD_HOVER)
                    for sub in child.winfo_children():
                        if sub.cget("bg") == _CARD_BG:
                            sub.config(bg=_CARD_HOVER)
                except Exception:
                    pass

        def _leave(e):
            card.config(bg=_CARD_BG)
            for child in card.winfo_children():
                try:
                    if child.cget("bg") == _CARD_HOVER:
                        child.config(bg=_CARD_BG)
                    for sub in child.winfo_children():
                        if sub.cget("bg") == _CARD_HOVER:
                            sub.config(bg=_CARD_BG)
                except Exception:
                    pass

        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)
        return card

    def _make_delete_btn(self, parent, command) -> tk.Label:
        btn = tk.Label(parent, text="✕", bg=_CARD_BG, fg=_DIM,
                       font=("Segoe UI", 9), cursor="hand2", padx=4)
        btn.pack(side="right")
        btn.bind("<Enter>", lambda e: btn.config(fg=_RED_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(fg=_DIM))
        btn.bind("<Button-1>", lambda e: command())
        return btn

    # ── Notes ─────────────────────────────────────────────────────────────

    def _populate_notes(self):
        notes = db.get_all_notes()
        if not notes:
            tk.Label(self._inner_frame, text=locales.get("no_notes"),
                     bg=_BG2, fg=_DIM, font=("Segoe UI", 11)).pack(pady=40)
            return

        for note in notes:
            card = self._make_card(self._inner_frame)
            hdr = tk.Frame(card, bg=_CARD_BG)
            hdr.pack(fill="x")

            title = note["title"] or (
                locales.get("default_list_title") if note["note_type"] == "list"
                else locales.get("default_note_title")
            )
            tk.Label(hdr, text=title, bg=_CARD_BG, fg=_ACCENT,
                     font=("Segoe UI", 10, "bold"), anchor="w").pack(side="left")

            tk.Label(hdr, text=note["category"], bg=_CARD_BG, fg=_DIM,
                     font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))

            nid = note["id"]
            self._make_delete_btn(hdr, lambda i=nid: self._delete_note(i))

            if note["note_type"] == "list":
                self._render_list(card, note)
            else:
                tk.Label(card, text=note["content"], bg=_CARD_BG, fg=_FG,
                         font=("Segoe UI", 10), anchor="w", justify="left",
                         wraplength=420).pack(fill="x", pady=(6, 0))

            tk.Label(card, text=note["updated_at"], bg=_CARD_BG, fg=_DIM,
                     font=("Segoe UI", 8), anchor="e").pack(fill="x", pady=(4, 0))

    def _render_list(self, parent: tk.Frame, note: dict):
        try:
            items = json.loads(note["content"])
        except (json.JSONDecodeError, TypeError):
            items = []

        for entry in items:
            row = tk.Frame(parent, bg=_CARD_BG)
            row.pack(fill="x", pady=1)

            checked = entry.get("checked", False)
            text = entry.get("item", "")
            symbol = "☑" if checked else "☐"
            fg = _DIM if checked else _FG

            nid = note["id"]
            item_text = text
            btn = tk.Button(
                row, text=f"{symbol}  {text}", bg=_CARD_BG, fg=fg,
                font=("Segoe UI", 10), bd=0, anchor="w", cursor="hand2",
                activebackground=_CARD_HOVER, activeforeground=fg,
                command=lambda i=nid, t=item_text: self._toggle_item(i, t),
            )
            btn.pack(fill="x")

    def _toggle_item(self, note_id: int, item_text: str):
        db.check_item(note_id, item_text)
        self._refresh()

    def _delete_note(self, note_id: int):
        db.delete_note(note_id)
        self._refresh()

    # ── Appointments ──────────────────────────────────────────────────────

    def _populate_appointments(self):
        appts = db.get_appointments()
        if not appts:
            tk.Label(self._inner_frame, text=locales.get("no_appointments"),
                     bg=_BG2, fg=_DIM, font=("Segoe UI", 11)).pack(pady=40)
            return

        for a in appts:
            card = self._make_card(self._inner_frame)
            hdr = tk.Frame(card, bg=_CARD_BG)
            hdr.pack(fill="x")

            tk.Label(hdr, text=a["title"], bg=_CARD_BG, fg=_ACCENT,
                     font=("Segoe UI", 10, "bold"), anchor="w").pack(side="left")

            aid = a["id"]
            self._make_delete_btn(hdr, lambda i=aid: self._delete_appt(i))

            try:
                dt = datetime.fromisoformat(a["dt"])
                dt_str = dt.strftime("%d/%m/%Y  %H:%M")
            except Exception:
                dt_str = a["dt"]
            tk.Label(card, text=f"📅  {dt_str}", bg=_CARD_BG, fg=_FG,
                     font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(6, 0))

            if a["description"]:
                tk.Label(card, text=a["description"], bg=_CARD_BG, fg=_DIM,
                         font=("Segoe UI", 9), anchor="w", wraplength=420,
                         justify="left").pack(fill="x", pady=(2, 0))

    def _delete_appt(self, aid: int):
        db.delete_appointment(aid)
        self._refresh()

    # ── Reminders ─────────────────────────────────────────────────────────

    def _populate_reminders(self):
        rems = db.get_all_reminders(include_notified=True)
        if not rems:
            tk.Label(self._inner_frame, text=locales.get("no_reminders"),
                     bg=_BG2, fg=_DIM, font=("Segoe UI", 11)).pack(pady=40)
            return

        for r in rems:
            card = self._make_card(self._inner_frame)
            hdr = tk.Frame(card, bg=_CARD_BG)
            hdr.pack(fill="x")

            done = r["notified"]
            status = "✓" if done else "⏰"
            fg = _DIM if done else _FG
            tk.Label(hdr, text=f"{status}  {r['message']}", bg=_CARD_BG, fg=fg,
                     font=("Segoe UI", 10), anchor="w").pack(side="left")

            rid = r["id"]
            self._make_delete_btn(hdr, lambda i=rid: self._delete_rem(i))

            try:
                dt = datetime.fromisoformat(r["remind_at"])
                dt_str = dt.strftime("%d/%m/%Y  %H:%M")
            except Exception:
                dt_str = r["remind_at"]
            tk.Label(card, text=dt_str, bg=_CARD_BG, fg=_DIM,
                     font=("Segoe UI", 8), anchor="e").pack(fill="x", pady=(4, 0))

    def _delete_rem(self, rid: int):
        db.delete_reminder(rid)
        self._refresh()
