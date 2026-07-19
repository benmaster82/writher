import ctypes
import locale
import os
import queue
import re
import threading
import time
import tkinter as tk

# Fix DPI awareness before any window is created.
# CustomTkinter changes the DPI mode which shifts widget positioning.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)   # PROCESS_SYSTEM_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Use the OS locale for date/time formatting (%x, %X).
try:
    locale.setlocale(locale.LC_TIME, "")
except locale.Error:
    pass

_STOP = object()  # sentinel to shut down pipeline workers

from logger import log
from recorder import Recorder
from transcriber import Transcriber
from injector import inject
from hotkey import HotkeyListener
from tray_icon import TrayIcon
from widget import RecordingWidget
import assistant
import config
import database as db
import locales
import notifier
from notifier import ReminderScheduler
from notes_window import NotesWindow
from settings_window import SettingsWindow
from replacements import apply_replacements

_pipeline_queue   = queue.Queue()
_assistant_queue  = queue.Queue()

recorder    = Recorder()
transcriber = None
tray        = None
widget      = None
root        = None
notes_win   = None
settings_win = None
scheduler   = None
hotkey_listener = None

_quit_requested = threading.Event()
_shutting_down = False

_rec_start  = 0.0
_MIN_DURATION = 0.5
_DELETE_CONFIRM_SECONDS = 15.0
_DELETE_CONFIRM_TOKEN = re.compile(r"^__confirm_delete__:(note|appointment|reminder):(\d+)$")
_pending_delete = None

# Toggle-mode timeout timers
_dict_timeout_timer  = None
_assist_timeout_timer = None


# ── Load persisted settings into config at startup ────────────────────────

def _load_settings():
    """Read settings from DB and apply them to config module."""
    from hotkey_util import str_to_key

    hold = db.get_setting("hold_to_record", "")
    if hold != "":
        config.HOLD_TO_RECORD = hold == "1"
    keep_clip = db.get_setting("keep_transcript_in_clipboard", "")
    if keep_clip != "":
        config.KEEP_TRANSCRIPT_IN_CLIPBOARD = keep_clip == "1"
    max_sec = db.get_setting("max_record_seconds", "")
    if max_sec != "":
        try:
            config.MAX_RECORD_SECONDS = int(max_sec)
        except ValueError:
            pass
    mic = db.get_setting("mic_device_name", "")
    if mic != "":
        config.MIC_DEVICE_NAME = mic if mic != "none" else None
    ollama_model = db.get_setting("ollama_model", "")
    if ollama_model:
        config.OLLAMA_MODEL = ollama_model
    ollama_url = db.get_setting("ollama_url", "")
    if ollama_url:
        config.OLLAMA_URL = ollama_url
    assistant_provider = db.get_setting("assistant_provider", "")
    if assistant_provider in {"ollama", "openai"}:
        config.ASSISTANT_PROVIDER = assistant_provider
    openai_model = db.get_setting("openai_model", "")
    if openai_model:
        config.OPENAI_MODEL = openai_model
    openai_url = db.get_setting("openai_url", "")
    if openai_url:
        config.OPENAI_URL = openai_url
    whisper = db.get_setting("whisper_model", "")
    if whisper:
        config.MODEL_SIZE = whisper
    lang = db.get_setting("language", "")
    if lang:
        config.LANGUAGE = lang
    wlang = db.get_setting("whisper_language", "")
    if wlang != "":
        config.WHISPER_LANGUAGE = None if wlang == "auto" else wlang

    # Hotkeys
    hk_dict = db.get_setting("hotkey_dictation", "")
    if hk_dict:
        parsed = str_to_key(hk_dict)
        if parsed is not None:
            config.HOTKEY = parsed
    hk_assist = db.get_setting("hotkey_assistant", "")
    if hk_assist:
        parsed = str_to_key(hk_assist)
        if parsed is not None:
            config.ASSISTANT_HOTKEY = parsed


# ── Toggle-mode timeout helpers ───────────────────────────────────────────

def _start_timeout(mode: str):
    """Start a safety timer that auto-stops recording in toggle mode."""
    global _dict_timeout_timer, _assist_timeout_timer
    if config.HOLD_TO_RECORD:
        return
    seconds = getattr(config, "MAX_RECORD_SECONDS", 120)
    if seconds <= 0:
        return
    if mode == "dictation":
        _dict_timeout_timer = threading.Timer(seconds, _timeout_dictation)
        _dict_timeout_timer.daemon = True
        _dict_timeout_timer.start()
    elif mode == "assistant":
        _assist_timeout_timer = threading.Timer(seconds, _timeout_assistant)
        _assist_timeout_timer.daemon = True
        _assist_timeout_timer.start()


def _cancel_timeout(mode: str):
    global _dict_timeout_timer, _assist_timeout_timer
    if mode == "dictation" and _dict_timeout_timer is not None:
        _dict_timeout_timer.cancel()
        _dict_timeout_timer = None
    elif mode == "assistant" and _assist_timeout_timer is not None:
        _assist_timeout_timer.cancel()
        _assist_timeout_timer = None


def _timeout_dictation():
    log.warning("Toggle-mode dictation timeout reached.")
    if hotkey_listener:
        hotkey_listener.force_stop_dictation()


def _timeout_assistant():
    log.warning("Toggle-mode assistant timeout reached.")
    if hotkey_listener:
        hotkey_listener.force_stop_assistant()


# ── Dictation callbacks (AltGr) ──────────────────────────────────────────

def _on_hotkey_press():
    global _rec_start
    _rec_start = time.monotonic()
    recorder.start()
    if tray:
        tray.set_recording(True)
    if widget:
        widget.show_recording()
    _start_timeout("dictation")
    log.info("Recording started (dictation).")


def _on_hotkey_release():
    _cancel_timeout("dictation")
    audio = recorder.stop()
    duration = time.monotonic() - _rec_start
    if tray:
        tray.set_recording(False)
    log.info("Recording stopped (%.2fs).", duration)

    if audio is not None and len(audio) > 0 and duration >= _MIN_DURATION:
        if widget:
            widget.show_processing()
        _pipeline_queue.put(audio)
    else:
        if widget:
            widget.hide()
        if duration < _MIN_DURATION:
            log.info("Too short (%.2fs), skipping.", duration)
        else:
            log.info("Empty audio, skipping.")


# ── Assistant callbacks (Ctrl+R) ──────────────────────────────────────────

def _on_assist_press():
    global _rec_start
    _rec_start = time.monotonic()
    recorder.start()
    if tray:
        tray.set_recording(True)
    if widget:
        widget.show_assistant()
        widget.set_expression("listening")
    _start_timeout("assistant")
    log.info("Recording started (assistant).")


def _on_assist_release():
    _cancel_timeout("assistant")
    audio = recorder.stop()
    duration = time.monotonic() - _rec_start
    if tray:
        tray.set_recording(False)
    log.info("Assistant recording stopped (%.2fs).", duration)

    if audio is not None and len(audio) > 0 and duration >= _MIN_DURATION:
        if widget:
            widget.show_processing()
            widget.set_expression("thinking")
        _assistant_queue.put(audio)
    else:
        if widget:
            widget.hide()


# ── Pipeline workers ──────────────────────────────────────────────────────

def _dictation_worker():
    """Transcribe audio and paste the result into the active application."""
    while True:
        item = _pipeline_queue.get()
        if item is _STOP:
            break
        try:
            log.info("Transcribing (dictation)...")
            text = transcriber.transcribe(item)
            if text:
                log.debug("Raw: %r", text)
                text = apply_replacements(text)
                log.info("Transcribed: %r", text)
                inject(text)
            else:
                log.info("No speech detected.")
        except Exception as exc:
            log.error("Dictation pipeline error: %s", exc)
        finally:
            if widget:
                widget.hide()


def _parse_delete_token(result: str):
    m = _DELETE_CONFIRM_TOKEN.match(result or "")
    if not m:
        return None
    return m.group(1), int(m.group(2))

def _run_on_ui_thread(func):
    """Schedule a Tk/CustomTkinter operation on the Tk main thread."""
    if root:
        root.after(0, func)

def _set_pending_delete(kind: str, item_id: int):
    global _pending_delete
    _pending_delete = {
        "kind": kind,
        "id": item_id,
        "expires_at": time.monotonic() + _DELETE_CONFIRM_SECONDS,
    }

    def _open_dialog():
        try:
            if not notes_win:
                return

            if not (notes_win._win and notes_win._win.winfo_exists()):
                notes_win.show("notes")

            notes_win.show_voice_delete_confirmation(kind, item_id)
            log.info("Pending delete dialog opened: %s #%d", kind, item_id)

        except Exception as exc:
            log.error("Could not open voice delete dialog: %s", exc)

    _run_on_ui_thread(_open_dialog)

    log.info(
        "Pending delete set: %s #%d (expires in %.1fs)",
        kind,
        item_id,
        _DELETE_CONFIRM_SECONDS,
    )

def _clear_pending_delete():
    global _pending_delete
    _pending_delete = None

def _close_voice_delete_dialog():
    """Close/hide the voice delete dialog on the Tk main thread."""
    if not root:
        return

    def _close():
        try:
            if notes_win and notes_win._voice_delete_dialog:
                dialog = notes_win._voice_delete_dialog
                notes_win._voice_delete_dialog = None
                notes_win._safe_destroy_dialog(dialog)
        except Exception as exc:
            log.error("Could not close voice delete dialog: %s", exc)

    root.after(0, _close)


def _matches_locale_choice(text: str, key: str) -> bool:
    t = " ".join((text or "").strip().lower().split())
    if not t:
        return False

    choices = [
        " ".join(choice.strip().lower().split())
        for choice in locales.get_choices(key)
        if choice.strip()
    ]
    if not choices:
        return False

    alternatives = "|".join(re.escape(choice) for choice in choices)
    pattern = rf"(?<!\w)(?:{alternatives})(?!\w)"
    return bool(re.search(pattern, t))


def _is_affirmative(text: str) -> bool:
    return _matches_locale_choice(text, "delete_confirmations")


def _is_negative(text: str) -> bool:
    return _matches_locale_choice(text, "delete_rejections")


def _refresh_notes_window_if_open():
    if notes_win and notes_win._win and notes_win._win.winfo_exists():
        root.after(0, notes_win._refresh)


def _delete_by_pending(kind: str, item_id: int) -> str:
    if kind == "note":
        title = locales.get("default_note_title")
        for note in db.get_all_notes():
            if note["id"] == item_id:
                title = note["title"] or title
                break
        else:
            return locales.get("delete_item_missing", item=locales.get("delete_item_note"))
        db.delete_note(item_id)
        _refresh_notes_window_if_open()
        return locales.get("note_deleted", title=title, nid=item_id)

    if kind == "appointment":
        title = None
        for appointment in db.get_appointments():
            if appointment["id"] == item_id:
                title = appointment["title"]
                break
        if title is None:
            return locales.get("delete_item_missing", item=locales.get("delete_item_appointment"))
        db.delete_appointment(item_id)
        _refresh_notes_window_if_open()
        return locales.get("appointment_deleted", title=title, aid=item_id)

    if kind == "reminder":
        message = None
        for reminder in db.get_all_reminders(include_notified=True):
            if reminder["id"] == item_id:
                message = reminder["message"]
                break
        if message is None:
            return locales.get("delete_item_missing", item=locales.get("delete_item_reminder"))
        db.delete_reminder(item_id)
        _refresh_notes_window_if_open()
        return locales.get("reminder_deleted", message=message, rid=item_id)

    return locales.get("error", detail=f"Unsupported delete kind: {kind}")


def _handle_pending_delete_confirmation(text: str):
    if _pending_delete is None:
        return None

    now = time.monotonic()
    if now > _pending_delete["expires_at"]:
        log.info("Pending delete expired.")
        _close_voice_delete_dialog()
        _clear_pending_delete()
        return "__delete_confirm_timeout__"

    if _is_affirmative(text):
        kind = _pending_delete["kind"]
        item_id = _pending_delete["id"]
        _close_voice_delete_dialog()
        _clear_pending_delete()
        return _delete_by_pending(kind, item_id)

    if _is_negative(text):
        _close_voice_delete_dialog()
        _clear_pending_delete()
        return "__delete_cancelled__"

    remaining = int(max(1, _pending_delete["expires_at"] - now))
    return f"__delete_confirm_repeat__:{remaining}"


def _assistant_worker():
    """Transcribe audio, send it to the local LLM, and execute its action."""
    while True:
        item = _assistant_queue.get()
        if item is _STOP:
            break
        try:
            log.info("Transcribing (assistant)...")
            text = transcriber.transcribe(item)
            if not text:
                log.info("No speech detected.")
                if widget:
                    widget.hide()
                continue

            log.info("Assistant heard: %r", text)
            result = _handle_pending_delete_confirmation(text)
            if result is None:
                if not assistant.ping_provider():
                    provider = getattr(config, "ASSISTANT_PROVIDER", "ollama")
                    url = (config.OPENAI_URL if provider == "openai"
                           else config.OLLAMA_URL)
                    log.warning("Assistant provider %s unreachable at %s — "
                                "aborting assistant call.", provider, url)
                    notifier.notify(
                        locales.get("assistant_unreachable_title"),
                        locales.get("assistant_unreachable_body"),
                    )
                    if widget:
                        widget.set_expression("error")
                        widget.show_message(
                            locales.get("assistant_unreachable_body"), 3000)
                    continue
                result = assistant.process(text)
            log.info("Assistant result: %s", result)

            token = _parse_delete_token(result)
            if token:
                kind, item_id = token
                _set_pending_delete(kind, item_id)
                if widget:
                    widget.set_expression("listening")
                    widget.show_message(
                        locales.get(
                            "delete_confirm_prompt",
                            item=locales.get(f"delete_item_{kind}"),
                            seconds=int(_DELETE_CONFIRM_SECONDS),
                        ),
                        2200,
                    )
                continue

            # Handle special show commands
            if result == "__delete_confirm_timeout__":
                if widget:
                    widget.set_expression("sad")
                    widget.show_message(locales.get("delete_confirm_timeout"), 2200)
            elif result == "__delete_cancelled__":
                if widget:
                    widget.set_expression("sad")
                    widget.show_message(locales.get("delete_cancelled"), 2200)
            elif result.startswith("__delete_confirm_repeat__:"):
                remaining = int(result.rsplit(":", 1)[1])
                if widget:
                    widget.set_expression("listening")
                    widget.show_message(locales.get("delete_confirm_repeat", seconds=remaining), 2200)
            elif result == "__show_notes__":
                if notes_win:
                    root.after(0, lambda: notes_win.show("notes"))
                if widget:
                    widget.set_expression("happy")
                    widget.show_message(locales.get("show_notes"), 2000)
            elif result == "__show_appointments__":
                if notes_win:
                    root.after(0, lambda: notes_win.show("appointments"))
                if widget:
                    widget.set_expression("happy")
                    widget.show_message(locales.get("show_appointments"), 2000)
            elif result == "__show_reminders__":
                if notes_win:
                    root.after(0, lambda: notes_win.show("reminders"))
                if widget:
                    widget.set_expression("happy")
                    widget.show_message(locales.get("show_reminders"), 2000)
            elif result == locales.get("not_understood") or result.startswith(locales.get("error", detail="")):
                if widget:
                    widget.set_expression("sad")
                    widget.show_message("✗", 2000)
            else:
                if widget:
                    widget.set_expression("happy")
                    widget.show_message("✓", 2000)

        except Exception as exc:
            log.error("Assistant pipeline error: %s", exc)
            if widget:
                widget.set_expression("error")
                widget.show_message(locales.get("assistant_error"), 2000)


# ── Quit & Main ───────────────────────────────────────────────────────────

def _show_notes():
    """Open notes window from tray menu."""
    if notes_win:
        root.after(0, lambda: notes_win.show("notes"))


def _show_settings():
    """Open settings window from tray menu."""
    if settings_win:
        root.after(0, lambda: settings_win.show())


def _request_quit():
    """Receive a tray-thread request without calling Tk from that thread."""
    _quit_requested.set()


def _shutdown_requested() -> bool:
    """Return True as soon as shutdown is requested or has begun."""
    return _quit_requested.is_set() or _shutting_down


def _poll_quit_request():
    """Run shutdown on Tk's main thread when the tray requests it."""
    if _quit_requested.is_set():
        _quit()
        return
    if root:
        root.after(50, _poll_quit_request)


def _quit():
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    log.info("Quitting...")
    _cancel_timeout("dictation")
    _cancel_timeout("assistant")
    _pipeline_queue.put(_STOP)
    _assistant_queue.put(_STOP)
    if scheduler:
        scheduler.stop()
    if hotkey_listener:
        try:
            hotkey_listener.stop()
        except Exception:
            pass
    if tray:
        try:
            tray.stop()
        except Exception:
            pass
    try:
        recorder.stop()
    except Exception:
        pass
    # Hide child windows immediately, then destroy root after event queue drains
    if root:
        try:
            if notes_win and notes_win._win and notes_win._win.winfo_exists():
                notes_win._win.withdraw()
            if settings_win and settings_win._win and settings_win._win.winfo_exists():
                settings_win._win.withdraw()
        except Exception:
            pass
        try:
            root.after(50, _destroy_root)
        except Exception:
            _destroy_root()


def _destroy_root():
    """Destroy root after pending Tk events have been processed."""
    try:
        root.destroy()
    except Exception:
        pass
    log.info("Shutdown complete.")


def _acquire_instance_lock():
    """Return a Win32 mutex handle if this is the first instance, else exit."""
    import ctypes
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Local\\WritHerSingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log.error("Another instance of WritHer is already running. Exiting.")
        try:
            notifier.notify(
                locales.get("already_running_title"),
                locales.get("already_running_body"),
            )
        except Exception:
            pass
        raise SystemExit(1)
    return mutex  # keep reference so it isn't garbage-collected


def _whisper_model_is_cached(size: str) -> bool:
    """Return True if the faster-whisper model is already on disk.

    Mirrors huggingface_hub's cache resolution (HF_HUB_CACHE / HF_HOME /
    default ~/.cache/huggingface/hub) so the startup widget can honestly
    say "Downloading" vs "Loading".
    """
    import os
    hub = os.environ.get("HF_HUB_CACHE")
    if not hub:
        hf_home = os.environ.get("HF_HOME") or os.path.join(
            os.path.expanduser("~"), ".cache", "huggingface")
        hub = os.path.join(hf_home, "hub")
    snapshots = os.path.join(
        hub, f"models--Systran--faster-whisper-{size}", "snapshots")
    try:
        return any(os.scandir(snapshots))
    except OSError:
        return False


def _finish_startup():
    """Load the Whisper model and start the pipelines.

    Runs on a background thread so the Tk mainloop can paint the widget
    while the model loads — on first launch the download takes minutes,
    and without visible feedback the app looks dead.
    """
    global transcriber, scheduler, hotkey_listener
    from hotkey_util import key_display_name

    downloading = not _whisper_model_is_cached(config.MODEL_SIZE)
    widget.show_status(locales.get(
        "model_downloading" if downloading else "model_loading"))
    log.info("Model '%s' cached: %s", config.MODEL_SIZE, not downloading)

    try:
        transcriber = Transcriber()
    except Exception as exc:
        log.error("Whisper model load failed: %s", exc)
        widget.show_status(locales.get("model_error"), expression="error")
        notifier.notify(
            locales.get("model_error_title"),
            locales.get("model_error_body"),
        )
        return  # tray stays alive so the user can read the toast and quit

    if _shutdown_requested():
        log.info("Startup cancelled after model load: shutdown requested.")
        return

    db.save_setting(model_flag, "1")

    if _shutdown_requested():
        return
    scheduler = ReminderScheduler()
    scheduler.start()

    if _shutdown_requested():
        scheduler.stop()
        scheduler = None
        return
    t1 = threading.Thread(target=_dictation_worker, daemon=True)
    t1.start()
    t2 = threading.Thread(target=_assistant_worker, daemon=True)
    t2.start()

    if _shutdown_requested():
        return
    hotkey_listener = HotkeyListener(
        on_press_cb=_on_hotkey_press,
        on_release_cb=_on_hotkey_release,
        on_assist_press_cb=_on_assist_press,
        on_assist_release_cb=_on_assist_release,
    )
    hotkey_listener.start()

    if _shutdown_requested():
        hotkey_listener.stop()
        hotkey_listener = None
        return
    dict_key = key_display_name(config.HOTKEY)
    # Wording must match the configured recording mode: "hold" is wrong
    # (and misleading) when the user has toggle mode enabled.
    rec_mode = "hold" if config.HOLD_TO_RECORD else "toggle"
    widget.set_expression("happy")
    widget.show_message(
        locales.get(f"startup_ready_{rec_mode}", hotkey=dict_key), 3500)

    if db.get_setting("welcome_shown", "") != "1":
        notifier.notify(
            locales.get("welcome_title"),
            locales.get(
                f"welcome_body_{rec_mode}",
                dict_key=dict_key,
                assist_key=key_display_name(config.ASSISTANT_HOTKEY),
            ),
        )
        db.save_setting("welcome_shown", "1")

    log.info("Ready. %s=dictate, %s=assistant.",
             dict_key, key_display_name(config.ASSISTANT_HOTKEY))


def main():
    global tray, widget, root, notes_win, settings_win

    _mutex = _acquire_instance_lock()

    db.init()
    _load_settings()

    root = tk.Tk()
    root.withdraw()

    widget = RecordingWidget(root)
    notes_win = NotesWindow(root)
    settings_win = SettingsWindow(root)

    recorder.on_level = lambda rms: widget.update_level(min(1.0, rms * 8))
    recorder.on_mic_error = lambda msg: widget.show_message(msg, 4000)

    tray = TrayIcon(on_quit=_request_quit, on_show_notes=_show_notes,
                    on_show_settings=_show_settings)
    tray.start()
    tray.set_tooltip(locales.get("tray_idle"))

    threading.Thread(target=_finish_startup, daemon=True).start()

    root.after(50, _poll_quit_request)
    root.mainloop()

    # Belt and braces: pystray's run_detached() thread is non-daemon and can
    # survive icon.stop(), leaving a ghost process that keeps holding the
    # single-instance mutex ("already running" with no tray icon). Give
    # stragglers a moment to finish, then force the process to exit.
    for t in threading.enumerate():
        if t is not threading.current_thread() and not t.daemon:
            t.join(timeout=2.0)
    log.info("Process exit.")
    os._exit(0)


if __name__ == "__main__":
    main()
