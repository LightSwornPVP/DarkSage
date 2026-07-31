"""CLI entry point for the DarkSage publication DOCX/PDF generator.

Usage:
    scripts/publication/.venv/Scripts/python.exe scripts/publication/docgen/generate.py \
        --source docs/publication/DARKSAGE_EXECUTIVE_PRODUCT_PLAN.md \
        --doc-id DSF-004 --short-title "Executive Product Plan" \
        --out-dir docs/publication/releases/

Deterministic: the only "generated" timestamp written into either artifact
is the real git baseline commit (and that commit's own commit date) via
_repo.git_head() -- never a wall-clock "now". Running this twice against an
unchanged working tree and HEAD produces byte-identical output (verified by
scripts/publication/tests/test_docgen.py).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PUB_DIR = _THIS_DIR.parent
if str(_PUB_DIR) not in sys.path:
    sys.path.insert(0, str(_PUB_DIR))

import _repo  # noqa: E402

from docgen.docx_render import render_docx  # noqa: E402
from docgen.parser import parse_markdown_file  # noqa: E402
from docgen.pdf_render import render_pdf  # noqa: E402


def _git_commit_date(repo_root: Path, commit: str) -> str:
    """Real commit date (ISO-8601) for the given commit -- never wall-clock
    "now". Falls back to the bare commit hash if git metadata is
    unavailable for any reason (never fabricates a date)."""
    try:
        result = subprocess.run(
            ["git", "show", "-s", "--format=%cI", commit],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
        date = result.stdout.strip()
        if result.returncode == 0 and date:
            return date
    except (OSError, subprocess.SubprocessError):
        pass
    return f"(commit {commit}, date unavailable)"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate a DarkSage DSF-NNN DOCX/PDF release artifact.")
    parser.add_argument("--source", required=True, help="Repository-relative path to the controlled Markdown source.")
    parser.add_argument("--doc-id", required=True, help="Document ID, e.g. DSF-004 (used for header/footer/cover).")
    parser.add_argument("--short-title", default=None, help="Short title for the running header (defaults to the document's own H1).")
    parser.add_argument("--out-dir", default="docs/publication/releases", help="Repository-relative output directory.")
    parser.add_argument("--formats", default="docx,pdf", help="Comma-separated subset of: docx,pdf")
    args = parser.parse_args(argv)

    formats = {f.strip().lower() for f in args.formats.split(",") if f.strip()}
    unknown = formats - {"docx", "pdf"}
    if unknown:
        _repo.eprint(f"error: unknown format(s) {sorted(unknown)}; expected docx and/or pdf")
        return 2

    source_path = _repo.resolve_repo_path(args.source)
    if not source_path.is_file():
        _repo.eprint(f"error: source file not found: {_repo.repo_relative(source_path)}")
        return 2

    out_dir = _repo.resolve_repo_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model = parse_markdown_file(source_path)
    if model.doc_id and model.doc_id != args.doc_id:
        _repo.eprint(
            f"warning: --doc-id {args.doc_id!r} differs from the source's own "
            f"Document Control 'Document ID' field {model.doc_id!r}; using --doc-id for filenames/headers."
        )
    model.doc_id = args.doc_id

    baseline_commit = _repo.git_head()
    generation_date = _git_commit_date(_repo.REPO_ROOT, baseline_commit)
    short_title = args.short_title or model.title

    written = []
    if "docx" in formats:
        docx_path = out_dir / f"{args.doc_id}.docx"
        render_docx(model, docx_path, _repo.REPO_ROOT, generation_date, baseline_commit, short_title=short_title)
        written.append((docx_path, _repo.sha256_of_file(docx_path)))
    if "pdf" in formats:
        pdf_path = out_dir / f"{args.doc_id}.pdf"
        pages = render_pdf(model, pdf_path, _repo.REPO_ROOT, generation_date, baseline_commit, short_title=short_title)
        written.append((pdf_path, _repo.sha256_of_file(pdf_path)))
        print(f"{_repo.repo_relative(pdf_path)}: {pages} pages")

    for path, digest in written:
        print(f"{_repo.repo_relative(path)}  sha256={digest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
