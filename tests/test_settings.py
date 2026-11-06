from pathlib import Path

from qjai_producthunt.settings import Settings


def test_settings_default_to_producthunt_and_use_new_project_paths(monkeypatch):
    monkeypatch.setattr("qjai_producthunt.settings.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("PRODUCTHUNT_SOURCE", raising=False)
    monkeypatch.delenv("OMNIROUTE_MODEL", raising=False)
    settings = Settings.load(Path("/nonexistent/.env"))
    assert settings.source == "producthunt"
    assert settings.database_path == Path("data/producthunt.sqlite")
    assert settings.output_dir == Path("output")
    assert settings.opportunity_threshold == 60
    assert settings.max_research == 5
    assert settings.omni_model == "minimax-cn/MiniMax-M3"


def test_fixture_source_is_only_available_for_offline_tests(monkeypatch):
    monkeypatch.setattr("qjai_producthunt.settings.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("PRODUCTHUNT_SOURCE", "fixture")
    assert Settings.load(Path("/nonexistent/.env")).source == "fixture"


def test_settings_reject_invalid_threshold_and_research_limit(monkeypatch):
    monkeypatch.setattr("qjai_producthunt.settings.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("PRODUCTHUNT_OPPORTUNITY_THRESHOLD", "101")
    try:
        Settings.load(Path("/nonexistent/.env"))
        assert False, "invalid threshold must fail"
    except ValueError as exc:
        assert "between 0 and 100" in str(exc)
    monkeypatch.setenv("PRODUCTHUNT_OPPORTUNITY_THRESHOLD", "60")
    monkeypatch.setenv("PRODUCTHUNT_MAX_RESEARCH", "0")
    try:
        Settings.load(Path("/nonexistent/.env"))
        assert False, "invalid research limit must fail"
    except ValueError as exc:
        assert "between 1 and 20" in str(exc)
