from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from qjai_producthunt.research import FixtureEvidenceCollector
from qjai_producthunt.runtimes import AgentTask, DemoRuntime
from qjai_producthunt.schemas import AIScreeningResult, OpportunityScreeningResult, Product, ArticleDraft, ArticleSection, HeadlineProposal
from qjai_producthunt.settings import Settings
from qjai_producthunt.sources import FixtureProductSource
from qjai_producthunt.storage import StepStore
from qjai_producthunt.pipeline import DailyPipeline, _select_research_candidates


@pytest.mark.asyncio
async def test_offline_unit_workflow_and_resume(tmp_path: Path, monkeypatch):
    # Fixture mode is retained for isolated unit tests only; the production CLI rejects it.
    monkeypatch.setenv("PRODUCTHUNT_SOURCE", "fixture")
    cfg = replace(Settings.load(tmp_path / "missing.env"),
        fixture_path=Path("tests/fixtures/product_hunt_20.json"),
        database_path=tmp_path / "db.sqlite", output_dir=tmp_path / "output")
    pipeline = DailyPipeline(cfg, DemoRuntime(), FixtureProductSource(cfg.fixture_path),
                             FixtureEvidenceCollector(), StepStore(cfg.database_path))
    day = date(2026, 10, 25)
    first = await pipeline.run(day)
    assert first.run_id == "producthunt:v1:demo:2026-10-25"
    assert first.initial_products == 20
    assert first.ai_related_products >= 5
    # Demo scoring is 85 for every AI-related fixture, so >5 all qualify and all are researched.
    assert first.researched_products == first.ai_related_products
    assert Path(first.article_json_path).is_file()
    assert Path(first.markdown_path).is_file()
    assert not (cfg.output_dir / day.isoformat() / "cover.jpg").exists()
    second = await pipeline.run(day)
    assert first == second


def test_pipeline_run_has_no_channel_delivery_switch():
    import inspect
    parameters = inspect.signature(DailyPipeline.run).parameters
    assert list(parameters) == ["self", "day"]


class CountingRuntime(DemoRuntime):
    def __init__(self, *, incomplete_first=False):
        self.calls = []
        self.incomplete_first = incomplete_first

    async def generate(self, task, output_type):
        if output_type in (AIScreeningResult, OpportunityScreeningResult):
            ids = [p["external_id"] for p in task.payload["products"]]
            self.calls.append((task.name, ids))
        result = await super().generate(task, output_type)
        if (self.incomplete_first and task.name == "ai_screening"
                and len([c for c in self.calls if c[0] == "ai_screening"]) == 1):
            # Model changes a product ID and duplicates another: neither can be accepted.
            rows = [r.model_copy() for r in result.items]
            rows[0].product_id = "invalid-model-id"
            rows.append(rows[1].model_copy())
            return AIScreeningResult(items=rows)
        return result


@pytest.mark.asyncio
async def test_ai_screening_salvages_partial_checkpoint_and_only_rescreens_missing(tmp_path: Path):
    products = await FixtureProductSource(
        Path("tests/fixtures/product_hunt_20.json")
    ).top20(date(2026, 10, 31))
    cfg = replace(Settings.load(tmp_path / "missing.env"),
        source="fixture", database_path=tmp_path / "db.sqlite",
        output_dir=tmp_path / "output")
    store = StepStore(cfg.database_path)
    old = await DemoRuntime().generate(AgentTask("ai_screening", "", {
        "products": [p.model_dump() for p in products[:17]],
    }), AIScreeningResult)
    run_id = "producthunt:v1:demo:2026-10-31"
    store.save(run_id, "ai_screening", old.model_dump(mode="json"))
    runtime = CountingRuntime()
    wf = DailyPipeline(cfg, runtime, FixtureProductSource(
        Path("tests/fixtures/product_hunt_20.json")), FixtureEvidenceCollector(), store)

    first = await wf.run(date(2026, 10, 31))
    assert first.initial_products == 20
    ai_calls = [ids for name, ids in runtime.calls if name == "ai_screening"]
    assert len(ai_calls) == 1
    assert ai_calls[0] == [p.external_id for p in products[17:]]
    saved = store.read(run_id, "ai_screening:validated_v1")
    assert {item["product_id"] for item in saved["items"]} == {
        p.external_id for p in products}
    calls_before = len(runtime.calls)
    await wf.run(date(2026, 10, 31))
    assert len(runtime.calls) == calls_before


@pytest.mark.asyncio
async def test_rescreen_only_invalid_or_duplicate_ids_and_resume_without_replays(tmp_path: Path):
    cfg = replace(Settings.load(tmp_path / "missing.env"),
        source="fixture", database_path=tmp_path / "db.sqlite",
        output_dir=tmp_path / "output")
    store = StepStore(cfg.database_path)
    runtime = CountingRuntime(incomplete_first=True)
    wf = DailyPipeline(cfg, runtime, FixtureProductSource(
        Path("tests/fixtures/product_hunt_20.json")), FixtureEvidenceCollector(), store)
    products = await wf.source.top20(date(2026, 10, 31))
    run_id = "producthunt:v1:demo:2026-10-31"

    ai = await wf._complete_product_decisions(
        run_id, "ai_screening", products, AIScreeningResult, "Classify AI")
    assert len(ai.items) == 20
    assert [x.product_id for x in ai.items] == [p.external_id for p in products]
    calls = [ids for name, ids in runtime.calls if name == "ai_screening"]
    assert len(calls) == 5  # Initial five, retry two, then three five-item chunks
    assert len(calls[0]) == 5
    assert calls[1] == [products[0].external_id, products[1].external_id]
    assert all(len(chunk) <= 5 for chunk in calls)
    await wf._complete_product_decisions(
        run_id, "ai_screening", products, AIScreeningResult, "Classify AI")
    assert len([ids for name, ids in runtime.calls if name == "ai_screening"]) == 5


@pytest.mark.asyncio
async def test_opportunity_partial_checkpoint_is_repaired_without_scoring_all_again(tmp_path: Path):
    products = await FixtureProductSource(
        Path("tests/fixtures/product_hunt_20.json")
    ).top20(date(2026, 10, 31))
    selected = products[:8]
    cfg = replace(Settings.load(tmp_path / "missing.env"),
        source="fixture", database_path=tmp_path / "db.sqlite")
    store = StepStore(cfg.database_path)
    run_id = "producthunt:v1:demo:2026-10-31"
    partial = await DemoRuntime().generate(AgentTask("opportunity_screening", "", {
        "products": [p.model_dump() for p in selected[:6]],
    }), OpportunityScreeningResult)
    store.save(run_id, "opportunity_screening", partial.model_dump(mode="json"))
    runtime = CountingRuntime()
    wf = DailyPipeline(cfg, runtime, FixtureProductSource(
        Path("tests/fixtures/product_hunt_20.json")), FixtureEvidenceCollector(), store)

    result = await wf._complete_product_decisions(
        run_id, "opportunity_screening", selected,
        OpportunityScreeningResult, "Score products")
    assert len(result.items) == 8
    assert [ids for name, ids in runtime.calls if name == "opportunity_screening"] == [
        [p.external_id for p in selected[6:]]
    ]



def _products(count: int) -> list[Product]:
    return [
        Product(external_id=f"p{i}", rank=i + 1, name=f"Product {i}")
        for i in range(count)
    ]


def test_research_selection_uses_top_five_when_five_or_fewer_score_above_60():
    products = _products(9)
    scores = {
        "p0": 75, "p1": 69, "p2": 60, "p3": 58, "p4": 57,
        "p5": 55, "p6": 50, "p7": 45, "p8": 40,
    }
    selected = _select_research_candidates(products, scores, threshold=60, limit=5)
    assert [p.external_id for p in selected] == ["p0", "p1", "p2", "p3", "p4"]


def test_research_selection_includes_all_when_more_than_five_score_above_60():
    # Real October 31 Product Hunt scoring values supplied in the live diagnostic.
    products = _products(13)
    scores = {
        "p0": 75, "p1": 69, "p2": 67, "p3": 67, "p4": 66,
        "p5": 61, "p6": 60, "p7": 60, "p8": 60, "p9": 59,
        "p10": 52, "p11": 49, "p12": 40,
    }
    selected = _select_research_candidates(products, scores, threshold=60, limit=5)
    assert [p.external_id for p in selected] == [
        "p0", "p1", "p2", "p3", "p4", "p5"
    ]


def test_research_selection_strictly_greater_than_60_and_ties_by_rank():
    products = _products(7)
    scores = {
        "p0": 80, "p1": 70, "p2": 66, "p3": 66, "p4": 61,
        "p5": 60, "p6": 59,
    }
    selected = _select_research_candidates(products, scores, threshold=60, limit=5)
    assert [p.external_id for p in selected] == ["p0", "p1", "p2", "p3", "p4"]


def test_research_selection_returns_all_above_60_without_five_item_cap():
    products = _products(8)
    scores = {
        "p0": 100, "p1": 99, "p2": 98, "p3": 97, "p4": 96,
        "p5": 95, "p6": 94, "p7": 60,
    }
    selected = _select_research_candidates(products, scores, threshold=60, limit=5)
    assert len(selected) == 7



def _article_for_headline(title: str) -> ArticleDraft:
    return ArticleDraft(title_subject=title, digest="产品分析",
        lead="今天分析 AI Agent 与后端系统的真实应用机会。",
        sections=[ArticleSection(heading="后端工作流机会", paragraphs=["该方向值得验证。"])],
        conclusion="应该从明确的用户问题入手。")


class HeadlineOnlyRuntime(DemoRuntime):
    def __init__(self, proposals):
        self.proposals = list(proposals)
        self.calls = []

    async def generate(self, task, output_type):
        if output_type is not HeadlineProposal:
            raise AssertionError("Headline-only repair must not regenerate the article")
        self.calls.append((task.name, task.payload))
        return HeadlineProposal(title=self.proposals[len(self.calls) - 1])


@pytest.mark.asyncio
async def test_overlong_headline_rewritten_without_regenerating_article_and_cached(tmp_path):
    cfg = replace(Settings.load(tmp_path / "missing.env"),
                  source="fixture", database_path=tmp_path / "headlines.sqlite")
    store = StepStore(cfg.database_path)
    runtime = HeadlineOnlyRuntime([
        "AI 代理别只会写代码：后端、调度和运营工作流都值得重新做",
        "AI Agent 创业机会不止写代码",
    ])
    wf = DailyPipeline(cfg, runtime, None, None, store)
    article = _article_for_headline(
        "AI 代理别只会写代码：后端、调度、运维和数据工作流的机会")
    title = await wf._resolve_headline("existing:real:run", article)
    assert title == "AI Agent 创业机会不止写代码"
    assert len(runtime.calls) == 2
    assert all(name == "headline-editor" for name, _ in runtime.calls)
    assert all("maximum_utf8_bytes" in payload for _, payload in runtime.calls)

    # Existing valid repair checkpoint avoids even the title model on rerun.
    again = await wf._resolve_headline("existing:real:run", article)
    assert again == title
    assert len(runtime.calls) == 2
    assert store.read("existing:real:run", "headline:no_prefix_v5")["title"] == title


@pytest.mark.asyncio
async def test_short_original_headline_no_extra_model_call(tmp_path):
    cfg = replace(Settings.load(tmp_path / "missing.env"),
                  source="fixture", database_path=tmp_path / "headlines.sqlite")
    runtime = HeadlineOnlyRuntime([])
    wf = DailyPipeline(cfg, runtime, None, None, StepStore(cfg.database_path))
    article = _article_for_headline("产品猎人日报｜后端 AI Agent 值得关注")
    title = await wf._resolve_headline("another:run", article)
    assert title == "后端 AI Agent 值得关注"
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_invalid_headline_rewrites_fail_without_checkpoint(tmp_path):
    cfg = replace(Settings.load(tmp_path / "missing.env"),
                  source="fixture", database_path=tmp_path / "headlines.sqlite")
    store = StepStore(cfg.database_path)
    runtime = HeadlineOnlyRuntime(["超长标题" * 25] * 3)
    wf = DailyPipeline(cfg, runtime, None, None, store)
    article = _article_for_headline("超长原始标题" * 20)
    with pytest.raises(ValueError, match="article generation failed"):
        await wf._resolve_headline("another:invalid:run", article)
    assert len(runtime.calls) == 3
    assert store.read("another:invalid:run", "headline:no_prefix_v5") is None
