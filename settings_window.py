"""Settings window - CustomTkinter + Pandora Blackboard theme.

Allows the user to configure:
  - Recording mode: hold-to-record vs toggle (press to start/stop)
  - Max recording duration in seconds (toggle mode only)
  - Keyboard shortcuts for dictation and assistant
  - Microphone device selection
  - Ollama model and URL
  - Whisper model size
  - Interface language
"""

import tkinter as tk
import threading
import sounddevice as sd
import customtkinter as ctk
from pynput import keyboard as kb
from PIL import ImageTk

from logger import log
import config
import database as db
import locales
from brand import make_title_bar_image
from hotkey_util import (key_to_str, key_display_name, is_blocked,
                         canonical_modifier, hotkeys_equal)
import theme as T

_WIN_W, _WIN_H = 460, 680
_TITLE_H = 40

# Whisper model options
_WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

# Supported languages
_LANGUAGES = [("en", "English"), ("it", "Italiano"), ("de", "Deutsch")]

# Recognition (Whisper) language options — value None means auto-detect.
_RECOGNITION_LANGS = [(None, "Auto"), ("en", "EN"), ("it", "IT"), ("de", "DE")]


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
        # Recognition language
        self._recog_dropdown = None
        self._recog_hint = None
        # Language
        self._lang_dropdown = None
        # Hotkey configuration
        self._hk_dict_btn = None
        self._hk_assist_btn = None
        self._hk_listener = None  # temporary listener for key capture
        self._hk_capturing = None  # "dictation" or "assistant" or None
        # Log viewer
        self._log_box = None
        self._log_refresh_btn = None
        self._log_refresh_job = None
        # Clipboard retention toggle
        self._keep_clip_switch_var = None
        self._keep_clip_switch = None
        # Symbol mode toggle
        self._symbol_switch_var = None
        self._symbol_switch = None
        # Vocabulary editor
        self._vocab_spoken_entry = None
        self._vocab_written_entry = None
        self._vocab_list_frame = None
        # Priming terms
        self._priming_entry = None
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

        # ── 2. Keyboard shortcuts ────────────────────────────────────
        self._build_section_label(pad, locales.get("setting_hotkeys"))

        # Dictation hotkey row
        hk_dict_row = ctk.CTkFrame(pad, fg_color="transparent")
        hk_dict_row.pack(fill="x", pady=(0, T.PAD_S))

        ctk.CTkLabel(
            hk_dict_row, text=locales.get("setting_hotkey_dictation"),
            font=T.FONT_SMALL, text_color=T.FG_DIM, anchor="w",
        ).pack(side="left")

        self._hk_dict_btn = ctk.CTkButton(
            hk_dict_row, text=key_display_name(config.HOTKEY),
            font=T.FONT_SMALL, height=32, width=140, corner_radius=6,
            fg_color=T.BG_CARD, hover_color=T.BG_HOVER,
            border_color=T.BORDER, border_width=1,
            text_color=T.FG,
            command=lambda: self._start_hotkey_capture("dictation"),
        )
        self._hk_dict_btn.pack(side="right")

        # Assistant hotkey row
        hk_assist_row = ctk.CTkFrame(pad, fg_color="transparent")
        hk_assist_row.pack(fill="x", pady=(0, T.PAD_M))

        ctk.CTkLabel(
            hk_assist_row, text=locales.get("setting_hotkey_assistant"),
            font=T.FONT_SMALL, text_color=T.FG_DIM, anchor="w",
        ).pack(side="left")

        self._hk_assist_btn = ctk.CTkButton(
            hk_assist_row, text=key_display_name(config.ASSISTANT_HOTKEY),
            font=T.FONT_SMALL, height=32, width=140, corner_radius=6,
            fg_color=T.BG_CARD, hover_color=T.BG_HOVER,
            border_color=T.BORDER, border_width=1,
            text_color=T.FG,
            command=lambda: self._start_hotkey_capture("assistant"),
        )
        self._hk_assist_btn.pack(side="right")

        self._build_separator(pad)

        # ── 3. Microphone ────────────────────────────────────────────
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

        # ── 4. Ollama model ──────────────────────────────────────────
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

        # ── 5. Whisper model ─────────────────────────────────────────
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

        # Whisper hint (accuracy recommendation, only visible when
        # Symbol & spelling mode is enabled — set by _sync_ui).
        self._whisper_hint = ctk.CTkLabel(
            pad, text=locales.get("setting_whisper_hint"),
            font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
            wraplength=_WIN_W - 3 * T.PAD_L, justify="left",
        )

        # Whisper change note
        self._whisper_note = ctk.CTkLabel(
            pad, text="", font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
        )
        self._whisper_note.pack(fill="x")

        self._build_separator(pad)

        # ── 5b. Recognition language ────────────────────────────────
        self._build_section_label(pad, locales.get("setting_recognition_lang"))

        recog_labels = [
            locales.get("setting_recognition_auto") if code is None else label
            for code, label in _RECOGNITION_LANGS
        ]
        self._recog_dropdown = ctk.CTkComboBox(
            pad, values=recog_labels, font=T.FONT_SMALL,
            dropdown_font=T.FONT_SMALL,
            fg_color=T.BG_CARD, border_color=T.BORDER,
            button_color=T.BORDER_GLOW, button_hover_color=T.FG_DIM,
            dropdown_fg_color=T.BG_CARD, dropdown_hover_color=T.BG_HOVER,
            dropdown_text_color=T.FG, text_color=T.FG,
            height=36, corner_radius=6,
            command=self._on_recognition_change, state="readonly",
        )
        self._recog_dropdown.pack(fill="x", pady=(0, T.PAD_S))

        self._recog_hint = ctk.CTkLabel(
            pad, text=locales.get("setting_recognition_hint"),
            font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
            wraplength=_WIN_W - 3 * T.PAD_L, justify="left",
        )

        self._build_separator(pad)

        # ── 6. Language ──────────────────────────────────────────────
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

        self._build_separator(pad)

        # ── 6b. Clipboard retention ──────────────────────────────────
        self._build_section_label(pad, locales.get("setting_keep_clipboard"))

        self._keep_clip_switch_var = tk.StringVar(
            value="1" if db.get_setting(
                "keep_transcript_in_clipboard", "0") == "1" else "0")
        self._keep_clip_switch = ctk.CTkSwitch(
            pad, text="", variable=self._keep_clip_switch_var,
            onvalue="1", offvalue="0",
            command=self._on_keep_clipboard_toggle,
            fg_color=T.BG_INPUT, progress_color=T.ACCENT,
            button_color=T.FG, button_hover_color=T.ACCENT_HOVER,
        )
        self._keep_clip_switch.pack(anchor="w", pady=(0, T.PAD_S))

        ctk.CTkLabel(
            pad, text=locales.get("setting_keep_clipboard_hint"),
            font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
            wraplength=_WIN_W - 3 * T.PAD_L, justify="left",
        ).pack(fill="x", pady=(0, T.PAD_M))

        self._build_separator(pad)

        # ── 7. Symbol & spelling mode ────────────────────────────────
        self._build_section_label(pad, locales.get("setting_symbol_mode"))

        self._symbol_switch_var = tk.StringVar(
            value="1" if db.get_setting("symbol_mode", "0") == "1" else "0")
        self._symbol_switch = ctk.CTkSwitch(
            pad, text="", variable=self._symbol_switch_var,
            onvalue="1", offvalue="0",
            command=self._on_symbol_mode_toggle,
            fg_color=T.BG_INPUT, progress_color=T.ACCENT,
            button_color=T.FG, button_hover_color=T.ACCENT_HOVER,
        )
        self._symbol_switch.pack(anchor="w", pady=(0, T.PAD_S))

        ctk.CTkLabel(
            pad, text=locales.get("setting_symbol_mode_hint"),
            font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
            wraplength=_WIN_W - 3 * T.PAD_L, justify="left",
        ).pack(fill="x", pady=(0, T.PAD_M))

        self._build_separator(pad)

        # ── 8. Custom vocabulary (Layer A) ───────────────────────────
        self._build_section_label(pad, locales.get("setting_vocabulary"))

        vocab_input_row = ctk.CTkFrame(pad, fg_color="transparent")
        vocab_input_row.pack(fill="x", pady=(0, T.PAD_S))

        self._vocab_spoken_entry = ctk.CTkEntry(
            vocab_input_row, font=T.FONT_SMALL, height=32,
            corner_radius=6, fg_color=T.BG_CARD, border_color=T.BORDER,
            text_color=T.FG,
            placeholder_text=locales.get("setting_vocab_spoken"),
        )
        self._vocab_spoken_entry.pack(side="left", fill="x", expand=True,
                                      padx=(0, T.PAD_S))

        self._vocab_written_entry = ctk.CTkEntry(
            vocab_input_row, font=T.FONT_SMALL, height=32,
            corner_radius=6, fg_color=T.BG_CARD, border_color=T.BORDER,
            text_color=T.FG,
            placeholder_text=locales.get("setting_vocab_written"),
        )
        self._vocab_written_entry.pack(side="left", fill="x", expand=True,
                                       padx=(0, T.PAD_S))

        ctk.CTkButton(
            vocab_input_row, text=locales.get("setting_vocab_add"),
            width=64, height=32, corner_radius=6,
            fg_color=T.BG_CARD, hover_color=T.BG_HOVER,
            border_color=T.BORDER, border_width=1, text_color=T.FG,
            font=T.FONT_SMALL, command=self._on_vocab_add,
        ).pack(side="right")

        self._vocab_list_frame = ctk.CTkFrame(pad, fg_color="transparent")
        self._vocab_list_frame.pack(fill="x", pady=(0, T.PAD_M))
        self._refresh_vocab_list()

        self._build_separator(pad)

        # ── 9. Priming terms ─────────────────────────────────────────
        self._build_section_label(pad, locales.get("setting_priming"))

        self._priming_entry = ctk.CTkTextbox(
            pad, height=60, font=T.FONT_SMALL,
            fg_color=T.BG_CARD, text_color=T.FG,
            border_color=T.BORDER, border_width=1,
            corner_radius=6, wrap="word",
        )
        self._priming_entry.pack(fill="x", pady=(0, T.PAD_S))
        # Preload existing terms
        existing = ", ".join(db.list_priming_terms())
        if existing:
            self._priming_entry.insert("1.0", existing)
        self._priming_entry.bind("<FocusOut>", lambda e: self._on_priming_save())

        ctk.CTkLabel(
            pad, text=locales.get("setting_priming_hint"),
            font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
            wraplength=_WIN_W - 3 * T.PAD_L, justify="left",
        ).pack(fill="x", pady=(0, T.PAD_M))

        self._build_separator(pad)

        # ── 10. Log viewer ───────────────────────────────────────────
        log_header = ctk.CTkFrame(pad, fg_color="transparent")
        log_header.pack(fill="x", pady=(0, T.PAD_S))

        ctk.CTkLabel(
            log_header, text=locales.get("setting_log"),
            font=T.FONT_TITLE, text_color=T.FG, anchor="w",
        ).pack(side="left")

        self._log_refresh_btn = ctk.CTkButton(
            log_header, text="⟳", width=36, height=28,
            fg_color=T.BG_CARD, hover_color=T.BG_HOVER,
            border_color=T.BORDER, border_width=1,
            text_color=T.FG, font=(T.FONT_FAMILY, 16),
            corner_radius=6, command=self._refresh_log,
        )
        self._log_refresh_btn.pack(side="right")

        self._log_box = ctk.CTkTextbox(
            pad, height=180, font=("Courier New", 9),
            fg_color=T.BG_CARD, text_color=T.FG_DIM,
            border_color=T.BORDER, border_width=1,
            corner_radius=6, wrap="none",
            state="disabled",
        )
        self._log_box.pack(fill="x", pady=(0, T.PAD_M))

        # Kick off initial load and auto-refresh
        self._schedule_log_refresh()

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
        if self._log_refresh_job is not None:
            try:
                if self._win:
                    self._win.after_cancel(self._log_refresh_job)
            except Exception:
                pass
            self._log_refresh_job = None
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

        # Recognition language
        if self._recog_dropdown:
            current = config.WHISPER_LANGUAGE
            matched = False
            for code, label in _RECOGNITION_LANGS:
                if code == current:
                    display = (locales.get("setting_recognition_auto")
                               if code is None else label)
                    self._recog_dropdown.set(display)
                    matched = True
                    break
            if not matched and current:
                # A language accepted from Auto detection may intentionally
                # fall outside the compact Auto/EN/IT/DE dropdown list.
                self._recog_dropdown.set(current.upper())

        # Language
        if self._lang_dropdown:
            current_lang = config.LANGUAGE
            for code, name in _LANGUAGES:
                if code == current_lang:
                    self._lang_dropdown.set(name)
                    break

        # Hotkeys
        if self._hk_dict_btn:
            self._hk_dict_btn.configure(text=key_display_name(config.HOTKEY))
        if self._hk_assist_btn:
            self._hk_assist_btn.configure(text=key_display_name(config.ASSISTANT_HOTKEY))

        # Symbol mode hint visibility follows the toggle state
        symbol_on = db.get_setting("symbol_mode", "0") == "1"
        self._update_whisper_hint_visibility(symbol_on)
        # Recognition-language hint: only when non-English AND symbol mode ON
        self._update_recognition_hint_visibility(symbol_on)

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

    # ── Recognition-language callback ─────────────────────────────────────

    def _on_recognition_change(self, selected: str):
        auto_label = locales.get("setting_recognition_auto")
        for code, label in _RECOGNITION_LANGS:
            display = auto_label if code is None else label
            if display == selected:
                config.WHISPER_LANGUAGE = code
                db.save_setting("whisper_language",
                                "auto" if code is None else code)
                log.info("Recognition language set to: %s",
                         "auto" if code is None else code)
                symbol_on = db.get_setting("symbol_mode", "0") == "1"
                self._update_recognition_hint_visibility(symbol_on)
                return

    def _update_recognition_hint_visibility(self, symbol_on: bool):
        if not self._recog_hint:
            return
        show = symbol_on and config.WHISPER_LANGUAGE not in (None, "en")
        if show:
            self._recog_hint.pack(fill="x")
        else:
            self._recog_hint.pack_forget()

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

    # ── Clipboard retention ───────────────────────────────────────────────

    def _on_keep_clipboard_toggle(self):
        enabled = self._keep_clip_switch_var.get() == "1"
        config.KEEP_TRANSCRIPT_IN_CLIPBOARD = enabled
        db.save_setting("keep_transcript_in_clipboard", "1" if enabled else "0")
        log.info("Keep transcript in clipboard: %s",
                 "ON" if enabled else "OFF")

    # ── Symbol mode / vocabulary / priming ────────────────────────────────

    def _on_symbol_mode_toggle(self):
        enabled = self._symbol_switch_var.get() == "1"
        db.save_setting("symbol_mode", "1" if enabled else "0")
        log.info("Symbol & spelling mode: %s", "ON" if enabled else "OFF")
        self._update_whisper_hint_visibility(enabled)
        self._update_recognition_hint_visibility(enabled)

    def _update_whisper_hint_visibility(self, enabled: bool):
        if not self._whisper_hint:
            return
        if enabled:
            self._whisper_hint.pack(fill="x")
        else:
            self._whisper_hint.pack_forget()

    def _on_vocab_add(self):
        spoken = self._vocab_spoken_entry.get().strip()
        written = self._vocab_written_entry.get().strip()
        if not spoken or not written:
            return
        db.save_vocabulary_entry(spoken, written)
        log.info("Vocabulary entry saved: %r → %r", spoken, written)
        self._vocab_spoken_entry.delete(0, "end")
        self._vocab_written_entry.delete(0, "end")
        self._refresh_vocab_list()

    def _refresh_vocab_list(self):
        if not self._vocab_list_frame:
            return
        for child in self._vocab_list_frame.winfo_children():
            child.destroy()
        entries = db.list_vocabulary()
        if not entries:
            ctk.CTkLabel(
                self._vocab_list_frame,
                text=locales.get("setting_vocab_empty"),
                font=T.FONT_TINY, text_color=T.FG_DIM, anchor="w",
            ).pack(fill="x")
            return
        for spoken, written in sorted(entries):
            row = ctk.CTkFrame(self._vocab_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row, text=f"{spoken}  →  {written}",
                font=T.FONT_SMALL, text_color=T.FG, anchor="w",
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="✕", width=28, height=24, corner_radius=4,
                fg_color="transparent", hover_color=T.CLOSE_HOVER,
                border_color=T.BORDER, border_width=1,
                text_color=T.FG_DIM, font=(T.FONT_FAMILY, 12),
                command=lambda s=spoken: self._on_vocab_delete(s),
            ).pack(side="right")

    def _on_vocab_delete(self, spoken: str):
        db.delete_vocabulary_entry(spoken)
        log.info("Vocabulary entry deleted: %r", spoken)
        self._refresh_vocab_list()

    def _on_priming_save(self):
        if not self._priming_entry:
            return
        raw = self._priming_entry.get("1.0", "end").strip()
        terms = [t.strip() for t in raw.split(",") if t.strip()]
        db.replace_priming_terms(terms)
        log.info("Priming terms saved (%d).", len(terms))

    # ── Hotkey capture ────────────────────────────────────────────────────

    def _start_hotkey_capture(self, target: str):
        """Enter key-capture mode for the given target ('dictation' or 'assistant').

        Hold any combination of Ctrl/Shift/Alt/Win, then press the trigger key.
        Press Escape to cancel without changing the hotkey.
        """
        btn = self._hk_dict_btn if target == "dictation" else self._hk_assist_btn
        if not btn or not self._win:
            return

        btn.configure(
            text=locales.get("setting_hotkey_press"),
            fg_color=T.BORDER_GLOW, border_color=T.ACCENT,
        )

        held_modifiers: set = set()

        def on_press(key):
            if key == kb.Key.esc:
                self._root.after(0, lambda: self._reset_hotkey_btn(target))
                return False  # cancel

            mod = canonical_modifier(key)
            if mod is not None:
                held_modifiers.add(mod)
                return  # keep listening — waiting for the trigger key

            # Non-modifier pressed: form the hotkey and finish capture.
            if held_modifiers:
                hotkey = (frozenset(held_modifiers), key)
            else:
                hotkey = key
            self._root.after(0, lambda: self._finish_hotkey_capture(target, hotkey))
            return False  # stop listener

        def on_release(key):
            mod = canonical_modifier(key)
            if mod is not None:
                held_modifiers.discard(mod)

        capture_listener = kb.Listener(on_press=on_press, on_release=on_release)
        capture_listener.start()

    def _finish_hotkey_capture(self, target: str, key):
        """Process the captured key and apply it."""
        btn = self._hk_dict_btn if target == "dictation" else self._hk_assist_btn
        if not btn or not self._win:
            return

        # Check if key is blocked
        if is_blocked(key):
            btn.configure(
                text=key_display_name(key) + " ✗",
                fg_color=T.RED, border_color=T.RED,
                text_color="#ffffff",
            )
            btn.after(1200, lambda: self._reset_hotkey_btn(target))
            return

        # Check for conflict with the other hotkey
        other_key = config.ASSISTANT_HOTKEY if target == "dictation" else config.HOTKEY
        if hotkeys_equal(key, other_key):
            btn.configure(
                text=locales.get("setting_hotkey_conflict"),
                fg_color=T.RED, border_color=T.RED,
                text_color="#ffffff",
            )
            btn.after(1200, lambda: self._reset_hotkey_btn(target))
            return

        # Apply the new hotkey
        display = key_display_name(key)
        if target == "dictation":
            config.HOTKEY = key
            db.save_setting("hotkey_dictation", key_to_str(key))
        else:
            config.ASSISTANT_HOTKEY = key
            db.save_setting("hotkey_assistant", key_to_str(key))

        log.info("Hotkey %s set to: %s", target, display)

        # Visual confirmation
        btn.configure(
            text=display, fg_color=T.GREEN, border_color=T.GREEN,
            text_color="#000000",
        )
        btn.after(800, lambda: self._reset_hotkey_btn(target))

    def _reset_hotkey_btn(self, target: str):
        """Reset hotkey button to normal appearance with current value."""
        btn = self._hk_dict_btn if target == "dictation" else self._hk_assist_btn
        if not btn or not self._win:
            return
        current = config.HOTKEY if target == "dictation" else config.ASSISTANT_HOTKEY
        btn.configure(
            text=key_display_name(current),
            fg_color=T.BG_CARD, border_color=T.BORDER,
            text_color=T.FG,
        )

    # ── Log viewer ────────────────────────────────────────────────────────

    def _refresh_log(self):
        if not self._log_box or not self._win:
            return
        try:
            from paths import LOG_PATH
            with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            content = "".join(lines[-80:])
        except Exception as exc:
            content = f"(could not read log: {exc})"
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.insert("end", content)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _schedule_log_refresh(self):
        if not self._win or not self._win.winfo_exists():
            return
        self._refresh_log()
        self._log_refresh_job = self._win.after(2000, self._schedule_log_refresh)

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
