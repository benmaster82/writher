# Prototypes — concepts, not production code

Visual reference files for WritHer's "agentic" evolution. They are **not** imported
by the app: they exist only to show and discuss the graphic direction.

## `widget_proto.py`

Native prototype (tkinter + Pillow) of the agentic widget: it starts as a compact
pill (Pandora eyes + waveform, gradient border) and, in agentic mode, expands to
show the plan, live steps, an inline confirmation with a countdown, and the final
outcome.

```
python docs/prototypes/widget_proto.py          # launch the widget on the desktop
python docs/prototypes/widget_proto.py --dump    # save PNGs of each phase
```

Runtime keys: `SPACE` = replay · `ESC` = quit · click Consenti/Annulla.

### What already shipped to production
- The **pill graphics** (per-mode gradient border + glow, enlarged Pandora eyes,
  magenta chromakey) were ported to `widget.py`, wired to the existing logic.
- The **confirmation card** (amber border + countdown) became `agent_panel.py`.

The remaining phases (live multi-step plan, action log + undo, hands-free voice
mode) are still concepts to be explored later.
