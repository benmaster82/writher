"""Centralised i18n string table for Writher.

All user-facing strings are stored here, keyed by language code.
Use ``get(key)`` to retrieve the string for the current ``config.LANGUAGE``.
Supports format placeholders via ``get(key, **kwargs)``.

To add a new language, add a new entry to ``_STRINGS`` with the same keys.
"""

import config

LocaleValue = str | tuple[str, ...]

# ── String tables ─────────────────────────────────────────────────────────

_STRINGS: dict[str, dict[str, LocaleValue]] = {
    "en": {
        # assistant.py — dispatch confirmations
        "note_saved":           "Note saved (#{nid})",
        "list_saved":           "List '{title}' saved ({count} items)",
        "added_to_list":        "Added to '{title}'",
        "list_not_found":       "List '{title}' not found",
        "note_not_found":       "Note matching '{keyword}' not found",
        "note_deleted":         "Note '{title}' deleted (#{nid})",
        "appointment_created":  "Appointment created: {title} ({dt})",
        "appointment_not_found": "Appointment matching '{keyword}' not found",
        "appointment_deleted":   "Appointment '{title}' deleted (#{aid})",
        "reminder_not_found":   "Reminder matching '{keyword}' not found",
        "reminder_deleted":     "Reminder '{message}' deleted (#{rid})",
        "reminder_set":         "Reminder set: {dt}",
        "unknown_command":      "Unknown command: {name}",
        "error":                "Error: {detail}",
        "not_understood":       "I didn't understand the command",
        "delete_confirmations": (
            "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
            "confirm", "confirmed", "please do", "do it", "go ahead",
            "delete", "delete it",
        ),
        "delete_rejections": (
            "no", "nope", "nah", "cancel", "stop", "abort", "do not",
            "don't", "dont", "keep it", "never mind", "nevermind",
            "leave it",
        ),

        # assistant.py — system prompt fragments
        "system_prompt": (
            "You are Writher, a voice assistant for productivity. "
            "Current date and time: {now} ({weekday}). "
            "The user speaks in {lang_name}. "
            "Interpret their request and call the appropriate function. "
            "When the user says relative times like 'tomorrow', 'in one hour', "
            "'next Monday', convert them to absolute ISO datetimes. "
            "Always respond by calling a function — never reply with plain text "
            "unless no function fits."
        ),
        "lang_name": "English",

        # main.py — widget messages
        "show_notes":           "📝 Here are your notes",
        "show_appointments":    "📅 Here is your agenda",
        "show_reminders":       "⏰ Here are your reminders",
        "assistant_error":      "Assistant error",

        # tray_icon.py
        "tray_idle":            "Writher — idle",
        "tray_recording":       "Writher — recording...",
        "tray_ollama_down":     "Writher — Ollama not reachable",
        "tray_notes_agenda":    "Notes & Agenda",
        "tray_quit":            "Quit",

        # notes_window.py — UI labels
        "no_notes":             "No notes",
        "no_appointments":      "No appointments",
        "no_reminders":         "No reminders",
        "tab_notes":            "📝  Notes",
        "tab_agenda":           "📅  Agenda",
        "tab_reminders":        "⏰  Reminders",
        "default_list_title":   "List",
        "default_note_title":   "Note",

        # notifier.py
        "reminder_toast_title":     "Writher Reminder",
        "appointment_toast_title":  "Writher Appointment",
        "appointment_toast_body":   "📅 {title} — in {minutes} min",
        "appointment_toast_now":    "📅 {title} — now!",

        # tray_icon.py — settings menu
        "tray_settings":            "Settings",

        # settings_window.py
        "settings_title":           "Settings",
        "setting_record_mode":      "Recording mode",
        "setting_hold":             "Hold to record",
        "setting_toggle":           "Press to start / stop",
        "setting_max_duration":     "Max recording (seconds)",
        "setting_saved":            "Settings saved",
        "setting_microphone":       "Microphone",
        "setting_mic_default":      "System default",
        "setting_ollama_model":     "Ollama model",
        "setting_ollama_url":       "Ollama URL",
        "setting_whisper_model":    "Whisper model",
        "setting_language":         "Language",
        "setting_restart_required": "Restart required to apply",

        # settings_window.py — hotkey configuration
        "setting_hotkeys":          "Keyboard shortcuts",
        "setting_hotkey_dictation": "Dictation",
        "setting_hotkey_assistant": "Assistant",
        "setting_hotkey_press":     "Press a key...",
        "setting_hotkey_conflict":  "Already in use",
    },

    "it": {
        "note_saved":           "Nota salvata (#{nid})",
        "list_saved":           "Lista '{title}' salvata ({count} elementi)",
        "added_to_list":        "Aggiunto a '{title}'",
        "list_not_found":       "Lista '{title}' non trovata",
        "note_not_found":       "Nota con '{keyword}' non trovata",
        "note_deleted":         "Nota '{title}' eliminata (#{nid})",
        "appointment_created":  "Appuntamento creato: {title} ({dt})",
        "appointment_not_found": "Appuntamento con '{keyword}' non trovato",
        "appointment_deleted":   "Appuntamento '{title}' eliminato (#{aid})",
        "reminder_not_found":   "Reminder con '{keyword}' non trovato",
        "reminder_deleted":     "Reminder '{message}' eliminato (#{rid})",
        "reminder_set":         "Reminder impostato: {dt}",
        "unknown_command":      "Comando sconosciuto: {name}",
        "error":                "Errore: {detail}",
        "not_understood":       "Non ho capito il comando",
        "delete_confirmations": (
            "si", "sì", "certo", "certamente", "ok", "okay",
            "va bene", "confermo", "conferma", "procedi",
            "elimina", "eliminalo", "cancella", "cancellalo",
        ),
        "delete_rejections": (
            "no", "nope", "annulla", "stop", "ferma", "fermati",
            "aspetta", "lascia", "lascia stare", "lascia perdere",
            "non eliminare", "non cancellare", "mantieni",
        ),

        "system_prompt": (
            "You are Writher, a voice assistant for productivity. "
            "Current date and time: {now} ({weekday}). "
            "The user speaks in {lang_name}. "
            "Interpret their request and call the appropriate function. "
            "When the user says relative times like 'domani', 'tra un'ora', "
            "'lunedì prossimo', convert them to absolute ISO datetimes. "
            "Always respond by calling a function — never reply with plain text "
            "unless no function fits."
        ),
        "lang_name": "Italian",

        "show_notes":           "📝 Ecco le note",
        "show_appointments":    "📅 Ecco l'agenda",
        "show_reminders":       "⏰ Ecco i reminder",
        "assistant_error":      "Errore assistente",

        "tray_idle":            "Writher — inattivo",
        "tray_recording":       "Writher — registrazione...",
        "tray_ollama_down":     "Writher — Ollama non raggiungibile",
        "tray_notes_agenda":    "Note & Agenda",
        "tray_quit":            "Esci",

        "no_notes":             "Nessuna nota",
        "no_appointments":      "Nessun appuntamento",
        "no_reminders":         "Nessun reminder",
        "tab_notes":            "📝  Note",
        "tab_agenda":           "📅  Agenda",
        "tab_reminders":        "⏰  Reminder",
        "default_list_title":   "Lista",
        "default_note_title":   "Nota",

        "reminder_toast_title":     "Writher Promemoria",
        "appointment_toast_title":  "Writher Appuntamento",
        "appointment_toast_body":   "📅 {title} — tra {minutes} min",
        "appointment_toast_now":    "📅 {title} — adesso!",

        # tray_icon.py — settings menu
        "tray_settings":            "Impostazioni",

        # settings_window.py
        "settings_title":           "Impostazioni",
        "setting_record_mode":      "Modalità registrazione",
        "setting_hold":             "Tieni premuto per registrare",
        "setting_toggle":           "Premi per avviare / fermare",
        "setting_max_duration":     "Durata max registrazione (secondi)",
        "setting_saved":            "Impostazioni salvate",
        "setting_microphone":       "Microfono",
        "setting_mic_default":      "Predefinito di sistema",
        "setting_ollama_model":     "Modello Ollama",
        "setting_ollama_url":       "URL Ollama",
        "setting_whisper_model":    "Modello Whisper",
        "setting_language":         "Lingua",
        "setting_restart_required": "Riavvio necessario per applicare",

        # settings_window.py — hotkey configuration
        "setting_hotkeys":          "Scorciatoie tastiera",
        "setting_hotkey_dictation": "Dettatura",
        "setting_hotkey_assistant": "Assistente",
        "setting_hotkey_press":     "Premi un tasto...",
        "setting_hotkey_conflict":  "Già in uso",
    },
}

_FALLBACK = "en"


# ── Public API ────────────────────────────────────────────────────────────

def _lookup(key: str) -> LocaleValue:
    lang = getattr(config, "LANGUAGE", _FALLBACK)
    table = _STRINGS.get(lang, _STRINGS[_FALLBACK])
    return table.get(key, _STRINGS[_FALLBACK].get(key, key))


def get(key: str, **kwargs) -> str:
    """Return the localised string for *key*, formatted with *kwargs*.

    Falls back to English if the key is missing in the active language.
    """
    template = _lookup(key)
    if not isinstance(template, str):
        return key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


def get_choices(key: str) -> tuple[str, ...]:
    """Return the localised choice list for *key*.

    Use this for non-display locale entries, such as spoken confirmation
    variants for destructive actions.
    """
    choices = _lookup(key)
    if isinstance(choices, tuple):
        return choices
    return (choices,)
