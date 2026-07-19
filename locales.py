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
        "delete_confirm_prompt": "Say yes within {seconds}s to delete this {item}",
        "delete_confirm_repeat": "Please say yes or no ({seconds}s left)",
        "delete_confirm_timeout": "Delete confirmation timed out",
        "delete_cancelled":      "Delete cancelled",
        "delete_item_missing":   "{item} was not found",
        "delete_item_note":      "note",
        "delete_item_appointment": "appointment",
        "delete_item_reminder":  "reminder",
        "confirm_delete_title":  "Confirm delete {item}",
        "field_name":            "Name",
        "field_created":         "Created",
        "field_event":           "Event",
        "field_remind":          "Remind At",
        "confirm_delete_warning": "This action cannot be undone.",
        "btn_cancel":            "Cancel",
        "btn_delete":            "Delete",
        "listening_for_confirm": "Listening for voice confirmation...",
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
        "ollama_unreachable_title": "Writher — assistant unavailable",
        "ollama_unreachable_body":  "Ollama is not running — assistant mode unavailable",
        "assistant_unreachable_title": "Writher — assistant unavailable",
        "assistant_unreachable_body":  "Local LLM provider is not reachable — assistant mode unavailable",

        # main.py — startup
        "model_downloading":    "Downloading speech model...",
        "model_loading":        "Loading speech model...",
        "startup_ready_hold":   "✓ Ready — hold {hotkey}",
        "startup_ready_toggle": "✓ Ready — press {hotkey}",
        "welcome_title":        "WritHer is ready",
        "welcome_body_hold":    "Hold {dict_key} and speak — text appears in any app. Hold {assist_key} for the voice assistant.",
        "welcome_body_toggle":  "Press {dict_key}, speak, then press it again — text appears in any app. Press {assist_key} for the voice assistant.",
        "model_error":          "Speech model failed to load",
        "model_error_title":    "WritHer — speech model error",
        "model_error_body":     "Could not load the speech model. Check your internet connection (first launch) and restart WritHer.",
        "already_running_title": "WritHer is already running",
        "already_running_body":  "Check the system tray (the ^ arrow next to the clock).",

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
        "setting_assistant_provider": "Assistant provider",
        "setting_assistant_model":  "Assistant model",
        "setting_assistant_url":    "Assistant URL",
        "setting_ollama_model":     "Ollama model",
        "setting_ollama_url":       "Ollama URL",
        "setting_whisper_model":    "Whisper model",
        "setting_whisper_hint":     "Recommended: 'small' or larger for reliable Symbol & spelling mode phrases",
        "setting_recognition_lang": "Recognition language",
        "setting_recognition_auto": "Auto",
        "setting_recognition_hint": "Symbol phrases are English-only; enabling Symbol & spelling mode with a non-English recognition language may miss substitutions.",
        "setting_language":         "Language",
        "setting_restart_required": "Restart required to apply",

        # settings_window.py — hotkey configuration
        "setting_hotkeys":          "Keyboard shortcuts",
        "setting_hotkey_dictation": "Dictation",
        "setting_hotkey_assistant": "Assistant",
        "setting_hotkey_press":     "Press a key...",
        "setting_hotkey_conflict":  "Already in use",

        # settings_window.py — log viewer
        "setting_log":              "Log",

        # settings_window.py — replacements
        "setting_keep_clipboard":       "Keep transcript in clipboard",
        "setting_keep_clipboard_hint":  "When on, skip restoring the previous clipboard so the transcribed text stays available for re-paste.",
        "setting_symbol_mode":      "Symbol & spelling mode",
        "setting_symbol_mode_hint": "When on, spoken symbols and digits are substituted and letter-by-letter spelling is glued.",
        "setting_vocabulary":       "Custom vocabulary",
        "setting_vocab_spoken":     "Spoken form",
        "setting_vocab_written":    "Written form",
        "setting_vocab_add":        "Add",
        "setting_vocab_delete":     "Delete",
        "setting_vocab_empty":      "No entries yet",
        "setting_priming":          "Priming terms (best-effort)",
        "setting_priming_hint":     "Comma-separated hints joined into faster-whisper's initial prompt. Best-effort.",
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
        "delete_confirm_prompt": "Di' si entro {seconds}s per eliminare questo {item}",
        "delete_confirm_repeat": "Di' si o no ({seconds}s rimasti)",
        "delete_confirm_timeout": "Conferma eliminazione scaduta",
        "delete_cancelled":      "Eliminazione annullata",
        "delete_item_missing":   "{item} non trovato",
        "delete_item_note":      "nota",
        "delete_item_appointment": "appuntamento",
        "delete_item_reminder":  "reminder",
        "confirm_delete_title":  "Conferma eliminazione {item}",
        "field_name":            "Nome",
        "field_created":         "Creato",
        "field_event":           "Evento",
        "field_remind":          "Ricorda il",
        "confirm_delete_warning": "Questa azione non può essere annullata.",
        "btn_cancel":            "Annulla",
        "btn_delete":            "Elimina",
        "listening_for_confirm": "In ascolto della conferma vocale...",
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
        "ollama_unreachable_title": "Writher — assistente non disponibile",
        "ollama_unreachable_body":  "Ollama non è in esecuzione — modalità assistente non disponibile",
        "assistant_unreachable_title": "Writher — assistente non disponibile",
        "assistant_unreachable_body":  "Il provider LLM locale non è raggiungibile — modalità assistente non disponibile",

        "model_downloading":    "Download modello vocale...",
        "model_loading":        "Caricamento modello vocale...",
        "startup_ready_hold":   "✓ Pronto — tieni premuto {hotkey}",
        "startup_ready_toggle": "✓ Pronto — premi {hotkey}",
        "welcome_title":        "WritHer è pronto",
        "welcome_body_hold":    "Tieni premuto {dict_key} e parla — il testo appare in qualsiasi app. Tieni premuto {assist_key} per l'assistente vocale.",
        "welcome_body_toggle":  "Premi {dict_key}, parla, poi premi di nuovo — il testo appare in qualsiasi app. Premi {assist_key} per l'assistente vocale.",
        "model_error":          "Errore caricamento modello",
        "model_error_title":    "WritHer — errore modello vocale",
        "model_error_body":     "Impossibile caricare il modello vocale. Controlla la connessione (primo avvio) e riavvia WritHer.",
        "already_running_title": "WritHer è già in esecuzione",
        "already_running_body":  "Controlla la system tray (la freccia ^ vicino all'orologio).",

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
        "setting_assistant_provider": "Provider dell'assistente",
        "setting_assistant_model":  "Modello dell'assistente",
        "setting_assistant_url":    "URL dell'assistente",
        "setting_ollama_model":     "Modello Ollama",
        "setting_ollama_url":       "URL Ollama",
        "setting_whisper_model":    "Modello Whisper",
        "setting_whisper_hint":     "Consigliato: 'small' o superiore per frasi affidabili della modalità Simboli e ortografia",
        "setting_recognition_lang": "Lingua di riconoscimento",
        "setting_recognition_auto": "Auto",
        "setting_recognition_hint": "Le frasi dei simboli sono solo in inglese; attivando la modalità Simboli e ortografia con un'altra lingua di riconoscimento potrebbero mancare delle sostituzioni.",
        "setting_language":         "Lingua",
        "setting_restart_required": "Riavvio necessario per applicare",

        # settings_window.py — hotkey configuration
        "setting_hotkeys":          "Scorciatoie tastiera",
        "setting_hotkey_dictation": "Dettatura",
        "setting_hotkey_assistant": "Assistente",
        "setting_hotkey_press":     "Premi un tasto...",
        "setting_hotkey_conflict":  "Già in uso",

        # settings_window.py — log viewer
        "setting_log":              "Log",

        "setting_keep_clipboard":       "Mantieni la trascrizione negli appunti",
        "setting_keep_clipboard_hint":  "Se attivo, salta il ripristino degli appunti precedenti così il testo trascritto rimane disponibile per essere reincollato.",
        "setting_symbol_mode":      "Modalità Simboli e ortografia",
        "setting_symbol_mode_hint": "Se attiva, i simboli parlati e le cifre vengono sostituiti e la scansione lettera per lettera viene unita.",
        "setting_vocabulary":       "Vocabolario personalizzato",
        "setting_vocab_spoken":     "Forma parlata",
        "setting_vocab_written":    "Forma scritta",
        "setting_vocab_add":        "Aggiungi",
        "setting_vocab_delete":     "Elimina",
        "setting_vocab_empty":      "Nessuna voce",
        "setting_priming":          "Termini di priming (best-effort)",
        "setting_priming_hint":     "Suggerimenti separati da virgola inseriti nell'initial prompt di faster-whisper. Best-effort.",
    },

    "de": {
        "note_saved":           "Notiz gespeichert (#{nid})",
        "list_saved":           "Liste '{title}' gespeichert ({count} Einträge)",
        "added_to_list":        "Zu '{title}' hinzugefügt",
        "list_not_found":       "Liste '{title}' nicht gefunden",
        "note_not_found":       "Notiz mit '{keyword}' nicht gefunden",
        "note_deleted":         "Notiz '{title}' gelöscht (#{nid})",
        "appointment_created":  "Termin erstellt: {title} ({dt})",
        "appointment_not_found": "Termin mit '{keyword}' nicht gefunden",
        "appointment_deleted":   "Termin '{title}' gelöscht (#{aid})",
        "reminder_not_found":   "Erinnerung mit '{keyword}' nicht gefunden",
        "reminder_deleted":     "Erinnerung '{message}' gelöscht (#{rid})",
        "reminder_set":         "Erinnerung gesetzt: {dt}",
        "delete_confirm_prompt": "Sagen Sie ja innerhalb von {seconds}s, um dieses {item} zu löschen",
        "delete_confirm_repeat": "Bitte sagen Sie ja oder nein ({seconds}s verbleiben)",
        "delete_confirm_timeout": "Löschbestätigung abgelaufen",
        "delete_cancelled":      "Löschen abgebrochen",
        "delete_item_missing":   "{item} wurde nicht gefunden",
        "delete_item_note":      "Notiz",
        "delete_item_appointment": "Termin",
        "delete_item_reminder":  "Erinnerung",
        "confirm_delete_title":  "{item} löschen bestätigen",
        "field_name":            "Name",
        "field_created":         "Erstellt",
        "field_event":           "Ereignis",
        "field_remind":          "Erinnern am",
        "confirm_delete_warning": "Diese Aktion kann nicht rückgängig gemacht werden.",
        "btn_cancel":            "Abbrechen",
        "btn_delete":            "Löschen",
        "listening_for_confirm": "Warte auf Sprachbestätigung...",
        "unknown_command":      "Unbekannter Befehl: {name}",
        "error":                "Fehler: {detail}",
        "not_understood":       "Ich habe den Befehl nicht verstanden",
        "delete_confirmations": (
            "ja", "jep", "jo", "klar", "ok", "okay",
            "bestätigen", "bestätigt", "mach es", "los", "weiter",
            "löschen", "lösch es",
        ),
        "delete_rejections": (
            "nein", "nope", "nö", "abbrechen", "stopp", "halt",
            "nicht löschen", "behalten", "egal", "vergiss es",
        ),

        "system_prompt": (
            "You are Writher, a voice assistant for productivity. "
            "Current date and time: {now} ({weekday}). "
            "The user speaks in {lang_name}. "
            "Interpret their request and call the appropriate function. "
            "When the user says relative times like 'morgen', 'in einer Stunde', "
            "'nächsten Montag', convert them to absolute ISO datetimes. "
            "Always respond by calling a function — never reply with plain text "
            "unless no function fits."
        ),
        "lang_name": "German",

        "show_notes":           "📝 Hier sind Ihre Notizen",
        "show_appointments":    "📅 Hier ist Ihre Agenda",
        "show_reminders":       "⏰ Hier sind Ihre Erinnerungen",
        "assistant_error":      "Assistentenfehler",
        "ollama_unreachable_title": "Writher — Assistent nicht verfügbar",
        "ollama_unreachable_body":  "Ollama läuft nicht — Assistentenmodus nicht verfügbar",
        "assistant_unreachable_title": "Writher — Assistent nicht verfügbar",
        "assistant_unreachable_body":  "Der lokale LLM-Anbieter ist nicht erreichbar — Assistentenmodus nicht verfügbar",

        "model_downloading":    "Sprachmodell wird heruntergeladen...",
        "model_loading":        "Sprachmodell wird geladen...",
        "startup_ready_hold":   "✓ Bereit — {hotkey} gedrückt halten",
        "startup_ready_toggle": "✓ Bereit — {hotkey} drücken",
        "welcome_title":        "WritHer ist bereit",
        "welcome_body_hold":    "{dict_key} gedrückt halten und sprechen — der Text erscheint in jeder App. {assist_key} für den Sprachassistenten.",
        "welcome_body_toggle":  "{dict_key} drücken, sprechen, erneut drücken — der Text erscheint in jeder App. {assist_key} für den Sprachassistenten.",
        "model_error":          "Sprachmodell-Fehler",
        "model_error_title":    "WritHer — Sprachmodell-Fehler",
        "model_error_body":     "Sprachmodell konnte nicht geladen werden. Internetverbindung prüfen (Erststart) und WritHer neu starten.",
        "already_running_title": "WritHer läuft bereits",
        "already_running_body":  "Siehe System-Tray (^-Pfeil neben der Uhr).",

        "tray_idle":            "Writher — bereit",
        "tray_recording":       "Writher — Aufnahme...",
        "tray_ollama_down":     "Writher — Ollama nicht erreichbar",
        "tray_notes_agenda":    "Notizen & Agenda",
        "tray_quit":            "Beenden",

        "no_notes":             "Keine Notizen",
        "no_appointments":      "Keine Termine",
        "no_reminders":         "Keine Erinnerungen",
        "tab_notes":            "📝  Notizen",
        "tab_agenda":           "📅  Agenda",
        "tab_reminders":        "⏰  Erinnerungen",
        "default_list_title":   "Liste",
        "default_note_title":   "Notiz",

        "reminder_toast_title":     "Writher Erinnerung",
        "appointment_toast_title":  "Writher Termin",
        "appointment_toast_body":   "📅 {title} — in {minutes} Min.",
        "appointment_toast_now":    "📅 {title} — jetzt!",

        "tray_settings":            "Einstellungen",

        "settings_title":           "Einstellungen",
        "setting_record_mode":      "Aufnahmemodus",
        "setting_hold":             "Halten zum Aufnehmen",
        "setting_toggle":           "Drücken zum Starten / Stoppen",
        "setting_max_duration":     "Max. Aufnahmedauer (Sekunden)",
        "setting_saved":            "Einstellungen gespeichert",
        "setting_microphone":       "Mikrofon",
        "setting_mic_default":      "Systemstandard",
        "setting_assistant_provider": "Assistentenanbieter",
        "setting_assistant_model":  "Assistentenmodell",
        "setting_assistant_url":    "Assistenten-URL",
        "setting_ollama_model":     "Ollama-Modell",
        "setting_ollama_url":       "Ollama-URL",
        "setting_whisper_model":    "Whisper-Modell",
        "setting_whisper_hint":     "Empfohlen: 'small' oder größer für zuverlässige Phrasen im Symbol- & Buchstabiermodus",
        "setting_recognition_lang": "Erkennungssprache",
        "setting_recognition_auto": "Auto",
        "setting_recognition_hint": "Symbol-Phrasen sind nur auf Englisch verfügbar; im Symbol- & Buchstabiermodus mit einer anderen Erkennungssprache können Ersetzungen fehlen.",
        "setting_language":         "Sprache",
        "setting_restart_required": "Neustart erforderlich",

        "setting_hotkeys":          "Tastenkürzel",
        "setting_hotkey_dictation": "Diktat",
        "setting_hotkey_assistant": "Assistent",
        "setting_hotkey_press":     "Taste drücken...",
        "setting_hotkey_conflict":  "Bereits belegt",

        "setting_log":              "Log",

        "setting_keep_clipboard":       "Transkript in der Zwischenablage behalten",
        "setting_keep_clipboard_hint":  "Wenn aktiv, wird der vorherige Inhalt der Zwischenablage nicht wiederhergestellt — der transkribierte Text bleibt zum erneuten Einfügen verfügbar.",
        "setting_symbol_mode":      "Symbol- & Buchstabiermodus",
        "setting_symbol_mode_hint": "Wenn aktiv, werden gesprochene Symbole und Zahlen ersetzt und einzelne Buchstaben zusammengefügt.",
        "setting_vocabulary":       "Benutzerdefiniertes Vokabular",
        "setting_vocab_spoken":     "Gesprochene Form",
        "setting_vocab_written":    "Geschriebene Form",
        "setting_vocab_add":        "Hinzufügen",
        "setting_vocab_delete":     "Löschen",
        "setting_vocab_empty":      "Noch keine Einträge",
        "setting_priming":          "Priming-Begriffe (best-effort)",
        "setting_priming_hint":     "Komma-getrennte Hinweise für faster-whispers initial_prompt. Best-effort.",
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
