"""Centralised path resolution for WritHer.

Provides a single DATA_DIR for all writable files (database, logs, recovery).
- When running from source: uses the project directory
- When running as PyInstaller exe: uses %APPDATA%/WritHer/

Also provides BUNDLE_DIR for read-only bundled assets (icons, images).
"""

import os
import sys


def _is_frozen() -> bool:
    """Return True if running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def _get_data_dir() -> str:
    """Return the directory for writable user data (DB, logs, recovery)."""
    if _is_frozen():
        # PyInstaller exe: use %APPDATA%/WritHer/
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        data_dir = os.path.join(appdata, "WritHer")
    else:
        # Running from source: use the project directory
        data_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_bundle_dir() -> str:
    """Return the directory where bundled read-only assets live.

    For PyInstaller this is the _MEIPASS temp dir or _internal folder.
    For source, it's the project directory.
    """
    if _is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# Resolved once at import time
DATA_DIR = _get_data_dir()
BUNDLE_DIR = _get_bundle_dir()

# Convenience paths
DB_PATH = os.path.join(DATA_DIR, "writher.db")
LOG_PATH = os.path.join(DATA_DIR, "writher.log")
RECOVERY_PATH = os.path.join(DATA_DIR, "recovery_notes.txt")
ICO_PATH = os.path.join(DATA_DIR, "writher.ico")
PNG_PATH = os.path.join(DATA_DIR, "writher_icon.png")
