"""Read a verified local Product Hunt artifact for Notion-only recovery.

The producer may read only bounded, locally saved JSON and Markdown artifacts.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from .article import render_markdown
from .schemas import ArticleDraft


def _regular_text(path: Path, maximum: int) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("Expected a bounded, regular article artifact")
    return path.read_text(encoding="utf-8")


def read_saved_article(output_dir: Path, day: date) -> dict[str, str]:
    folder = output_dir / day.isoformat()
    raw = _regular_text(folder / "article.json", 300_000)
    markdown = _regular_text(folder / "article.md", 190_000)
    doc = json.loads(raw)
    if not isinstance(doc, dict) or doc.get("source") != "producthunt" or doc.get("snapshot_date") != day.isoformat():
        raise ValueError("Saved article identity is not a real Product Hunt day")
    title = doc.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("Saved article title is invalid")
    article = ArticleDraft.model_validate(doc.get("article"))
    if not article.digest.strip() or len(article.digest) > 2_000:
        raise ValueError("Saved article summary is invalid")
    if markdown != render_markdown(article, title):
        raise ValueError("Saved Markdown differs from the validated article JSON")
    if not markdown.strip() or len(markdown.encode("utf-8")) > 180_000:
        raise ValueError("Saved article Markdown is invalid or oversized")
    return {"title": title, "markdown": markdown}
