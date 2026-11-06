"""Canonical article title validation and Markdown rendering for Notion."""

from __future__ import annotations

from .schemas import ArticleDraft

MAX_TITLE_BYTES = 64
_TRAILING_PUNCTUATION = " :：,，。.!！?？;；、-—|｜"


def article_title(subject: str) -> str:
    """Validate a complete downstream-compatible title; never truncate it."""
    title = subject.strip()
    changed = True
    while changed:
        changed = False
        for prefix in ("产品猎人日报｜", "AI创业情报｜", "AI 创业情报｜"):
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
                changed = True
    title = title.lstrip("｜|:：-— ").rstrip(_TRAILING_PUNCTUATION).strip()
    if not title:
        raise ValueError("Article title cannot be empty")
    size = len(title.encode("utf-8"))
    if size > MAX_TITLE_BYTES:
        raise ValueError(f"Article title exceeds {MAX_TITLE_BYTES} UTF-8 bytes ({size}); rewrite it instead of truncating")
    return title


def render_markdown(article: ArticleDraft, title: str) -> str:
    lines = [f"# {title}", "", article.lead, ""]
    for section in article.sections:
        lines.extend([f"## {section.heading}", ""])
        for paragraph in section.paragraphs:
            lines.extend([paragraph, ""])
        for url in section.source_urls:
            lines.append(f"- 资料来源：{url}")
        lines.append("")
    lines.extend(["## 创业观察", "", article.conclusion, ""])
    return "\n".join(lines)
