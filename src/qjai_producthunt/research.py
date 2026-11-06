"""Conservative evidence collection with a traceable Product Hunt API fallback.

Product Hunt webpages are NEVER scraped. Its authorized API snapshot is already
available in Product records and may be cited as an attributed product listing,
not as independent verification of vendor claims.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import sys
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from .schemas import Evidence, Product


USER_AGENT = "QJAI-ProductHunt/1.0 (+contact: qjai.org; respects robots.txt)"
_PRODUCT_HUNT_HOSTS = {"producthunt.com", "www.producthunt.com"}


def _producthunt_api_evidence(product: Product) -> list[Evidence]:
    """Attribute text to a real Product Hunt API post, without scraping its page."""
    parsed = urlsplit(product.product_hunt_url)
    if parsed.scheme != "https" or parsed.hostname not in _PRODUCT_HUNT_HOSTS:
        return []
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        return []
    parts = [
        f"产品名称：{product.name}",
        f"Product Hunt 标语（产品自述）：{product.tagline or '未提供'}",
        f"Product Hunt 描述（产品自述）：{(product.description or '未提供')[:2600]}",
    ]
    if product.votes_count is not None:
        parts.append(f"API 快照中的票数：{product.votes_count}（动态值，不代表实际收入或用户数）")
    parts.append(
        "以上是 Product Hunt 官方 API 提供的产品条目原始信息，"
        "其中产品功能、定价、商业模式等陈述未经过厂商官网或第三方独立核验；"
        "不能据此宣称销售额、付费用户数、市场规模或实际使用效果。"
    )
    return [Evidence(
        url=product.product_hunt_url,
        title=f"{product.name} — Product Hunt API 条目（非独立核验）",
        excerpt="；".join(parts),
        kind="producthunt_api",
    )]


def _note(product: Product, reason: str) -> None:
    # Deliberately omit URLs, response bodies and credentials from logs.
    print(f"evidence[{product.external_id}]: {reason}", file=sys.stderr, flush=True)


async def _safe_public_https(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Only public HTTPS websites are allowed")
    if parts.port not in {None, 443}:
        raise ValueError("Non-standard ports are not allowed")
    infos = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, 443, type=socket.SOCK_STREAM)
    if not infos or any(not ipaddress.ip_address(i[4][0]).is_global for i in infos):
        raise ValueError("Non-public IP address is forbidden")


class WebsiteEvidenceCollector:
    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled

    async def collect(self, product: Product) -> list[Evidence]:
        # Always include the authorized API listing as attributed primary input.
        # It is useful even when vendor-site evidence is blocked or unavailable.
        api_evidence = _producthunt_api_evidence(product)
        if not self.enabled or not product.website_url:
            _note(product, "no vendor website URL; using attributed Product Hunt API listing")
            return api_evidence

        parts = urlsplit(product.website_url)
        if parts.hostname in _PRODUCT_HUNT_HOSTS:
            # Post.website in the official API is a REDIRECT to a vendor website,
            # not necessarily the actual vendor domain. Do not scrape PH webpages
            # or treat a Product Hunt tracking redirect as the vendor's own site.
            _note(product, "API website is a Product Hunt redirect; using attributed API listing")
            return api_evidence

        try:
            await _safe_public_https(product.website_url)
            robots_url = f"https://{parts.hostname}/robots.txt"
            async with httpx.AsyncClient(
                timeout=12, headers={"User-Agent": USER_AGENT}, follow_redirects=False
            ) as client:
                robots_response = await client.get(robots_url)
                # RFC 9309: a missing robots policy (404) allows access;
                # other errors are conservatively treated as disallow.
                if robots_response.status_code not in {200, 404}:
                    _note(product, f"vendor robots status {robots_response.status_code}; using API listing")
                    return api_evidence
                if robots_response.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(robots_response.text.splitlines())
                    if not parser.can_fetch(USER_AGENT, product.website_url):
                        _note(product, "vendor robots disallows page; using API listing")
                        return api_evidence
                response = await client.get(product.website_url)
                if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
                    _note(product, f"vendor HTTP {response.status_code} or non-HTML; using API listing")
                    return api_evidence
                if len(response.content) > 2_000_000:
                    _note(product, "vendor response too large; using API listing")
                    return api_evidence
                soup = BeautifulSoup(response.text, "html.parser")
                for item in soup.select("script,style,nav,footer,header,iframe"):
                    item.decompose()
                title = (soup.title.get_text(" ", strip=True) if soup.title else product.name)[:150]
                excerpt = " ".join(soup.stripped_strings)[:6000]
                if not excerpt:
                    _note(product, "vendor HTML has no readable content; using API listing")
                    return api_evidence
                _note(product, "vendor webpage readable; including first-party evidence")
                vendor_evidence = Evidence(url=product.website_url, title=title, excerpt=excerpt)
                return [vendor_evidence, *api_evidence]
        except (ValueError, OSError, httpx.HTTPError, socket.gaierror) as exc:
            _note(product, f"vendor fetch failed ({type(exc).__name__}); using API listing")
            return api_evidence


class FixtureEvidenceCollector:
    """CI-only unit test helper; never selected by production CLI."""

    async def collect(self, product: Product) -> list[Evidence]:
        return [Evidence(url=product.website_url or "https://example.com/fixture",
                         title=product.name, excerpt="Synthetic test fixture, NOT verified research.",
                         kind="fixture")]
