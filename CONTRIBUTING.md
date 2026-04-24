# Contributing to WritHer

Thanks for your interest in contributing! WritHer is a young open-source project and every contribution matters - whether it's code, bug reports, translations, or just feedback.

## Getting Started

### Prerequisites

- Python 3.11+
- Windows 10/11 (current platform)
- Git

### Setup

```bash
git clone https://github.com/benmaster82/writher.git
cd writher
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

WritHer will appear in the system tray. Hold `AltGr` to dictate, hold `Ctrl+R` for assistant mode.

## Project Structure

```
main.py              - Entry point, orchestrator, Tk event loop
config.py            - All default settings
hotkey.py            - Keyboard listener (hold/toggle modes)
recorder.py          - Microphone capture (sounddevice)
transcriber.py       - Speech-to-text (faster-whisper)
injector.py          - Clipboard paste into active app (Win32 API)
assistant.py         - Ollama LLM integration + function calling
database.py          - SQLite storage (notes, appointments, reminders, settings)
notifier.py          - Toast notifications + reminder scheduler
widget.py            - Floating pill overlay with animated eyes (Tkinter + PIL)
notes_window.py      - Notes/Agenda/Reminders viewer (CustomTkinter)
settings_window.py   - Settings UI (CustomTkinter)
tray_icon.py         - System tray icon (pystray)
brand.py             - Pandora Blackboard icon renderer (PIL)
theme.py             - Unified colour palette and fonts
locales.py           - i18n string tables (EN, IT)
logger.py            - Rotating file + console logger
```

## How to Contribute

### Reporting Bugs

Open an [issue](https://github.com/benmaster82/writher/issues) with:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS version and Python version
- Any relevant log output from `writher.log`

### Suggesting Features

Open an issue with the `enhancement` label. Describe the use case and why it would be useful.

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes
4. Test manually (run the app, try the feature)
5. Commit with a clear message: `git commit -m "feat: add your feature"`
6. Push to your fork: `git push origin feat/your-feature`
7. Open a Pull Request

No formal review process - just describe what you changed and why.

## Areas Where Help is Needed

### macOS Port

The following modules use Windows-specific APIs and need macOS equivalents:

- `injector.py` - Uses Win32 clipboard API (ctypes) and `Ctrl+V` simulation
- `notifier.py` - Uses winotify / PowerShell balloon tips
- `widget.py` - Uses `WS_EX_NOACTIVATE` and `-transparentcolor` (Windows-only Tk features)
- `hotkey.py` - Uses pynput (works cross-platform, but key names may differ)

### Linux Port

Same as macOS, plus:

- `injector.py` - Replace with xdotool or xclip + xdotool key simulation
- `notifier.py` - Replace with libnotify / notify-send
- `widget.py` - Transparency and click-through may need X11/Wayland specific handling

### New Languages

Adding a language is straightforward:

1. Open `locales.py`
2. Copy the `"en"` dictionary
3. Translate all values
4. Add it with your language code (e.g. `"fr"`, `"de"`, `"es"`)

No code changes needed beyond `locales.py`.

### Ollama Model Testing

WritHer uses Ollama's function calling API. Not all models support it equally well. If you test a model, please report:

- Model name and size (e.g. `llama3.1:8b`)
- Whether function calling works reliably
- Any issues with date/time parsing
- Response time on your hardware

### UI/UX Improvements

The UI uses CustomTkinter with a unified theme defined in `theme.py`. All colours and fonts are centralized there. If you want to improve the look:

- Edit `theme.py` for colours and fonts
- Edit `notes_window.py` or `settings_window.py` for layout
- The floating widget (`widget.py`) uses raw Tkinter + PIL - it's more complex but well-commented

## Code Style

- No strict linter enforced, but keep it clean and readable
- Follow the existing patterns in the codebase
- Use `log.info()` / `log.error()` for logging (never `print()`)
- Add i18n strings to `locales.py` for any user-facing text (both EN and IT)
- Use `theme.py` constants for colours and fonts in UI code
- Persist user settings via `database.save_setting()` / `database.get_setting()`

## Commit Messages

We use conventional-ish commit messages:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `chore:` - Maintenance, dependencies, config

## Questions?

Open an issue or start a discussion. No question is too small.
