"""SQLite storage for notes, appointments and reminders."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from paths import DB_PATH

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    """Create tables if they don't exist and run safe migrations."""
    with _lock:
        c = _conn()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL DEFAULT '',
                content    TEXT NOT NULL DEFAULT '',
                category   TEXT NOT NULL DEFAULT 'general',
                note_type  TEXT NOT NULL DEFAULT 'text',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS appointments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                dt          TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                notified    INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                message    TEXT NOT NULL,
                remind_at  TEXT NOT NULL,
                notified   INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """)
        # Safe migration: add notified column to appointments if missing
        cols = [row[1] for row in c.execute("PRAGMA table_info(appointments)")]
        if "notified" not in cols:
            c.execute("ALTER TABLE appointments ADD COLUMN notified INTEGER NOT NULL DEFAULT 0")

        # Settings key/value store
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Custom vocabulary (Layer A of the replacement engine).
        # spoken is the key; stored lowercase so lookups are case-insensitive.
        c.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                spoken  TEXT PRIMARY KEY,
                written TEXT NOT NULL
            )
        """)

        # Priming terms — joined into faster-whisper's initial_prompt.
        c.execute("""
            CREATE TABLE IF NOT EXISTS priming_terms (
                term TEXT PRIMARY KEY
            )
        """)

        c.commit()
        c.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Notes ─────────────────────────────────────────────────────────────────

def save_note(content: str, category: str = "general", title: str = "") -> int:
    """Save a free-text note. Returns the new note id."""
    now = _now()
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO notes (title,content,category,note_type,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (title, content, category, "text", now, now),
        )
        c.commit()
        nid = cur.lastrowid
        c.close()
    return nid


def save_list(title: str, items: list[str], category: str = "general") -> int:
    """Save a list note (shopping, todo …). Returns the new note id."""
    now = _now()
    data = json.dumps([{"item": it, "checked": False} for it in items],
                      ensure_ascii=False)
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO notes (title,content,category,note_type,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (title, data, category, "list", now, now),
        )
        c.commit()
        nid = cur.lastrowid
        c.close()
    return nid


def add_to_list(note_id: int, items: list[str]) -> bool:
    """Append items to an existing list note."""
    with _lock:
        c = _conn()
        row = c.execute("SELECT content, note_type FROM notes WHERE id=?",
                        (note_id,)).fetchone()
        if not row or row["note_type"] != "list":
            c.close()
            return False
        current = json.loads(row["content"])
        current.extend({"item": it, "checked": False} for it in items)
        c.execute("UPDATE notes SET content=?, updated_at=? WHERE id=?",
                  (json.dumps(current, ensure_ascii=False), _now(), note_id))
        c.commit()
        c.close()
    return True


def check_item(note_id: int, item_text: str) -> bool:
    """Toggle checked state for an item in a list note (fuzzy match)."""
    with _lock:
        c = _conn()
        row = c.execute("SELECT content, note_type FROM notes WHERE id=?",
                        (note_id,)).fetchone()
        if not row or row["note_type"] != "list":
            c.close()
            return False
        current = json.loads(row["content"])
        target = item_text.strip().lower()
        found = False
        for entry in current:
            if entry["item"].strip().lower() == target:
                entry["checked"] = not entry["checked"]
                found = True
                break
        if found:
            c.execute("UPDATE notes SET content=?, updated_at=? WHERE id=?",
                      (json.dumps(current, ensure_ascii=False), _now(), note_id))
            c.commit()
        c.close()
    return found


def find_list_by_title(title: str) -> dict | None:
    """Find a list note by fuzzy title match. Returns dict or None."""
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM notes WHERE note_type='list' ORDER BY updated_at DESC"
        ).fetchall()
        c.close()
    target = title.strip().lower()
    for r in rows:
        if target in r["title"].strip().lower():
            return dict(r)
    return None


def find_note_by_keyword(keyword: str) -> dict | None:
    """Find a note by fuzzy title/content match. Returns dict or None."""
    target = keyword.strip().lower()
    if not target:
        return None
    keyword_pattern = f"%{target}%"
    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT * FROM notes"
            " WHERE lower(title) LIKE ? OR lower(content) LIKE ?"
            " ORDER BY updated_at DESC",
            (keyword_pattern, keyword_pattern),
        ).fetchone()
        c.close()
    return dict(row) if row else None


def get_all_notes() -> list[dict]:
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM notes ORDER BY updated_at DESC").fetchall()
        c.close()
    return [dict(r) for r in rows]


def delete_note(note_id: int):
    with _lock:
        c = _conn()
        c.execute("DELETE FROM notes WHERE id=?", (note_id,))
        c.commit()
        c.close()


# ── Appointments ──────────────────────────────────────────────────────────

def create_appointment(title: str, dt: str, description: str = "") -> int:
    """Create a calendar appointment. *dt* is ISO datetime string."""
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO appointments (title,dt,description,created_at)"
            " VALUES (?,?,?,?)",
            (title, dt, description, _now()),
        )
        c.commit()
        aid = cur.lastrowid
        c.close()
    return aid


def get_appointments(from_dt: str | None = None, to_dt: str | None = None) -> list[dict]:
    """Return appointments optionally filtered by date range."""
    with _lock:
        c = _conn()
        q = "SELECT * FROM appointments"
        params: list = []
        clauses = []
        if from_dt:
            clauses.append("dt >= ?")
            params.append(from_dt)
        if to_dt:
            clauses.append("dt <= ?")
            params.append(to_dt)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY dt ASC"
        rows = c.execute(q, params).fetchall()
        c.close()
    return [dict(r) for r in rows]


def find_appointment_by_keyword(keyword: str) -> dict | None:
    """Find an appointment by fuzzy title/description match. Returns dict or None."""
    target = keyword.strip().lower()
    if not target:
        return None
    keyword_pattern = f"%{target}%"
    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT * FROM appointments"
            " WHERE lower(title) LIKE ? OR lower(description) LIKE ?"
            " ORDER BY dt ASC",
            (keyword_pattern, keyword_pattern),
        ).fetchone()
        c.close()
    return dict(row) if row else None


def delete_appointment(aid: int):
    with _lock:
        c = _conn()
        c.execute("DELETE FROM appointments WHERE id=?", (aid,))
        c.commit()
        c.close()


def get_upcoming_appointments(within_minutes: int) -> list[dict]:
    """Return appointments due within *within_minutes* that haven't been notified yet."""
    now = datetime.now()
    cutoff = (now + timedelta(minutes=within_minutes)).isoformat(timespec="seconds")
    now_str = now.isoformat(timespec="seconds")
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM appointments WHERE notified=0 AND dt<=? AND dt>=?"
            " ORDER BY dt ASC",
            (cutoff, now_str),
        ).fetchall()
        c.close()
    return [dict(r) for r in rows]


def get_past_unnotified_appointments() -> list[dict]:
    """Return appointments whose time has passed but were never notified."""
    now_str = datetime.now().isoformat(timespec="seconds")
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM appointments WHERE notified=0 AND dt<=?"
            " ORDER BY dt ASC",
            (now_str,),
        ).fetchall()
        c.close()
    return [dict(r) for r in rows]


def mark_appointment_notified(aid: int):
    with _lock:
        c = _conn()
        c.execute("UPDATE appointments SET notified=1 WHERE id=?", (aid,))
        c.commit()
        c.close()


# ── Reminders ─────────────────────────────────────────────────────────────

def set_reminder(message: str, remind_at: str) -> int:
    """Create a reminder. *remind_at* is ISO datetime string."""
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO reminders (message,remind_at,notified,created_at)"
            " VALUES (?,?,0,?)",
            (message, remind_at, _now()),
        )
        c.commit()
        rid = cur.lastrowid
        c.close()
    return rid


def get_pending_reminders() -> list[dict]:
    """Return reminders that are due and not yet notified."""
    now = _now()
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM reminders WHERE notified=0 AND remind_at<=?"
            " ORDER BY remind_at ASC", (now,)
        ).fetchall()
        c.close()
    return [dict(r) for r in rows]


def find_reminder_by_keyword(keyword: str) -> dict | None:
    """Find a reminder by fuzzy message match. Returns dict or None."""
    target = keyword.strip().lower()
    if not target:
        return None
    keyword_pattern = f"%{target}%"
    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT * FROM reminders"
            " WHERE lower(message) LIKE ?"
            " ORDER BY remind_at ASC",
            (keyword_pattern,)
        ).fetchone()
        c.close()
    return dict(row) if row else None


def mark_reminder_notified(rid: int):
    with _lock:
        c = _conn()
        c.execute("UPDATE reminders SET notified=1 WHERE id=?", (rid,))
        c.commit()
        c.close()


def get_all_reminders(include_notified: bool = False) -> list[dict]:
    with _lock:
        c = _conn()
        q = "SELECT * FROM reminders"
        if not include_notified:
            q += " WHERE notified=0"
        q += " ORDER BY remind_at ASC"
        rows = c.execute(q).fetchall()
        c.close()
    return [dict(r) for r in rows]


def delete_reminder(rid: int):
    with _lock:
        c = _conn()
        c.execute("DELETE FROM reminders WHERE id=?", (rid,))
        c.commit()
        c.close()


# ── Settings ──────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    """Return a setting value, or *default* if not found."""
    with _lock:
        c = _conn()
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        c.close()
    return row["value"] if row else default


def save_setting(key: str, value: str):
    """Insert or update a setting."""
    with _lock:
        c = _conn()
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        c.commit()
        c.close()


def save_settings(settings: dict[str, str]):
    """Save multiple settings atomically."""
    with _lock:
        c = _conn()
        try:
            c.executemany(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                settings.items(),
            )
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()


# ── Custom vocabulary (Layer A) ───────────────────────────────────────────

def list_vocabulary() -> list[tuple[str, str]]:
    """Return all vocabulary entries as [(spoken, written), ...]."""
    with _lock:
        c = _conn()
        rows = c.execute("SELECT spoken, written FROM vocabulary").fetchall()
        c.close()
    return [(r["spoken"], r["written"]) for r in rows]


def save_vocabulary_entry(spoken: str, written: str):
    """Insert or update a vocabulary entry. Spoken is stored lowercase."""
    key = spoken.strip().lower()
    if not key:
        return
    with _lock:
        c = _conn()
        c.execute(
            "INSERT INTO vocabulary (spoken, written) VALUES (?, ?)"
            " ON CONFLICT(spoken) DO UPDATE SET written=excluded.written",
            (key, written),
        )
        c.commit()
        c.close()


def delete_vocabulary_entry(spoken: str):
    key = spoken.strip().lower()
    with _lock:
        c = _conn()
        c.execute("DELETE FROM vocabulary WHERE spoken=?", (key,))
        c.commit()
        c.close()


# ── Priming terms ─────────────────────────────────────────────────────────

def list_priming_terms() -> list[str]:
    with _lock:
        c = _conn()
        rows = c.execute("SELECT term FROM priming_terms ORDER BY term").fetchall()
        c.close()
    return [r["term"] for r in rows]


def replace_priming_terms(terms: list[str]):
    """Replace the full priming-term set with *terms*."""
    normalized = [t.strip() for t in terms if t and t.strip()]
    with _lock:
        c = _conn()
        c.execute("DELETE FROM priming_terms")
        c.executemany(
            "INSERT OR IGNORE INTO priming_terms (term) VALUES (?)",
            [(t,) for t in normalized],
        )
        c.commit()
        c.close()
