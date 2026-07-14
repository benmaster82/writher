"""Post-processing pipeline for dictation output.

Two layers, both inert by default:

  Layer A — user vocabulary
    Applied whenever the user has defined any spoken → written mappings.
    Case-insensitive, whole-word, longest-first.

  Layer B — spoken symbols / numbers / spelling collapse
    Opt-in via the "Symbol & spelling mode" toggle (default OFF). When
    ON, spoken names for symbols and digits become characters, and runs
    of single-character or all-digit tokens are glued together so
    letter-by-letter spelling and inline symbol-code phrases work
    ("W H forward slash F A T" → "WH/FAT").

Apply order:
    Layer A → Layer B substitutions → single-char / digit collapse

With Layer B OFF and no user vocabulary, output is byte-identical to
Whisper's raw transcription (aside from a leading/trailing whitespace
trim, which the fork's symbols.py already performed).
"""

import re

import database as db


# ── Layer B: symbol / number / spelling data ──────────────────────────────

# Multi-word phrases first (longer patterns take precedence), then single-word.
# Apostrophe is intentionally excluded from the code-separator symbols so
# contractions like "don't" stay glued together (see _CONTRACTION_RE).
_SUBS = [
    # Multi-word
    (re.compile(r"\bforward slash\b",     re.IGNORECASE), "/"),
    (re.compile(r"\bback slash\b",        re.IGNORECASE), r"\\"),
    (re.compile(r"\bbackslash\b",         re.IGNORECASE), r"\\"),
    (re.compile(r"\bdouble colon\b",      re.IGNORECASE), "::"),
    (re.compile(r"\bdouble quote\b",      re.IGNORECASE), '"'),
    (re.compile(r"\bsingle quote\b",      re.IGNORECASE), "'"),
    (re.compile(r"\bopen bracket\b",      re.IGNORECASE), "("),
    (re.compile(r"\bclose bracket\b",     re.IGNORECASE), ")"),
    (re.compile(r"\bleft bracket\b",      re.IGNORECASE), "("),
    (re.compile(r"\bright bracket\b",     re.IGNORECASE), ")"),
    (re.compile(r"\bopen parenthesis\b",  re.IGNORECASE), "("),
    (re.compile(r"\bclose parenthesis\b", re.IGNORECASE), ")"),
    (re.compile(r"\bopen curly\b",        re.IGNORECASE), "{"),
    (re.compile(r"\bclose curly\b",       re.IGNORECASE), "}"),
    (re.compile(r"\bleft curly\b",        re.IGNORECASE), "{"),
    (re.compile(r"\bright curly\b",       re.IGNORECASE), "}"),
    (re.compile(r"\bopen square\b",       re.IGNORECASE), "["),
    (re.compile(r"\bclose square\b",      re.IGNORECASE), "]"),
    (re.compile(r"\bleft square\b",       re.IGNORECASE), "["),
    (re.compile(r"\bright square\b",      re.IGNORECASE), "]"),
    (re.compile(r"\bless than\b",         re.IGNORECASE), "<"),
    (re.compile(r"\bgreater than\b",      re.IGNORECASE), ">"),
    (re.compile(r"\bexclamation mark\b",  re.IGNORECASE), "!"),
    (re.compile(r"\bquestion mark\b",     re.IGNORECASE), "?"),
    (re.compile(r"\bat sign\b",           re.IGNORECASE), "@"),
    (re.compile(r"\bhash sign\b",         re.IGNORECASE), "#"),
    (re.compile(r"\bpound sign\b",        re.IGNORECASE), "#"),
    (re.compile(r"\bpercent sign\b",      re.IGNORECASE), "%"),
    (re.compile(r"\bdollar sign\b",       re.IGNORECASE), "$"),
    (re.compile(r"\bvertical bar\b",      re.IGNORECASE), "|"),
    (re.compile(r"\bequal sign\b",        re.IGNORECASE), "="),
    (re.compile(r"\bequals sign\b",       re.IGNORECASE), "="),
    (re.compile(r"\bplus sign\b",         re.IGNORECASE), "+"),
    (re.compile(r"\bminus sign\b",        re.IGNORECASE), "-"),
    (re.compile(r"\bnew line\b",          re.IGNORECASE), "\n"),
    (re.compile(r"\bnew paragraph\b",     re.IGNORECASE), "\n\n"),
    # Single-word
    (re.compile(r"\bslash\b",      re.IGNORECASE), "/"),
    (re.compile(r"\bsemicolon\b",  re.IGNORECASE), ";"),
    (re.compile(r"\bcolon\b",      re.IGNORECASE), ":"),
    (re.compile(r"\bunderscore\b", re.IGNORECASE), "_"),
    (re.compile(r"\bdash\b",       re.IGNORECASE), "-"),
    (re.compile(r"\bhyphen\b",     re.IGNORECASE), "-"),
    (re.compile(r"\bminus\b",      re.IGNORECASE), "-"),
    (re.compile(r"\bplus\b",       re.IGNORECASE), "+"),
    (re.compile(r"\basterisk\b",   re.IGNORECASE), "*"),
    (re.compile(r"\btilde\b",      re.IGNORECASE), "~"),
    (re.compile(r"\bcaret\b",      re.IGNORECASE), "^"),
    (re.compile(r"\bpercent\b",    re.IGNORECASE), "%"),
    (re.compile(r"\bampersand\b",  re.IGNORECASE), "&"),
    (re.compile(r"\bpipe\b",       re.IGNORECASE), "|"),
    (re.compile(r"\bbacktick\b",   re.IGNORECASE), "`"),
    # Number words → digits
    (re.compile(r"\bzero\b|\bnought\b", re.IGNORECASE), "0"),
    (re.compile(r"\bone\b",             re.IGNORECASE), "1"),
    (re.compile(r"\btwo\b",             re.IGNORECASE), "2"),
    (re.compile(r"\bthree\b",           re.IGNORECASE), "3"),
    (re.compile(r"\bfour\b",            re.IGNORECASE), "4"),
    (re.compile(r"\bfive\b",            re.IGNORECASE), "5"),
    (re.compile(r"\bsix\b",             re.IGNORECASE), "6"),
    (re.compile(r"\bseven\b",           re.IGNORECASE), "7"),
    (re.compile(r"\beight\b",           re.IGNORECASE), "8"),
    (re.compile(r"\bnine\b",            re.IGNORECASE), "9"),
]

# Symbols that may appear embedded in a token (excluding apostrophe).
_SPLIT_SYM_RE = re.compile(r"[/\\:;_@#$%&|~^*+=<>!?()\[\]{}\"\-]")

# Contraction: word+apostrophe+word (e.g. don't, we're, it's). Never split.
_CONTRACTION_RE = re.compile(r"^\w+'\w+$")


# ── Layer A ───────────────────────────────────────────────────────────────

def apply_layer_a(text: str, vocab: dict[str, str]) -> str:
    """Substitute user-defined spoken forms with their written equivalents.

    - Case-insensitive, whole-word.
    - Spoken forms may contain internal spaces.
    - Longest spoken form wins when overlaps are possible.
    """
    if not vocab:
        return text
    # Longest-first so multi-word spoken forms match before their prefixes.
    for spoken in sorted(vocab.keys(), key=len, reverse=True):
        if not spoken.strip():
            continue
        pattern = re.compile(r"\b" + re.escape(spoken) + r"\b", re.IGNORECASE)
        text = pattern.sub(vocab[spoken], text)
    return text


# ── Layer B ───────────────────────────────────────────────────────────────

def _split_embedded_symbols(text: str) -> str:
    """Break tokens that embed a non-apostrophe symbol into single chars.

    Contractions matching `word'word` are never split, which keeps "don't"
    intact.
    """
    parts = []
    for token in text.split(" "):
        if _CONTRACTION_RE.match(token):
            parts.append(token)
        elif len(token) > 1 and _SPLIT_SYM_RE.search(token):
            parts.append(" ".join(token))
        else:
            parts.append(token)
    return " ".join(parts)


def _collapse_glueables(text: str) -> str:
    """Merge consecutive single-character or all-digit tokens.

    A gap between two space-separated tokens collapses when both tokens are
    "glueable" — length 1, or entirely digits. Multi-character words break
    the run. This is the single guard that fixes ``meter-was``,
    ``dollar+tax``, ``<happy`` while preserving ``WH/FIT`` and ``123/45``.
    """
    tokens = text.split(" ")
    result: list[str] = []
    buf: list[str] = []

    def _flush():
        if buf:
            result.append("".join(buf))
            buf.clear()

    for tok in tokens:
        if tok == "":
            _flush()
            result.append("")
        elif len(tok) == 1 or tok.isdigit():
            buf.append(tok)
        else:
            _flush()
            result.append(tok)
    _flush()
    return " ".join(result)


def apply_layer_b(text: str) -> str:
    """Symbol/number substitution + spelling collapse. Idempotent-ish."""
    for pattern, repl in _SUBS:
        text = pattern.sub(repl, text)
    text = _split_embedded_symbols(text)
    text = _collapse_glueables(text)
    return text


# ── Public API ────────────────────────────────────────────────────────────

def _load_vocab() -> dict[str, str]:
    try:
        return {spoken: written for spoken, written in db.list_vocabulary()}
    except Exception:
        return {}


def is_symbol_mode_enabled() -> bool:
    try:
        return db.get_setting("symbol_mode", "0") == "1"
    except Exception:
        return False


def apply_replacements(text: str) -> str:
    """Run the full pipeline: Layer A, then Layer B (if enabled)."""
    if not text:
        return text
    text = apply_layer_a(text, _load_vocab())
    if is_symbol_mode_enabled():
        text = apply_layer_b(text)
    return text.strip()


def get_initial_prompt() -> str | None:
    """Return priming terms joined for faster-whisper's initial_prompt, or None."""
    try:
        terms = db.list_priming_terms()
    except Exception:
        return None
    if not terms:
        return None
    return ", ".join(terms)
