"""Intermediate document representation shared by the DOCX and PDF renderers.

Standard library only (dataclasses). The parser (parser.py) produces a
Document; docx_render.py and pdf_render.py each consume the same Document
independently -- neither renderer derives its content from the other's
output, per the "PDF is not a DOCX-to-PDF conversion" requirement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Heading:
    level: int  # 1 = H1 (document title), 2 = H2, 3 = H3, 4 = H4
    text: str
    anchor: str  # stable, unique slug for TOC/bookmark linking
    skip_in_body: bool = False  # True for the Document Control / Revision
    # History headings, whose table content is pulled onto dedicated pages
    # instead of being repeated in the flowing body text.


@dataclass
class Paragraph:
    text: str  # raw inline markdown (bold/italic/code/links) resolved at render time
    skip_in_body: bool = False


@dataclass
class Table:
    header: List[str]
    rows: List[List[str]]
    skip_in_body: bool = False


@dataclass
class CodeBlock:
    text: str


@dataclass
class ListBlock:
    ordered: bool
    items: List[str]


@dataclass
class Blockquote:
    text: str


@dataclass
class Rule:
    pass


@dataclass
class Figure:
    number: int
    title: str
    caption: str  # remaining descriptive text from the source paragraph
    source_path: Optional[str] = None
    rendered_png: Optional[str] = None
    accessibility_text: Optional[str] = None


Block = object  # Heading | Paragraph | Table | CodeBlock | ListBlock | Blockquote | Rule | Figure


@dataclass
class RevisionRow:
    version: str
    date: str
    author: str
    summary: str


@dataclass
class Document:
    doc_id: str
    title: str
    doc_control: "dict[str, str]" = field(default_factory=dict)
    revision_history: List[RevisionRow] = field(default_factory=list)
    blocks: List[Block] = field(default_factory=list)
    source_path: str = ""

    @property
    def version(self) -> str:
        return self.doc_control.get("Version", "")

    @property
    def status(self) -> str:
        return self.doc_control.get("Status", "")

    @property
    def classification(self) -> str:
        return self.doc_control.get("Classification", "")

    @property
    def owner(self) -> str:
        return self.doc_control.get("Owner", "")

    @property
    def repository(self) -> str:
        return self.doc_control.get("Repository", "")

    def headings(self) -> List[Heading]:
        return [b for b in self.blocks if isinstance(b, Heading) and not b.skip_in_body]
