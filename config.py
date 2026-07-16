from pynput.keyboard import Key, KeyCode

# ── Hotkeys ───────────────────────────────────────────────────────────────
# Hold AltGr to dictate (paste text directly)
HOTKEY = Key.alt_gr

# Hold Ctrl+Alt+R to activate assistant mode (notes, agenda, reminders).
# This is a combo hotkey: (frozenset of modifier names, trigger KeyCode).
# Ctrl+Alt+R avoids the Ctrl+Shift+R browser-reload conflict.
ASSISTANT_HOTKEY = (frozenset({"ctrl", "alt"}), KeyCode.from_vk(82))

# ── Language ──────────────────────────────────────────────────────────────
# Controls the UI and assistant strings.
# Supported values: "en" (English), "it" (Italian), "de" (German).
LANGUAGE = "en"

# ── Whisper ───────────────────────────────────────────────────────────────
# Recognition language passed to faster-whisper's transcribe().
# None = per-clip auto-detect (recommended for mixed-language users).
# Otherwise a Whisper language code: "en", "it", "de", ...
WHISPER_LANGUAGE = None

MODEL_SIZE = "base"
SAMPLE_RATE = 16000
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# ── Microphone ────────────────────────────────────────────────────────────
# None = system default.  Set to device name (str) to use a specific mic.
MIC_DEVICE_NAME = None

# ── Ollama (assistant) ───────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"

# ── Clipboard ─────────────────────────────────────────────────────────────
# True  = leave the transcript in the clipboard after paste
#         (skip the save/restore round-trip).
# False = save the user's clipboard before paste and restore it after.
KEEP_TRANSCRIPT_IN_CLIPBOARD = False

# Seconds to wait before restoring the clipboard (increase for slow apps).
CLIPBOARD_RESTORE_DELAY = 0.5

# ── Recording mode ────────────────────────────────────────────────────────
# True = hold key to record (release stops).  False = toggle (press start, press stop).
HOLD_TO_RECORD = True

# Maximum recording duration in seconds (toggle mode only, safety net).
MAX_RECORD_SECONDS = 120

# ── Appointment notifications ─────────────────────────────────────────────
# How many minutes before an appointment to send a toast notification.
APPOINTMENT_REMIND_MINUTES = 15
