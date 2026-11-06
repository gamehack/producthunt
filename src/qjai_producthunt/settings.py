"""Small, explicit environment contract for the standalone Product Hunt producer."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    if raw not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true or false")
    return raw in {"true", "1", "yes"}


@dataclass(frozen=True)
class Settings:
    source: str
    fixture_path: Path
    database_path: Path
    output_dir: Path
    opportunity_threshold: int
    max_research: int
    ph_token: str
    ph_commercial_authorized: bool
    omni_base_url: str
    omni_api_key: str
    omni_model: str

    @classmethod
    def load(cls, env_path: Path | None = None) -> "Settings":
        if env_path is None:
            load_dotenv(override=False)
        else:
            load_dotenv(env_path, override=False)
        result = cls(
            source=os.getenv("PRODUCTHUNT_SOURCE", "producthunt").strip(),
            fixture_path=Path("tests/fixtures/product_hunt_20.json"),
            database_path=Path(os.getenv("PRODUCTHUNT_DB_PATH", "data/producthunt.sqlite")),
            output_dir=Path(os.getenv("PRODUCTHUNT_OUTPUT_DIR", "output")),
            opportunity_threshold=int(os.getenv("PRODUCTHUNT_OPPORTUNITY_THRESHOLD", "60")),
            max_research=int(os.getenv("PRODUCTHUNT_MAX_RESEARCH", "5")),
            ph_token=os.getenv("PRODUCT_HUNT_TOKEN", "").strip(),
            ph_commercial_authorized=_flag("PRODUCT_HUNT_COMMERCIAL_AUTHORIZED"),
            omni_base_url=os.getenv("OMNIROUTE_BASE_URL", "").strip(),
            omni_api_key=os.getenv("OMNIROUTE_API_KEY", "").strip(),
            omni_model=os.getenv("OMNIROUTE_MODEL", "minimax-m3").strip(),
        )
        if result.source not in {"producthunt", "fixture"}:
            raise ValueError("PRODUCTHUNT_SOURCE must be producthunt")
        if not 0 <= result.opportunity_threshold <= 100:
            raise ValueError("PRODUCTHUNT_OPPORTUNITY_THRESHOLD must be between 0 and 100")
        if not 1 <= result.max_research <= 20:
            raise ValueError("PRODUCTHUNT_MAX_RESEARCH must be between 1 and 20")
        return result
