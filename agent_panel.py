"""Expanded 'agent' panel for WritHer — the rich voice-delete confirmation.

A dedicated floating window (borderless, topmost) that shows the confirm card
from the design prototype: a dark rounded panel with an amber gradient border
+ soft glow, white Pandora eyes, the prompt, and a live countdown ring. It is
kept fully separate from the pill widget (widget.py) so the pill is untouched.

Everything is rendered with Pillow. Transparency uses a magenta chromakey
(#ff00ff) — a colour the design can never produce, so the soft glow never
leaves stray transparent pixels (the near-black key #000001 did).

Public API (thread-safe — calls are marshalled onto the Tk main thread):
    panel = AgentPanel(root)
    panel.show_confirm(prompt, seconds, on_timeout=cb)
    panel.hide()
"""

import ctypes
import math
import time
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

# ── constants ─────────────────────────────────────────────────────────────
S = 2                       # supersample for crisp borders/text
CHROMA = (255, 0, 255)
CHROMA_HEX = "#ff00ff"

BLACK = (0, 0, 0); WHITE = (255, 255, 255)
FG = (242, 242, 247); DIM = (139, 139, 156); FAINT = (86, 86, 103)
LINE = (32, 32, 42); AMBER = (255, 176, 32)

PW, PH = 400, 140           # panel size (final px)
RAD = 22


# ── Win32: don't steal focus (same trick as widget.py) ────────────────────
def _no_activate(hwnd: int) -> None:
    try:
        GWL_EXSTYLE = -20
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080
        s = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, s | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    except Exception:
        pass


# ── fonts (Segoe UI + Consolas), rendered at supersample size ─────────────
_FONTS = {}
def _font(pt, bold=False, mono=False):
    key = (pt, bold, mono)
    if key in _FONTS:
        return _FONTS[key]
    path = ("C:/Windows/Fonts/consolab.ttf" if (mono and bold) else
            "C:/Windows/Fonts/consola.ttf" if mono else
            "C:/Windows/Fonts/segoeuib.ttf" if bold else
            "C:/Windows/Fonts/segoeui.ttf")
    try:
        f = ImageFont.truetype(path, int(pt * S))
    except Exception:
        f = ImageFont.load_default()
    _FONTS[key] = f
    return f


def _text(d, xy, s, f, fill, anchor="la"):
    d.text((xy[0] * S, xy[1] * S), s, font=f, fill=fill, anchor=anchor)

def _tw(d, s, f):
    return d.textlength(s, font=f) / S

def _wrap(d, s, f, maxw):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if _tw(d, t, f) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _grad(w, h, c0, c1):
    base = Image.new("RGB", (w, 1)); px = base.load()
    for x in range(w):
        t = x / max(1, w - 1)
        px[x, 0] = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    return base.resize((w, h))


# ── cached pieces (built once) ────────────────────────────────────────────
_GLOW = None
def _glow():
    global _GLOW
    if _GLOW is None:
        n = 64
        a = Image.new("L", (n, n), 0)
        ImageDraw.Draw(a).ellipse([n * 0.32, n * 0.32, n * 0.68, n * 0.68], fill=255)
        a = a.filter(ImageFilter.GaussianBlur(n * 0.12))
        g = Image.new("RGBA", (n, n), (255, 255, 255, 0))
        g.putalpha(a.point(lambda v: int(v * 0.72)))
        _GLOW = g
    return _GLOW


_BORDER = None
def _border_img():
    """Panel base: black fill + amber gradient border with soft inner glow."""
    global _BORDER
    if _BORDER is not None:
        return _BORDER
    W, H = PW * S, PH * S
    img = Image.new("RGB", (W, H), BLACK)
    ring = Image.new("L", (W, H), 0)
    rd = ImageDraw.Draw(ring)
    bw = max(2, int(1.7 * S))
    rd.rounded_rectangle([0, 0, W - 1, H - 1], radius=RAD * S, fill=255)
    rd.rounded_rectangle([bw, bw, W - 1 - bw, H - 1 - bw],
                         radius=max(1, RAD * S - bw), fill=0)
    grad = _grad(W, H, AMBER, (255, 138, 61))
    img.paste(grad, (0, 0),
              ring.filter(ImageFilter.GaussianBlur(int(3.5 * S))).point(lambda a: int(a * 0.55)))
    img.paste(grad, (0, 0), ring)
    _BORDER = img
    return img


_MASK = None
def _mask():
    global _MASK
    if _MASK is None:
        m = Image.new("L", (PW, PH), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, PW - 1, PH - 1], radius=RAD, fill=255)
        _MASK = m.point(lambda a: 255 if a >= 128 else 0)
    return _MASK


def _eyes(img, cx, cy, tick):
    cx, cy = cx * S, cy * S
    spread = 13 * S
    r = 6.5 * S * (0.9 + 0.12 * math.sin(tick * 0.16))
    lx, rx = cx - spread, cx + spread
    gsz = max(2, int(r * 6.2))
    gg = _glow().resize((gsz, gsz))
    for ex in (lx, rx):
        img.paste(gg, (int(ex - gsz / 2), int(cy - gsz / 2)), gg)
    d = ImageDraw.Draw(img)
    for ex in (lx, rx):
        d.ellipse([ex - r, cy - r, ex + r, cy + r], fill=WHITE)


def render_confirm(prompt, remaining, total, tick, hint="di' «sì» o «no»"):
    """Compose the confirm panel (magenta corners → transparent)."""
    img = _border_img().copy()
    _eyes(img, 42, 34, tick)
    d = ImageDraw.Draw(img)
    d.line([90 * S, 18 * S, 90 * S, 50 * S], fill=LINE, width=int(1 * S))
    _text(d, (106, 25), "Assistente", _font(16.5, bold=True), FG)
    tw = _tw(d, "Assistente", _font(16.5, bold=True))
    _text(d, (106 + tw + 9, 27), "· confermi?", _font(13, mono=True), FAINT)

    y = 66
    for ln in _wrap(d, prompt, _font(16, bold=True), PW - 44):
        _text(d, (22, y), ln, _font(16, bold=True), FG); y += 25

    ry = PH - 30
    cx, cy, rr = 34, ry, 13
    d.ellipse([(cx - rr) * S, (cy - rr) * S, (cx + rr) * S, (cy + rr) * S], fill=(24, 24, 30))
    frac = max(0.0, remaining / total) if total else 0.0
    d.arc([(cx - rr) * S, (cy - rr) * S, (cx + rr) * S, (cy + rr) * S],
          -90, -90 + 360 * frac, fill=AMBER, width=int(2.5 * S))
    _text(d, (cx, cy), str(int(math.ceil(max(0, remaining)))),
          _font(10.5, mono=True), DIM, anchor="mm")
    _text(d, (58, ry - 8), hint, _font(12.5), DIM)

    final = img.resize((PW, PH), Image.LANCZOS)
    frame = Image.new("RGB", (PW, PH), CHROMA)
    frame.paste(final, (0, 0), _mask())
    return frame


class AgentPanel:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=CHROMA_HEX)
        self.win.wm_attributes("-transparentcolor", CHROMA_HEX)
        sw = self.win.winfo_screenwidth(); sh = self.win.winfo_screenheight()
        x = (sw - PW) // 2; y = sh - PH - 90
        self.win.geometry("%dx%d+%d+%d" % (PW, PH, x, y))
        self.canvas = tk.Canvas(self.win, width=PW, height=PH,
                                highlightthickness=0, bg=CHROMA_HEX, bd=0)
        self.canvas.pack()
        self._imgid = self.canvas.create_image(0, 0, anchor="nw")
        self._imgtk = None
        self.win.withdraw()

        self._visible = False
        self._tick = 0
        self._prompt = ""
        self._hint = "di' «sì» o «no»"
        self._until = 0.0
        self._total = 1.0
        self._on_timeout = None
        self._fired = False
        self._after = None
        self.win.after(60, lambda: _no_activate(self.win.winfo_id()))

    # ── public (thread-safe) ──────────────────────────────────────────────
    def show_confirm(self, prompt: str, seconds: float, on_timeout=None, hint=None):
        self.root.after(0, lambda: self._show(prompt, seconds, on_timeout, hint))

    def hide(self):
        self.root.after(0, self._hide)

    # ── internals (Tk thread) ─────────────────────────────────────────────
    def _show(self, prompt, seconds, on_timeout, hint=None):
        self._prompt = prompt
        if hint:
            self._hint = hint
        self._total = max(0.1, float(seconds))
        self._until = time.monotonic() + seconds
        self._on_timeout = on_timeout
        self._fired = False
        self._tick = 0
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        if not self._visible:
            self._visible = True
            if self._after is None:
                self._loop()

    def _loop(self):
        if not self._visible or not self.win.winfo_exists():
            self._after = None
            return
        self._tick += 1
        remaining = self._until - time.monotonic()
        if remaining <= 0:
            remaining = 0
            if not self._fired:
                self._fired = True
                cb = self._on_timeout
                if cb:
                    try:
                        cb()
                    except Exception:
                        pass
        try:
            img = render_confirm(self._prompt, remaining, self._total,
                                 self._tick, self._hint)
            self._imgtk = ImageTk.PhotoImage(img)
            self.canvas.itemconfig(self._imgid, image=self._imgtk)
        except Exception:
            pass
        self._after = self.root.after(33, self._loop)

    def _hide(self):
        self._visible = False
        if self._after is not None:
            try:
                self.root.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        try:
            self.win.withdraw()
        except Exception:
            pass
