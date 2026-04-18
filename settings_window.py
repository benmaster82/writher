"""Settings window — CustomTkinter + Pandora Blackboard theme.

Allows the user to configure:
  - Recording mode: hold-to-record vs toggle (press to start/stop)
  - Max recording duration in seconds (toggle mode only)
  - Microphone device selection
"""

import tkinter as tk
import sounddevice as sd
import customtkinter as ctk
from PIL import ImageTk

from logger import log
import config
import database as db
import locales
from brand import make_title_bar_image
import theme as T

_WIN_W, _WIN_H = 440, 420
_TITLE_H = 40


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
        self._slider_val_label = None
        self._slider_section = None
        self._mic_dropdown = None
        self._mic_devices = []   # list of (index, name)
        self._refresh_btn = None

    def show(self):
        if self._win is not None:
            try:
                if self._win.winfo_exists():
                    self._win.attributes("-topmost", True)
                    self._win.lift()
                    self._win.focus_force()
                    self._win.after(100, lambda: self._win.attributes("-topmost", True)
                                    if self._win and self._win.winfo_exists() else None)
                    self._sync_ui()
                    return
            except Exception:
                pass
        self._build()
        self._sync_ui()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self):
        win = ctk.CTkToplevel(self._root)
        win.overrideredirect(True)
        win.configure(fg_color=T.BG_DEEP)
        win.attributes("-topmost", True)

        sx = win.winfo_screenwidth()
        sy = win.winfo_screenheight()
        x = (sx - _WIN_W) // 2
        y = (sy - _WIN_H) // 2
        win.geometry(f"{_WIN_W}x{_WIN_H}+{x}+{y}")
        self._win = win

        outer = ctk.CTkFrame(win, fg_color=T.BG_DEEP, border_color=T.BORDER,
                             border_width=1, corner_radius=0)
        outer.pack(fill="both", expand=True)

        # ── Title bar ────────────────────────────────────────────────
        title_bar = ctk.CTkFrame(outer, fg_color=T.TITLE_BG, height=_TITLE_H,
                                 corner_radius=0)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)

        eye_img = make_title_bar_image(size=20)
        self._title_eye_tk = ImageTk.PhotoImage(eye_img)
        eye_lbl = tk.Label(title_bar, image=self._title_eye_tk, bg=T.TITLE_BG)
        eye_lbl.pack(side="left", padx=(14, 8))

        title_lbl = ctk.CTkLabel(title_bar, text=locales.get("settings_title"),
                                 font=T.FONT_TITLE, text_color=T.FG)
        title_lbl.pack(side="left")

        close_btn = ctk.CTkButton(
            title_bar, text="✕", width=44, height=_TITLE_H,
            fg_color="transparent", hover_color=T.CLOSE_HOVER,
            text_color=T.FG_DIM, font=(T.FONT_FAMILY, 15),
            corner_radius=0, command=self._close,
        )
        close_btn.pack(side="right")

        for w in (title_bar, title_lbl):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        # ── Content ──────────────────────────────────────────────────
        content = ctk.CTkFrame(outer, fg_color=T.BG, corner_radius=0)
        content.pack(fill="both", expand=True, padx=1, pady=(0, 1))

        pad = ctk.CTkFrame(content, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=T.PAD_XL, pady=T.PAD_L)

        # Recording mode label
        ctk.CTkLabel(pad, text=locales.get("setting_record_mode"),
                     font=T.FONT_TITLE, text_color=T.FG,
                     anchor="w").pack(fill="x", pady=(0, T.PAD_M))

        # Mode buttons
        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, T.PAD_L))

        self._hold_btn = ctk.CTkButton(
            btn_row, text=locales.get("setting_hold"),
            font=T.FONT_SMALL, height=36, corner_radius=6,
            fg_color=T.BG_CARD, hover_color=T.BG_HOVER,
            border_color=T.BORDER, border_width=1,
            text_color=T.FG, command=lambda: self._set_mode(True),
        )
        self._hold_btn.pack(side="left", padx=(0, T.PAD_M))

        self._toggle_btn = ctk.CTkButton(
            btn_row, text=locales.get("setting_toggle"),
            font=T.FONT_SMALL, height=36, corner_radius=6,
            fg_color=T.BG_CARD, hover_color=T.BG_HOVER,
            border_color=T.BORDER, border_width=1,
            text_color=T.FG, command=lambda: self._set_mode(False),
        )
        self._toggle_btn.pack(side="left")

        # Separator
        ctk.CTkFrame(pad, fg_color=T.BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=(0, T.PAD_L))

        # Max duration section (toggle mode only)
        self._slider_section = ctk.CTkFrame(pad, fg_color="transparent")
        self._slider_section.pack(fill="x")

        lbl_row = ctk.CTkFrame(self._slider_section, fg_color="transparent")
        lbl_row.pack(fill="x", pady=(0, T.PAD_M))

        ctk.CTkLabel(lbl_row, text=locales.get("setting_max_duration"),
                     font=T.FONT_TITLE, text_color=T.FG,
                     anchor="w").pack(side="left")

        self._slider_val_label = ctk.CTkLabel(
            lbl_row, text="120s", font=T.FONT_TITLE,
            text_color=T.ACCENT, anchor="e",
        )
        self._slider_val_label.pack(side="right")

        self._slider = ctk.CTkSlider(
            self._slider_section, from_=30, to=300,
            fg_color=T.BG_INPUT, progress_color=T.ACCENT,
            button_color=T.ACCENT, button_hover_color=T.ACCENT_HOVER,
            height=18, corner_radius=9,
            command=self._on_slider_change,
        )
        self._slider.pack(fill="x")

        # Separator
        ctk.CTkFrame(pad, fg_color=T.BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=T.PAD_L)

        # ── Microphone selection ─────────────────────────────────────
        ctk.CTkLabel(pad, text=locales.get("setting_microphone"),
                     font=T.FONT_TITLE, text_color=T.FG,
                     anchor="w").pack(fill="x", pady=(0, T.PAD_M))

        mic_row = ctk.CTkFrame(pad, fg_color="transparent")
        mic_row.pack(fill="x")

        self._mic_devices = self._get_input_devices()
        mic_names = [name for _, name in self._mic_devices]

        self._mic_dropdown = ctk.CTkComboBox(
            mic_row, values=mic_names, font=T.FONT_SMALL,
            dropdown_font=T.FONT_SMALL,
            fg_color=T.BG_CARD, border_color=T.BORDER,
            button_color=T.BORDER_GLOW, button_hover_color=T.FG_DIM,
            dropdown_fg_color=T.BG_CARD, dropdown_hover_color=T.BG_HOVER,
            dropdown_text_color=T.FG, text_color=T.FG,
            height=36, corner_radius=6,
            command=self._on_mic_change,
            state="readonly",
        )
        self._mic_dropdown.pack(side="left", fill="x", expand=True)

        self._refresh_btn = ctk.CTkButton(
            mic_row, text="⟳", width=36, height=36,
            fg_color=T.BG_CARD, hover_color=T.BG_HOVER,
            border_color=T.BORDER, border_width=1,
            text_color=T.FG, font=(T.FONT_FAMILY, 16),
            corner_radius=6, command=self._on_refresh_mic,
        )
        self._refresh_btn.pack(side="right", padx=(T.PAD_M, 0))

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
        hold = getattr(config, "HOLD_TO_RECORD", True)
        self._update_mode_buttons(hold)
        max_sec = getattr(config, "MAX_RECORD_SECONDS", 120)
        if self._slider:
            self._slider.set(max_sec)
        if self._slider_val_label:
            self._slider_val_label.configure(text=f"{max_sec}s")
        self._update_slider_visibility(hold)
        # Refresh mic list every time settings is shown
        self._refresh_mic_list()
        self._sync_mic_dropdown()

    def _update_mode_buttons(self, hold: bool):
        if self._hold_btn:
            if hold:
                self._hold_btn.configure(
                    fg_color=T.FG, text_color="#000000",
                    border_color=T.FG, hover_color=T.ACCENT_HOVER,
                )
            else:
                self._hold_btn.configure(
                    fg_color=T.BG_CARD, text_color=T.FG,
                    border_color=T.BORDER, hover_color=T.BG_HOVER,
                )
        if self._toggle_btn:
            if not hold:
                self._toggle_btn.configure(
                    fg_color=T.FG, text_color="#000000",
                    border_color=T.FG, hover_color=T.ACCENT_HOVER,
                )
            else:
                self._toggle_btn.configure(
                    fg_color=T.BG_CARD, text_color=T.FG,
                    border_color=T.BORDER, hover_color=T.BG_HOVER,
                )

    def _update_slider_visibility(self, hold: bool):
        if self._slider_section:
            if hold:
                self._slider_section.pack_forget()
            else:
                self._slider_section.pack(fill="x")

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
        if self._slider_val_label:
            self._slider_val_label.configure(text=f"{seconds}s")

    # ── Microphone helpers ────────────────────────────────────────────────

    @staticmethod
    def _get_input_devices() -> list[tuple[int | None, str]]:
        """Return list of (device_index, display_name) for input devices.

        Filters to show only Windows WASAPI devices (the real hardware),
        avoiding duplicates from MME / DirectSound / WDM-KS drivers.
        Falls back to all input devices if no WASAPI host is found.
        """
        default_label = locales.get("setting_mic_default")
        devices = [(None, default_label)]

        try:
            # Force PortAudio to re-scan hardware (picks up newly connected devices)
            sd._terminate()
            sd._initialize()

            all_devs = sd.query_devices()
            host_apis = sd.query_hostapis()

            # Find the WASAPI host API index
            wasapi_idx = None
            for i, api in enumerate(host_apis):
                if "WASAPI" in api.get("name", ""):
                    wasapi_idx = i
                    break

            seen_names = set()
            for i, dev in enumerate(all_devs):
                if dev["max_input_channels"] <= 0:
                    continue
                # Filter to WASAPI only (if available)
                if wasapi_idx is not None and dev.get("hostapi") != wasapi_idx:
                    continue
                name = dev["name"]
                # Skip exact duplicate names
                if name in seen_names:
                    continue
                seen_names.add(name)
                devices.append((i, name))

            # Fallback: if WASAPI filter left us with nothing, show all
            if len(devices) == 1:
                seen_names.clear()
                for i, dev in enumerate(all_devs):
                    if dev["max_input_channels"] > 0:
                        name = dev["name"]
                        if name not in seen_names:
                            seen_names.add(name)
                            devices.append((i, name))

        except Exception as exc:
            log.warning("Could not enumerate audio devices: %s", exc)
        return devices

    def _sync_mic_dropdown(self):
        """Set the dropdown to reflect the current config value."""
        if not self._mic_dropdown:
            return
        current_name = getattr(config, "MIC_DEVICE_NAME", None)
        if current_name:
            for idx, name in self._mic_devices:
                if name == current_name:
                    self._mic_dropdown.set(name)
                    return
        # Fallback to default
        if self._mic_devices:
            self._mic_dropdown.set(self._mic_devices[0][1])

    def _refresh_mic_list(self):
        """Re-scan audio devices and update the dropdown values."""
        self._mic_devices = self._get_input_devices()
        if self._mic_dropdown:
            mic_names = [name for _, name in self._mic_devices]
            self._mic_dropdown.configure(values=mic_names)

    def _on_mic_change(self, selected_name: str):
        """Called when user picks a mic from the dropdown."""
        for idx, name in self._mic_devices:
            if name == selected_name:
                if idx is None:
                    # System default
                    config.MIC_DEVICE_NAME = None
                    db.save_setting("mic_device_name", "none")
                else:
                    config.MIC_DEVICE_NAME = name
                    db.save_setting("mic_device_name", name)
                log.info("Microphone set to: %s", name)
                return

    def _on_refresh_mic(self):
        """Re-scan devices and update dropdown without closing the window."""
        self._refresh_mic_list()
        self._sync_mic_dropdown()
        log.info("Microphone list refreshed.")
        # Visual feedback: flash the button green briefly
        if self._refresh_btn:
            self._refresh_btn.configure(fg_color=T.GREEN, text_color="#000000")
            self._refresh_btn.after(
                500, lambda: self._refresh_btn.configure(
                    fg_color=T.BG_CARD, text_color=T.FG)
                if self._refresh_btn and self._win else None
            )
