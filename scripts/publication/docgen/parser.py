"""Markdown -> model.Document parser for the DarkSage publication pipeline.

Handles the controlled-Markdown subset actually used by the DarkSage
DSF-NNN flagship documents: H1/H2/H3 headings, pipe tables (with header
separator row), fenced code blocks, blockquotes, bulleted/numbered lists,
horizontal rules, bold "**Figure N -- Title**" figure markers, and plain
paragraphs. Standard library only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .model import (
    Blockquote,
    CodeBlock,
    Document,
    Figure,
    Heading,
    ListBlock,
    Paragraph,
    Rule,
    RevisionRow,
    Table,
)

_FIGURE_RE = re.compile(r"^\*\*Figure\s+(\d+)\s+[\u2014\-]{1,2}\s+(.+?)\*\*(.*)$", re.DOTALL)
_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")
_ORDERED_ITEM_RE = re.compile(r"^\s*\d+\.\s+(.*)$")
_BULLET_ITEM_RE = re.compile(r"^\s*[-*]\s+(.*)$")


def _slugify(text: str, seen: dict) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug or "section"
    if slug in seen:
        seen[slug] += 1
        slug = f"{slug}-{seen[slug]}"
    else:
        seen[slug] = 0
    return slug


def _split_table_row(line: str) -> List[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def parse_markdown(text: str, source_path: str = "") -> Document:
    lines = text.splitlines()
    n = len(lines)
    i = 0

    doc_title = ""
    blocks: List[object] = []
    seen_slugs: dict = {}
    doc_control: dict = {}
    revision_history: List[RevisionRow] = []

    # Tracks whether we are inside the first "Document Control" or
    # "Revision History" H2 section, so their table(s) can be captured into
    # doc_control/revision_history AND flagged skip_in_body (dedicated Cover
    # / Document-Control / Revision-History pages render them instead of the
    # flowing body repeating the same large table).
    in_doc_control_section = False
    in_revision_history_section = False
    captured_doc_control_table = False
    captured_revision_table = False

    def paragraph_buffer_flush(buf: List[str]):
        if not buf:
            return None
        text_joined = " ".join(s.strip() for s in buf).strip()
        buf.clear()
        if not text_joined:
            return None
        m = _FIGURE_RE.match(text_joined)
        if m:
            number = int(m.group(1))
            title = m.group(2).strip()
            caption = m.group(3).strip().lstrip("*").strip()
            return Figure(number=number, title=title, caption=caption)
        return Paragraph(text=text_joined, skip_in_body=(in_doc_control_section or in_revision_history_section))

    para_buf: List[str] = []

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        # Fenced code block
        if stripped.startswith("```"):
            b = paragraph_buffer_flush(para_buf)
            if b is not None:
                blocks.append(b)
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            blocks.append(CodeBlock(text="\n".join(code_lines)))
            continue

        # Blank line -> paragraph boundary
        if stripped == "":
            b = paragraph_buffer_flush(para_buf)
            if b is not None:
                blocks.append(b)
            i += 1
            continue

        # Horizontal rule (bare --- / *** line, not a table separator --
        # table separators are only consumed inside the table-parsing branch)
        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            b = paragraph_buffer_flush(para_buf)
            if b is not None:
                blocks.append(b)
            blocks.append(Rule())
            i += 1
            continue

        # Headings
        heading_m = re.match(r"^(#{1,4})\s+(.*)$", raw)
        if heading_m:
            b = paragraph_buffer_flush(para_buf)
            if b is not None:
                blocks.append(b)
            level = len(heading_m.group(1))
            htext = heading_m.group(2).strip()
            if level == 1:
                doc_title = htext
                i += 1
                continue
            anchor = _slugify(htext, seen_slugs)

            bare = re.sub(r"^\d+(\.\d+)*\.?\s*", "", htext).strip()
            is_doc_control_heading = level == 2 and bare.lower() == "document control"
            is_revision_heading = level == 2 and bare.lower() == "revision history"

            in_doc_control_section = is_doc_control_heading
            in_revision_history_section = is_revision_heading

            heading = Heading(
                level=level,
                text=htext,
                anchor=anchor,
                skip_in_body=is_doc_control_heading or is_revision_heading,
            )
            blocks.append(heading)
            i += 1
            continue

        # Table (header row + separator row)
        if _TABLE_ROW_RE.match(raw) and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]) and "-" in lines[i + 1]:
            b = paragraph_buffer_flush(para_buf)
            if b is not None:
                blocks.append(b)
            header = _split_table_row(raw)
            i += 2  # skip header + separator
            rows: List[List[str]] = []
            while i < n and _TABLE_ROW_RE.match(lines[i]):
                rows.append(_split_table_row(lines[i]))
                i += 1
            skip = in_doc_control_section or in_revision_history_section
            table = Table(header=header, rows=rows, skip_in_body=skip)
            blocks.append(table)

            if in_doc_control_section and not captured_doc_control_table:
                for r in rows:
                    if len(r) >= 2:
                        doc_control[r[0].strip()] = r[1].strip()
                captured_doc_control_table = True
            if in_revision_history_section and not captured_revision_table:
                idx = {name.strip().lower(): pos for pos, name in enumerate(header)}
                for r in rows:
                    def cell(name: str) -> str:
                        pos = idx.get(name)
                        return r[pos].strip() if pos is not None and pos < len(r) else ""

                    revision_history.append(
                        RevisionRow(
                            version=cell("version"),
                            date=cell("date"),
                            author=cell("author"),
                            summary=cell("summary"),
                        )
                    )
                captured_revision_table = True
            continue

        # Blockquote
        if stripped.startswith(">"):
            b = paragraph_buffer_flush(para_buf)
            if b is not None:
                blocks.append(b)
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append(Blockquote(text=" ".join(quote_lines)))
            continue

        # Lists
        if _BULLET_ITEM_RE.match(raw) or _ORDERED_ITEM_RE.match(raw):
            b = paragraph_buffer_flush(para_buf)
            if b is not None:
                blocks.append(b)
            ordered = bool(_ORDERED_ITEM_RE.match(raw))
            items: List[str] = []
            while i < n:
                m_b = _BULLET_ITEM_RE.match(lines[i])
                m_o = _ORDERED_ITEM_RE.match(lines[i])
                if ordered and m_o:
                    items.append(m_o.group(1).strip())
                    i += 1
                elif not ordered and m_b:
                    items.append(m_b.group(1).strip())
                    i += 1
                elif lines[i].strip() and (lines[i].startswith("  ") or lines[i].startswith("\t")) and items:
                    # continuation line of the previous item
                    items[-1] = items[-1] + " " + lines[i].strip()
                    i += 1
                else:
                    break
            blocks.append(ListBlock(ordered=ordered, items=items))
            continue

        # Plain paragraph line -- accumulate
        para_buf.append(raw)
        i += 1

    b = paragraph_buffer_flush(para_buf)
    if b is not None:
        blocks.append(b)

    doc_id = doc_control.get("Document ID") or re.sub(r"\s.*$", "", doc_title)
    return Document(
        doc_id=doc_id,
        title=doc_title,
        doc_control=doc_control,
        revision_history=revision_history,
        blocks=blocks,
        source_path=source_path,
    )


def parse_markdown_file(path: Path) -> Document:
    text = Path(path).read_text(encoding="utf-8")
    return parse_markdown(text, source_path=str(path))
