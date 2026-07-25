"""Runtime font detection and reportlab registration.

DSF-003 SS3.1 requires a generation run to "detect actual font availability
at run time ... and record whichever font in the stack it actually used" --
never silently assume Aptos/Aptos Display/Consolas are present, and never
bundle font binaries in the repository. This module probes the small,
fixed set of well-known OS font-file locations for the DSF-003-preferred
candidates first (Aptos/Aptos Display/Consolas), then the documented
portable fallback stack, and only registers what is actually found on disk.
python-docx never needs registration (Word/LibreOffice resolve font names
against whatever is installed on the *viewing* machine at open time), but
reportlab must have an actually loadable font to typeset the PDF now, so
this module's result also decides what pdf_render.py can safely reference.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_WINFONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

# (registered-family-name, regular file, bold file, italic file, bold-italic file)
_CANDIDATES = [
    ("Consolas", "consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
    ("Arial", "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    ("Times New Roman", "times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
]


class ResolvedFonts:
    """Plain family names are safe for BOTH renderers (docx run.font.name,
    or reportlab fontName when relying on a registered font *family* so
    <b>/<i> markup auto-selects the bold/italic resource). The *_bold names
    are the exact registered bold resource, needed only where reportlab
    must render bold text without going through <b> markup (e.g. a
    ParagraphStyle applied directly to already-bold display text)."""

    def __init__(self):
        self.body = "Helvetica"
        self.body_bold = "Helvetica-Bold"
        self.heading = "Helvetica"
        self.heading_bold = "Helvetica-Bold"
        self.display = "Times-Roman"
        self.display_bold = "Times-Bold"
        self.mono = "Courier"
        self.mono_bold = "Courier-Bold"
        self.mono_registered = False
        self.body_registered = False
        self.display_registered = False
        self.notes = []

    def describe(self) -> str:
        return "; ".join(self.notes) if self.notes else "base-14 PDF fonts only (no TTF found)"


def resolve_and_register() -> ResolvedFonts:
    result = ResolvedFonts()
    for family, reg, bold, italic, bolditalic in _CANDIDATES:
        reg_path = _WINFONTS / reg
        if not reg_path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(family, str(reg_path)))
            bold_path = _WINFONTS / bold
            italic_path = _WINFONTS / italic
            bolditalic_path = _WINFONTS / bolditalic
            bold_name = f"{family}-Bold"
            italic_name = f"{family}-Italic"
            bolditalic_name = f"{family}-BoldItalic"
            if bold_path.is_file():
                pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
            else:
                bold_name = family
            if italic_path.is_file():
                pdfmetrics.registerFont(TTFont(italic_name, str(italic_path)))
            else:
                italic_name = family
            if bolditalic_path.is_file():
                pdfmetrics.registerFont(TTFont(bolditalic_name, str(bolditalic_path)))
            else:
                bolditalic_name = bold_name
            pdfmetrics.registerFontFamily(
                family, normal=family, bold=bold_name, italic=italic_name, boldItalic=bolditalic_name,
            )
            if family == "Consolas":
                result.mono = family
                result.mono_bold = bold_name
                result.mono_registered = True
                result.notes.append(f"mono -> {family} (detected at {reg_path})")
            elif family == "Arial":
                result.body = family
                result.body_bold = bold_name
                result.heading = family
                result.heading_bold = bold_name
                result.body_registered = True
                result.notes.append(f"body/heading -> {family} (detected at {reg_path})")
            elif family == "Times New Roman":
                result.display = family
                result.display_bold = bold_name
                result.display_registered = True
                result.notes.append(f"cover/display -> {family} (detected at {reg_path})")
        except Exception as exc:  # pragma: no cover -- defensive, falls back to base-14
            result.notes.append(f"{family} registration failed ({exc}); using base-14 fallback")
    if not result.notes:
        result.notes.append("no DSF-003-candidate TTF found on this machine; using reportlab base-14 fonts")
    return result
