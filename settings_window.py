"""Settings window - CustomTkinter + Pandora Blackboard theme.

Allows the user to configure:
  - Recording mode: hold-to-record vs toggle (press to start/stop)
  - Max recording duration in seconds (toggle mode only)
  - Microphone device selection
  - Ollama model and URL
  - Whisper model size
  - Interface language
"""

import tkinter as tk
import threading
import sounddevice as sd
import customtkinter as ctk
from PIL import ImageTk

from logger import log
import config
import database as db
import locales
from brand import make_title_bar_image
import theme as T

_WIN_W, _WIN_H = 460, 580
_TITLE_H = 40

# Whisper model options
_WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

# Supported languages
_LANGUAGES = [("en", "English"), ("it", "Italiano")]


def _fetch_ollama_models() -> list[str]:
    """Query Ollama /api/tags for installed models. Returns list of names."""
    try:
        import requests
        resp = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception as exc:
        log.warning("Could not fetch Ollama models: %s", exc)
    return []


class SettingsWindow:
    def __init__(self, root: tk.Tk, on_language_change=None,
                 on_whisper_change=None):
        self._root = root
        self._win = None
        self._drag_x = 0
        self._drag_y = 0
        self._title_eye_tk = None
        # Recording mode
        self._hold_btn = None
        self._toggle_btn = None
        self._slider = None
        self._slider_val_label = None
        self._slider_section = None
        # Microphone
        self._mic_dropdown = None
        self._mic_devices = []
        self._refresh_btn = None
        # Ollama
        self._ollama_model_dropdown = None
        self._ollama_url_entry = None
        # Whisper
        self._whisper_dropdown = None
        # Language
        self._lang_dropdown = None
        # Callbacks
        self._cb_language_change = on_language_change
        self._cb_whisper_change = on_whisper_change

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

        # ── Scrollable content ────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(
            outer, fg_color=T.BG, corner_radius=0,
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.BORDER_GLOW,
        )
        scroll.pack(fill="both", expand=True, padx=1, pady=(0, 1))

        pad = ctk.CTkFrame(scroll, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=T.PAD_L, pady=T.PAD_L)

        # ── 1. Recording mode ────────────────────────────────────────
        self._build_section_label(pad, locales.get("setting_record_mode"))

        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, T.PAD_M))

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

        # Max duration (toggle only)
        self._slider_section = ctk.CTkFrame(pad, fg_color="transparent")
        self._slider_section.pack(fill="x")

        lbl_row = ctk.CTkFrame(self._slider_section, fg_color="transparent")
        lbl_row.pack(fill="x", pady=(0, T.PAD_S))

        ctk.CTkLabel(lbl_row, text=locales.get("setting_max_duration"),
                     font=T.FONT_SMALL, text_color=T.FG_DIM,
                     anchor="w").pack(side="left")

        self._slider_val_label = ctk.CTkLabel(
            lbl_row, text="120s", font=T.FONT_SMALL,
            text_color=T.ACCENT, anchor="e",
        )
        self._slider_val_label.pack(side="right")

        self._slider = ctk.CTkSlider(
            self._slider_section, from_=30, to=300,
            fg_color=T.BG_INPUT, progress_color=T.ACCENT,
            button_color=T.ACCENT, button_hover_color=T.ACCENT_HOVER,
            height=16, corner_radius=8,
            command=self._on_slider_change,
        )
        self._slider.pack(fill="x")

        self._build_separator(pad)

        # ── 2. Microphone ────────────────────────────────────────────
        self._build_section_label(pad, locales.get("setting_microphone"))

        mic_row = ctk.CTkFrame(pad, fg_color="transparent")
        mic_row.pack(fill="x", pady=(0, T.PAD_M))

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
            command=self._on_mic_change, state="readonly",
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

        self._build_separator(pad)

        # ── 3. Ollama model ──────────────────────────────────────────
        self._build_section_label(pad, locales.get("setting_ollama_model"))

        self._ollama_model_dropdown = ctk.CTkComboBox(
            pad, values=[], font=T.FONT_SMALL,
            dropdown_font=T.FONT_SMALL,
            fg_color=T.BG_CARD, border_color=T.BORDER,
            button_color=T.BORDER_GLOW, button_hover_color=T.FG_DIM,
            dropdown_fg_color=T.BG_CARD, dropdown_hover_color=T.BG_HOVER,
            dropdown_text_color=T.FG, text_color=T.FG,
            height=36, corner_radius=6,
            command=self._on_ollama_model_change,
        )
        self._ollama_model_dropdown.pack(fill="x", pady=(0, T.PAD_M))

        # Ollama URL
        self._build_section_label(pad, locales.get("setting_ollama_url"))

        self._ollama_url_entry = ctk.CTkEntry(
            pad, font=T.FONT_SMALL, height=36, corner_radius=6,
            fg_color=T.BG_CARD, border_color=T.BORDER,
            text_color=T.FG, placeholder_text="http://localhost:11434",
        )
        self._ollama_url_entry.pack(fill="x", pady=(0, T.PAD_M))
        self._ollama_url_entry.bind("<FocusOut>", lambda e: self._on_ollama_url_change())
        self._ollama_url_entry.bind("<Return>", lambda e: self._on_ollama_url_change())

        self._build_separator(pad)

        # ── 4. Whisper model ─────────────────────────────────────────
        self._build_section_label(pad, locales.get("setting_whisper_model"))

        self._whisper_dropdown = ctk.CTkComboBox(
            pad, values=_WHISPER_MODELS, font=T.FONT_SMALL,
            dropdown_font=T.FONT_SMALL,
            fg_color=T.BG_CARD, border_color=T.BORDER,
            button_color=T.BORDER_GLOW, button_hover_color=T.FG_DIM,
            dropdown_fg_color=T.BG_CARD, dropdown_hover_color=T.BG_HOVER,
            dropdown_text_color=T.FG, text_color=T.FG,
            height=36, corner_radius=6,
            command=self._on_whisper_change, state="readonly",
        )
        self._whisper_dropdown.pack(fill="x", pady=(0, T.PAD_M))

        # Whisper change note
        self._whisper_note = ctk.CTkLabel(
            pad, text="", font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
        )
        self._whisper_note.pack(fill="x")

        self._build_separator(pad)

        # ── 5. Language ──────────────────────────────────────────────
        self._build_section_label(pad, locales.get("setting_language"))

        lang_names = [name for _, name in _LANGUAGES]
        self._lang_dropdown = ctk.CTkComboBox(
            pad, values=lang_names, font=T.FONT_SMALL,
            dropdown_font=T.FONT_SMALL,
            fg_color=T.BG_CARD, border_color=T.BORDER,
            button_color=T.BORDER_GLOW, button_hover_color=T.FG_DIM,
            dropdown_fg_color=T.BG_CARD, dropdown_hover_color=T.BG_HOVER,
            dropdown_text_color=T.FG, text_color=T.FG,
            height=36, corner_radius=6,
            command=self._on_language_change_cb, state="readonly",
        )
        self._lang_dropdown.pack(fill="x", pady=(0, T.PAD_M))

        # Language change note
        self._lang_note = ctk.CTkLabel(
            pad, text="", font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
        )
        self._lang_note.pack(fill="x")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _build_section_label(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, font=T.FONT_TITLE, text_color=T.FG,
                     anchor="w").pack(fill="x", pady=(0, T.PAD_S))

    def _build_separator(self, parent):
        ctk.CTkFrame(parent, fg_color=T.BORDER, height=1,
                     corner_radius=0).pack(fill="x", pady=T.PAD_M)

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
        # Recording mode
        hold = getattr(config, "HOLD_TO_RECORD", True)
        self._update_mode_buttons(hold)
        max_sec = getattr(config, "MAX_RECORD_SECONDS", 120)
        if self._slider:
            self._slider.set(max_sec)
        if self._slider_val_label:
            self._slider_val_label.configure(text=f"{max_sec}s")
        self._update_slider_visibility(hold)

        # Microphone
        self._refresh_mic_list()
        self._sync_mic_dropdown()

        # Ollama model - fetch in background to avoid blocking UI
        if self._ollama_model_dropdown:
            self._ollama_model_dropdown.set(config.OLLAMA_MODEL)
            threading.Thread(target=self._fetch_and_update_ollama_models,
                             daemon=True).start()

        # Ollama URL
        if self._ollama_url_entry:
            self._ollama_url_entry.delete(0, "end")
            self._ollama_url_entry.insert(0, config.OLLAMA_URL)

        # Whisper model
        if self._whisper_dropdown:
            self._whisper_dropdown.set(config.MODEL_SIZE)

        # Language
        if self._lang_dropdown:
            current_lang = config.LANGUAGE
            for code, name in _LANGUAGES:
                if code == current_lang:
                    self._lang_dropdown.set(name)
                    break

    def _fetch_and_update_ollama_models(self):
        """Fetch Ollama models in background thread, update dropdown on main thread."""
        models = _fetch_ollama_models()
        if models and self._win and self._ollama_model_dropdown:
            current = config.OLLAMA_MODEL
            # Ensure current model is in the list even if not installed
            if current and current not in models:
                models.insert(0, current)
            self._root.after(0, lambda: self._ollama_model_dropdown.configure(values=models)
                             if self._win and self._ollama_model_dropdown else None)

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

    # ── Ollama callbacks ──────────────────────────────────────────────────

    def _on_ollama_model_change(self, value: str):
        value = value.strip()
        if value:
            config.OLLAMA_MODEL = value
            db.save_setting("ollama_model", value)
            log.info("Ollama model set to: %s", value)

    def _on_ollama_url_change(self):
        if not self._ollama_url_entry:
            return
        value = self._ollama_url_entry.get().strip()
        if value and value != config.OLLAMA_URL:
            config.OLLAMA_URL = value
            db.save_setting("ollama_url", value)
            log.info("Ollama URL set to: %s", value)
            # Refresh model list with new URL
            threading.Thread(target=self._fetch_and_update_ollama_models,
                             daemon=True).start()

    # ── Whisper callback ──────────────────────────────────────────────────

    def _on_whisper_change(self, value: str):
        if value == config.MODEL_SIZE:
            return
        config.MODEL_SIZE = value
        db.save_setting("whisper_model", value)
        log.info("Whisper model set to: %s", value)
        if self._whisper_note:
            self._whisper_note.configure(text=locales.get("setting_restart_required"))
        if self._cb_whisper_change:
            self._cb_whisper_change(value)

    # ── Language callback ─────────────────────────────────────────────────

    def _on_language_change_cb(self, selected_name: str):
        for code, name in _LANGUAGES:
            if name == selected_name:
                if code == config.LANGUAGE:
                    return
                config.LANGUAGE = code
                db.save_setting("language", code)
                log.info("Language set to: %s", code)
                if self._lang_note:
                    self._lang_note.configure(text=locales.get("setting_restart_required"))
                if self._cb_language_change:
                    self._cb_language_change(code)
                return

    # ── Microphone helpers ────────────────────────────────────────────────

    @staticmethod
    def _get_input_devices() -> list[tuple[int | None, str]]:
        """Return list of (device_index, display_name) for WASAPI input devices."""
        default_label = locales.get("setting_mic_default")
        devices = [(None, default_label)]
        try:
            sd._terminate()
            sd._initialize()
            all_devs = sd.query_devices()
            host_apis = sd.query_hostapis()
            wasapi_idx = None
            for i, api in enumerate(host_apis):
                if "WASAPI" in api.get("name", ""):
                    wasapi_idx = i
                    break
            seen_names = set()
            for i, dev in enumerate(all_devs):
                if dev["max_input_channels"] <= 0:
                    continue
                if wasapi_idx is not None and dev.get("hostapi") != wasapi_idx:
                    continue
                name = dev["name"]
                if name in seen_names:
                    continue
                seen_names.add(name)
                devices.append((i, name))
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
        if not self._mic_dropdown:
            return
        current_name = getattr(config, "MIC_DEVICE_NAME", None)
        if current_name:
            for idx, name in self._mic_devices:
                if name == current_name:
                    self._mic_dropdown.set(name)
                    return
        if self._mic_devices:
            self._mic_dropdown.set(self._mic_devices[0][1])

    def _refresh_mic_list(self):
        self._mic_devices = self._get_input_devices()
        if self._mic_dropdown:
            mic_names = [name for _, name in self._mic_devices]
            self._mic_dropdown.configure(values=mic_names)

    def _on_mic_change(self, selected_name: str):
        for idx, name in self._mic_devices:
            if name == selected_name:
                if idx is None:
                    config.MIC_DEVICE_NAME = None
                    db.save_setting("mic_device_name", "none")
                else:
                    config.MIC_DEVICE_NAME = name
                    db.save_setting("mic_device_name", name)
                log.info("Microphone set to: %s", name)
                return

    def _on_refresh_mic(self):
        self._refresh_mic_list()
        self._sync_mic_dropdown()
        log.info("Microphone list refreshed.")
        if self._refresh_btn:
            self._refresh_btn.configure(fg_color=T.GREEN, text_color="#000000")
            self._refresh_btn.after(
                500, lambda: self._refresh_btn.configure(
                    fg_color=T.BG_CARD, text_color=T.FG)
                if self._refresh_btn and self._win else None
            )
