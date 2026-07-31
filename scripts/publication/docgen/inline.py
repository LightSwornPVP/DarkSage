"""Inline Markdown span parsing shared by both renderers.

Handles the inline markup actually used in the DarkSage flagship documents:
**bold**, `code`, *italic*, and [label](target) links (rendered as their
label text -- neither generated artifact re-hosts the external targets
these links point to, most of which are other repository Markdown files
outside the generated document itself).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_TOKEN_RE = re.compile(
    r"\[(?P<link_text>[^\]]+)\]\((?P<link_target>[^)]+)\)"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|`(?P<code>[^`]+)`"
    r"|\*(?P<italic>[^*]+)\*"
)

STATUS_COLORS = {
    "committed/mvp": "signal_green",
    "committed": "signal_green",
    "planned": "warning_amber",
    "future/exploratory": "soft_gray",
}


@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    status_color: str = ""  # "signal_green" | "warning_amber" | "soft_gray" | ""


def parse_inline(text: str) -> List[Span]:
    spans: List[Span] = []
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        if m.start() > pos:
            spans.append(Span(text=text[pos : m.start()]))
        if m.group("link_text") is not None:
            spans.append(Span(text=m.group("link_text")))
        elif m.group("bold") is not None:
            content = m.group("bold")
            status = STATUS_COLORS.get(content.strip().lower(), "")
            spans.append(Span(text=content, bold=True, status_color=status))
        elif m.group("code") is not None:
            spans.append(Span(text=m.group("code"), code=True))
        elif m.group("italic") is not None:
            spans.append(Span(text=m.group("italic"), italic=True))
        pos = m.end()
    if pos < len(text):
        spans.append(Span(text=text[pos:]))
    if not spans:
        spans.append(Span(text=text))
    return spans
