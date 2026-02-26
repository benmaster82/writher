import queue
import threading
import time
import tkinter as tk

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
from notifier import ReminderScheduler
from notes_window import NotesWindow
from settings_window import SettingsWindow

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

_rec_start  = 0.0
_MIN_DURATION = 0.5

# Toggle-mode timeout timers
_dict_timeout_timer  = None
_assist_timeout_timer = None


# ── Load persisted settings into config at startup ────────────────────────

def _load_settings():
    """Read settings from DB and apply them to config module."""
    hold = db.get_setting("hold_to_record", "")
    if hold != "":
        config.HOLD_TO_RECORD = hold == "1"
    max_sec = db.get_setting("max_record_seconds", "")
    if max_sec != "":
        try:
            config.MAX_RECORD_SECONDS = int(max_sec)
        except ValueError:
            pass


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
                log.info("Transcribed: %r", text)
                inject(text)
            else:
                log.info("No speech detected.")
        except Exception as exc:
            log.error("Dictation pipeline error: %s", exc)
        finally:
            if widget:
                widget.hide()


def _assistant_worker():
    """Transcribe audio, send to Ollama, and execute the returned action."""
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
            result = assistant.process(text)
            log.info("Assistant result: %s", result)

            # Handle special show commands
            if result == "__show_notes__":
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
                    widget.show_message(result, 3000)
            else:
                if widget:
                    widget.set_expression("happy")
                    widget.show_message(result, 3000)

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


def _quit():
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
    if root:
        try:
            root.after(0, root.destroy)
        except Exception:
            pass
    log.info("Shutdown complete.")


def main():
    global transcriber, tray, widget, root, notes_win, settings_win, scheduler
    global hotkey_listener

    db.init()
    _load_settings()

    root = tk.Tk()
    root.withdraw()

    widget = RecordingWidget(root)
    notes_win = NotesWindow(root)
    settings_win = SettingsWindow(root)

    recorder.on_level = lambda rms: widget.update_level(min(1.0, rms * 8))
    recorder.on_mic_error = lambda msg: widget.show_message(msg, 4000)

    tray = TrayIcon(on_quit=_quit, on_show_notes=_show_notes,
                    on_show_settings=_show_settings)
    tray.start()

    # Check Ollama connectivity at startup
    if not assistant.ping_ollama():
        log.warning("Ollama is not reachable at %s", config.OLLAMA_URL)
        tray.set_tooltip(locales.get("tray_ollama_down"))

    transcriber = Transcriber()

    scheduler = ReminderScheduler()
    scheduler.start()

    t1 = threading.Thread(target=_dictation_worker, daemon=True)
    t1.start()
    t2 = threading.Thread(target=_assistant_worker, daemon=True)
    t2.start()

    hotkey_listener = HotkeyListener(
        on_press_cb=_on_hotkey_press,
        on_release_cb=_on_hotkey_release,
        on_assist_press_cb=_on_assist_press,
        on_assist_release_cb=_on_assist_release,
    )
    hotkey_listener.start()

    log.info("Ready. AltGr=dictate, Ctrl+R=assistant.")
    root.mainloop()


if __name__ == "__main__":
    main()
