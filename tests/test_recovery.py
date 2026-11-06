"""Validate local saved article artifacts for Notion recovery."""

from datetime import date
from pathlib import Path
import json

import pytest

from qjai_producthunt.recovery import read_saved_article
from qjai_producthunt.article import render_markdown
from qjai_producthunt.schemas import ArticleDraft, ArticleSection


DAY = date(2026, 10, 31)


def write_article(root: Path, *, source="producthunt", date_label="2026-10-31") -> Path:
    folder = root / DAY.isoformat()
    folder.mkdir(parents=True)
    article = ArticleDraft(
        title_subject="AI 创业机会", digest="独立创业项目观察", lead="基于真实资料。",
        sections=[ArticleSection(heading="案例", paragraphs=["关注可核实的事实。"],
                                 source_urls=["https://example.com/case"])],
        conclusion="需要验证客户是否愿意付费。",
    )
    title = "AI 创业机会"
    (folder / "article.json").write_text(json.dumps({
        "title": title, "snapshot_date": date_label, "source": source,
        "article": article.model_dump(mode="json"), "research": [],
    }, ensure_ascii=False), encoding="utf8")
    (folder / "article.md").write_text(render_markdown(article, title), encoding="utf8")
    return folder


def test_reads_verified_real_article_for_notion_recovery(tmp_path):
    write_article(tmp_path)
    data = read_saved_article(tmp_path, DAY)
    assert data["title"] == "AI 创业机会"
    assert "https://example.com/case" in data["markdown"]
    assert "source" not in data


@pytest.mark.parametrize("source,date_label", [
    ("fixture", "2026-10-31"), ("demo", "2026-10-31"),
    ("producthunt", "2026-10-30"),
])
def test_rejects_nonproduction_or_wrong_date(tmp_path, source, date_label):
    write_article(tmp_path, source=source, date_label=date_label)
    with pytest.raises(ValueError):
        read_saved_article(tmp_path, DAY)


def test_rejects_markdown_that_differs_from_article_json(tmp_path):
    folder = write_article(tmp_path)
    (folder / "article.md").write_text("tampered", encoding="utf8")
    with pytest.raises(ValueError, match="differs"):
        read_saved_article(tmp_path, DAY)


def test_rejects_symlink_file(tmp_path):
    folder = write_article(tmp_path)
    body = folder / "article.md"
    body.unlink()
    body.symlink_to(folder / "article.json")
    with pytest.raises(ValueError, match="regular"):
        read_saved_article(tmp_path, DAY)


