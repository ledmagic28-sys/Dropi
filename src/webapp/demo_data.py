"""
Datos de demostración para que el dashboard funcione sin credenciales reales.
Simula respuestas de Mercado Libre + Meta Ad Library + FB Marketplace
para varios productos populares de Dropi en Colombia.
"""

from __future__ import annotations

import time
from typing import Optional


# Productos demo con datos realistas (valores representativos del mercado CO)
DEMO_PRODUCTS = {
    "masajeador cuello": {
        "mercadolibre": {
            "unique_sellers": 847,
            "total_listings": 2341,
            "avg_price": 142000,
            "min_price": 38000,
            "max_price": 489000,
            "currency": "COP",
            "estimated_monthly_sales": 12800,
            "top_sellers": [("seller_981", 42), ("seller_442", 31), ("seller_103", 28)],
        },
        "ads_library": {
            "unique_advertisers": 67,
            "total_ads": 189,
            "oldest_ad_days": 94,
            "newest_ad_days": 1,
            "avg_days_running": 38.4,
            "new_entrants_7d": 12,
            "new_entrants_ratio": 0.18,
            "saturation_score": 55,
            "platforms": {"facebook": 189, "instagram": 144},
            "top_advertisers": [("Salud Total CO", 14), ("Relax Pro", 9), ("Massage Home", 7)],
        },
        "marketplace": {
            "total_listings": 234,
            "min_price": 79000,
            "max_price": 250000,
            "currency": "COP",
            "available": True,
        },
    },
    "crema anticelulitica": {
        "mercadolibre": {
            "unique_sellers": 312,
            "total_listings": 680,
            "avg_price": 58000,
            "min_price": 22000,
            "max_price": 180000,
            "currency": "COP",
            "estimated_monthly_sales": 4200,
            "top_sellers": [("beauty_hub_co", 22), ("farma_plus", 14)],
        },
        "ads_library": {
            "unique_advertisers": 24,
            "total_ads": 71,
            "oldest_ad_days": 61,
            "newest_ad_days": 2,
            "avg_days_running": 22.1,
            "new_entrants_7d": 6,
            "new_entrants_ratio": 0.25,
            "saturation_score": 35,
            "platforms": {"facebook": 71, "instagram": 58},
            "top_advertisers": [("Natural Beauty CO", 8), ("Skin Lab", 5)],
        },
        "marketplace": {
            "total_listings": 88,
            "min_price": 25000,
            "max_price": 120000,
            "currency": "COP",
            "available": True,
        },
    },
    "luz led ring": {
        "mercadolibre": {
            "unique_sellers": 1240,
            "total_listings": 3890,
            "avg_price": 95000,
            "min_price": 19000,
            "max_price": 450000,
            "currency": "COP",
            "estimated_monthly_sales": 18500,
            "top_sellers": [("tech_store_co", 64), ("photo_pro", 41)],
        },
        "ads_library": {
            "unique_advertisers": 142,
            "total_ads": 518,
            "oldest_ad_days": 210,
            "newest_ad_days": 1,
            "avg_days_running": 67.5,
            "new_entrants_7d": 8,
            "new_entrants_ratio": 0.05,
            "saturation_score": 87,
            "platforms": {"facebook": 518, "instagram": 410, "messenger": 180},
            "top_advertisers": [("Foto Pro CO", 35), ("Tech Deals", 28)],
        },
        "marketplace": {
            "total_listings": 412,
            "min_price": 22000,
            "max_price": 320000,
            "currency": "COP",
            "available": True,
        },
    },
    "termo electrico taza": {
        "mercadolibre": {
            "unique_sellers": 48,
            "total_listings": 92,
            "avg_price": 110000,
            "min_price": 55000,
            "max_price": 220000,
            "currency": "COP",
            "estimated_monthly_sales": 180,
            "top_sellers": [("home_magic", 6), ("gift_hub", 4)],
        },
        "ads_library": {
            "unique_advertisers": 4,
            "total_ads": 9,
            "oldest_ad_days": 18,
            "newest_ad_days": 3,
            "avg_days_running": 9.2,
            "new_entrants_7d": 3,
            "new_entrants_ratio": 0.60,
            "saturation_score": 12,
            "platforms": {"facebook": 9, "instagram": 6},
            "top_advertisers": [("Home Magic", 2), ("Gift Hub", 2)],
        },
        "marketplace": {
            "total_listings": 14,
            "min_price": 49000,
            "max_price": 180000,
            "currency": "COP",
            "available": True,
        },
    },
}


def _closest_demo_key(query: str) -> Optional[str]:
    """Encuentra la clave demo más parecida a la búsqueda del usuario."""
    q = query.lower().strip()
    for key in DEMO_PRODUCTS:
        if any(word in q for word in key.split()):
            return key
    return None


def fake_triangulation(query: str, country: str = "CO", delay_ms: int = 1500) -> dict:
    """
    Devuelve un resultado de triangulación con datos demo.
    Si la búsqueda coincide parcialmente con un producto demo, usa esos datos.
    De lo contrario, sintetiza datos proporcionales al largo del query.
    """
    # Simula latencia de red (para ver los loaders)
    time.sleep(delay_ms / 1000)

    key = _closest_demo_key(query)
    if key:
        data = DEMO_PRODUCTS[key]
    else:
        # Sintetiza algo razonable basado en el nombre
        seed = sum(ord(c) for c in query)
        sellers = 50 + (seed % 800)
        data = {
            "mercadolibre": {
                "unique_sellers": sellers,
                "total_listings": sellers * 2 + (seed % 500),
                "avg_price": 40000 + (seed % 200000),
                "min_price": 15000,
                "max_price": 280000,
                "currency": "COP",
                "estimated_monthly_sales": sellers * 5 + (seed % 2000),
                "top_sellers": [(f"seller_{i}", 10 - i) for i in range(3)],
            },
            "ads_library": {
                "unique_advertisers": max(3, sellers // 15),
                "total_ads": max(8, sellers // 5),
                "oldest_ad_days": 14 + (seed % 90),
                "newest_ad_days": seed % 7,
                "avg_days_running": 20.0 + (seed % 40),
                "new_entrants_7d": max(1, sellers // 80),
                "new_entrants_ratio": 0.15,
                "saturation_score": min(90, 20 + sellers // 10),
                "platforms": {"facebook": sellers // 5, "instagram": sellers // 7},
                "top_advertisers": [(f"Marca {i+1}", 5 - i) for i in range(3)],
            },
            "marketplace": {
                "total_listings": sellers // 4,
                "min_price": 20000,
                "max_price": 200000,
                "currency": "COP",
                "available": True,
            },
        }

    return _build_result(query, country, data)


def _build_result(query: str, country: str, data: dict) -> dict:
    ml = data["mercadolibre"]
    ads = data["ads_library"]
    mkt = data["marketplace"]

    total_sellers = ml["unique_sellers"] + ads["unique_advertisers"]
    total_ads = ads["total_ads"]

    # Demanda
    demand = 0
    if ml["estimated_monthly_sales"] >= 5000:
        demand += 35
    elif ml["estimated_monthly_sales"] >= 1000:
        demand += 25
    elif ml["estimated_monthly_sales"] >= 200:
        demand += 15
    elif ml["total_listings"] > 0:
        demand += 8

    if ads["unique_advertisers"] >= 20:
        demand += 30
    elif ads["unique_advertisers"] >= 8:
        demand += 20
    elif ads["unique_advertisers"] >= 3:
        demand += 10

    if ads["oldest_ad_days"] >= 90:
        demand += 20
    elif ads["oldest_ad_days"] >= 30:
        demand += 10

    if mkt["total_listings"] >= 100:
        demand += 15
    elif mkt["total_listings"] >= 30:
        demand += 8

    demand = min(100, demand)

    # Saturación
    ml_sat = 0
    if ml["unique_sellers"] >= 2000: ml_sat = 85
    elif ml["unique_sellers"] >= 1000: ml_sat = 70
    elif ml["unique_sellers"] >= 500: ml_sat = 55
    elif ml["unique_sellers"] >= 200: ml_sat = 38
    elif ml["unique_sellers"] >= 80: ml_sat = 22
    elif ml["unique_sellers"] >= 30: ml_sat = 12
    elif ml["unique_sellers"] >= 10: ml_sat = 5

    saturation = int(ads["saturation_score"] * 0.6 + ml_sat * 0.4)
    saturation = min(100, saturation)

    # Veredicto
    if saturation >= 75:
        level = "EVITAR"
        rec = (
            "Mercado saturado. Hay demasiados competidores peleando por el mismo cliente. "
            "Tu CPA será elevado y los márgenes muy apretados. "
            "Busca variantes del producto, un nicho más específico o un producto complementario."
        )
    elif saturation >= 50:
        level = "TESTEAR_DIFERENCIACION"
        rec = (
            "Mercado activo y competido. Hay espacio, pero solo si entras con un ángulo único: "
            "creative superior, bundle exclusivo o un nicho demográfico que los demás no están atacando. "
            "CPA esperado: medio-alto."
        )
    elif demand >= 30:
        level = "TESTEAR"
        rec = (
            "Sweet spot. Demanda validada y poca saturación — es el mejor momento para entrar. "
            "Arranca con presupuesto controlado, mide CPA los primeros 3 días y escala si los números cuadran."
        )
    else:
        level = "TESTEAR"
        rec = (
            "Mercado emergente con poca validación. Alto potencial si eres de los primeros, "
            "alto riesgo si el producto no engancha. Prueba con presupuesto bajo y una métrica de CPA clara."
        )

    return {
        "query": query,
        "country": country,
        "demand_score": demand,
        "saturation_score": saturation,
        "total_sellers": total_sellers,
        "total_ads": total_ads,
        "oldest_ad_days": ads["oldest_ad_days"],
        "recommendation": rec,
        "recommendation_level": level,
        "mercadolibre": ml,
        "ads_library": ads,
        "marketplace": mkt,
        "is_demo": True,
    }
