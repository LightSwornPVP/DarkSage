"""PDF renderer for the DarkSage publication pipeline.

Builds the PDF directly from the shared intermediate model.Document (never
by converting the generated DOCX), using reportlab's platypus layer for
flowing content plus a custom canvasmaker (invariant=1) for byte-stable,
non-wall-clock-timestamped output. Produces a real, navigable PDF outline
via canvas.bookmarkPage/addOutlineEntry, and an in-body Table of Contents
page with real page numbers via reportlab's two-pass TableOfContents
flowable (BaseDocTemplate.multiBuild).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from . import design
from .diagrams import DiagramRegistry
from .inline import Span, parse_inline
from .model import (
    Blockquote,
    CodeBlock,
    Document as ModelDocument,
    Figure,
    Heading,
    ListBlock,
    Paragraph as ModelParagraph,
    Rule,
    Table as ModelTable,
)

_STATUS_HEX = {
    "signal_green": design.SIGNAL_GREEN,
    "warning_amber": design.WARNING_AMBER,
    "soft_gray": design.SOFT_GRAY,
}


def _c(hex6: str):
    return colors.HexColor(f"#{hex6}")


def _spans_to_markup(spans: List[Span], default_color: Optional[str] = None) -> str:
    parts = []
    for span in spans:
        text = escape(span.text).replace("\n", "<br/>")
        color = _STATUS_HEX.get(span.status_color) if span.status_color else default_color
        if span.code:
            text = f'<font face="{design.MONO_FONT}">{text}</font>'
        if span.bold:
            text = f"<b>{text}</b>"
        if span.italic:
            text = f"<i>{text}</i>"
        if color:
            text = f'<font color="#{color}">{text}</font>'
        parts.append(text)
    return "".join(parts)


def _para_style(name, size, color_hex, font=None, leading=None, space_after=6,
                alignment=0, left_indent=0, bold=False):
    """font=None picks BODY_FONT or (if bold) the exact registered
    BODY_FONT_BOLD resource; pass an explicit font= for anything that needs
    a different family (mono, display) -- pass the already-bold resource
    name directly (e.g. design.DISPLAY_FONT_BOLD) rather than relying on
    this function to guess a "-Bold" suffix that may not be a real
    registered resource for that family."""
    if font is None:
        font = design.BODY_FONT_BOLD if bold else design.BODY_FONT
    return ParagraphStyle(
        name=name,
        fontName=font,
        fontSize=size,
        leading=leading or size * 1.2,
        textColor=_c(color_hex),
        spaceAfter=space_after,
        alignment=alignment,
        leftIndent=left_indent,
    )


class _HeadingParagraph(Paragraph):
    """A Paragraph tagged with TOC/outline metadata, consumed by
    DSDocTemplate.afterFlowable to register a real page bookmark, an outline
    entry, and a TOC row -- all three keyed off the same anchor.

    Never split across a page/frame boundary: Paragraph.split() rebuilds
    fragments via self.__class__(None, style, bulletText=..., frags=...),
    but this subclass's __init__ takes fixed positional args (level,
    plain_text, key) with no matching keyword parameters, so accepting the
    base class's split behavior would raise TypeError whenever a long
    heading falls near the bottom of a page. Headings should not visually
    break mid-text at a page boundary regardless, so split() is disabled
    here -- reportlab's frame logic then moves the whole heading, intact,
    to the next page instead of raising."""

    def __init__(self, text, style, level, plain_text, key):
        Paragraph.__init__(self, text, style)
        self._ds_level = level
        self._ds_text = plain_text
        self._ds_key = key

    def split(self, availWidth, availHeight):
        return []


class DSDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, _HeadingParagraph):
            self.canv.bookmarkPage(flowable._ds_key)
            self.canv.addOutlineEntry(flowable._ds_text, flowable._ds_key, level=flowable._ds_level, closed=0)
            self.notify("TOCEntry", (flowable._ds_level, flowable._ds_text, self.page, flowable._ds_key))


def _draw_cover_background(cv, doc):
    cv.saveState()
    cv.setFillColor(_c(design.OBSIDIAN_BLACK))
    cv.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
    cv.restoreState()


def _make_body_background(short_title: str, doc_id: str, classification: str, version: str,
                           status: str, baseline_commit: str):
    def draw(cv, doc):
        cv.saveState()
        cv.setFillColor(_c(design.IVORY_WHITE))
        cv.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)

        top_y = letter[1] - 0.65 * inch
        cv.setFont(design.BODY_FONT, 8.5)
        cv.setFillColor(_c(design.NEAR_OBSIDIAN_BODY_TEXT))
        cv.drawString(design.MARGIN_NORMAL_INSIDE_IN * inch, top_y, f"DarkSage — {short_title}")
        cv.setFont(design.MONO_FONT_BOLD, 8.5)
        cv.setFillColor(_c(design.SAGE_GOLD))
        cv.drawRightString(letter[0] - design.MARGIN_NORMAL_OUTSIDE_IN * inch, top_y, doc_id)
        cv.setStrokeColor(_c(design.SAGE_GOLD))
        cv.setLineWidth(0.75)
        cv.line(
            design.MARGIN_NORMAL_INSIDE_IN * inch, top_y - 6,
            letter[0] - design.MARGIN_NORMAL_OUTSIDE_IN * inch, top_y - 6,
        )

        bottom_y = 0.55 * inch
        cv.setFont(design.BODY_FONT, 8.5)
        cv.setFillColor(_c(design.SOFT_GRAY))
        cv.drawString(design.MARGIN_NORMAL_INSIDE_IN * inch, bottom_y, f"Page {doc.page}")
        cv.drawRightString(letter[0] - design.MARGIN_NORMAL_OUTSIDE_IN * inch, bottom_y, f"Classification: {classification}")
        cv.setFont(design.BODY_FONT, 7.5)
        cv.drawCentredString(letter[0] / 2, bottom_y, f"v{version} — {status}")
        cv.setFont(design.MONO_FONT, 6.5)
        cv.drawCentredString(letter[0] / 2, bottom_y - 10, f"Generated from {doc_id} v{version} — baseline {baseline_commit}")
        cv.restoreState()

    return draw


def _build_cover_flowables(model: ModelDocument, generation_date: str, baseline_commit: str) -> List:
    story = []
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph(escape("DarkSage"), _para_style(
        "CoverTitle", design.SIZE_COVER_TITLE, design.HIGHLIGHT_GOLD,
        font=design.DISPLAY_FONT_BOLD,
        alignment=1, space_after=4,
    )))
    subtitle = model.title.split("—", 1)[-1].strip() or model.title
    story.append(Paragraph(escape(subtitle), _para_style(
        "CoverSubtitle", 17, design.IVORY_WHITE, font=design.BODY_FONT, alignment=1, space_after=18,
    )))
    story.append(Paragraph(escape(f"Version {model.version} — {model.status}"), _para_style(
        "CoverMeta", 12, design.SOFT_GRAY, alignment=1, space_after=4,
    )))
    story.append(Paragraph(escape(f"Owner: {model.owner}"), _para_style(
        "CoverMeta2", 11, design.SOFT_GRAY, alignment=1, space_after=4,
    )))
    story.append(Paragraph(escape(f"Classification: {model.classification}"), _para_style(
        "CoverMeta3", 11, design.SOFT_GRAY, alignment=1, space_after=24,
    )))
    story.append(Paragraph(escape(design.MOTTO), _para_style(
        "CoverMotto", 14, design.SAGE_GOLD, alignment=1, space_after=36,
    )))
    story.append(Spacer(1, 1.4 * inch))
    for label, value in [
        ("Source repository", model.repository),
        ("Source baseline commit", baseline_commit),
        ("Generation date", generation_date),
        ("Document ID", model.doc_id),
    ]:
        story.append(Paragraph(escape(f"{label}: {value}"), _para_style(
            f"CoverFoot_{label}", 9, design.SOFT_GRAY, font=design.MONO_FONT,
            alignment=1, space_after=2,
        )))
    return story


def _kv_table(rows: List[List[str]], col_widths) -> Table:
    data = [[Paragraph(_spans_to_markup(parse_inline(k)), _para_style("kvk", design.SIZE_TABLE, design.IVORY_WHITE, bold=True)),
             Paragraph(_spans_to_markup(parse_inline(v)), _para_style("kvv", design.SIZE_TABLE, design.NEAR_OBSIDIAN_BODY_TEXT))]
            for k, v in rows]
    t = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND", (0, 0), (0, -1), _c(design.CHARCOAL_GRAY)),
        ("GRID", (0, 0), (-1, -1), 0.5, _c(design.STEEL_GRAY)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(style))
    return t


def _document_control_flowables(model: ModelDocument, body_width: float) -> List:
    story = []
    story.append(_HeadingParagraph(
        "Document Control", _para_style("H1DC", design.SIZE_H1, design.OBSIDIAN_BLACK, bold=True, space_after=12),
        level=0, plain_text="Document Control", key="doc-control",
    ))
    order = [
        "Document ID", "Title", "Version", "Status", "Owner", "Contributors",
        "Classification", "Repository", "Created", "Last Updated",
        "Source Baseline Commit", "Controlling Sources", "Authority Boundary",
        "Publication Relationship",
    ]
    rows = [[k, model.doc_control[k]] for k in order if model.doc_control.get(k)]
    for k, v in model.doc_control.items():
        if k not in order:
            rows.append([k, v])
    story.append(_kv_table(rows, [body_width * 0.28, body_width * 0.72]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Status lifecycle: Draft → Under Review → Approved → Superseded/Deprecated.",
        _para_style("lifecycle", design.SIZE_CAPTION, design.SOFT_GRAY),
    ))
    return story


def _revision_history_flowables(model: ModelDocument, body_width: float) -> List:
    story = []
    story.append(_HeadingParagraph(
        "Revision History", _para_style("H1RH", design.SIZE_H1, design.OBSIDIAN_BLACK, bold=True, space_after=12),
        level=0, plain_text="Revision History", key="revision-history",
    ))
    widths = [w * body_width for w in (0.10, 0.13, 0.22, 0.55)]
    header = ["Version", "Date", "Author", "Summary"]
    data = [[Paragraph(h, _para_style("rhh", design.SIZE_TABLE_HEADER, design.HIGHLIGHT_GOLD, bold=True)) for h in header]]
    for rev in model.revision_history:
        data.append([
            Paragraph(_spans_to_markup(parse_inline(rev.version)), _para_style("rhv", design.SIZE_TABLE, design.NEAR_OBSIDIAN_BODY_TEXT)),
            Paragraph(_spans_to_markup(parse_inline(rev.date)), _para_style("rhd", design.SIZE_TABLE, design.NEAR_OBSIDIAN_BODY_TEXT)),
            Paragraph(_spans_to_markup(parse_inline(rev.author)), _para_style("rha", design.SIZE_TABLE, design.NEAR_OBSIDIAN_BODY_TEXT)),
            Paragraph(_spans_to_markup(parse_inline(rev.summary)), _para_style("rhs", design.SIZE_TABLE, design.NEAR_OBSIDIAN_BODY_TEXT)),
        ])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _c(design.OBSIDIAN_BLACK)),
        ("GRID", (0, 0), (-1, -1), 0.5, _c(design.STEEL_GRAY)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    return story


def _toc_flowables(toc_flowable: TableOfContents) -> List:
    story = []
    story.append(_HeadingParagraph(
        "Table of Contents", _para_style("H1TOC", design.SIZE_H1, design.OBSIDIAN_BLACK, bold=True, space_after=12),
        level=0, plain_text="Table of Contents", key="toc",
    ))
    story.append(toc_flowable)
    return story


def _render_table_flowable(block: ModelTable, body_width: float) -> Table:
    ncols = max(1, len(block.header))
    col_width = body_width / ncols
    font_size = design.SIZE_TABLE if ncols <= 4 else max(6.5, design.SIZE_TABLE - (ncols - 4) * 0.7)
    header_style = _para_style("th", font_size, design.IVORY_WHITE, bold=True, leading=font_size * 1.25)
    cell_style = _para_style("td", font_size, design.NEAR_OBSIDIAN_BODY_TEXT, leading=font_size * 1.25)
    data = [[Paragraph(escape(h), header_style) for h in block.header]]
    for row in block.rows:
        cells = []
        for i in range(ncols):
            val = row[i] if i < len(row) else ""
            cells.append(Paragraph(_spans_to_markup(parse_inline(val)), cell_style))
        data.append(cells)
    t = Table(data, colWidths=[col_width] * ncols, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _c(design.CHARCOAL_GRAY)),
        ("GRID", (0, 0), (-1, -1), 0.4, _c(design.STEEL_GRAY)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _render_figure_flowables(block: Figure, registry: DiagramRegistry, body_width: float, anchor_counter: List[int]) -> List:
    story = []
    anchor_counter[0] += 1
    key = f"figure-{block.number}-{anchor_counter[0]}"
    story.append(_HeadingParagraph(
        f"Figure {block.number} — {escape(block.title)}",
        _para_style("figH", design.SIZE_H2, design.OBSIDIAN_BLACK, bold=True, space_after=6),
        level=1, plain_text=f"Figure {block.number} — {block.title}", key=key,
    ))
    png = registry.png_path(block.number)
    if png and png.is_file():
        reader = ImageReader(str(png))
        px_w, px_h = reader.getSize()
        max_w = min(6.0 * inch, body_width)
        w = max_w
        h = w * (px_h / px_w)
        max_h = 6.5 * inch
        if h > max_h:
            h = max_h
            w = h * (px_w / px_h)
        img = Image(str(png), width=w, height=h)
        img.hAlign = "CENTER"
        story.append(img)
    else:
        story.append(Paragraph(
            f"[Figure {block.number} not yet rendered — see docs/publication/DIAGRAM_REGISTER.md row {block.number}.]",
            _para_style("figMissing", design.SIZE_CAPTION, design.WARNING_AMBER),
        ))
    if block.caption:
        story.append(Paragraph(escape(block.caption), _para_style("figCap", design.SIZE_CAPTION, design.SOFT_GRAY, space_after=4)))
    alt_text = registry.accessibility_text(block.number)
    if alt_text:
        story.append(Paragraph(
            f'<b>Accessibility description:</b> <i>{escape(alt_text)}</i>',
            _para_style("figAlt", design.SIZE_CAPTION, design.SOFT_GRAY),
        ))
    return story


def _render_blockquote_flowable(block: Blockquote, body_width: float) -> Table:
    p = Paragraph(_spans_to_markup(parse_inline(block.text)),
                  _para_style("bq", design.SIZE_BODY, design.STEEL_GRAY, leading=design.SIZE_BODY * 1.2))
    t = Table([[p]], colWidths=[body_width])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 2.5, _c(design.SAGE_GOLD)),
        ("LEFTPADDING", (0, 0), (0, 0), 10),
        ("TOPPADDING", (0, 0), (0, 0), 4),
        ("BOTTOMPADDING", (0, 0), (0, 0), 4),
    ]))
    return t


def _render_code_flowable(block: CodeBlock, body_width: float) -> Table:
    text = escape(block.text).replace("\n", "<br/>")
    p = Paragraph(text,
                  _para_style("code", design.SIZE_MONO - 1, design.NEAR_OBSIDIAN_BODY_TEXT,
                              font=design.MONO_FONT, leading=(design.SIZE_MONO - 1) * 1.3))
    t = Table([[p]], colWidths=[body_width])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.75, _c(design.STEEL_GRAY)),
        ("BACKGROUND", (0, 0), (0, 0), _c(design.IVORY_WHITE)),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("RIGHTPADDING", (0, 0), (0, 0), 8),
        ("TOPPADDING", (0, 0), (0, 0), 6),
        ("BOTTOMPADDING", (0, 0), (0, 0), 6),
    ]))
    return t


def _render_list_flowables(block: ListBlock) -> List:
    story = []
    for idx, item in enumerate(block.items, start=1):
        prefix = f"{idx}. " if block.ordered else "• "
        markup = escape(prefix) + _spans_to_markup(parse_inline(item))
        story.append(Paragraph(markup, _para_style(
            "li", design.SIZE_BODY, design.NEAR_OBSIDIAN_BODY_TEXT, left_indent=16, space_after=3,
        )))
    return story


def render_pdf(
    model: ModelDocument,
    out_path: Path,
    repo_root: Path,
    generation_date: str,
    baseline_commit: str,
    short_title: Optional[str] = None,
) -> int:
    """Renders the PDF and returns the final page count."""
    registry = DiagramRegistry(repo_root)
    short_title = short_title or model.title

    body_width = letter[0] - (design.MARGIN_NORMAL_INSIDE_IN + design.MARGIN_NORMAL_OUTSIDE_IN) * inch
    body_height = letter[1] - (design.MARGIN_NORMAL_TOP_IN + design.MARGIN_NORMAL_BOTTOM_IN) * inch

    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = DSDocTemplate(
        str(out_path),
        pagesize=letter,
        title=f"{model.doc_id} — {model.title}",
        author=model.owner or "DarkSage",
        subject=model.doc_id,
    )

    cover_frame = Frame(
        design.MARGIN_COVER_SIDE_IN * inch, design.MARGIN_COVER_BOTTOM_IN * inch,
        letter[0] - 2 * design.MARGIN_COVER_SIDE_IN * inch,
        letter[1] - (design.MARGIN_COVER_TOP_IN + design.MARGIN_COVER_BOTTOM_IN) * inch,
        id="cover",
    )
    body_frame = Frame(
        design.MARGIN_NORMAL_INSIDE_IN * inch, design.MARGIN_NORMAL_BOTTOM_IN * inch,
        body_width, body_height, id="body",
    )

    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], onPage=_draw_cover_background),
        PageTemplate(id="Body", frames=[body_frame], onPage=_make_body_background(
            short_title, model.doc_id, model.classification, model.version, model.status, baseline_commit,
        )),
    ])

    toc = TableOfContents()
    toc.levelStyles = [
        _para_style("TOC0", 11, design.NEAR_OBSIDIAN_BODY_TEXT, bold=True, space_after=4),
        _para_style("TOC1", 10, design.STEEL_GRAY, left_indent=14, space_after=2),
        _para_style("TOC2", 9, design.STEEL_GRAY, left_indent=28, space_after=1),
    ]

    story: List = []
    story.extend(_build_cover_flowables(model, generation_date, baseline_commit))
    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())

    story.extend(_document_control_flowables(model, body_width))
    story.append(PageBreak())
    story.extend(_revision_history_flowables(model, body_width))
    story.append(PageBreak())
    story.extend(_toc_flowables(toc))
    story.append(PageBreak())

    anchor_counter = [0]
    seen_real_h2 = False
    for block in model.blocks:
        if isinstance(block, Heading):
            if block.skip_in_body:
                continue
            if block.level == 2:
                seen_real_h2 = True
                level = 0
            elif block.level == 4:
                level = 2
            else:
                level = 0 if not seen_real_h2 else 1
            if block.level == 4:
                size = design.SIZE_H4
            else:
                size = design.SIZE_H1 if level == 0 else design.SIZE_H2
            key = f"h-{block.anchor}"
            story.append(_HeadingParagraph(
                escape(block.text),
                _para_style(f"H_{key}", size, design.OBSIDIAN_BLACK, bold=(block.level != 4),
                            space_after=(design.H1_SPACE_AFTER_PT if level == 0 else design.H2_SPACE_AFTER_PT)),
                level=level, plain_text=block.text, key=key,
            ))
        elif isinstance(block, ModelParagraph):
            if block.skip_in_body:
                continue
            story.append(Paragraph(_spans_to_markup(parse_inline(block.text)),
                                    _para_style("body", design.SIZE_BODY, design.NEAR_OBSIDIAN_BODY_TEXT,
                                                leading=design.SIZE_BODY * 1.2)))
        elif isinstance(block, ModelTable):
            if block.skip_in_body:
                continue
            story.append(_render_table_flowable(block, body_width))
            story.append(Spacer(1, 8))
        elif isinstance(block, Figure):
            story.extend(_render_figure_flowables(block, registry, body_width, anchor_counter))
        elif isinstance(block, Blockquote):
            story.append(_render_blockquote_flowable(block, body_width))
            story.append(Spacer(1, 6))
        elif isinstance(block, CodeBlock):
            story.append(_render_code_flowable(block, body_width))
            story.append(Spacer(1, 6))
        elif isinstance(block, ListBlock):
            story.extend(_render_list_flowables(block))
        elif isinstance(block, Rule):
            story.append(Spacer(1, 4))

    def _invariant_canvasmaker(*args, **kwargs):
        kwargs["invariant"] = 1
        return pdfcanvas.Canvas(*args, **kwargs)

    doc.multiBuild(story, canvasmaker=_invariant_canvasmaker)
    return doc.page
