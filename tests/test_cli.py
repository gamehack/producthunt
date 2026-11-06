from argparse import Namespace
from pathlib import Path

import pytest

from qjai_producthunt.cli import _execute, parser


@pytest.mark.asyncio
async def test_operational_cli_rejects_fixture_source_before_network(monkeypatch):
    monkeypatch.setenv("PRODUCTHUNT_SOURCE", "fixture")
    monkeypatch.setattr("qjai_producthunt.settings.load_dotenv", lambda *args, **kwargs: None)
    with pytest.raises(PermissionError, match="official Product Hunt source"):
        await _execute(Namespace(env=None, command="run", date=None))


def test_cli_has_no_wechat_or_cms_delivery_commands():
    help_text = parser().format_help()
    assert "run" in help_text
    assert "sync-notion" in help_text
    assert "write-draft" not in help_text
    assert "sync-cms" not in help_text


def test_cli_sync_notion_requires_explicit_date():
    with pytest.raises(SystemExit):
        parser().parse_args(["sync-notion"])
