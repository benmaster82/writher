"""Floating recording-indicator widget with Pandora Blackboard avatar.

Redesigned to match the JSX floating pill widget:
 - True pill/capsule shape (fully rounded ends)
 - Glassmorphic dark background with per-state border glow
 - Pandora Blackboard [ · · ] bot eyes with expression states
 - Status text labels ("Listening...", "Thinking...", etc.)
 - Minimal waveform bars (5 bars, listening/recording only)
 - Subtle outer glow matching state accent color
 - Smooth fade-in / fade-out transitions
 - Three modes: RECORDING, PROCESSING, ASSISTANT
 - Expression states: idle, listening, thinking, coding, happy,
   error, alert, surprised, wink, sleep, sad, love, loading
"""

import ctypes
import math
import threading
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageTk
from logger import log

# ── visual constants ──────────────────────────────────────────────────────
_CHROMAKEY = "#000001"

# Pandora Blackboard dark palette (matching JSX rgba(0,0,0,0.75))
_BG        = "#0c0c0f"      # near-black pill fill
_BG_INNER  = "#101016"      # subtle inner tone for avatar area
_BORDER    = "#1c1c26"      # default subtle border

# Widget dimensions — pill shape
_W, _H   = 220, 44
_RADIUS  = _H // 2          # full pill (borderRadius: height/2 in JSX)

# ── avatar / eye area ───────────────────────────────────────────────────
_AVA_CX     = 28             # center-x of eye area (left side of pill)
_AVA_CY     = _H // 2        # center-y
_EYE_SPREAD = 5.6            # half-distance between the two dots
_EYE_R      = 2.1            # base eye dot radius

# ── layout ────────────────────────────────────────────────────────────────
_SEP_X     = 48              # separator x after avatar
_TEXT_X    = _SEP_X + 10     # status text start x
_WAVE_X    = 0               # computed dynamically based on text

# Waveform (JSX-style: 5 thin bars, listening/recording only)
_BAR_W     = 2
_BAR_GAP   = 3
_N_BARS    = 5

# ── fade / animation constants ───────────────────────────────────────────
_ALPHA_MAX     = 0.95
_ALPHA_MIN     = 0.0
_FADE_STEPS    = 14
_FADE_INTERVAL = 18
_ANIM_FPS_MS   = 33          # ~30 fps

# ── JSX-matching accent colours per state ────────────────────────────────
# Format: accent_rgb, glow_rgba_str, border_rgb, border_opacity
_STATE_STYLE = {
    "idle":       {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.04, "label": ""},
    "listening":  {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Listening..."},
    "thinking":   {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Thinking..."},
    "coding":     {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Writing code..."},
    "happy":      {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Done!"},
    "error":      {"accent": (255, 68, 68),   "glow": (255, 68, 68),   "border": (255, 68, 68),   "border_a": 0.12, "label": "Error"},
    "alert":      {"accent": (255, 170, 0),   "glow": (255, 170, 0),   "border": (255, 170, 0),   "border_a": 0.12, "label": "Attention"},
    "surprised":  {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "!"},
    "wink":       {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Tip"},
    "sleep":      {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.04, "label": ""},
    "sad":        {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.06, "label": "Not found"},
    "love":       {"accent": (255, 107, 157), "glow": (255, 107, 157), "border": (255, 107, 157), "border_a": 0.12, "label": "Saved"},
    "loading":    {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Loading..."},
    # mode aliases
    "recording":  {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Listening..."},
    "processing": {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": "Thinking..."},
    "assistant":  {"accent": (255, 255, 255), "glow": (255, 255, 255), "border": (255, 255, 255), "border_a": 0.08, "label": ""},
}

# Eye theme per expression (eye_rgb, glow_rgb for the SVG-like dot rendering)
_EYE_THEME = {
    "idle":       {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "listening":  {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "thinking":   {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "coding":     {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "happy":      {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "error":      {"eye": (255, 68, 68),   "glow": (255, 68, 68)},
    "alert":      {"eye": (255, 170, 0),   "glow": (255, 170, 0)},
    "surprised":  {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "wink":       {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "sleep":      {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "sad":        {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "love":       {"eye": (255, 107, 157), "glow": (255, 107, 157)},
    "loading":    {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "recording":  {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "processing": {"eye": (255, 255, 255), "glow": (255, 255, 255)},
    "assistant":  {"eye": (255, 255, 255), "glow": (255, 255, 255)},
}

_IDLE_STYLE = _STATE_STYLE["idle"]
_IDLE_EYE   = _EYE_THEME["idle"]


# ── colour helpers ────────────────────────────────────────────────────────

def _hex_to_rgb(c: str) -> tuple:
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _lerp_rgb(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# ── Windows helpers ───────────────────────────────────────────────────────

def _no_activate(hwnd: int) -> None:
    try:
        GWL_EXSTYLE      = -20
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080
        s = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, s | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )
    except Exception:
        pass


# ── pill background renderer ─────────────────────────────────────────────

def _render_pill(w: int, h: int, radius: int,
                 fill_rgb: tuple, border_rgb: tuple, border_a: float,
                 glow_rgb: tuple, chromakey_rgb: tuple) -> Image.Image:
    """Render a JSX-style pill with border glow at high-res then downscale."""
    scale  = 4
    sw, sh = w * scale, h * scale
    sr     = radius * scale

    # Start with transparent
    pill = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pill)

    # Outer border
    border_alpha = max(1, int(255 * border_a))
    draw.rounded_rectangle(
        [0, 0, sw - 1, sh - 1], radius=sr,
        fill=border_rgb + (border_alpha,),
    )

    # Inner fill
    bw = max(scale, int(scale * 1.2))
    draw.rounded_rectangle(
        [bw, bw, sw - 1 - bw, sh - 1 - bw],
        radius=max(1, sr - bw),
        fill=fill_rgb + (255,),
    )

    # Subtle top-edge highlight (inset 0 1px 0 rgba(255,255,255,0.04))
    hi_rgb = (255, 255, 255)
    for yy in range(bw, bw + scale * 2):
        a = int(10 * (1.0 - (yy - bw) / (scale * 2)))
        if a <= 0:
            break
        draw.line([(sr, yy), (sw - sr, yy)], fill=hi_rgb + (a,))

    pill = pill.resize((w, h), Image.LANCZOS)

    # Convert to chromakey for transparent regions
    pixels = pill.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a >= 200:
                pixels[x, y] = (r, g, b, 255)
            else:
                pixels[x, y] = chromakey_rgb + (255,)

    return pill.convert("RGB")


class RecordingWidget:
    RECORDING  = "recording"
    PROCESSING = "processing"
    ASSISTANT  = "assistant"

    def __init__(self, root: tk.Tk):
        self._root       = root
        self._win        = None
        self._canvas     = None
        self._bar_ids    = []
        self._text_id    = None
        self._label_id   = None    # status label (JSX-style)
        self._sep_ids    = []      # separator lines
        self._after_anim = None
        self._after_fade = None
        self._after_msg  = None
        self._tick       = 0
        self._level      = 0.4
        self._level_lock = threading.Lock()
        self._bg_tk      = None
        self._mode       = None
        self._alpha      = _ALPHA_MIN
        self._fading     = None
        self._expression = "idle"
        # Avatar (PIL-rendered)
        self._ava_img_id = None
        self._ava_tk     = None
        # Cached pill backgrounds per state
        self._pill_cache = {}

    # ── public API ────────────────────────────────────────────────────────

    def show_recording(self):
        self._root.after(0, lambda: self._show(self.RECORDING))

    def show_processing(self):
        self._root.after(0, lambda: self._show(self.PROCESSING))

    def show_assistant(self):
        self._root.after(0, lambda: self._show(self.ASSISTANT))

    def show_message(self, text: str, duration_ms: int = 3000):
        self._root.after(0, lambda: self._show_msg(text, duration_ms))

    def hide(self):
        self._root.after(0, self._start_fade_out)

    def update_level(self, level: float):
        with self._level_lock:
            self._level = max(0.15, min(1.0, level))

    def set_expression(self, expr: str):
        """Set bot eye expression: idle, listening, thinking, coding, happy,
        error, alert, surprised, wink, sleep, sad, love, loading"""
        if expr in _STATE_STYLE:
            self._expression = expr

    # ── fade transitions ──────────────────────────────────────────────────

    def _set_alpha(self, alpha: float):
        self._alpha = max(_ALPHA_MIN, min(_ALPHA_MAX, alpha))
        if self._win:
            try:
                self._win.wm_attributes("-alpha", self._alpha)
            except Exception:
                pass

    def _start_fade_in(self):
        self._fading = "in"
        self._cancel_fade()
        self._fade_step()

    def _start_fade_out(self):
        if self._win is None or self._alpha <= _ALPHA_MIN:
            self._do_hide()
            return
        self._fading = "out"
        self._cancel_fade()
        self._fade_step()

    def _fade_step(self):
        step = _ALPHA_MAX / _FADE_STEPS
        if self._fading == "in":
            new_alpha = self._alpha + step
            if new_alpha >= _ALPHA_MAX:
                self._set_alpha(_ALPHA_MAX)
                self._fading = None
                return
            self._set_alpha(new_alpha)
        elif self._fading == "out":
            new_alpha = self._alpha - step
            if new_alpha <= _ALPHA_MIN:
                self._set_alpha(_ALPHA_MIN)
                self._fading = None
                self._do_hide()
                return
            self._set_alpha(new_alpha)
        else:
            return
        self._after_fade = self._root.after(_FADE_INTERVAL, self._fade_step)

    def _cancel_fade(self):
        if self._after_fade is not None:
            try:
                self._root.after_cancel(self._after_fade)
            except Exception:
                pass
            self._after_fade = None

    # ── show / hide internals ─────────────────────────────────────────────

    def _show(self, mode: str):
        needs_build = (self._win is None)
        if not needs_build:
            try:
                needs_build = not self._win.winfo_exists()
            except Exception:
                needs_build = True
        if needs_build:
            self._bar_ids = []
            self._build()

        if self._fading == "out":
            self._cancel_fade()
        if self._win:
            self._win.deiconify()

        self._mode = mode
        self._tick = 0

        # Auto-set expression based on mode
        if mode == self.RECORDING:
            self._expression = "listening"
        elif mode == self.PROCESSING:
            self._expression = "thinking"
        elif mode == self.ASSISTANT:
            self._expression = "listening"

        # Show waveform bars during recording and assistant (both record audio)
        show_bars = (mode in (self.RECORDING, self.ASSISTANT))
        for bid in self._bar_ids:
            self._canvas.itemconfig(bid, state="normal" if show_bars else "hidden")

        # Update label
        self._update_label()

        if self._text_id:
            self._canvas.itemconfig(self._text_id, state="hidden")

        if self._after_msg is not None:
            try:
                self._root.after_cancel(self._after_msg)
            except Exception:
                pass
            self._after_msg = None

        if self._alpha < _ALPHA_MAX:
            self._start_fade_in()
        if self._after_anim is None:
            self._animate()

    def _do_hide(self):
        self._mode = None
        self._expression = "idle"
        if self._after_anim is not None:
            try:
                self._root.after_cancel(self._after_anim)
            except Exception:
                pass
            self._after_anim = None
        if self._after_msg is not None:
            try:
                self._root.after_cancel(self._after_msg)
            except Exception:
                pass
            self._after_msg = None
        if self._win is not None:
            try:
                self._win.withdraw()
            except Exception:
                pass

    def _show_msg(self, text: str, duration_ms: int):
        needs_build = (self._win is None)
        if not needs_build:
            try:
                needs_build = not self._win.winfo_exists()
            except Exception:
                needs_build = True
        if needs_build:
            self._bar_ids = []
            self._build()

        if self._fading == "out":
            self._cancel_fade()
        if self._win:
            self._win.deiconify()

        for bid in self._bar_ids:
            self._canvas.itemconfig(bid, state="hidden")
        if self._label_id:
            self._canvas.itemconfig(self._label_id, state="hidden")
        if self._text_id:
            self._canvas.itemconfig(self._text_id, text=text, state="normal")

        self._mode = None
        if self._alpha < _ALPHA_MAX:
            self._start_fade_in()

        if self._after_msg is not None:
            try:
                self._root.after_cancel(self._after_msg)
            except Exception:
                pass
        self._after_msg = self._root.after(duration_ms, self._start_fade_out)

    # ── update status label ───────────────────────────────────────────────

    def _update_label(self):
        if self._label_id is None or self._canvas is None:
            return
        style = _STATE_STYLE.get(self._expression, _IDLE_STYLE)
        label = style["label"]
        accent = style["accent"]

        if label:
            # Opacity: sleep=0.3, normal=0.6 (matching JSX)
            opacity = 0.3 if self._expression == "sleep" else 0.6
            r = int(accent[0] * opacity)
            g = int(accent[1] * opacity)
            b = int(accent[2] * opacity)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self._canvas.itemconfig(self._label_id, text=label,
                                    fill=color, state="normal")
        else:
            self._canvas.itemconfig(self._label_id, text="", state="hidden")

    # ── update pill border per state ──────────────────────────────────────

    def _update_pill_bg(self):
        if self._canvas is None:
            return

        expr = self._expression
        style = _STATE_STYLE.get(expr, _IDLE_STYLE)

        cache_key = (expr, tuple(style["border"]), style["border_a"])
        if cache_key in self._pill_cache:
            self._bg_tk = self._pill_cache[cache_key]
        else:
            fill_rgb = _hex_to_rgb(_BG)
            ck_rgb   = _hex_to_rgb(_CHROMAKEY)
            pill = _render_pill(
                _W, _H, _RADIUS,
                fill_rgb=fill_rgb,
                border_rgb=style["border"],
                border_a=style["border_a"],
                glow_rgb=style["glow"],
                chromakey_rgb=ck_rgb,
            )
            self._bg_tk = ImageTk.PhotoImage(pill)
            self._pill_cache[cache_key] = self._bg_tk

        self._canvas.itemconfig(self._bg_img_id, image=self._bg_tk)

    # ── build ─────────────────────────────────────────────────────────────

    def _build(self):
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", _ALPHA_MIN)
        win.wm_attributes("-transparentcolor", _CHROMAKEY)
        win.configure(bg=_CHROMAKEY)
        self._alpha = _ALPHA_MIN

        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{_W}x{_H}+{(sw - _W) // 2}+{sh - _H - 52}")

        c = tk.Canvas(win, width=_W, height=_H, bg=_CHROMAKEY,
                      highlightthickness=0)
        c.pack()

        # ── Pill background ───────────────────────────────────────
        fill_rgb = _hex_to_rgb(_BG)
        ck_rgb   = _hex_to_rgb(_CHROMAKEY)
        style = _STATE_STYLE.get(self._expression, _IDLE_STYLE)
        bg_img = _render_pill(
            _W, _H, _RADIUS,
            fill_rgb=fill_rgb,
            border_rgb=style["border"],
            border_a=style["border_a"],
            glow_rgb=style["glow"],
            chromakey_rgb=ck_rgb,
        )
        self._bg_tk = ImageTk.PhotoImage(bg_img)
        self._bg_img_id = c.create_image(0, 0, image=self._bg_tk, anchor="nw")

        # ── Avatar eyes (PIL-rendered each frame) ─────────────────
        self._ava_img_id = c.create_image(
            _AVA_CX, _AVA_CY, image=None, anchor="center"
        )
        self._ava_tk = None

        # ── Separator (thin line, matching JSX divider) ───────────
        sep_top, sep_bot = 12, _H - 12
        sep = c.create_line(_SEP_X, sep_top, _SEP_X, sep_bot,
                            fill="#222230", width=1)
        self._sep_ids.append(sep)

        # ── Status label text (JSX-style) ─────────────────────────
        self._label_id = c.create_text(
            _TEXT_X, _H // 2,
            text="", fill="#666670",
            font=("Segoe UI", 10),
            anchor="w", state="hidden",
        )

        # ── Waveform bars (JSX-style: 5 bars, only during listening)
        wave_start_x = _TEXT_X + 90   # after status text
        mid_y = _H // 2
        for i in range(_N_BARS):
            cx = wave_start_x + i * (_BAR_W + _BAR_GAP) + _BAR_W // 2
            bid = c.create_line(
                cx, mid_y - 2, cx, mid_y + 2,
                fill="#ffffff", width=_BAR_W, capstyle=tk.ROUND,
            )
            self._bar_ids.append(bid)
            c.itemconfig(bid, state="hidden")

        # ── Feedback text (for show_message) ──────────────────────
        self._text_id = c.create_text(
            (_SEP_X + _W - 10) // 2, _H // 2,
            text="", fill="#c8c8d4",
            font=("Segoe UI", 10),
            anchor="center", state="hidden",
        )

        self._canvas = c
        self._win    = win
        win.after(30, lambda: _no_activate(win.winfo_id()))

    # ── avatar rendering: Pandora Blackboard eyes ────────────────────────

    def _update_avatar(self):
        """Render Pandora Blackboard [ · · ] bot eyes matching JSX SVG style.

        Uses gaussian blur glow filter like the JSX version.
        Each expression modifies how the two dots are drawn.
        """
        c = self._canvas
        if c is None:
            return

        t = self._tick
        expr = self._expression
        eye_theme = _EYE_THEME.get(expr, _IDLE_EYE)

        eye_rgb  = eye_theme["eye"]
        glow_rgb = eye_theme["glow"]

        # ── Render at high-res (matching JSX SVG approach) ────────
        sz = 28          # output size
        scale = 6
        s_sz     = sz * scale
        s_cx     = s_sz // 2
        s_cy     = s_sz // 2
        s_spread = _EYE_SPREAD * scale
        s_er     = _EYE_R * scale

        # Transparent background (no rounded rect — eyes float over pill)
        img  = Image.new("RGBA", (s_sz, s_sz), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        lx = s_cx - s_spread   # left eye x
        rx = s_cx + s_spread   # right eye x
        ey = s_cy              # eye y center

        # ── Draw expression ───────────────────────────────────────
        if expr in ("idle", "listening", "recording"):
            if expr in ("listening", "recording"):
                # JSX: pulsing r and opacity
                phase = (t * 0.1) % (2 * math.pi)
                pulse = 0.8 + 0.4 * abs(math.sin(phase))
            else:
                pulse = 1.0

            r = s_er * pulse
            # Glow (mimicking JSX feGaussianBlur)
            glow_img = Image.new("RGBA", (s_sz, s_sz), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            gr = r * 2.5
            glow_draw.ellipse([lx - gr, ey - gr, lx + gr, ey + gr],
                              fill=glow_rgb + (50,))
            glow_draw.ellipse([rx - gr, ey - gr, rx + gr, ey + gr],
                              fill=glow_rgb + (50,))
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=r * 1.2))
            img = Image.alpha_composite(img, glow_img)
            draw = ImageDraw.Draw(img)
            # Core dots
            draw.ellipse([lx - r, ey - r, lx + r, ey + r], fill=eye_rgb + (255,))
            draw.ellipse([rx - r, ey - r, rx + r, ey + r], fill=eye_rgb + (255,))

        elif expr in ("thinking", "processing"):
            # JSX: dots drift left/right (cx animates)
            drift = math.sin(t * 0.06) * s_spread * 0.3
            dlx = lx - drift
            drx = rx + drift
            r = s_er
            # Glow
            glow_img = Image.new("RGBA", (s_sz, s_sz), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            gr = r * 2.5
            glow_draw.ellipse([dlx - gr, ey - gr, dlx + gr, ey + gr],
                              fill=glow_rgb + (40,))
            glow_draw.ellipse([drx - gr, ey - gr, drx + gr, ey + gr],
                              fill=glow_rgb + (40,))
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=r * 1.2))
            img = Image.alpha_composite(img, glow_img)
            draw = ImageDraw.Draw(img)
            draw.ellipse([dlx - r, ey - r, dlx + r, ey + r], fill=eye_rgb + (155,))
            draw.ellipse([drx - r, ey - r, drx + r, ey + r], fill=eye_rgb + (155,))

        elif expr == "coding":
            # JSX: left steady, right blinks on/off
            r = s_er
            blink = 1.0 if (t % 15) < 10 else 0.3
            # Glow
            glow_img = Image.new("RGBA", (s_sz, s_sz), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            gr = r * 2.5
            glow_draw.ellipse([lx - gr, ey - gr, lx + gr, ey + gr],
                              fill=glow_rgb + (50,))
            glow_draw.ellipse([rx - gr, ey - gr, rx + gr, ey + gr],
                              fill=glow_rgb + (int(50 * blink),))
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=r * 1.2))
            img = Image.alpha_composite(img, glow_img)
            draw = ImageDraw.Draw(img)
            draw.ellipse([lx - r, ey - r, lx + r, ey + r], fill=eye_rgb + (255,))
            draw.ellipse([rx - r, ey - r, rx + r, ey + r],
                         fill=eye_rgb + (int(255 * blink),))

        elif expr == "happy":
            # JSX: arc curves (^ ^)
            line_w = max(2, int(scale * 0.6))
            for cx_pos in (lx, rx):
                span = s_er * 1.5
                pts = []
                for i in range(20):
                    frac = i / 19.0
                    px = cx_pos - span + 2 * span * frac
                    py = ey + s_er * 0.3 - abs(math.sin(math.pi * frac)) * s_er * 2
                    pts.append((px, py))
                for i in range(len(pts) - 1):
                    draw.line([pts[i], pts[i + 1]], fill=eye_rgb + (255,), width=line_w)

        elif expr == "error":
            # JSX: X X crosses
            line_w = max(2, int(scale * 0.55))
            cross_r = s_er
            for cx_pos in (lx, rx):
                draw.line([(cx_pos - cross_r, ey - cross_r),
                           (cx_pos + cross_r, ey + cross_r)],
                          fill=eye_rgb + (255,), width=line_w)
                draw.line([(cx_pos + cross_r, ey - cross_r),
                           (cx_pos - cross_r, ey + cross_r)],
                          fill=eye_rgb + (255,), width=line_w)

        elif expr == "alert":
            # JSX: ! ! exclamation marks, blinking
            blink = 0.3 + 0.7 * abs(math.sin(t * 0.2))
            a = int(255 * blink)
            line_w = max(2, int(scale * 0.55))
            for cx_pos in (lx, rx):
                draw.line([(cx_pos, ey - s_er * 1.2), (cx_pos, ey + s_er * 0.3)],
                          fill=eye_rgb + (a,), width=line_w)
                dot_r = s_er * 0.3
                dot_y = ey + s_er * 1.4
                draw.ellipse([cx_pos - dot_r, dot_y - dot_r,
                              cx_pos + dot_r, dot_y + dot_r],
                             fill=eye_rgb + (a,))

        elif expr == "surprised":
            # JSX: bigger dots (r * 1.6)
            r = s_er * 1.6
            glow_img = Image.new("RGBA", (s_sz, s_sz), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            gr = r * 2.5
            glow_draw.ellipse([lx - gr, ey - gr, lx + gr, ey + gr],
                              fill=glow_rgb + (50,))
            glow_draw.ellipse([rx - gr, ey - gr, rx + gr, ey + gr],
                              fill=glow_rgb + (50,))
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=r * 1.0))
            img = Image.alpha_composite(img, glow_img)
            draw = ImageDraw.Draw(img)
            draw.ellipse([lx - r, ey - r, lx + r, ey + r], fill=eye_rgb + (230,))
            draw.ellipse([rx - r, ey - r, rx + r, ey + r], fill=eye_rgb + (230,))

        elif expr == "wink":
            # JSX: left dot, right horizontal line
            r = s_er
            glow_img = Image.new("RGBA", (s_sz, s_sz), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            gr = r * 2.5
            glow_draw.ellipse([lx - gr, ey - gr, lx + gr, ey + gr],
                              fill=glow_rgb + (50,))
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=r * 1.2))
            img = Image.alpha_composite(img, glow_img)
            draw = ImageDraw.Draw(img)
            draw.ellipse([lx - r, ey - r, lx + r, ey + r], fill=eye_rgb + (255,))
            line_half = s_er * 1.2
            line_w = max(2, int(scale * 0.5))
            draw.line([(rx - line_half, ey), (rx + line_half, ey)],
                      fill=eye_rgb + (180,), width=line_w)

        elif expr == "sleep":
            # JSX: two dashes (— —), very dim
            line_w = max(2, int(scale * 0.45))
            line_half = s_er
            draw.line([(lx - line_half, ey), (lx + line_half, ey)],
                      fill=eye_rgb + (50,), width=line_w)
            draw.line([(rx - line_half, ey), (rx + line_half, ey)],
                      fill=eye_rgb + (50,), width=line_w)

        elif expr == "sad":
            # JSX: dots with tear lines
            r = s_er * 0.8
            draw.ellipse([lx - r, ey - r * 0.3 - r, lx + r, ey - r * 0.3 + r],
                         fill=eye_rgb + (100,))
            draw.ellipse([rx - r, ey - r * 0.3 - r, rx + r, ey - r * 0.3 + r],
                         fill=eye_rgb + (100,))
            # Tear lines
            tear_w = max(1, int(scale * 0.25))
            tear_len = s_er * 2.5
            draw.line([(lx, ey + r * 0.8), (lx, ey + r * 0.8 + tear_len)],
                      fill=eye_rgb + (50,), width=tear_w)
            draw.line([(rx, ey + r * 0.8), (rx, ey + r * 0.8 + tear_len)],
                      fill=eye_rgb + (50,), width=tear_w)

        elif expr == "love":
            # JSX: heart shapes, pulsing opacity
            pulse = 0.4 + 0.45 * abs(math.sin(t * 0.12))
            a = int(255 * (0.4 + 0.45 * abs(math.sin(t * 0.12))))
            hr = s_er * 1.1
            for cx_pos in (lx, rx):
                offset = hr * 0.5
                draw.ellipse([cx_pos - hr, ey - hr - offset,
                              cx_pos, ey - offset],
                             fill=eye_rgb + (a,))
                draw.ellipse([cx_pos, ey - hr - offset,
                              cx_pos + hr, ey - offset],
                             fill=eye_rgb + (a,))
                draw.polygon([
                    (cx_pos - hr, ey - offset * 0.5),
                    (cx_pos + hr, ey - offset * 0.5),
                    (cx_pos, ey + hr * 1.0)
                ], fill=eye_rgb + (a,))

        elif expr == "loading":
            # JSX: spinning arc segments
            angle = (t * 8) % 360
            line_w = max(2, int(scale * 0.7))
            arc_r = s_er * 1.3
            # Background circles
            draw.ellipse([lx - arc_r, ey - arc_r, lx + arc_r, ey + arc_r],
                         outline=eye_rgb + (30,), width=max(1, line_w // 2))
            draw.ellipse([rx - arc_r, ey - arc_r, rx + arc_r, ey + arc_r],
                         outline=eye_rgb + (30,), width=max(1, line_w // 2))
            # Spinning arcs
            draw.arc([lx - arc_r, ey - arc_r, lx + arc_r, ey + arc_r],
                     start=angle, end=angle + 90,
                     fill=eye_rgb + (155,), width=line_w)
            draw.arc([rx - arc_r, ey - arc_r, rx + arc_r, ey + arc_r],
                     start=angle, end=angle + 90,
                     fill=eye_rgb + (155,), width=line_w)

        elif expr == "assistant":
            # Warm pulsing dots
            with self._level_lock:
                level = self._level
            pulse = 0.8 + 0.35 * level + 0.15 * math.sin(t * 0.1)
            r = s_er * pulse
            glow_img = Image.new("RGBA", (s_sz, s_sz), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            gr = r * 2.5
            glow_draw.ellipse([lx - gr, ey - gr, lx + gr, ey + gr],
                              fill=glow_rgb + (45,))
            glow_draw.ellipse([rx - gr, ey - gr, rx + gr, ey + gr],
                              fill=glow_rgb + (45,))
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=r * 1.2))
            img = Image.alpha_composite(img, glow_img)
            draw = ImageDraw.Draw(img)
            draw.ellipse([lx - r, ey - r, lx + r, ey + r], fill=eye_rgb + (255,))
            draw.ellipse([rx - r, ey - r, rx + r, ey + r], fill=eye_rgb + (255,))

        # ── Downscale ─────────────────────────────────────────────
        img = img.resize((sz, sz), Image.LANCZOS)

        self._ava_tk = ImageTk.PhotoImage(img)
        c.itemconfig(self._ava_img_id, image=self._ava_tk)

    # ── animation loop ────────────────────────────────────────────────────

    def _animate(self):
        if self._mode is None or self._canvas is None:
            self._after_anim = None
            return

        self._tick += 1
        mid_y = _H // 2

        # Update avatar expression
        self._update_avatar()

        # Update pill border color per state
        self._update_pill_bg()

        # Update label
        self._update_label()

        # Waveform bars (recording + assistant both show animated bars)
        if self._mode in (self.RECORDING, self.ASSISTANT):
            with self._level_lock:
                level = self._level
            max_amp = (_H - 16) / 2
            wave_start_x = _TEXT_X + 90
            t = self._tick * 0.12
            for i, bid in enumerate(self._bar_ids):
                phase = t + i * 0.25
                val = (math.sin(phase) + 1) / 2
                amp = 2 + val * max_amp * 0.6 * level
                cx = wave_start_x + i * (_BAR_W + _BAR_GAP) + _BAR_W // 2
                self._canvas.coords(bid, cx, mid_y - amp, cx, mid_y + amp)
                opacity = 0.25 + 0.35 * val
                c_val = int(255 * opacity)
                self._canvas.itemconfig(bid, fill=f"#{c_val:02x}{c_val:02x}{c_val:02x}",
                                        state="normal")

        elif self._mode == self.PROCESSING:
            for bid in self._bar_ids:
                self._canvas.itemconfig(bid, state="hidden")

        self._after_anim = self._canvas.after(_ANIM_FPS_MS, self._animate)
