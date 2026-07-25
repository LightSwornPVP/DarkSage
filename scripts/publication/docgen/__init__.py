"""DarkSage publication document-generation pipeline.

Deterministic, offline Markdown -> DOCX/PDF generator implementing the
DarkSage Visual Design System (docs/publication/DARKSAGE_VISUAL_DESIGN_SYSTEM.md).

Modules:
    model        Intermediate document representation (dataclasses).
    parser       Markdown -> model.Document parser.
    design       Design-system constants (colors, fonts, sizes, margins).
    docx_render  DOCX renderer (python-docx).
    pdf_render   PDF renderer (reportlab).
    generate     CLI entry point tying the above together.
"""
