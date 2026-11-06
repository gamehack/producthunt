"""CLI for the standalone Product Hunt -> Notion READY producer."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .notion_sync import EXPECTED_PARENT_PAGE_ID, sync_article
from .pipeline import DailyPipeline
from .recovery import read_saved_article
from .research import WebsiteEvidenceCollector
from .runtimes import OpenAIAgentRuntime
from .settings import Settings
from .sources import ProductHuntSource
from .storage import StepStore


def _default_day() -> date:
    """Most recently completed Product Hunt calendar day in Los Angeles."""
    return datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=1)


def _require_notion_config() -> None:
    if os.getenv("NOTION_ENABLE_SYNC", "").strip().lower() != "true":
        raise PermissionError("NOTION_ENABLE_SYNC must be true")
    if os.getenv("NOTION_AUTOSYNC_AFTER_GENERATION", "").strip().lower() != "true":
        raise PermissionError("NOTION_AUTOSYNC_AFTER_GENERATION must be true")
    if len(os.getenv("NOTION_API_KEY", "").strip()) < 20:
        raise ValueError("NOTION_API_KEY is required")
    if os.getenv("NOTION_PARENT_PAGE_ID", "").strip().lower() != EXPECTED_PARENT_PAGE_ID:
        raise PermissionError("NOTION_PARENT_PAGE_ID must be the allowlisted Notion 08 page")


def _require_production_config(settings: Settings) -> None:
    if settings.source != "producthunt":
        raise PermissionError("Production runs accept only the official Product Hunt source")
    if not settings.ph_token:
        raise ValueError("PRODUCT_HUNT_TOKEN is required")
    if not settings.ph_commercial_authorized:
        raise PermissionError("PRODUCT_HUNT_COMMERCIAL_AUTHORIZED must be true")
    if not all((settings.omni_base_url, settings.omni_api_key, settings.omni_model)):
        raise ValueError("OMNIROUTE_BASE_URL, OMNIROUTE_API_KEY and OMNIROUTE_MODEL are required")
    _require_notion_config()

async def _execute(args: argparse.Namespace) -> dict[str, object]:
    settings = Settings.load(args.env)
    if args.command == "sync-notion":
        if settings.source != "producthunt" or not settings.ph_commercial_authorized:
            raise PermissionError("Notion recovery requires a validated Product Hunt article")
        _require_notion_config()
        day = date.fromisoformat(args.date)
        if day.isoformat() != args.date:
            raise ValueError("Date must be canonical YYYY-MM-DD")
        saved = read_saved_article(settings.output_dir, day)
        result = sync_article(
            source_key=f"producthunt:{day.isoformat()}",
            title=f"{day.isoformat()}｜{saved['title']}",
            unique_prefix=f"{day.isoformat()}｜",
            markdown=saved["markdown"],
        )
        return result

    _require_production_config(settings)
    day = date.fromisoformat(args.date) if args.date else _default_day()
    runtime = OpenAIAgentRuntime(
        settings.omni_base_url, settings.omni_api_key, settings.omni_model
    )
    source = ProductHuntSource(
        settings.ph_token, commercial_authorized=settings.ph_commercial_authorized
    )
    pipeline = DailyPipeline(
        settings, runtime, source, WebsiteEvidenceCollector(),
        StepStore(settings.database_path),
    )
    result = await pipeline.run(day)
    return result.model_dump(mode="json")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="producthunt",
        description="Product Hunt opportunity research -> verified Notion READY article",
    )
    root.add_argument("--env", help="Private .env file path; defaults to ./.env")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Generate the latest completed Product Hunt day")
    run.add_argument("--date", help="Explicit Product Hunt date, YYYY-MM-DD (America/Los_Angeles)")
    recover = commands.add_parser("sync-notion", help="Recover a validated local article into Notion")
    recover.add_argument("--date", required=True, help="Exact Product Hunt date, YYYY-MM-DD")
    return root


def main() -> None:
    root = parser()
    try:
        args = root.parse_args()
        result = asyncio.run(_execute(args))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (PermissionError, ValueError, RuntimeError, OSError) as exc:
        root.exit(2, f"producthunt: {exc}\n")


if __name__ == "__main__":
    main()
