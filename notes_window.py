"""Notes, Agenda & Reminders window — CustomTkinter + Pandora Blackboard theme.

Features:
  - Dark glassmorphic design matching the floating widget
  - Resizable window with maximize / restore support
  - Custom title bar with drag, close, and maximize buttons
  - Tabbed interface (Notes, Agenda, Reminders)
  - Scrollable card-based content
"""

import json
import re
import tkinter as tk
from datetime import datetime

import customtkinter as ctk
from PIL import ImageTk

from logger import log
import database as db
import locales
from brand import make_title_bar_image
import theme as T


_SECONDS_RE = re.compile(r"\D\d{2}(?=\D*$)")


def _format_dt_os(dt: datetime) -> str:
    """Format a datetime using the OS locale's short date and time (no seconds).

    Examples (time portion):
        09:11:00     -> 09:11
        9:11:00 AM   -> 9:11 AM
        09.11.00     -> 09.11
    """
    return f"{dt.strftime('%x')}  {_SECONDS_RE.sub('', dt.strftime('%X'))}"


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
        self._voice_delete_dialog = None

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
                if self._voice_delete_dialog and self._voice_delete_dialog.winfo_exists():
                    self._safe_destroy_dialog(self._voice_delete_dialog)
            except Exception:
                pass
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
            self._maximized = False
            self._tab_buttons = {}

    def _safe_destroy_dialog(self, dialog):
        """Hide a CustomTkinter dialog safely.

        Important:
        We do NOT destroy this dialog here, because CustomTkinter can still have
        pending draw callbacks for CTkButton canvases.
        """
        if not dialog:
            return

        try:
            if not dialog.winfo_exists():
                return
        except Exception:
            return

        try:
            dialog.grab_release()
        except Exception:
            pass

        try:
            dialog.withdraw()
        except Exception:
            pass
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
            try:
                ts = datetime.fromisoformat(note["updated_at"])
                ts_str = _format_dt_os(ts)
            except Exception:
                ts_str = note["updated_at"]
            ctk.CTkLabel(inner, text=ts_str, font=T.FONT_SMALL,
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
        note = None
        for n in db.get_all_notes():
            if n["id"] == note_id:
                note = n
                break
        if note:
            self._show_delete_confirmation_dialog("note", note_id, note)

    # ── Delete Confirmation Dialog ────────────────────────────────────────

    def _show_delete_confirmation_dialog(self, item_type: str, item_id: int, item_data: dict, voice_mode: bool = False, on_voice_confirm=None):
        """Show a modal confirmation dialog before deleting an item.
        
        Args:
            item_type: "note", "appointment", or "reminder"
            item_id: ID of the item to delete
            item_data: Dictionary with item information
            voice_mode: If True, dialog is waiting for voice confirmation
            on_voice_confirm: Callback function for voice confirmation
        """
        # Create modal dialog window, falling back to root if main window is not yet available
        parent = self._win if self._win and self._win.winfo_exists() else self._root
        dialog = ctk.CTkToplevel(parent)
        dialog.overrideredirect(True)
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        
        # Configure style
        dialog.configure(fg_color=T.BG_DEEP)
        
        # Dialog size and position (centered over main window)
        dialog_w, dialog_h = 400, 300 if not voice_mode else 320
        try:
            mx = self._win.winfo_x() + self._win.winfo_width() // 2
            my = self._win.winfo_y() + self._win.winfo_height() // 2
        except:
            mx = self._win.winfo_screenwidth() // 2
            my = self._win.winfo_screenheight() // 2
        
        dialog.geometry(f"{dialog_w}x{dialog_h}+{mx - dialog_w//2}+{my - dialog_h//2}")
        
        # Outer border frame
        outer = ctk.CTkFrame(dialog, fg_color=T.BG_DEEP, border_color=T.BORDER,
                             border_width=1, corner_radius=8)
        outer.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Title
        title_map = {
            "note": locales.get("delete_item_note"),
            "appointment": locales.get("delete_item_appointment"),
            "reminder": locales.get("delete_item_reminder"),
        }
        title_text = locales.get("confirm_delete_title", item=title_map.get(item_type, item_type))
        
        title_lbl = ctk.CTkLabel(
            outer, text=title_text, font=(T.FONT_FAMILY, 14, "bold"),
            text_color=T.FG
        )
        title_lbl.pack(pady=(16, 12), padx=16)
        
        # Content frame
        content = ctk.CTkFrame(outer, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=12)
        
        # Build info lines
        info_lines = []
        
        # Name
        if item_type == "note":
            name = item_data.get("title") or locales.get("default_note_title")
            info_lines.append((locales.get("field_name", default="Name"), name))
        elif item_type == "appointment":
            name = item_data.get("title", "")
            info_lines.append((locales.get("field_name", default="Name"), name))
        elif item_type == "reminder":
            name = item_data.get("message", "")
            info_lines.append((locales.get("field_name", default="Name"), name))
        
        # Created date
        created_at = item_data.get("created_at", "")
        if created_at:
            try:
                created_dt = datetime.fromisoformat(created_at)
                created_str = _format_dt_os(created_dt)
            except:
                created_str = created_at
            info_lines.append((locales.get("field_created", default="Created"), created_str))
        
        # Event date (for appointment and reminder)
        if item_type == "appointment":
            event_at = item_data.get("dt", "")
            if event_at:
                try:
                    event_dt = datetime.fromisoformat(event_at)
                    event_str = _format_dt_os(event_dt)
                except:
                    event_str = event_at
                info_lines.append((locales.get("field_event", default="Event"), event_str))
        elif item_type == "reminder":
            remind_at = item_data.get("remind_at", "")
            if remind_at:
                try:
                    remind_dt = datetime.fromisoformat(remind_at)
                    remind_str = _format_dt_os(remind_dt)
                except:
                    remind_str = remind_at
                info_lines.append((locales.get("field_remind", default="Remind At"), remind_str))
        
        # Display info lines
        for label, value in info_lines:
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=4)
            
            lbl = ctk.CTkLabel(row, text=f"{label}:", font=T.FONT_SMALL,
                              text_color=T.FG_DIM, width=80, anchor="w")
            lbl.pack(side="left", padx=(0, 8))
            
            val = ctk.CTkLabel(row, text=str(value), font=T.FONT_BODY,
                              text_color=T.FG, anchor="w", wraplength=250)
            val.pack(side="left", fill="x", expand=True)
        
        # Voice mode indicator
        if voice_mode:
            voice_lbl = ctk.CTkLabel(
                content, text="🎤  " + locales.get("listening_for_confirm", default="Listening for voice confirmation..."),
                font=T.FONT_SMALL, text_color=T.ACCENT, wraplength=350
            )
            voice_lbl.pack(pady=(8, 0))
        
        # Warning
        warning = ctk.CTkLabel(
            content, text=locales.get("confirm_delete_warning", default="This action cannot be undone."),
            font=T.FONT_SMALL, text_color=T.RED, wraplength=350
        )
        warning.pack(pady=(8, 0))
        
        # Button frame
        btn_frame = ctk.CTkFrame(outer, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=12)
        
        # Cancel button
        def close_dialog():
            if on_voice_confirm:
                on_voice_confirm(False)  # Signal cancellation
            else:
                self._safe_destroy_dialog(dialog)
        cancel_btn = tk.Button(
            btn_frame, 
            text=locales.get("btn_cancel", default="Cancel"),
            bg=T.BG,
            fg=T.FG,
            activebackground=T.BG_HOVER,
            activeforeground=T.FG,
            relief="flat",
            bd=0,
            font=T.FONT_BODY,
            command=close_dialog,
        )
        cancel_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        # Delete button
        def confirm_delete():
            if on_voice_confirm:
                on_voice_confirm(True)  # Signal confirmation
            else:
                self._safe_destroy_dialog(dialog)
                self._confirm_delete(item_type, item_id)
        
        delete_btn = tk.Button(
            btn_frame,
            text=locales.get("btn_delete", default="Delete"),
            bg=T.RED,
            fg=T.FG,
            activebackground=T.RED_HOVER,
            activeforeground=T.FG,
            relief="flat",
            bd=0,
            font=T.FONT_BODY,
            command=confirm_delete,
        )
        delete_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))
        
        # Make dialog modal
        dialog.grab_set()
        dialog.focus()
        
        # Store reference for voice mode
        if voice_mode:
            self._voice_delete_dialog = dialog
    
    def show_voice_delete_confirmation(self, item_type: str, item_id: int):
        """Show delete confirmation dialog in voice mode (called from main.py).
        
        Returns callback function for voice confirmation.
        """
        # Get item data
        item_data = None
        
        if item_type == "note":
            for note in db.get_all_notes():
                if note["id"] == item_id:
                    item_data = note
                    break
        elif item_type == "appointment":
            for appt in db.get_appointments():
                if appt["id"] == item_id:
                    item_data = appt
                    break
        elif item_type == "reminder":
            for rem in db.get_all_reminders(include_notified=True):
                if rem["id"] == item_id:
                    item_data = rem
                    break
        
        if not item_data:
            return None
        
        def on_voice_confirm(confirmed: bool):
            dialog = self._voice_delete_dialog
            self._voice_delete_dialog = None

            if dialog:
                self._safe_destroy_dialog(dialog)

            if confirmed:
                self._confirm_delete(item_type, item_id)
        
        self._show_delete_confirmation_dialog(
            item_type, item_id, item_data, 
            voice_mode=True, 
            on_voice_confirm=on_voice_confirm
        )
        
        return on_voice_confirm

    def _confirm_delete(self, item_type: str, item_id: int):
        """Execute the deletion after confirmation."""
        if item_type == "note":
            db.delete_note(item_id)
        elif item_type == "appointment":
            db.delete_appointment(item_id)
        elif item_type == "reminder":
            db.delete_reminder(item_id)
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
                dt_str = _format_dt_os(dt)
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
        appointment = None
        for a in db.get_appointments():
            if a["id"] == aid:
                appointment = a
                break
        if appointment:
            self._show_delete_confirmation_dialog("appointment", aid, appointment)

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
                dt_str = _format_dt_os(dt)
            except Exception:
                dt_str = r["remind_at"]
            ctk.CTkLabel(inner, text=dt_str, font=T.FONT_SMALL,
                         text_color=T.FG_DIM, anchor="e").pack(fill="x",
                         pady=(T.PAD_M, 0))

    def _delete_rem(self, rid: int):
        reminder = None
        for r in db.get_all_reminders(include_notified=True):
            if r["id"] == rid:
                reminder = r
                break
        if reminder:
            self._show_delete_confirmation_dialog("reminder", rid, reminder)
