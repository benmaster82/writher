"""Windows toast notifications and reminder/appointment scheduler thread."""

import subprocess
import threading
import time
from datetime import datetime
from logger import log
import config
import database as db
import locales
from brand import get_notification_icon_path

# Try multiple notification backends in order of preference
_backend = None

try:
    from winotify import Notification as _WinotifyNotification
    _backend = "winotify"
except ImportError:
    pass

if _backend is None:
    try:
        from plyer import notification as _plyer
        _backend = "plyer"
    except ImportError:
        pass


def _send_toast(title: str, message: str):
    """Show a Windows toast notification using the best available backend."""
    ico = get_notification_icon_path()

    if _backend == "winotify":
        try:
            toast = _WinotifyNotification(
                app_id="Writher",
                title=title,
                msg=message,
                duration="long",
                icon=ico,
            )
            toast.show()
            log.info("Toast sent via winotify.")
            return
        except Exception as exc:
            log.warning("winotify failed: %s", exc)

    if _backend == "plyer":
        try:
            _plyer.notify(
                title=title,
                message=message,
                app_name="Writher",
                timeout=10,
            )
            log.info("Toast sent via plyer.")
            return
        except Exception as exc:
            log.warning("plyer failed: %s", exc)

    # Fallback: simple PowerShell BurntToast or basic balloon tip
    try:
        ps = (
            f'Add-Type -AssemblyName System.Windows.Forms; '
            f'$n = New-Object System.Windows.Forms.NotifyIcon; '
            f'$n.Icon = [System.Drawing.SystemIcons]::Information; '
            f'$n.Visible = $true; '
            f'$n.ShowBalloonTip(10000, "{_ps_escape(title)}", '
            f'"{_ps_escape(message)}", '
            f'[System.Windows.Forms.ToolTipIcon]::Info); '
            f'Start-Sleep -Seconds 12; '
            f'$n.Dispose()'
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        log.info("Toast sent via PowerShell balloon.")
    except Exception as exc:
        log.warning("All notification methods failed: %s", exc)


def _ps_escape(s: str) -> str:
    """Escape string for safe embedding in PowerShell double-quoted string."""
    return s.replace('"', '`"').replace("'", "`'").replace("\n", " ")


class ReminderScheduler:
    """Background thread that checks for due reminders and upcoming
    appointments every 30 seconds."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            self._check_reminders()
            self._check_appointments()
            self._stop.wait(30)

    def _check_reminders(self):
        """Fire toast for reminders that are due."""
        try:
            pending = db.get_pending_reminders()
            for rem in pending:
                _send_toast(locales.get("reminder_toast_title"), rem["message"])
                db.mark_reminder_notified(rem["id"])
                log.info("Reminder notified: %s", rem["message"])
        except Exception as exc:
            log.error("Reminder scheduler error: %s", exc)

    def _check_appointments(self):
        """Fire toast for appointments within the configured lead time."""
        try:
            lead = getattr(config, "APPOINTMENT_REMIND_MINUTES", 15)
            upcoming = db.get_upcoming_appointments(within_minutes=lead)
            now = datetime.now()

            for appt in upcoming:
                try:
                    appt_dt = datetime.fromisoformat(appt["dt"])
                    delta_min = max(0, int((appt_dt - now).total_seconds() / 60))
                except (ValueError, TypeError):
                    delta_min = 0

                title = appt.get("title", "")
                if delta_min <= 0:
                    body = locales.get("appointment_toast_now", title=title)
                else:
                    body = locales.get("appointment_toast_body",
                                       title=title, minutes=delta_min)

                _send_toast(locales.get("appointment_toast_title"), body)
                db.mark_appointment_notified(appt["id"])
                log.info("Appointment notified: %s (in %d min)", title, delta_min)
        except Exception as exc:
            log.error("Appointment scheduler error: %s", exc)
