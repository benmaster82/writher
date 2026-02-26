from pynput.keyboard import Key

# ── Hotkeys ───────────────────────────────────────────────────────────────
# Hold AltGr to dictate (paste text directly)
HOTKEY = Key.alt_gr

# Hold Ctrl+R to activate assistant mode (notes, agenda, reminders)
ASSISTANT_HOTKEY = Key.ctrl_r

# ── Language ──────────────────────────────────────────────────────────────
# Controls both Whisper transcription and all UI / assistant strings.
# Supported values: "en" (English), "it" (Italian).
LANGUAGE = "en"

# ── Whisper ───────────────────────────────────────────────────────────────
MODEL_SIZE = "base"
SAMPLE_RATE = 16000
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# ── Ollama (assistant) ───────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "gpt-oss:120b-cloud"

# ── Recording mode ────────────────────────────────────────────────────────
# True = hold key to record (release stops).  False = toggle (press start, press stop).
HOLD_TO_RECORD = True

# Maximum recording duration in seconds (toggle mode only, safety net).
MAX_RECORD_SECONDS = 120

# ── Appointment notifications ─────────────────────────────────────────────
# How many minutes before an appointment to send a toast notification.
APPOINTMENT_REMIND_MINUTES = 15
