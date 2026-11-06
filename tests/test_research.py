"""Only mocked network calls are used here; no PH website scraping or draft writes."""

import pytest

from qjai_producthunt.research import WebsiteEvidenceCollector
from qjai_producthunt.schemas import Product


def product(**overrides) -> Product:
    args = dict(
        external_id="42", rank=1, name="telemetry.dev",
        tagline="A telemetry platform", description="Product makers say it helps developers.",
        votes_count=123,
        product_hunt_url="https://www.producthunt.com/posts/telemetry-dev",
        website_url="https://www.producthunt.com/r/abc123",
    )
    args.update(overrides)
    return Product(**args)


@pytest.mark.asyncio
async def test_ph_api_website_redirect_does_not_get_scraped(monkeypatch):
    import qjai_producthunt.research as research

    async def unreachable(*args, **kwargs):
        raise AssertionError("PH website redirect must never be fetched")

    monkeypatch.setattr(research, "_safe_public_https", unreachable)
    evidence = await WebsiteEvidenceCollector().collect(product())
    assert len(evidence) == 1
    assert evidence[0].kind == "producthunt_api"
    assert evidence[0].url == "https://www.producthunt.com/posts/telemetry-dev"
    assert "未经过厂商官网或第三方独立核验" in evidence[0].excerpt
    assert "123" in evidence[0].excerpt


@pytest.mark.asyncio
async def test_non_public_ph_url_never_becomes_evidence():
    evidence = await WebsiteEvidenceCollector().collect(product(
        product_hunt_url="https://example.com/posts/telemetry-dev",
        website_url="",
    ))
    assert evidence == []


@pytest.mark.asyncio
async def test_vendor_robots_denied_retains_attributed_api_listing(monkeypatch):
    import qjai_producthunt.research as research

    async def safe_url(_url):
        return None

    class FakeResponse:
        status_code = 403

    class FakeClient:
        def __init__(self, **_kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def get(self, url):
            assert url == "https://vendor.example/robots.txt"
            return FakeResponse()

    monkeypatch.setattr(research, "_safe_public_https", safe_url)
    monkeypatch.setattr(research.httpx, "AsyncClient", FakeClient)
    evidence = await WebsiteEvidenceCollector().collect(product(
        website_url="https://vendor.example/",
    ))
    assert len(evidence) == 1
    assert evidence[0].kind == "producthunt_api"


@pytest.mark.asyncio
async def test_vendor_html_evidence_included_alongside_api_listing(monkeypatch):
    import qjai_producthunt.research as research

    async def safe_url(_url):
        return None

    class FakeResponse:
        def __init__(self, status_code, *, body="", content_type="text/html"):
            self.status_code = status_code
            self.text = body
            self.content = body.encode()
            self.headers = {"content-type": content_type}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def get(self, url):
            if url.endswith("/robots.txt"):
                return FakeResponse(404)
            assert url == "https://vendor.example/"
            return FakeResponse(200, body="<html><head><title>Vendor</title></head><body><main>Official product documentation</main></body></html>")

    monkeypatch.setattr(research, "_safe_public_https", safe_url)
    monkeypatch.setattr(research.httpx, "AsyncClient", FakeClient)
    evidence = await WebsiteEvidenceCollector().collect(product(
        website_url="https://vendor.example/",
    ))
    assert [e.kind for e in evidence] == ["product_official", "producthunt_api"]
    assert evidence[0].url == "https://vendor.example/"
    assert "Official product documentation" in evidence[0].excerpt
