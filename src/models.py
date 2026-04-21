from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Ad:
    ad_id: str
    page_id: str
    page_name: str
    start_date: Optional[datetime]
    stop_date: Optional[datetime]
    is_active: bool
    creative_bodies: list[str] = field(default_factory=list)
    creative_link_titles: list[str] = field(default_factory=list)
    creative_link_descriptions: list[str] = field(default_factory=list)
    creative_link_captions: list[str] = field(default_factory=list)
    publisher_platforms: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    snapshot_url: Optional[str] = None

    @property
    def days_running(self) -> int:
        if self.start_date is None:
            return 0
        end = self.stop_date or datetime.now(timezone.utc)
        return max(0, (end - self.start_date).days)

    @property
    def primary_copy(self) -> str:
        if self.creative_bodies:
            return self.creative_bodies[0]
        if self.creative_link_descriptions:
            return self.creative_link_descriptions[0]
        return ""

    @property
    def primary_title(self) -> str:
        return self.creative_link_titles[0] if self.creative_link_titles else ""


@dataclass
class MarketAnalysis:
    query: str
    country: str
    total_ads: int
    unique_advertisers: int
    oldest_ad_days: int
    newest_ad_days: int
    avg_days_running: float
    new_entrants_7d: int
    new_entrants_ratio: float
    platforms: dict[str, int]
    top_advertisers: list[tuple[str, int]]
    saturation_score: int
    recommendation: str
    reasoning: list[str]
