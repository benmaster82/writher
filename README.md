<p align="center">
  <img src="img/logo_writher.png" width="280" alt="Writher">
</p>

<h1 align="center">WritHer</h1>

<p align="center">
  <strong>Offline voice assistant & dictation tool for Windows (Python) — dictate text anywhere or manage notes, appointments and reminders hands-free.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?logo=windows" alt="Windows">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/whisper-faster--whisper-orange" alt="Faster Whisper">
  <img src="https://img.shields.io/badge/LLM-Ollama-white?logo=ollama" alt="Ollama">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

<p align="center">
  <a href="https://www.youtube.com/watch?v=lfV0LF3EGMw">
    <img src="https://img.youtube.com/vi/lfV0LF3EGMw/maxresdefault.jpg" width="600" alt="Writher Demo Video">
  </a>
</p>

---

## 🆕 What's New

- 🎙️ **Microphone selection** — pick your input device from Settings, with hot-plug refresh
- 🔄 **Toggle recording mode** — press once to start, press again to stop (alternative to hold)
- ⏱️ **Safety timeout** — auto-stops recording in toggle mode if you forget
- 🎨 **Redesigned UI** — CustomTkinter with unified Pandora Blackboard theme (pure black + bright white)
- 🖥️ **Resizable Notes window** — drag to resize, maximize/restore, DPI-aware
- ⚡ **Faster Ollama responses** — timeout increased from 10s to 30s for larger models
- 🐛 **Bug fixes** — clean shutdown, widget positioning, visual artifacts removed

---

## What is WritHer?

WritHer sits quietly in your system tray and gives you two super-powers:

| Mode | Hotkey | What it does |
|---|---|---|
| **Dictation** | `AltGr` | Transcribes your voice and pastes the text directly into whichever app has focus — editors, browsers, chat windows, anything. |
| **Assistant** | `Ctrl+R` | Understands natural-language commands and saves notes, creates appointments, sets reminders, manages lists — all by voice. |

Both hotkeys support two recording modes, configurable from the **Settings** window in the system tray:

| Recording mode | How it works |
|---|---|
| **Hold** (default) | Hold the key to record, release to stop. |
| **Toggle** | Press once to start recording, press again to stop. A configurable safety timeout auto-stops the recording if you forget. |

Everything runs **locally**: speech recognition via [faster-whisper](https://github.com/SYSTRAN/faster-whisper), intent parsing via [Ollama](https://ollama.com), and data stored in a local SQLite database. No cloud, no API keys, no telemetry.

---

## Features

- **Real-time dictation** — speak and text appears. Supports both hold-to-record and toggle (press to start/stop) modes. Clipboard is saved and restored automatically.
- **Voice-controlled assistant** — save notes, create shopping/todo lists, schedule appointments, set reminders, all through natural speech.
- **Smart date parsing** — say *"remind me tomorrow at 9"* or *"meeting next Monday at 3pm"* and the LLM converts relative times to absolute datetimes.
- **Toast notifications** — get Windows notifications when reminders fire or appointments are approaching.
- **Animated floating widget** — a minimal pill-shaped overlay with expressive "Pandora Blackboard" eyes that react to state (listening, thinking, happy, error, etc.).
- **Notes & Agenda window** — a dark-themed resizable window to browse, check off list items, and delete notes/appointments/reminders. Supports maximize/restore and drag-to-resize.
- **Settings window** — configure recording mode, max recording duration, and microphone device directly from the system tray. All settings are persisted across restarts.
- **Microphone selection** — choose your input device from a dropdown in Settings. Supports hot-plug detection with a refresh button — no restart needed.
- **Modern UI** — built with CustomTkinter and a unified "Pandora Blackboard" theme (pure black + bright white) defined in a single `theme.py` file.
- **Multi-language** — ships with English and Italian; easy to add more via the `locales.py` string table.
- **Fully offline** — no internet required after model download.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                     main.py                          │
│            (orchestrator + Tk event loop)             │
├──────────┬───────────┬───────────┬───────────────────┤
│ hotkey   │ recorder  │ widget    │ tray_icon          │
│ listener │ (audio)   │ (overlay) │ (system tray)      │
├──────────┴───────────┴───────────┴───────────────────┤
│                                                      │
│  Dictation pipeline          Assistant pipeline      │
│  ┌───────────┐               ┌───────────┐           │
│  │transcriber│               │transcriber│           │
│  │ (Whisper) │               │ (Whisper) │           │
│  └─────┬─────┘               └─────┬─────┘           │
│        ▼                           ▼                 │
│   injector                    assistant              │
│  (clipboard                  (Ollama LLM             │
│   + Ctrl+V)                  + function calls)       │
│                                    │                 │
│                                    ▼                 │
│                               database               │
│                              (SQLite)                │
│                                    │                 │
│                              notifier                │
│                          (toast scheduler)            │
└──────────────────────────────────────────────────────┘
```

---

## Requirements

- **Windows 10/11**
- **Python 3.11+**
- **Ollama** running locally (for the assistant mode)
- A working **microphone**

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/benmaster82/writher.git
cd writher
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install faster-whisper numpy sounddevice pynput pystray Pillow requests winotify customtkinter
```

> **Optional:** install `plyer` as a fallback notification backend:
> ```bash
> pip install plyer
> ```

### 4. Install and start Ollama

Download from [ollama.com](https://ollama.com), then pull a model that supports function calling:

```bash
ollama pull llama3.1:8b
```

Update `config.py` with your model name:

```python
OLLAMA_MODEL = "llama3.1:8b"
```

### 5. Run

```bash
python main.py
```

Writher appears in the system tray. Hold `AltGr` to dictate, hold `Ctrl+R` for assistant commands.

---

## Configuration

All settings live in **`config.py`**:

```python
# Hotkeys
HOTKEY = Key.alt_gr            # Dictation
ASSISTANT_HOTKEY = Key.ctrl_r  # Assistant

# Language ("en" or "it")
LANGUAGE = "en"

# Recording mode
HOLD_TO_RECORD = True          # True = hold key, False = toggle (press/press)
MAX_RECORD_SECONDS = 120       # Safety timeout for toggle mode (seconds)

# Microphone
MIC_DEVICE_INDEX = None        # None = system default, or device index (int)

# Whisper
MODEL_SIZE = "base"            # tiny, base, small, medium, large-v3
DEVICE = "cpu"                 # "cpu" or "cuda"
COMPUTE_TYPE = "int8"          # int8, float16, float32

# Ollama
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"

# Notification lead time
APPOINTMENT_REMIND_MINUTES = 15
```

> **Note:** `HOLD_TO_RECORD`, `MAX_RECORD_SECONDS`, and `MIC_DEVICE_INDEX` can also be changed at runtime from the **Settings** window in the system tray. Changes made there are persisted in the database and override `config.py` defaults.

### Choosing a Whisper model

| Model | Size | Speed | Accuracy |
|---|---|---|---|
| `tiny` | 39 MB | ⚡ fastest | basic |
| `base` | 74 MB | ⚡ fast | good (default) |
| `small` | 244 MB | moderate | better |
| `medium` | 769 MB | slower | great |
| `large-v3` | 1.5 GB | slowest | best |

For CUDA acceleration, install `ctranslate2` with CUDA support and set `DEVICE = "cuda"`.

---

## Usage

### Dictation mode

**Hold mode** (default):

1. Focus any text field (editor, browser, chat…)
2. **Hold** `AltGr`
3. Speak
4. **Release** — transcribed text is pasted automatically

**Toggle mode:**

1. Focus any text field
2. **Press** `AltGr` once to start recording
3. Speak
4. **Press** `AltGr` again to stop — transcribed text is pasted automatically

> In toggle mode, a safety timeout (configurable in Settings) will auto-stop the recording if you forget to press the key again.

### Assistant mode

**Hold mode** (default):

1. **Hold** `Ctrl+R`
2. Speak a command
3. **Release** — Writher processes and confirms

**Toggle mode:**

1. **Press** `Ctrl+R` once to start recording
2. Speak a command
3. **Press** `Ctrl+R` again to stop — Writher processes and confirms

**Example commands:**

- *"Save a note: remember to buy milk"*
- *"Create a shopping list: bread, eggs, butter, coffee"*
- *"Add pasta to the shopping list"*
- *"Appointment with the dentist tomorrow at 3pm"*
- *"Remind me to call Marco in one hour"*
- *"Show me my notes"*
- *"Show my agenda"*

### System tray

Right-click the tray icon to access:

- **Notes & Agenda** — open the notes/appointments/reminders viewer
- **Settings** — configure recording mode (hold vs toggle), max recording duration, and microphone device
- **Quit** — exit WritHer

> **Tip:** Windows may hide the tray icon in the overflow area (the ^ arrow). To keep it always visible, go to **Settings → Personalization → Taskbar → Other system tray icons** and enable WritHer.

---

## Adding a language

1. Open `locales.py`
2. Add a new entry to the `_STRINGS` dictionary (copy `"en"` as a template)
3. Set `LANGUAGE` in `config.py` to your language code

---

## Project structure

```
writher/
├── main.py              # Entry point and orchestrator
├── config.py            # All user-configurable settings
├── hotkey.py            # Dual-hotkey listener with hold/toggle modes (pynput)
├── recorder.py          # Microphone recording (sounddevice)
├── transcriber.py       # Speech-to-text (faster-whisper)
├── injector.py          # Clipboard paste into active app (Win32 API)
├── assistant.py         # Ollama LLM integration + function calling
├── database.py          # SQLite storage (notes, appointments, reminders, settings)
├── notifier.py          # Toast notifications + reminder/appointment scheduler
├── widget.py            # Floating pill overlay with animated eyes
├── notes_window.py      # Notes/Agenda/Reminders viewer window (CustomTkinter)
├── settings_window.py   # Settings window (CustomTkinter)
├── tray_icon.py         # System tray icon (pystray)
├── brand.py             # "Pandora Blackboard" icon renderer
├── theme.py             # Unified colour palette and font definitions
├── locales.py           # i18n string tables (EN, IT)
├── logger.py            # Rotating file + console logger
├── debug_keys.py        # Key event debugger utility
├── requirements.txt     # Python dependencies
├── img/
│   └── logo_writher.png # Logo for README
└── LICENSE
```

---

## Troubleshooting

**AltGr not detected?**
Run `python debug_keys.py` to see exactly what pynput reports for your keyboard. Some keyboard layouts map AltGr differently.

**Ollama not reachable?**
Make sure Ollama is running (`ollama serve`) and the URL in `config.py` matches. The tray tooltip will show a warning if the connection fails at startup.

**No audio / microphone not found?**
WritHer uses the system default input device unless you select a specific one in Settings. If the widget shows "🎤 No microphone detected", check your Windows sound settings. You can also open **Settings** from the tray and use the microphone dropdown to pick the correct device. Hit the ⟳ button to refresh the list if you just plugged in a new mic.

**"No speech detected" but microphone works?**
This usually means Whisper received audio but couldn't recognize speech. Common causes:
- Wrong input device selected (e.g. "Stereo Mix" instead of your actual mic) — check the microphone dropdown in Settings
- Microphone volume too low in Windows sound settings (aim for 70-80%)
- Try switching to `MODEL_SIZE = "small"` in `config.py` for better accuracy with lower quality audio

**Text not pasting?**
The injector uses `Ctrl+V` via the clipboard. Some apps with custom input handling may not respond. If injection fails, the text is saved to `recovery_notes.txt` so nothing is lost.

**Tray icon not visible?**
Windows 11 hides new tray icons by default. Go to **Settings → Personalization → Taskbar → Other system tray icons** and enable WritHer to keep it always visible.

---

## License

MIT

---

<p align="center">
  <sub>Built with 🎙️ faster-whisper · 🧠 Ollama · 🐍 Python</sub>
</p>
