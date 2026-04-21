from collections import Counter
from statistics import mean

from .models import Ad, MarketAnalysis


def analyze(ads: list[Ad], query: str, country: str) -> MarketAnalysis:
    total = len(ads)
    if total == 0:
        return MarketAnalysis(
            query=query,
            country=country,
            total_ads=0,
            unique_advertisers=0,
            oldest_ad_days=0,
            newest_ad_days=0,
            avg_days_running=0.0,
            new_entrants_7d=0,
            new_entrants_ratio=0.0,
            platforms={},
            top_advertisers=[],
            saturation_score=0,
            recommendation="SIN DATOS — No se encontraron anuncios para esta busqueda.",
            reasoning=[
                "Posibles causas: termino muy especifico, pais sin cobertura, o Meta filtro los resultados.",
                "Prueba con sinonimos, categoria mas amplia, o sin filtro de pais.",
            ],
        )

    days_list = [a.days_running for a in ads]
    oldest = max(days_list)
    newest = min(days_list)
    avg = mean(days_list)

    advertiser_counts = Counter(a.page_name or a.page_id for a in ads)
    unique_advertisers = len(advertiser_counts)

    new_entrants = sum(1 for d in days_list if d <= 7)
    new_ratio = new_entrants / total

    platform_counts: Counter[str] = Counter()
    for ad in ads:
        for p in ad.publisher_platforms:
            platform_counts[p] += 1

    score, reasoning = _score_saturation(
        total=total,
        unique_advertisers=unique_advertisers,
        oldest=oldest,
        avg=avg,
        new_ratio=new_ratio,
    )
    recommendation = _build_recommendation(score, total, unique_advertisers, oldest, new_ratio)

    return MarketAnalysis(
        query=query,
        country=country,
        total_ads=total,
        unique_advertisers=unique_advertisers,
        oldest_ad_days=oldest,
        newest_ad_days=newest,
        avg_days_running=round(avg, 1),
        new_entrants_7d=new_entrants,
        new_entrants_ratio=round(new_ratio, 2),
        platforms=dict(platform_counts),
        top_advertisers=advertiser_counts.most_common(10),
        saturation_score=score,
        recommendation=recommendation,
        reasoning=reasoning,
    )


def _score_saturation(
    total: int,
    unique_advertisers: int,
    oldest: int,
    avg: float,
    new_ratio: float,
) -> tuple[int, list[str]]:
    score = 0
    reasoning: list[str] = []

    if unique_advertisers >= 30:
        score += 35
        reasoning.append(f"{unique_advertisers} anunciantes distintos: mercado muy competido (+35).")
    elif unique_advertisers >= 15:
        score += 25
        reasoning.append(f"{unique_advertisers} anunciantes distintos: competencia media-alta (+25).")
    elif unique_advertisers >= 7:
        score += 15
        reasoning.append(f"{unique_advertisers} anunciantes distintos: competencia moderada (+15).")
    elif unique_advertisers >= 3:
        score += 5
        reasoning.append(f"{unique_advertisers} anunciantes: poca competencia (+5).")
    else:
        reasoning.append(f"Solo {unique_advertisers} anunciante(s): mercado muy chico o sin validacion.")

    if oldest >= 90:
        score += 25
        reasoning.append(f"Anuncio mas viejo lleva {oldest} dias: producto probado y rentable (+25).")
    elif oldest >= 30:
        score += 15
        reasoning.append(f"Anuncio mas viejo lleva {oldest} dias: producto con traccion (+15).")
    elif oldest >= 14:
        score += 5
        reasoning.append(f"Anuncio mas viejo lleva {oldest} dias: validacion inicial (+5).")
    else:
        reasoning.append(f"Anuncio mas viejo solo {oldest} dias: mercado emergente o sin validar.")

    if total >= 100:
        score += 20
        reasoning.append(f"{total} anuncios totales: alto volumen publicitario (+20).")
    elif total >= 30:
        score += 10
        reasoning.append(f"{total} anuncios totales: volumen medio (+10).")
    elif total >= 10:
        score += 3
        reasoning.append(f"{total} anuncios totales: volumen bajo (+3).")

    if new_ratio >= 0.3:
        score -= 15
        reasoning.append(f"{int(new_ratio*100)}% de anuncios son de los ultimos 7 dias: mercado caliente, nuevos entrantes (-15).")
    elif new_ratio <= 0.05 and total >= 10:
        score += 10
        reasoning.append("Casi no hay nuevos entrantes: mercado estancado, probablemente saturado (+10).")

    if avg >= 45:
        score += 5
        reasoning.append(f"Promedio de {avg:.0f} dias corriendo: anuncios consolidados (+5).")

    score = max(0, min(100, score))
    return score, reasoning


def _build_recommendation(
    score: int,
    total: int,
    unique_advertisers: int,
    oldest: int,
    new_ratio: float,
) -> str:
    if total < 5:
        return (
            "NO TESTEAR (todavia) — Muy pocos anuncios para validar. "
            "Producto sin demanda probada en este mercado o termino muy especifico."
        )
    if score < 25:
        return (
            "TESTEAR CON CAUTELA — Mercado fresco, poca competencia pero poca validacion. "
            "Alto potencial si eres primero, alto riesgo si el producto no engancha. "
            "Presupuesto inicial bajo y metrica clara de CPA."
        )
    if score < 50:
        return (
            "TESTEAR — Sweet spot. Hay validacion (otros venden) y todavia espacio. "
            "Entra con angulo propio (creative, oferta, bundle) y compite por CPA."
        )
    if score < 75:
        return (
            "TESTEAR CON DIFERENCIACION — Competitivo pero viable. "
            "Necesitas angulo unico: creative superior, oferta mejor, o nicho demografico especifico. "
            "CPA alto esperado, margen apretado."
        )
    return (
        "EVITAR / PIVOTAR — Saturado. Demasiados anunciantes peleando por el mismo cliente. "
        "CPA elevado, margenes comprimidos. Busca variantes del producto, nichos adyacentes, "
        "o productos complementarios menos explotados."
    )
