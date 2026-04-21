import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .tiktok import TikTokProduct


@dataclass
class ArbitrageOpportunity:
    product_name: str
    source_country: str
    target_country: str
    source_rank: int
    source_cvr: float
    source_ad_count: int
    gap_score: int
    reason: str


def _normalize(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _fuzzy_match(a: str, b: str, threshold: float = 0.72) -> bool:
    a_norm, b_norm = _normalize(a), _normalize(b)
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    if a_norm in b_norm or b_norm in a_norm:
        return True
    ratio = SequenceMatcher(None, a_norm, b_norm).ratio()
    return ratio >= threshold


def find_opportunities(
    source_products: list[TikTokProduct],
    target_products: list[TikTokProduct],
) -> list[ArbitrageOpportunity]:
    target_names = [p.name for p in target_products]
    opportunities: list[ArbitrageOpportunity] = []

    for i, sp in enumerate(source_products, start=1):
        matches_in_target = any(_fuzzy_match(sp.name, tn) for tn in target_names)
        if matches_in_target:
            continue

        source_rank = sp.rank or i
        cvr = sp.cvr or 0.0
        ad_count = sp.ad_count or 0

        gap_score = _score_opportunity(source_rank, cvr, ad_count, len(source_products))
        reason = _build_reason(sp, matches_in_target=False)

        opportunities.append(
            ArbitrageOpportunity(
                product_name=sp.name,
                source_country=sp.country_code,
                target_country=(target_products[0].country_code if target_products else "?"),
                source_rank=source_rank,
                source_cvr=cvr,
                source_ad_count=ad_count,
                gap_score=gap_score,
                reason=reason,
            )
        )

    opportunities.sort(key=lambda o: o.gap_score, reverse=True)
    return opportunities


def _score_opportunity(rank: int, cvr: float, ad_count: int, total: int) -> int:
    score = 0
    if rank <= 5:
        score += 40
    elif rank <= 15:
        score += 30
    elif rank <= 30:
        score += 20
    else:
        score += 10

    if cvr >= 5:
        score += 30
    elif cvr >= 2:
        score += 20
    elif cvr >= 1:
        score += 10

    if ad_count >= 50:
        score += 20
    elif ad_count >= 10:
        score += 15
    elif ad_count >= 3:
        score += 10

    return min(100, score)


def _build_reason(sp: TikTokProduct, matches_in_target: bool) -> str:
    bits = []
    if sp.rank and sp.rank <= 10:
        bits.append(f"top {sp.rank} en {sp.country_code}")
    if sp.cvr:
        bits.append(f"CVR {sp.cvr:.1f}%")
    if sp.ad_count:
        bits.append(f"{sp.ad_count} anuncios corriendo")
    base = ", ".join(bits) if bits else f"trending en {sp.country_code}"
    return f"{base}. Sin presencia detectable en pais objetivo."
