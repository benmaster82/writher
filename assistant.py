"""Ollama-based assistant with function calling for notes, agenda and reminders."""

import json
import re
from datetime import datetime, timedelta
from logger import log
import config
import locales

try:
    import requests
except ImportError:
    requests = None

import database as db

# ── Tool definitions (sent to Ollama) ─────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a free-text note. Use for generic notes, thoughts, reminders without a specific time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":    {"type": "string", "description": "Short title for the note"},
                    "content":  {"type": "string", "description": "Full note content"},
                    "category": {"type": "string", "description": "Category: general, work, personal, idea",
                                 "default": "general"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_list",
            "description": "Save a list (shopping list, todo list, packing list, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":    {"type": "string", "description": "List title, e.g. 'Shopping', 'Todo'"},
                    "items":    {"type": "array", "items": {"type": "string"},
                                 "description": "List items"},
                    "category": {"type": "string", "description": "Category: shopping, todo, general",
                                 "default": "general"},
                },
                "required": ["title", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_list",
            "description": "Add items to an existing list note, found by title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "list_title": {"type": "string", "description": "Title of the existing list"},
                    "items":      {"type": "array", "items": {"type": "string"},
                                   "description": "Items to add"},
                },
                "required": ["list_title", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": "Create a calendar appointment with date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title":       {"type": "string", "description": "Appointment title"},
                    "datetime":    {"type": "string",
                                    "description": "ISO datetime, e.g. 2026-02-23T15:00"},
                    "description": {"type": "string", "description": "Optional details",
                                    "default": ""},
                },
                "required": ["title", "datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Set a reminder that will trigger a notification at the specified time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message":   {"type": "string", "description": "What to remind about"},
                    "remind_at": {"type": "string",
                                  "description": "ISO datetime for the reminder, e.g. 2026-02-23T10:00"},
                },
                "required": ["message", "remind_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "Show/search saved notes. Use when user asks to see their notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category (optional)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_appointments",
            "description": "Show upcoming appointments/agenda.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Show active (pending) reminders.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


# ── System prompt ─────────────────────────────────────────────────────────

def _system_prompt() -> str:
    """Build the system prompt using the active language."""
    now = datetime.now()
    return locales.get(
        "system_prompt",
        now=now.strftime("%Y-%m-%d %H:%M"),
        weekday=now.strftime("%A"),
        lang_name=locales.get("lang_name"),
    )


# ── Ollama API call ───────────────────────────────────────────────────────

def _call_ollama(text: str) -> dict | None:
    """Send transcribed text to Ollama and return the function-call dict."""
    if requests is None:
        log.error("requests library not installed")
        return None

    url = f"{config.OLLAMA_URL}/api/chat"
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": text},
        ],
        "tools": TOOLS,
        "stream": False,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.error("Ollama request failed: %s", exc)
        return None

    msg = data.get("message", {})

    # Check for tool_calls in the response
    tool_calls = msg.get("tool_calls")
    if tool_calls and len(tool_calls) > 0:
        tc = tool_calls[0]
        return {
            "function": tc["function"]["name"],
            "arguments": tc["function"].get("arguments", {}),
        }

    # Some models return the function call in the content as JSON
    content = msg.get("content", "").strip()
    if content:
        log.info("Ollama text response: %s", content)
        try:
            parsed = json.loads(content)
            if "function" in parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    return None


# ── Function dispatcher ───────────────────────────────────────────────────

def _dispatch(fc: dict) -> str:
    """Execute a function call and return a localised confirmation string."""
    name = fc["function"]
    args = fc.get("arguments", {})
    log.info("Assistant dispatch: %s(%s)", name, args)

    try:
        if name == "save_note":
            nid = db.save_note(
                content=args.get("content", ""),
                category=args.get("category", "general"),
                title=args.get("title", ""),
            )
            return locales.get("note_saved", nid=nid)

        elif name == "save_list":
            nid = db.save_list(
                title=args.get("title", locales.get("default_list_title")),
                items=args.get("items", []),
                category=args.get("category", "general"),
            )
            count = len(args.get("items", []))
            return locales.get("list_saved", title=args.get("title", ""), count=count)

        elif name == "add_to_list":
            existing = db.find_list_by_title(args.get("list_title", ""))
            if existing:
                db.add_to_list(existing["id"], args.get("items", []))
                return locales.get("added_to_list", title=existing["title"])
            else:
                return locales.get("list_not_found", title=args.get("list_title", ""))

        elif name == "create_appointment":
            aid = db.create_appointment(
                title=args.get("title", ""),
                dt=args.get("datetime", ""),
                description=args.get("description", ""),
            )
            return locales.get("appointment_created",
                               title=args.get("title", ""),
                               dt=args.get("datetime", ""))

        elif name == "set_reminder":
            rid = db.set_reminder(
                message=args.get("message", ""),
                remind_at=args.get("remind_at", ""),
            )
            return locales.get("reminder_set", dt=args.get("remind_at", ""))

        elif name == "list_notes":
            return "__show_notes__"

        elif name == "list_appointments":
            return "__show_appointments__"

        elif name == "list_reminders":
            return "__show_reminders__"

        else:
            return locales.get("unknown_command", name=name)

    except Exception as exc:
        log.error("Dispatch error: %s", exc)
        return locales.get("error", detail=str(exc))


# ── Public API ────────────────────────────────────────────────────────────

def ping_ollama() -> bool:
    """Quick connectivity check. Returns True if Ollama is reachable."""
    if requests is None:
        return False
    try:
        resp = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def process(text: str) -> str:
    """Process transcribed text through Ollama. Returns confirmation string.

    Special return values starting with '__show_' signal the caller
    to open the notes/agenda window.
    """
    log.info("Assistant input: %r", text)
    fc = _call_ollama(text)
    if fc is None:
        return locales.get("not_understood")
    return _dispatch(fc)
