"""Unified Pandora Blackboard theme for all Writher windows.

Single source of truth for colours, fonts, and spacing.
Pure black + bright white — matching the Pandora Blackboard brand.
"""

# ── Core Pandora Blackboard palette ───────────────────────────────────────
BG_DEEP     = "#000000"     # pure black background
BG          = "#050508"     # primary window background
BG_CARD     = "#0a0a0f"     # card / elevated surface
BG_HOVER    = "#111118"     # card hover state
BG_INPUT    = "#0a0a0f"     # input fields, sliders
BORDER      = "#1a1a24"     # subtle borders
BORDER_GLOW = "#2a2a3a"     # brighter border for focus / hover

# ── Text ──────────────────────────────────────────────────────────────────
FG          = "#ffffff"     # pure white primary text
FG_DIM      = "#888898"     # secondary / muted text
FG_ACCENT   = "#ccccdd"     # slightly muted white

# ── Accent ────────────────────────────────────────────────────────────────
ACCENT      = "#ffffff"     # white accent (on-brand)
ACCENT_HOVER = "#ddddee"   # accent hover
ACCENT_DIM  = "#666678"     # accent muted

# ── Semantic ──────────────────────────────────────────────────────────────
RED         = "#ff4444"
RED_HOVER   = "#ff6666"
GREEN       = "#55cc77"
YELLOW      = "#ffaa00"

# ── Title bar ─────────────────────────────────────────────────────────────
TITLE_BG    = "#000000"
CLOSE_HOVER = "#ff4444"

# ── Fonts ─────────────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_TITLE  = (FONT_FAMILY, 12, "bold")
FONT_BODY   = (FONT_FAMILY, 11)
FONT_SMALL  = (FONT_FAMILY, 10)
FONT_TINY   = (FONT_FAMILY, 9)

# ── Spacing ───────────────────────────────────────────────────────────────
PAD_S  = 4
PAD_M  = 8
PAD_L  = 16
PAD_XL = 24
