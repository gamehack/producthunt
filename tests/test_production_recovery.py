"""Production incident: unverifiable model URLs and transient OmniRoute 524."""
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import InternalServerError

from qjai_producthunt.pipeline import _filter_article_citations
from qjai_producthunt.runtimes import AgentTask, OpenAIAgentRuntime
from qjai_producthunt.schemas import ArticleDraft, ArticleSection, AIScreeningResult


def _article(urls):
    return ArticleDraft(
        title_subject="可验证的 AI 创业机会",
        digest="仅基于已有来源",
        lead="来自 Product Hunt 的产品研究",
        sections=[ArticleSection(heading="观察", paragraphs=["证据必须可追溯"], source_urls=urls)],
        conclusion="谨慎评估",
    )


def test_unverified_model_links_are_removed_but_provenance_is_preserved():
    known = "https://producthunt.com/posts/known"
    invented = "https://invented.invalid/hallucination"
    article, count = _filter_article_citations(_article([known, invented]), {known})
    assert count == 1
    assert article.sections[0].source_urls == [known]
    assert invented not in json.dumps(article.model_dump())


def test_no_unverified_link_is_ever_made_into_evidence():
    article, count = _filter_article_citations(
        _article(["https://untrusted.invalid/item"]), set(),
    )
    assert count == 1
    assert article.sections[0].source_urls == []  # Caller fails closed if all are empty.


@pytest.mark.asyncio
async def test_transient_http_524_gets_one_bounded_model_only_retry(monkeypatch):
    import agents
    import qjai_producthunt.runtimes as runtimes

    calls = 0
    sleeps = []

    async def fake_run(agent, payload, max_turns):
        nonlocal calls
        calls += 1
        if calls == 1:
            response = httpx.Response(
                524, request=httpx.Request("POST", "https://model.invalid/v1/chat/completions"),
            )
            raise InternalServerError("transient upstream timeout", response=response, body=None)
        return SimpleNamespace(final_output=json.dumps({"items": [{
            "product_id": "test-1", "category": "AI_CORE", "confidence": 0.9,
            "reason": "AI is core functionality",
        }]}))

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(agents.Runner, "run", staticmethod(fake_run))
    monkeypatch.setattr(runtimes.asyncio, "sleep", fake_sleep)
    runtime = OpenAIAgentRuntime("https://model.invalid/v1", "dummy-key", "minimax-m3")
    result = await runtime.generate(AgentTask("classify", "Classify", {
        "products": [{"external_id": "test-1"}],
    }), AIScreeningResult)
    assert result.items[0].product_id == "test-1"
    assert calls == 2
    assert sleeps == [8]
