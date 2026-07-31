"""Figure lookup: resolves a Diagram Register figure number to its rendered
PNG (for embedding) and its accessibility description (for alt text),
reading directly from the repository's own rendered-diagrams directory and
Mermaid source headers rather than hard-coding a second, drift-prone copy.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

_FIGURE_PREFIX_RE = re.compile(r"^figure-(\d+)-")
_ACCESS_HEADER_RE = re.compile(
    r"Accessibility description \(full sentence form[^\)]*\):\s*\n((?:%%.*\n?)+)"
)


class DiagramRegistry:
    """Resolves figure number -> (png_path, accessibility_text)."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.rendered_dir = repo_root / "docs" / "publication" / "diagrams" / "rendered"
        self.source_dir = repo_root / "docs" / "publication" / "diagrams" / "source"
        self._png_by_number: Dict[int, Path] = {}
        self._alt_by_number: Dict[int, str] = {}
        self._load()

    def _load(self) -> None:
        if self.rendered_dir.is_dir():
            for png in sorted(self.rendered_dir.glob("figure-*.png")):
                m = _FIGURE_PREFIX_RE.match(png.name)
                if m:
                    self._png_by_number[int(m.group(1))] = png

        if self.source_dir.is_dir():
            for mmd in sorted(self.source_dir.glob("figure-*.mmd")):
                m = _FIGURE_PREFIX_RE.match(mmd.name)
                if not m:
                    continue
                number = int(m.group(1))
                raw = mmd.read_text(encoding="utf-8")
                am = _ACCESS_HEADER_RE.search(raw)
                if am:
                    body = am.group(1)
                    sentences = " ".join(
                        line.strip().lstrip("%").strip()
                        for line in body.splitlines()
                        if line.strip().lstrip("%").strip()
                    )
                    self._alt_by_number[number] = sentences

    def png_path(self, number: int) -> Optional[Path]:
        return self._png_by_number.get(number)

    def accessibility_text(self, number: int) -> Optional[str]:
        return self._alt_by_number.get(number)
