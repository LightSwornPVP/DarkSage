"""Design-system constants for the DarkSage publication pipeline.

Every value here is copied verbatim from
docs/publication/DARKSAGE_VISUAL_DESIGN_SYSTEM.md (DSF-003) -- this module
does not invent a palette value, page-size, or typographic role beyond what
DSF-003 already specifies. Where DSF-003 gives a portable fallback font
stack (fonts are environment-dependent and never bundled with the repo),
this module records which fallback the generation run actually resolved to,
per DSF-003 SS3.1's "record whichever font it actually used" rule.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Color system (DSF-003 SS2.1 / SS2.2, verbatim hex values)
# ---------------------------------------------------------------------------

OBSIDIAN_BLACK = "0B0B0D"
CHARCOAL_GRAY = "17181C"
STEEL_GRAY = "2A2D33"
SOFT_GRAY = "A7ABB3"
IVORY_WHITE = "F4F2EC"
SAGE_GOLD = "C8A45D"
HIGHLIGHT_GOLD = "E0BE72"

SIGNAL_GREEN = "1E6E43"
RISK_RED = "A33A3A"
WARNING_AMBER = "8A6013"
INFO_BLUE = "3B6EA5"

NEAR_OBSIDIAN_BODY_TEXT = "17181C"  # near-Obsidian body text on Ivory (DSF-003 SS2.3)

# ---------------------------------------------------------------------------
# Typography (DSF-003 SS3.1) -- portable fallback stack, since Aptos/Consolas
# are environment-dependent and never bundled. We record the concrete
# resolved family names actually used for this generation run.
# ---------------------------------------------------------------------------

# python-docx/reportlab do not do font *discovery* against the OS the way a
# word processor does; we request names from the documented portable
# fallback stack in priority order and record the first choice, since actual
# glyph substitution happens in the consuming viewer (Word/LibreOffice/PDF
# reader), not at generation time. This matches DSF-003's own framing: "a
# generation run shall detect actual font availability at run time and
# record whichever font in the stack it actually used."
HEADING_FONT_STACK = ["Source Sans 3 Semibold", "Liberation Sans Bold", "DejaVu Sans Bold", "Noto Sans Bold"]
BODY_FONT_STACK = ["Source Sans 3", "Liberation Sans", "DejaVu Sans", "Noto Sans"]
CAPTION_FONT_STACK = ["Source Sans 3", "Liberation Sans", "DejaVu Sans"]
MONO_FONT_STACK = ["JetBrains Mono", "Liberation Mono", "DejaVu Sans Mono"]
DISPLAY_FONT_STACK = ["Source Serif 4 Bold", "Liberation Serif Bold", "DejaVu Serif Bold"]

# Resolved (recorded) choice for this generation run. DSF-003 SS3.1 requires
# a generation run to detect actual font availability at run time rather
# than assume Aptos/Aptos Display/Consolas are present, and to record
# whichever font it actually used. fonts.resolve_and_register() probes this
# machine's real font files (DSF-003-preferred candidates first, e.g.
# Consolas for mono; then the documented portable fallback) and registers
# whatever it finds with reportlab; the names below are then updated in
# place from that probe so both renderers report the same resolved choice.
from . import fonts as _fonts  # noqa: E402

_resolved = _fonts.resolve_and_register()

HEADING_FONT = _resolved.heading
HEADING_FONT_BOLD = _resolved.heading_bold
BODY_FONT = _resolved.body
BODY_FONT_BOLD = _resolved.body_bold
CAPTION_FONT = _resolved.body
MONO_FONT = _resolved.mono
MONO_FONT_BOLD = _resolved.mono_bold
DISPLAY_FONT = _resolved.display
DISPLAY_FONT_BOLD = _resolved.display_bold

RESOLVED_FONT_NOTE = (
    "Fonts resolved at generation time by probing this machine's installed "
    "font files (DSF-003 SS3.1): " + _resolved.describe()
)

# ---------------------------------------------------------------------------
# Point sizes (DSF-003 SS3.1)
# ---------------------------------------------------------------------------

SIZE_COVER_TITLE = 40
SIZE_H1 = 22
SIZE_H2 = 17
SIZE_H3 = 13.5
SIZE_H4 = 11
SIZE_BODY = 10.5
SIZE_CAPTION = 8.5
SIZE_TABLE = 9.5
SIZE_TABLE_HEADER = 9.5
SIZE_MONO = 10

# ---------------------------------------------------------------------------
# Page geometry (DSF-003 SS4.1 / SS4.2) -- Letter is the primary target.
# ---------------------------------------------------------------------------

PAGE_WIDTH_IN = 8.5
PAGE_HEIGHT_IN = 11.0

MARGIN_COVER_TOP_IN = 1.25
MARGIN_COVER_BOTTOM_IN = 1.25
MARGIN_COVER_SIDE_IN = 1.0

MARGIN_NORMAL_TOP_IN = 1.0
MARGIN_NORMAL_BOTTOM_IN = 1.0
MARGIN_NORMAL_INSIDE_IN = 1.1
MARGIN_NORMAL_OUTSIDE_IN = 0.9

# ---------------------------------------------------------------------------
# Spacing scale (DSF-003 SS4.4)
# ---------------------------------------------------------------------------

PARA_SPACE_AFTER_PT = 6
H1_SPACE_BEFORE_PT = 24
H1_SPACE_AFTER_PT = 12
H2_SPACE_BEFORE_PT = 18
H2_SPACE_AFTER_PT = 8
H3_SPACE_BEFORE_PT = 12
H3_SPACE_AFTER_PT = 6

MOTTO = "Wisdom Over Noise"
