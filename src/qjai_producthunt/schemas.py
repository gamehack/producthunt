"""Framework-neutral contracts shared by OpenAI and Claude adapters."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Product(BaseModel):
    external_id: str
    rank: int = Field(ge=1, le=20)
    name: str = Field(min_length=1)
    tagline: str = ""
    description: str = ""
    product_hunt_url: str = ""
    website_url: str = ""
    votes_count: int | None = None


class AIRelation(str, Enum):
    CORE = "AI_CORE"
    ENABLED = "AI_ENABLED"
    ECOSYSTEM = "AI_ECOSYSTEM"
    NON_AI = "NON_AI"
    UNCERTAIN = "UNCERTAIN"


class AIJudgement(BaseModel):
    product_id: str
    category: AIRelation
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=2)


class AIScreeningResult(BaseModel):
    items: list[AIJudgement]


class OpportunityScore(BaseModel):
    product_id: str
    market_need: int = Field(ge=0, le=25)
    monetization: int = Field(ge=0, le=25)
    solo_feasibility: int = Field(ge=0, le=20)
    ai_leverage: int = Field(ge=0, le=15)
    differentiation: int = Field(ge=0, le=15)
    reason: str = Field(min_length=2)
    caveat: str = ""

    @property
    def total(self) -> int:
        return sum((self.market_need, self.monetization, self.solo_feasibility,
                    self.ai_leverage, self.differentiation))


class OpportunityScreeningResult(BaseModel):
    items: list[OpportunityScore]


class Evidence(BaseModel):
    url: str
    title: str
    excerpt: str
    kind: str = "product_official"


class ResearchReport(BaseModel):
    product_id: str
    summary: str
    audience: str
    pain_point: str
    pricing: str
    business_model: str
    competitive_advantage: str
    opportunity: str
    risks: str
    verified_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class ArticleSection(BaseModel):
    heading: str
    paragraphs: list[str] = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list)


class HeadlineProposal(BaseModel):
    """Independent, full-sentence headline rewrite; never touch article body."""
    title: str = Field(min_length=1)


class ArticleDraft(BaseModel):
    title_subject: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    lead: str = Field(min_length=1)
    sections: list[ArticleSection] = Field(min_length=1)
    conclusion: str = Field(min_length=1)


class RunSummary(BaseModel):
    run_id: str
    snapshot_date: str
    source: str
    initial_products: int
    ai_related_products: int
    researched_products: int
    title: str
    article_json_path: str
    markdown_path: str
