"""WritHer — prototipo NATIVO del widget agentico (tkinter + Pillow).

Stessa architettura di widget.py: Toplevel borderless topmost + tk.Canvas +
immagini renderizzate in PIL. Total black, occhi bianchi, bordo a gradiente.
Angoli arrotondati "veri" via region Win32 (niente chromakey → niente frangia).

Il widget parte come pill compatta (occhi + waveform) e — in modalità agentica —
si allarga mostrando: cosa ha capito, gli step live, la barra di progresso, una
CONFERMA inline (Consenti / Annulla, con countdown) e l'esito finale.

Uso:
    python widget_proto.py            # avvia il widget sul desktop
    python widget_proto.py --dump     # salva PNG delle fasi (per revisione)

Comandi a runtime:  SPAZIO = ripeti · ESC = esci · click su Consenti/Annulla
"""

import sys
import math
import ctypes
import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk

# ── DPI aware (come main.py) ──────────────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

S = 2  # 2× per bordi/testo curati; il costo è contenuto (bordo in cache)

# ── palette (total black + bianco, gradiente solo sul contorno) ───────────
BLACK      = (0, 0, 0)
WHITE      = (255, 255, 255)
FG         = (242, 242, 247)
DIM        = (139, 139, 156)
FAINT      = (86, 86, 103)
LINE       = (32, 32, 42)
CYAN       = (56, 189, 248)
VIOLET     = (167, 139, 250)
AMBER      = (255, 176, 32)
RED        = (255, 93, 93)

# chromakey per la trasparenza: DEVE essere un colore che il design non può
# produrre. #000001 era troppo vicino al nero → il glow/anti-alias generava
# pixel (0,0,1) che venivano bucati (le "linee" trasparenti). Magenta è sicuro.
CHROMA     = (255, 0, 255)
CHROMA_HEX = "#ff00ff"
# la finestra è FISSA a questa dimensione: si anima solo il contenuto dentro,
# così tkinter non deve ridimensionare la finestra ogni frame (era lo scatto).
MAXW, MAXH = 480, 280

# ── font (Segoe UI + Consolas), caricati a risoluzione supersample ────────
_FONTS = {}
def font(pt, bold=False, mono=False):
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


# ── helper di disegno (coordinate in px finali, moltiplicate per S) ───────
def _round(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([box[0]*S, box[1]*S, box[2]*S, box[3]*S],
                        radius=r*S, fill=fill, outline=outline,
                        width=int(width*S))

def _text(d, xy, s, f, fill, anchor="la"):
    d.text((xy[0]*S, xy[1]*S), s, font=f, fill=fill, anchor=anchor)

def _check(d, cx, cy, r, color, wdt=1.7):
    """Spunta disegnata a vettore (PIL+Segoe non ha il glyph ✓)."""
    cx, cy, r = cx*S, cy*S, r*S
    d.line([(cx-0.42*r, cy+0.02*r), (cx-0.08*r, cy+0.34*r),
            (cx+0.46*r, cy-0.38*r)], fill=color, width=int(wdt*S), joint="curve")

def _cross(d, cx, cy, r, color, wdt=1.7):
    cx, cy, r = cx*S, cy*S, r*S
    d.line([(cx-0.4*r, cy-0.4*r), (cx+0.4*r, cy+0.4*r)], fill=color, width=int(wdt*S))
    d.line([(cx+0.4*r, cy-0.4*r), (cx-0.4*r, cy+0.4*r)], fill=color, width=int(wdt*S))

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


def _gradient(w, h, c0, c1):
    """Gradiente orizzontale c0→c1 come immagine RGB (w,h) in px supersample."""
    base = Image.new("RGB", (w, 1))
    px = base.load()
    for x in range(w):
        t = x / max(1, w - 1)
        px[x, 0] = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    return base.resize((w, h))


_GLOW = None
def _glow():
    """Sprite di glow MORBIDO (GaussianBlur), calcolato UNA sola volta."""
    global _GLOW
    if _GLOW is None:
        n = 64
        a = Image.new("L", (n, n), 0)
        ImageDraw.Draw(a).ellipse([n*0.32, n*0.32, n*0.68, n*0.68], fill=255)
        a = a.filter(ImageFilter.GaussianBlur(n * 0.12))
        g = Image.new("RGBA", (n, n), (255, 255, 255, 0))
        g.putalpha(a.point(lambda v: int(v * 0.72)))
        _GLOW = g
    return _GLOW


def _eyes(img, cx, cy, state, tick):
    """Occhi Pandora BIANCHI con glow, disegnati su img (coord finali)."""
    cx, cy = cx * S, cy * S
    spread, r = 13 * S, 6.5 * S
    if state == "listening":
        r *= 0.85 + 0.35 * abs(math.sin(tick * 0.18))
    elif state == "executing":
        r *= 0.85 + 0.3 * abs(math.sin(tick * 0.4))
    dx = 0
    if state == "thinking":
        dx = math.sin(tick * 0.12) * 3 * S
    lx, rx = cx - spread - dx, cx + spread + dx

    # glow via sprite morbido precalcolato (economico)
    gsz = max(2, int(r * 6.2))
    gg = _glow().resize((gsz, gsz))
    for ex in (lx, rx):
        img.paste(gg, (int(ex - gsz / 2), int(cy - gsz / 2)), gg)

    d = ImageDraw.Draw(img)
    if state == "happy":                     # occhi ad arco (^ ^)
        for ex in (lx, rx):
            d.rounded_rectangle([ex - r, cy - r*0.55, ex + r, cy + r*0.15],
                                radius=r*0.5, fill=WHITE)
    elif state == "awaiting":                # blink lento
        a = 255 if (tick // 8) % 2 == 0 else 70
        col = (255, 255, 255) if a == 255 else (120, 120, 120)
        for ex in (lx, rx):
            d.ellipse([ex - r, cy - r, ex + r, cy + r], fill=col)
    else:
        for ex in (lx, rx):
            d.ellipse([ex - r, cy - r, ex + r, cy + r], fill=WHITE)


# ── stato/altezza per fase ────────────────────────────────────────────────
CMD = "«prepara la mail per il dentista e fissa l'appuntamento giovedì alle 15»"
STEPS = [
    ("Scrivo la bozza (tono formale)", "compose_text"),
    ("Inserisco il testo nel documento attivo", "type_text"),
    ("Creo l'appuntamento giovedì 15:00", "create_appointment"),
]

def panel_size(phase):
    if phase == "idle":     return 156, 64
    if phase == "heard":    return 420, 118
    if phase == "working":  return 420, 232
    if phase == "confirm":  return 420, 198
    if phase in ("done", "cancelled"): return 420, 116
    return 156, 64


# button hitboxes (coord finali px, riempite in render confirm)
BTN = {}

# bordo (gradiente + soft glow) in CACHE per fase: niente blur ogni frame
_BORDERS = {}
def _bordered(phase):
    w, h = panel_size(phase)
    key = (phase if phase in ("confirm", "cancelled") else "n", w, h)
    b = _BORDERS.get(key)
    if b is not None:
        return b
    W, H = w * S, h * S
    img = Image.new("RGB", (W, H), BLACK)
    if phase == "confirm":     c0, c1 = AMBER, (255, 138, 61)
    elif phase == "cancelled": c0, c1 = RED, (255, 138, 138)
    else:                      c0, c1 = CYAN, VIOLET
    rad = 30 if phase == "idle" else 22
    ring = Image.new("L", (W, H), 0)
    rd = ImageDraw.Draw(ring)
    bw = max(2, int(1.7 * S))
    rd.rounded_rectangle([0, 0, W - 1, H - 1], radius=rad * S, fill=255)
    rd.rounded_rectangle([bw, bw, W - 1 - bw, H - 1 - bw],
                         radius=max(1, rad * S - bw), fill=0)
    grad = _gradient(W, H, c0, c1)
    # soft glow del contorno (verso l'interno), poi bordo netto sopra
    img.paste(grad, (0, 0),
              ring.filter(ImageFilter.GaussianBlur(int(3.5 * S))).point(lambda a: int(a * 0.55)))
    img.paste(grad, (0, 0), ring)
    _BORDERS[key] = img
    return img


def render(phase, st, tick):
    """Immagine RGB (supersample) del widget nella data fase."""
    w, h = panel_size(phase)
    img = _bordered(phase).copy()
    d = ImageDraw.Draw(img)

    # ── IDLE: occhi + waveform ──
    if phase == "idle":
        _eyes(img, 42, h // 2, "idle", tick)
        d = ImageDraw.Draw(img)
        bx, by = 80, h // 2
        for i in range(5):
            amp = 4 + (math.sin(tick * 0.12 + i * 0.5) + 1) * 6
            x = bx + i * 7
            d.rounded_rectangle([x*S, (by-amp)*S, (x+3)*S, (by+amp)*S],
                                radius=1.5*S, fill=(234, 234, 240))
        return img

    # ── HEADER (occhi + titolo) ──
    _eyes(img, 42, 32, st.get("eye", "thinking"), tick)
    d = ImageDraw.Draw(img)
    d.line([90*S, 16*S, 90*S, 48*S], fill=LINE, width=int(1*S))
    _text(d, (106, 23), "Assistente", font(16.5, bold=True), FG)
    twid = _tw(d, "Assistente", font(16.5, bold=True))
    _text(d, (106 + twid + 9, 25), st.get("sub", ""), font(13, mono=True), FAINT)

    if phase == "heard":
        y = 64
        for ln in _wrap(d, CMD, font(15, bold=True), w - 44):
            _text(d, (22, y), ln, font(15, bold=True), FG); y += 24
        return img

    if phase == "working":
        y = 64
        for ln in _wrap(d, CMD, font(14), w - 44):
            _text(d, (22, y), ln, font(14), DIM); y += 22
        y += 5
        d.line([22*S, y*S, (w-22)*S, y*S], fill=LINE, width=int(1*S)); y += 9
        for i, (label, tool) in enumerate(STEPS):
            state = st["steps"][i]
            mx, my = 34, y + 12
            if state == "done":
                d.ellipse([(mx-10)*S,(my-10)*S,(mx+10)*S,(my+10)*S], fill=WHITE)
                _check(d, mx, my, 10, BLACK)
                col = FG
            elif state == "run":
                d.rounded_rectangle([22*S, y*S, (w-22)*S, (y+24)*S], radius=8*S, fill=(20,20,26))
                a0 = (tick * 9) % 360
                d.arc([(mx-10)*S,(my-10)*S,(mx+10)*S,(my+10)*S], a0, a0+270, fill=WHITE, width=int(2*S))
                col = FG
            else:
                d.ellipse([(mx-10)*S,(my-10)*S,(mx+10)*S,(my+10)*S], outline=(70,70,84), width=int(1.5*S))
                _text(d, (mx, my), str(i+1), font(12), FAINT, anchor="mm")
                col = DIM
            _text(d, (54, y+4), label, font(15), col)
            y += 27
        pct = st.get("pct", 0)
        by = y + 9
        d.rounded_rectangle([22*S, by*S, (w-132)*S, (by+6)*S], radius=3*S, fill=(20,20,26))
        fillw = 22 + (w-154-22) * pct/100
        if pct > 0:
            d.rounded_rectangle([22*S, by*S, fillw*S, (by+6)*S], radius=3*S, fill=(242,242,247))
        _text(d, (w-22, by-5), st.get("tool", ""), font(12.5, mono=True), DIM, anchor="ra")
        return img

    if phase == "confirm":
        y = 66
        for ln in _wrap(d, "Inserisco il testo nel documento attivo?", font(16.5, bold=True), w-44):
            _text(d, (22, y), ln, font(16.5, bold=True), FG); y += 25
        y += 6
        _round(d, (22, y, w-22, y+34), 8, fill=(12,12,14), outline=LINE, width=1)
        _text(d, (32, y+9), "type_text", font(12.5, mono=True, bold=True), AMBER)
        tl = _tw(d, "type_text", font(12.5, mono=True, bold=True))
        _text(d, (32+tl, y+9), " · 128 caratteri → Blocco note", font(12.5, mono=True), DIM)
        y += 50
        sec = st.get("sec", 12)
        cx, cy, rr = 34, y+11, 12
        d.ellipse([(cx-rr)*S,(cy-rr)*S,(cx+rr)*S,(cy+rr)*S], fill=(24,24,30))
        d.arc([(cx-rr)*S,(cy-rr)*S,(cx+rr)*S,(cy+rr)*S], -90, -90+360*(sec/12.0), fill=AMBER, width=int(2.5*S))
        _text(d, (cx, cy), str(int(math.ceil(sec))), font(10.5, mono=True), DIM, anchor="mm")
        _text(d, (56, y+3), "di' «sì»", font(13.5), DIM)
        BTN.clear()
        yb, hb = y-4, 33
        x1 = w-22-100; x2 = w-22-100-11-86
        _round(d, (x2, yb, x2+86, yb+hb), 8, outline=(43,43,58), width=1.4)
        _text(d, (x2+43, yb+hb/2), "Annulla", font(14.5, bold=True), FG, anchor="mm")
        BTN["no"] = (x2, yb, x2+86, yb+hb)
        _round(d, (x1, yb, x1+100, yb+hb), 8, fill=WHITE)
        _text(d, (x1+50, yb+hb/2), "Consenti", font(14.5, bold=True), BLACK, anchor="mm")
        BTN["yes"] = (x1, yb, x1+100, yb+hb)
        return img

    if phase == "done":
        cy = h//2
        d.ellipse([22*S,(cy-12)*S,46*S,(cy+12)*S], fill=WHITE)
        _check(d, 34, cy, 12, BLACK, wdt=2.2)
        _text(d, (58, cy-15), "Mail inserita · appuntamento fissato", font(16, bold=True), FG)
        _text(d, (58, cy+7), "giovedì 15:00 · promemoria -15 min", font(12.5, mono=True), FAINT)
        return img

    if phase == "cancelled":
        cy = h//2
        _round(d, (22, cy-12, 46, cy+12), 12, outline=(74,34,34), width=1.4)
        _cross(d, 34, cy, 12, RED, wdt=2.2)
        _text(d, (58, cy-9), "Operazione annullata — nulla è stato modificato", font(14.5), FG)
        return img

    return img


def render_final(phase, st, tick):
    w, h = panel_size(phase)
    return render(phase, st, tick).resize((w, h), Image.LANCZOS)


_MASKS = {}
def _rmask(w, h, rad):
    """Maschera arrotondata a bordo NETTO, in cache (chiamata ogni frame)."""
    key = (w, h, rad)
    m = _MASKS.get(key)
    if m is None:
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=rad, fill=255)
        m = m.point(lambda a: 255 if a >= 128 else 0)
        _MASKS[key] = m
    return m


# ── modalità --dump: salva PNG delle fasi per revisione ───────────────────
def dump():
    frames = {
        "idle":    ("idle", {}, 6),
        "working": ("working", {"steps": ["done","run","pending"], "pct": 52,
                                 "tool": "type_text", "eye": "executing",
                                 "sub": "· sto lavorando"}, 8),
        "confirm": ("confirm", {"sec": 9, "eye": "awaiting", "sub": "· confermi?"}, 4),
        "done":    ("done", {"eye": "happy", "sub": "· fatto"}, 2),
    }
    for name, (ph, st, tk_) in frames.items():
        img = render_final(ph, st, tk_)
        canvas = Image.new("RGB", (img.width + 80, img.height + 80), (0, 0, 0))
        canvas.paste(img, (40, 40))
        canvas.save(f"proto_{name}.png")
        print("scritto proto_%s.png (%dx%d)" % (name, img.width, img.height))


# ── app tkinter ───────────────────────────────────────────────────────────
class Widget:
    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=CHROMA_HEX)
        self.win.wm_attributes("-transparentcolor", CHROMA_HEX)
        sw = self.win.winfo_screenwidth(); sh = self.win.winfo_screenheight()
        x = (sw - MAXW) // 2; y = sh - MAXH - 70
        self.win.geometry("%dx%d+%d+%d" % (MAXW, MAXH, x, y))
        self.canvas = tk.Canvas(self.win, width=MAXW, height=MAXH,
                                highlightthickness=0, bg=CHROMA_HEX, bd=0)
        self.canvas.pack()
        self.imgtk = None
        self.imgid = self.canvas.create_image(0, 0, anchor="nw")
        self.tick = 0
        self.phase = "idle"
        self.cur_w, self.cur_h = map(float, panel_size("idle"))
        self.tgt_w, self.tgt_h = self.cur_w, self.cur_h
        self.st = {}
        self.pending = None
        self.script = self._make_script()
        self.canvas.bind("<Button-1>", self._click)
        self.win.bind("<space>", lambda e: self._restart())
        self.win.bind("<Escape>", lambda e: root.destroy())
        self.win.focus_force()
        self._tick()
        self.root.after(700, self._advance)

    # loop ~30fps: la FINESTRA non cambia mai — si anima il contenuto dentro
    def _tick(self):
        self.tick += 1
        for attr, tgt in (("cur_w", self.tgt_w), ("cur_h", self.tgt_h)):
            cur = getattr(self, attr)
            if abs(cur - tgt) > 0.5:
                cur += (tgt - cur) * 0.4           # easing più deciso
            else:
                cur = tgt
            setattr(self, attr, cur)
        cw, ch = max(1, int(round(self.cur_w))), max(1, int(round(self.cur_h)))

        panel = render_final(self.phase, self.st, self.tick)
        if (panel.width, panel.height) != (cw, ch):
            panel = panel.resize((cw, ch))          # morph dolce, no resize finestra
        rad = 30 if self.phase == "idle" else 22
        frame = Image.new("RGB", (MAXW, MAXH), CHROMA)
        frame.paste(panel, ((MAXW - cw) // 2, MAXH - ch), _rmask(cw, ch, rad))
        self.imgtk = ImageTk.PhotoImage(frame)
        self.canvas.itemconfig(self.imgid, image=self.imgtk)
        self.root.after(16, self._tick)          # ~60fps (frame ora leggero)

    def _set(self, phase, st):
        self.phase = phase; self.st = st
        self.tgt_w, self.tgt_h = map(float, panel_size(phase))

    # sceneggiatura come lista di (attesa_ms, funzione)
    def _make_script(self):
        S = self
        return [
            (700,  lambda: S._set("heard", {"eye":"listening","sub":"· ho sentito"})),
            (1300, lambda: S._set("working", {"steps":["run","pending","pending"],
                     "pct":12,"tool":"compose_text","eye":"thinking","sub":"· sto lavorando"})),
            (1200, lambda: S._set("working", {"steps":["done","run","pending"],
                     "pct":45,"tool":"type_text","eye":"executing","sub":"· sto lavorando"})),
            (900,  lambda: S._confirm()),
        ]

    def _advance(self, i=0):
        if i >= len(self.script):
            return
        delay, fn = self.script[i]
        fn()
        self.pending = self.root.after(delay, lambda: self._advance(i+1))

    def _confirm(self):
        self._set("confirm", {"sec":12,"eye":"awaiting","sub":"· confermi?"})
        self._count(12)

    def _count(self, sec):
        self.st["sec"] = sec
        if self.phase != "confirm":
            return
        if sec <= 0:
            self._resolve(False); return
        self.pending = self.root.after(100, lambda: self._count(sec-0.1))

    def _click(self, e):
        if self.phase != "confirm":
            return
        cw, ch = int(round(self.cur_w)), int(round(self.cur_h))
        ox, oy = (MAXW - cw) // 2, MAXH - ch          # offset del pannello
        px, py = e.x - ox, e.y - oy
        for k, (x0,y0,x1,y1) in BTN.items():
            if x0 <= px <= x1 and y0 <= py <= y1:
                self._resolve(k == "yes"); return

    def _resolve(self, ok):
        if self.pending:
            self.root.after_cancel(self.pending); self.pending = None
        if not ok:
            self._set("cancelled", {"eye":"error","sub":"· annullato"})
            self.root.after(2200, self._collapse); return
        self._set("working", {"steps":["done","done","run"],"pct":80,
                              "tool":"create_appointment","eye":"executing","sub":"· sto lavorando"})
        self.root.after(1300, lambda: self._set("working",
            {"steps":["done","done","done"],"pct":100,"tool":"fatto",
             "eye":"executing","sub":"· sto lavorando"}))
        self.root.after(1900, lambda: self._set("done", {"eye":"happy","sub":"· fatto"}))
        self.root.after(4600, self._collapse)

    def _collapse(self):
        self._set("idle", {})

    def _restart(self):
        if self.pending:
            self.root.after_cancel(self.pending); self.pending = None
        self._set("idle", {})
        self.root.after(500, self._advance)


def main():
    root = tk.Tk(); root.withdraw()
    Widget(root)
    print("WritHer widget prototype — SPAZIO=ripeti · ESC=esci")
    root.mainloop()


if __name__ == "__main__":
    if "--dump" in sys.argv:
        dump()
    else:
        main()
