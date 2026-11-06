import pytest

from qjai_producthunt.article import article_title, render_markdown
from qjai_producthunt.schemas import ArticleDraft, ArticleSection


def test_published_title_uses_full_budget_without_column_prefix():
    title = article_title("产品猎人日报｜AI 代理不只会写代码：后端也值得重做")
    assert title == "AI 代理不只会写代码：后端也值得重做"
    assert "产品猎人日报｜" not in title
    assert len(title.encode("utf-8")) <= 64


def test_title_cleans_historic_prefixes_and_trailing_punctuation():
    title = article_title("AI创业情报｜产品猎人日报｜AI Agent 的新机会：")
    assert title == "AI Agent 的新机会"


def test_title_does_not_cut_long_headlines_into_incomplete_phrases():
    subject = "AI 代理别只会写代码：后端、调度、运维和数据工作流的机会"
    assert len(subject.encode("utf-8")) > 64
    with pytest.raises(ValueError, match="rewrite it instead of truncating"):
        article_title(subject)


def test_exact_title_byte_budget_and_english_ending():
    title = article_title("测" * 21 + "A")
    assert len(title.encode("utf-8")) == 64
    assert title.endswith("A")
    assert article_title("AI Agent in Action") == "AI Agent in Action"


def test_markdown_keeps_all_evidence_for_notion_authoritative_article():
    source = "https://www.producthunt.com/products/render?utm_source=api"
    article = ArticleDraft(
        title_subject="机会", digest="摘要", lead="资料限制：未经独立核验。",
        sections=[ArticleSection(heading="工具", paragraphs=["有关市场需求的假设。"], source_urls=[source])],
        conclusion="首先验证真实需求。",
    )
    markdown = render_markdown(article, "原创标题")
    assert markdown.startswith("# 原创标题\n")
    assert "资料限制" in markdown
    assert source in markdown
    assert "资料来源：" in markdown
