from pynput.keyboard import Key, KeyCode

# ── Hotkeys ───────────────────────────────────────────────────────────────
# Hold AltGr to dictate (paste text directly)
HOTKEY = Key.alt_gr

# Hold Ctrl+Alt+R to activate assistant mode (notes, agenda, reminders).
# This is a combo hotkey: (frozenset of modifier names, trigger KeyCode).
# Ctrl+Alt+R avoids the Ctrl+Shift+R browser-reload conflict.
ASSISTANT_HOTKEY = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))

# ── Language ──────────────────────────────────────────────────────────────
# Controls both Whisper transcription and all UI / assistant strings.
# Supported values: "en" (English), "it" (Italian).
LANGUAGE = "en"

# ── Whisper ───────────────────────────────────────────────────────────────
MODEL_SIZE = "small"
SAMPLE_RATE = 16000
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# ── Microphone ────────────────────────────────────────────────────────────
# None = system default.  Set to device name (str) to use a specific mic.
MIC_DEVICE_NAME = None

# ── Ollama (assistant) ───────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"

# ── Recording mode ────────────────────────────────────────────────────────
# True = hold key to record (release stops).  False = toggle (press start, press stop).
HOLD_TO_RECORD = True

# Maximum recording duration in seconds (toggle mode only, safety net).
MAX_RECORD_SECONDS = 120

# ── Appointment notifications ─────────────────────────────────────────────
# How many minutes before an appointment to send a toast notification.
APPOINTMENT_REMIND_MINUTES = 15
