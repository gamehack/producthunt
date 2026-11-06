"""Validate OpenAI Agents SDK wiring and manual JSON validation without provider calls."""

import json
from types import SimpleNamespace

import pytest

from qjai_producthunt.runtimes import AgentTask, OpenAIAgentRuntime
from qjai_producthunt.schemas import AIRelation, AIScreeningResult


def _valid_output():
    return {"items": [{
        "product_id": "sample-1",
        "category": "AI_CORE",
        "confidence": 0.99,
        "reason": "A sample synthetic agent product",
    }]}


@pytest.mark.asyncio
async def test_openai_adapter_uses_text_output_and_validates_json(monkeypatch):
    import agents

    observations = []

    async def fake_run(agent, input, max_turns):
        observations.append((agent, input, max_turns))
        fenced = chr(96) * 3 + "json" + chr(10) + json.dumps(_valid_output()) + chr(10) + chr(96) * 3
        return SimpleNamespace(final_output=fenced)

    monkeypatch.setattr(agents.Runner, "run", staticmethod(fake_run))
    runtime = OpenAIAgentRuntime("https://model.invalid/v1", "dummy-test-only", "minimax-m3")
    result = await runtime.generate(AgentTask("screening", "Classify provided products",
        {"products": [{"external_id": "sample-1", "name": "Agent Test"}]}), AIScreeningResult)

    assert result.items[0].category == AIRelation.CORE
    agent, task_input, max_turns = observations[0]
    assert isinstance(agent, agents.Agent)
    assert isinstance(agent.model, agents.OpenAIChatCompletionsModel)
    assert agent.model.model == "minimax-m3"
    assert agent.output_type is str
    assert "JSON Schema" in agent.instructions
    assert json.loads(task_input)["products"][0]["external_id"] == "sample-1"
    assert max_turns == 4


@pytest.mark.asyncio
async def test_openai_adapter_rejects_invalid_json_with_clear_error(monkeypatch):
    import agents

    async def fake_run(agent, input, max_turns):
        return SimpleNamespace(final_output="This is not JSON")

    monkeypatch.setattr(agents.Runner, "run", staticmethod(fake_run))
    runtime = OpenAIAgentRuntime("https://model.invalid/v1", "dummy-test-only", "minimax-m3")
    with pytest.raises(ValueError, match="JSON object"):
        await runtime.generate(AgentTask("screening", "Classify provided products", {}), AIScreeningResult)
