from datetime import date
from pathlib import Path

import pytest

from qjai_producthunt.sources import (FixtureProductSource, ProductHuntSource,
                                       pacific_date_window, POSTS_QUERY)


@pytest.mark.asyncio
async def test_fixture_has_twenty_ranked_products():
    items = await FixtureProductSource(Path("tests/fixtures/product_hunt_20.json")).top20(date(2026, 10, 25))
    assert len(items) == 20
    assert [item.rank for item in items] == list(range(1, 21))
    assert len({item.external_id for item in items}) == 20


def test_date_window_observes_pacific_daylight_saving():
    summer_start, summer_end = pacific_date_window(date(2026, 7, 15))
    winter_start, winter_end = pacific_date_window(date(2026, 12, 15))
    assert "T07:00:00" in summer_start
    assert "T07:00:00" in summer_end
    assert "T08:00:00" in winter_start
    assert "T08:00:00" in winter_end


@pytest.mark.asyncio
async def test_api_refuses_commercial_use_without_permission():
    with pytest.raises(PermissionError, match="permission"):
        await ProductHuntSource("example", commercial_authorized=False).top20(date(2026, 10, 25))


def test_query_uses_ranking_featured_and_day():
    assert "order: RANKING" in POSTS_QUERY
    assert "featured: true" in POSTS_QUERY
    assert "postedAfter" in POSTS_QUERY and "postedBefore" in POSTS_QUERY
