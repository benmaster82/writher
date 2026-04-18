"""Notes, Agenda & Reminders window — CustomTkinter + Pandora Blackboard theme.

Features:
  - Dark glassmorphic design matching the floating widget
  - Resizable window with maximize / restore support
  - Custom title bar with drag, close, and maximize buttons
  - Tabbed interface (Notes, Agenda, Reminders)
  - Scrollable card-based content
"""

import json
import tkinter as tk
from datetime import datetime

import customtkinter as ctk
from PIL import ImageTk

from logger import log
import database as db
import locales
from brand import make_title_bar_image
import theme as T

_WIN_W, _WIN_H = 520, 600
_MIN_W, _MIN_H = 380, 400
_TITLE_H = 40


class NotesWindow:
    def __init__(self, root: tk.Tk):
        self._root = root
        self._win = None
        self._current_tab = "notes"
        self._drag_x = 0
        self._drag_y = 0
        self._maximized = False
        self._restore_geo = None
        self._title_eye_tk = None
        self._tab_buttons = {}
        self._scroll_frame = None

    def show(self, tab: str = "notes"):
        if self._win is not None:
            try:
                if self._win.winfo_exists():
                    self._win.attributes("-topmost", True)
                    self._win.lift()
                    self._win.focus_force()
                    self._win.after(100, lambda: self._win.attributes("-topmost", False)
                                    if self._win and self._win.winfo_exists() else None)
                    self._switch_tab(tab)
                    return
            except Exception:
                pass
        self._build()
        self._switch_tab(tab)

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self):
        win = ctk.CTkToplevel(self._root)
        win.overrideredirect(True)
        win.configure(fg_color=T.BG_DEEP)
        win.attributes("-topmost", False)
        win.minsize(_MIN_W, _MIN_H)

        sx = win.winfo_screenwidth()
        sy = win.winfo_screenheight()
        x = (sx - _WIN_W) // 2
        y = (sy - _WIN_H) // 2
        win.geometry(f"{_WIN_W}x{_WIN_H}+{x}+{y}")
        self._win = win

        # Force to front on creation, then release topmost
        win.attributes("-topmost", True)
        win.after(100, lambda: win.attributes("-topmost", False)
                  if win.winfo_exists() else None)

        # Outer border frame
        outer = ctk.CTkFrame(win, fg_color=T.BG_DEEP, border_color=T.BORDER,
                             border_width=1, corner_radius=0)
        outer.pack(fill="both", expand=True)

        # ── Custom title bar ──────────────────────────────────────────
        title_bar = ctk.CTkFrame(outer, fg_color=T.TITLE_BG, height=_TITLE_H,
                                 corner_radius=0)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        # Pandora eyes icon
        eye_img = make_title_bar_image(size=20)
        self._title_eye_tk = ImageTk.PhotoImage(eye_img)
        eye_lbl = tk.Label(title_bar, image=self._title_eye_tk, bg=T.TITLE_BG)
        eye_lbl.pack(side="left", padx=(14, 8))

        title_lbl = ctk.CTkLabel(title_bar, text="Writher", font=(T.FONT_FAMILY, 13, "bold"),
                                 text_color=T.FG)
        title_lbl.pack(side="left")

        # Close button
        close_btn = ctk.CTkButton(
            title_bar, text="✕", width=44, height=_TITLE_H,
            fg_color="transparent", hover_color=T.CLOSE_HOVER,
            text_color=T.FG_DIM, font=(T.FONT_FAMILY, 15),
            corner_radius=0, command=self._close,
        )
        close_btn.pack(side="right")

        # Maximize / restore button
        self._max_btn = ctk.CTkButton(
            title_bar, text="□", width=44, height=_TITLE_H,
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.FG_DIM, font=(T.FONT_FAMILY, 14),
            corner_radius=0, command=self._toggle_maximize,
        )
        self._max_btn.pack(side="right")

        # Drag support
        for w in (title_bar, title_lbl):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

        # ── Tab bar ───────────────────────────────────────────────────
        tab_bar = ctk.CTkFrame(outer, fg_color=T.BG, height=52, corner_radius=0)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        tabs = [
            ("notes",        locales.get("tab_notes")),
            ("appointments", locales.get("tab_agenda")),
            ("reminders",    locales.get("tab_reminders")),
        ]

        for key, label in tabs:
            btn = ctk.CTkButton(
                tab_bar, text=label, font=(T.FONT_FAMILY, 12),
                fg_color="transparent", hover_color=T.BG_HOVER,
                text_color=T.FG_DIM, corner_radius=0,
                height=52, width=160,
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(side="left", fill="y")
            self._tab_buttons[key] = btn

        # Separator
        ctk.CTkFrame(outer, fg_color=T.BORDER, height=1,
                     corner_radius=0).pack(fill="x")

        # ── Scrollable content ────────────────────────────────────────
        self._scroll_frame = ctk.CTkScrollableFrame(
            outer, fg_color=T.BG, corner_radius=0,
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.BORDER_GLOW,
        )
        self._scroll_frame.pack(fill="both", expand=True)

        # ── Resize grip (bottom-right corner) ─────────────────────────
        grip = ctk.CTkLabel(outer, text="⋮⋮", font=(T.FONT_FAMILY, 12),
                            text_color=T.FG_DIM, width=20, cursor="size_nw_se")
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<Button-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._on_resize)

    # ── Drag ──────────────────────────────────────────────────────────────

    def _start_drag(self, event):
        if self._maximized:
            return
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        if self._maximized or not self._win:
            return
        x = self._win.winfo_x() + (event.x - self._drag_x)
        y = self._win.winfo_y() + (event.y - self._drag_y)
        self._win.geometry(f"+{x}+{y}")

    # ── Resize ────────────────────────────────────────────────────────────

    def _start_resize(self, event):
        if self._maximized:
            return
        self._resize_x = event.x_root
        self._resize_y = event.y_root
        self._resize_w = self._win.winfo_width()
        self._resize_h = self._win.winfo_height()

    def _on_resize(self, event):
        if self._maximized or not self._win:
            return
        dx = event.x_root - self._resize_x
        dy = event.y_root - self._resize_y
        new_w = max(_MIN_W, self._resize_w + dx)
        new_h = max(_MIN_H, self._resize_h + dy)
        self._win.geometry(f"{new_w}x{new_h}")

    # ── Maximize / Restore ────────────────────────────────────────────────

    def _toggle_maximize(self):
        if not self._win:
            return
        if self._maximized:
            self._win.geometry(self._restore_geo)
            self._max_btn.configure(text="□")
            self._maximized = False
        else:
            self._restore_geo = self._win.geometry()
            import ctypes
            from ctypes import wintypes
            # Get the work area (screen minus taskbar)
            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                            ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
            rect = RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0,
                                                        ctypes.byref(rect), 0)
            # Tk applies its own scaling — convert physical px to Tk units
            scale = self._win.tk.call("tk", "scaling") / (96 / 72)
            if scale <= 0:
                scale = 1.0
            x = int(rect.left / scale)
            y = int(rect.top / scale)
            w = int((rect.right - rect.left) / scale)
            h = int((rect.bottom - rect.top) / scale)
            self._win.geometry(f"{w}x{h}+{x}+{y}")
            self._max_btn.configure(text="❐")
            self._maximized = True

    # ── Close ─────────────────────────────────────────────────────────────

    def _close(self):
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
            self._maximized = False
            self._tab_buttons = {}

    # ── Tabs ──────────────────────────────────────────────────────────────

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        for key, btn in self._tab_buttons.items():
            if key == tab:
                btn.configure(text_color=T.FG, fg_color=T.BG_CARD)
            else:
                btn.configure(text_color=T.FG_DIM, fg_color="transparent")
        self._refresh()

    def _refresh(self):
        for w in self._scroll_frame.winfo_children():
            w.destroy()
        if self._current_tab == "notes":
            self._populate_notes()
        elif self._current_tab == "appointments":
            self._populate_appointments()
        elif self._current_tab == "reminders":
            self._populate_reminders()

    # ── Card helper ───────────────────────────────────────────────────────

    def _make_card(self) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self._scroll_frame, fg_color=T.BG_CARD,
            border_color=T.BORDER, border_width=1,
            corner_radius=10,
        )
        card.pack(fill="x", padx=T.PAD_L, pady=(T.PAD_M, T.PAD_S))

        def _enter(e):
            card.configure(border_color=T.BORDER_GLOW)
        def _leave(e):
            card.configure(border_color=T.BORDER)
        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)
        return card

    def _make_delete_btn(self, parent, command):
        btn = ctk.CTkButton(
            parent, text="✕", width=32, height=32,
            fg_color="transparent", hover_color=T.RED,
            text_color=T.FG_DIM, font=T.FONT_SMALL,
            corner_radius=6, command=command,
        )
        btn.pack(side="right", padx=(T.PAD_S, 0))
        return btn

    def _empty_label(self, text: str):
        ctk.CTkLabel(
            self._scroll_frame, text=text,
            text_color=T.FG_DIM, font=T.FONT_BODY,
        ).pack(pady=60)

    # ── Notes ─────────────────────────────────────────────────────────────

    def _populate_notes(self):
        notes = db.get_all_notes()
        if not notes:
            self._empty_label(locales.get("no_notes"))
            return

        for note in notes:
            card = self._make_card()
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=T.PAD_L, pady=T.PAD_L)

            # Header row
            hdr = ctk.CTkFrame(inner, fg_color="transparent")
            hdr.pack(fill="x")

            title = note["title"] or (
                locales.get("default_list_title") if note["note_type"] == "list"
                else locales.get("default_note_title")
            )
            ctk.CTkLabel(hdr, text=title, font=T.FONT_TITLE,
                         text_color=T.ACCENT).pack(side="left")
            ctk.CTkLabel(hdr, text=note["category"], font=T.FONT_TINY,
                         text_color=T.FG_DIM).pack(side="left", padx=(T.PAD_M, 0))

            nid = note["id"]
            self._make_delete_btn(hdr, lambda i=nid: self._delete_note(i))

            # Content
            if note["note_type"] == "list":
                self._render_list(inner, note)
            else:
                ctk.CTkLabel(inner, text=note["content"], font=T.FONT_BODY,
                             text_color=T.FG, anchor="w", justify="left",
                             wraplength=440).pack(fill="x", pady=(T.PAD_M, 0))

            # Timestamp
            ctk.CTkLabel(inner, text=note["updated_at"], font=T.FONT_SMALL,
                         text_color=T.FG_DIM, anchor="e").pack(fill="x",
                         pady=(T.PAD_M, 0))

    def _render_list(self, parent, note: dict):
        try:
            items = json.loads(note["content"])
        except (json.JSONDecodeError, TypeError):
            items = []

        for entry in items:
            checked = entry.get("checked", False)
            text = entry.get("item", "")
            nid = note["id"]
            item_text = text

            cb = ctk.CTkCheckBox(
                parent, text=text, font=T.FONT_BODY,
                text_color=T.FG_DIM if checked else T.FG,
                fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                border_color=T.BORDER_GLOW, checkmark_color=T.BG_DEEP,
                corner_radius=4,
                command=lambda i=nid, t=item_text: self._toggle_item(i, t),
            )
            if checked:
                cb.select()
            cb.pack(fill="x", pady=1, padx=(T.PAD_S, 0))

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
            self._empty_label(locales.get("no_appointments"))
            return

        for a in appts:
            card = self._make_card()
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=T.PAD_L, pady=T.PAD_L)

            hdr = ctk.CTkFrame(inner, fg_color="transparent")
            hdr.pack(fill="x")

            ctk.CTkLabel(hdr, text=a["title"], font=T.FONT_TITLE,
                         text_color=T.ACCENT).pack(side="left")

            aid = a["id"]
            self._make_delete_btn(hdr, lambda i=aid: self._delete_appt(i))

            try:
                dt = datetime.fromisoformat(a["dt"])
                dt_str = dt.strftime("%d/%m/%Y  %H:%M")
            except Exception:
                dt_str = a["dt"]
            ctk.CTkLabel(inner, text=f"📅  {dt_str}", font=T.FONT_BODY,
                         text_color=T.FG, anchor="w").pack(fill="x",
                         pady=(T.PAD_M, 0))

            if a["description"]:
                ctk.CTkLabel(inner, text=a["description"], font=T.FONT_SMALL,
                             text_color=T.FG_DIM, anchor="w", wraplength=440,
                             justify="left").pack(fill="x", pady=(T.PAD_S, 0))

    def _delete_appt(self, aid: int):
        db.delete_appointment(aid)
        self._refresh()

    # ── Reminders ─────────────────────────────────────────────────────────

    def _populate_reminders(self):
        rems = db.get_all_reminders(include_notified=True)
        if not rems:
            self._empty_label(locales.get("no_reminders"))
            return

        for r in rems:
            card = self._make_card()
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=T.PAD_L, pady=T.PAD_L)

            hdr = ctk.CTkFrame(inner, fg_color="transparent")
            hdr.pack(fill="x")

            done = r["notified"]
            status = "✓" if done else "⏰"
            fg = T.FG_DIM if done else T.FG
            ctk.CTkLabel(hdr, text=f"{status}  {r['message']}", font=T.FONT_BODY,
                         text_color=fg, anchor="w").pack(side="left")

            rid = r["id"]
            self._make_delete_btn(hdr, lambda i=rid: self._delete_rem(i))

            try:
                dt = datetime.fromisoformat(r["remind_at"])
                dt_str = dt.strftime("%d/%m/%Y  %H:%M")
            except Exception:
                dt_str = r["remind_at"]
            ctk.CTkLabel(inner, text=dt_str, font=T.FONT_SMALL,
                         text_color=T.FG_DIM, anchor="e").pack(fill="x",
                         pady=(T.PAD_M, 0))

    def _delete_rem(self, rid: int):
        db.delete_reminder(rid)
        self._refresh()
