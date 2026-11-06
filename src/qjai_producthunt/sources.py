"""Authorized Product Hunt API and deterministic fixture adapters."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from .schemas import Product


PACIFIC = ZoneInfo("America/Los_Angeles")
PH_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"


POSTS_QUERY = """
query DailyTop($after: DateTime!, $before: DateTime!) {
  posts(first: 20, featured: true, order: RANKING,
        postedAfter: $after, postedBefore: $before) {
    nodes {
      id name tagline description url website votesCount dailyRank
    }
  }
}
"""


def pacific_date_window(day: date) -> tuple[str, str]:
    start = datetime.combine(day, time.min, tzinfo=PACIFIC)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=PACIFIC)
    return (start.astimezone(timezone.utc).isoformat(),
            end.astimezone(timezone.utc).isoformat())


class FixtureProductSource:
    def __init__(self, path: Path):
        self.path = path

    async def top20(self, day: date) -> list[Product]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return _validate_top20([Product.model_validate(p) for p in data])


class ProductHuntSource:
    def __init__(self, token: str, *, commercial_authorized: bool):
        self.token = token
        self.commercial_authorized = commercial_authorized

    async def top20(self, day: date) -> list[Product]:
        if not self.commercial_authorized:
            raise PermissionError("Official Product Hunt API commercial permission is not confirmed")
        if not self.token:
            raise ValueError("PRODUCT_HUNT_TOKEN is required for authorized API access")
        after, before = pacific_date_window(day)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                PH_ENDPOINT,
                headers={"Authorization": f"Bearer {self.token}"},
                json={"query": POSTS_QUERY, "variables": {"after": after, "before": before}},
            )
            response.raise_for_status()
            payload = response.json()
        if payload.get("errors"):
            raise RuntimeError("Product Hunt API returned GraphQL errors")
        nodes = payload.get("data", {}).get("posts", {}).get("nodes", [])
        if not isinstance(nodes, list):
            raise ValueError("Product Hunt API response missing posts.nodes")
        products = [Product(
            external_id=str(node["id"]),
            rank=index,
            name=node["name"],
            tagline=node.get("tagline") or "",
            description=node.get("description") or "",
            product_hunt_url=node.get("url") or "",
            website_url=node.get("website") or "",
            votes_count=node.get("votesCount"),
        ) for index, node in enumerate(nodes, 1)]
        # An API query is a candidate for daily ranking. Compare its dailyRank
        # and featured listing with the website before enabling production.
        return _validate_top20(products)


def _validate_top20(products: list[Product]) -> list[Product]:
    if len(products) > 20:
        raise ValueError("Source returned more than 20 products")
    ids = [p.external_id for p in products]
    ranks = [p.rank for p in products]
    if len(set(ids)) != len(ids) or len(set(ranks)) != len(ranks):
        raise ValueError("Duplicate product ID or rank in daily source")
    if ranks != list(range(1, len(products) + 1)):
        raise ValueError("Source ranks must be consecutive starting at 1")
    return products
