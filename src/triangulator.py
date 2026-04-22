"""
Motor de triangulación: combina Mercado Libre + Meta Ad Library + Facebook Marketplace
para producir un score unificado de demanda/saturación por producto.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional

from .analyzer import analyze
from .client import MetaAdLibraryClient, MetaAdLibraryError
from .mercadolibre import MercadoLibreClient, MercadoLibreError, MercadoLibreResult
from .models import MarketAnalysis
from .scraper import MetaAdLibraryScraper, ScraperError


# ─────────────────────────────────────────────────────────
#  Resultado de Marketplace (scraping — sin API oficial)
# ─────────────────────────────────────────────────────────

@dataclass
class MarketplaceResult:
    query: str
    country: str
    total_listings: int
    min_price: float
    max_price: float
    currency: str
    new_today: int
    available: bool = True
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────
#  Resultado triangulado
# ─────────────────────────────────────────────────────────

@dataclass
class TriangulationResult:
    query: str
    country: str

    # Datos por fuente
    mercadolibre: Optional[MercadoLibreResult]
    ads_library: Optional[MarketAnalysis]
    marketplace: Optional[MarketplaceResult]

    # Scores combinados (0–100)
    demand_score: int
    saturation_score: int

    # Totales calculados
    total_sellers: int
    total_ads: int
    oldest_ad_days: int

    # Veredicto final
    recommendation: str
    recommendation_level: str   # "TESTEAR" | "TESTEAR_DIFERENCIACION" | "EVITAR" | "SIN_DATOS"
    reasoning: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────
#  Motor principal
# ─────────────────────────────────────────────────────────

class Triangulator:
    """
    Consulta las 3 fuentes en paralelo y combina los resultados
    en un único TriangulationResult.
    """

    def __init__(
        self,
        meta_token: Optional[str] = None,
        ml_max_results: int = 100,
        ads_max_pages: int = 5,
        use_scraper_fallback: bool = True,
        timeout: int = 30,
    ):
        self.meta_token = meta_token
        self.ml_max_results = ml_max_results
        self.ads_max_pages = ads_max_pages
        self.use_scraper_fallback = use_scraper_fallback
        self.timeout = timeout

    def run(self, query: str, country: str = "CO") -> TriangulationResult:
        """Ejecuta las 3 consultas en paralelo y devuelve el análisis combinado."""

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            future_ml  = pool.submit(self._fetch_ml, query, country)
            future_ads = pool.submit(self._fetch_ads, query, country)
            future_mkt = pool.submit(self._fetch_marketplace, query, country)

            ml_result  = future_ml.result()
            ads_result = future_ads.result()
            mkt_result = future_mkt.result()

        return _combine(query, country, ml_result, ads_result, mkt_result)

    # ── Fuente 1: Mercado Libre ───────────────────────────

    def _fetch_ml(self, query: str, country: str) -> Optional[MercadoLibreResult]:
        try:
            client = MercadoLibreClient(timeout=self.timeout)
            return client.search(query, country=country, max_results=self.ml_max_results)
        except MercadoLibreError:
            return None

    # ── Fuente 2: Meta Ad Library ─────────────────────────

    def _fetch_ads(self, query: str, country: str) -> Optional[MarketAnalysis]:
        # Intentar con token primero
        if self.meta_token:
            try:
                client = MetaAdLibraryClient(access_token=self.meta_token)
                ads = list(client.search(
                    query=query,
                    country=country,
                    active_status="ACTIVE",
                    max_pages=self.ads_max_pages,
                ))
                return analyze(ads, query=query, country=country)
            except MetaAdLibraryError:
                pass

        # Fallback: scraper sin token
        if self.use_scraper_fallback:
            try:
                scraper = MetaAdLibraryScraper()
                ads = list(scraper.search(query=query, country=country))
                return analyze(ads, query=query, country=country)
            except (ScraperError, Exception):
                pass

        return None

    # ── Fuente 3: Facebook Marketplace (scraping) ─────────

    def _fetch_marketplace(self, query: str, country: str) -> Optional[MarketplaceResult]:
        """
        Scraping de Facebook Marketplace vía Playwright.
        Retorna None si Playwright no está disponible o falla.
        """
        try:
            return _scrape_marketplace(query, country, timeout=self.timeout)
        except Exception:
            return None


# ─────────────────────────────────────────────────────────
#  Scraper de Facebook Marketplace (Playwright)
# ─────────────────────────────────────────────────────────

def _scrape_marketplace(query: str, country: str, timeout: int = 30) -> MarketplaceResult:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return MarketplaceResult(
            query=query, country=country,
            total_listings=0, min_price=0.0, max_price=0.0,
            currency="", new_today=0, available=False,
            error="Playwright no instalado. Ejecuta: playwright install chromium",
        )

    country_locales = {
        "CO": ("es-CO", "CO"),
        "MX": ("es-MX", "MX"),
        "AR": ("es-AR", "AR"),
        "CL": ("es-CL", "CL"),
        "PE": ("es-PE", "PE"),
        "US": ("en-US", "US"),
        "ES": ("es-ES", "ES"),
    }
    locale, marketplace_country = country_locales.get(country.upper(), ("es-CO", "CO"))

    url = (
        f"https://www.facebook.com/marketplace/{marketplace_country.lower()}/search"
        f"/?query={query.replace(' ', '%20')}&exact=false"
    )

    prices: list[float] = []
    listing_count = 0

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(locale=locale, viewport={"width": 1280, "height": 800})
            page = ctx.new_page()

            try:
                page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Contar listados
                items = page.query_selector_all('[data-testid="marketplace_search_feed"] > div')
                listing_count = len(items)

                # Extraer precios del HTML
                price_texts = page.evaluate("""
                    () => Array.from(document.querySelectorAll('span'))
                         .map(el => el.innerText.trim())
                         .filter(t => /^\\$[\\d.,]+/.test(t))
                         .slice(0, 50)
                """)
                for pt in price_texts:
                    cleaned = pt.replace("$", "").replace(".", "").replace(",", "").strip()
                    try:
                        prices.append(float(cleaned))
                    except ValueError:
                        pass

            except PWTimeout:
                pass
            finally:
                browser.close()

    except Exception as exc:
        return MarketplaceResult(
            query=query, country=country,
            total_listings=0, min_price=0.0, max_price=0.0,
            currency="", new_today=0, available=False,
            error=str(exc),
        )

    return MarketplaceResult(
        query=query,
        country=country,
        total_listings=listing_count,
        min_price=min(prices) if prices else 0.0,
        max_price=max(prices) if prices else 0.0,
        currency="COP" if country == "CO" else "MXN" if country == "MX" else "USD",
        new_today=0,
        available=True,
    )


# ─────────────────────────────────────────────────────────
#  Función de combinación y scoring
# ─────────────────────────────────────────────────────────

def _combine(
    query: str,
    country: str,
    ml: Optional[MercadoLibreResult],
    ads: Optional[MarketAnalysis],
    mkt: Optional[MarketplaceResult],
) -> TriangulationResult:

    reasoning: list[str] = []

    # ── Conteos brutos ────────────────────────────────────
    ml_sellers    = ml.unique_sellers if ml else 0
    ml_listings   = ml.total_listings if ml else 0
    ml_sales      = ml.estimated_monthly_sales if ml else 0
    ads_count     = ads.total_ads if ads else 0
    ads_sellers   = ads.unique_advertisers if ads else 0
    oldest_days   = ads.oldest_ad_days if ads else 0
    mkt_listings  = mkt.total_listings if mkt and mkt.available else 0

    total_sellers = ml_sellers + ads_sellers
    total_ads     = ads_count

    # ── DEMANDA (0–100) ───────────────────────────────────
    demand = 0

    # ML: ventas mensuales
    if ml_sales >= 5000:
        demand += 35; reasoning.append(f"ML: ~{ml_sales:,} ventas/mes en la muestra → demanda muy alta (+35).")
    elif ml_sales >= 1000:
        demand += 25; reasoning.append(f"ML: ~{ml_sales:,} ventas/mes → demanda alta (+25).")
    elif ml_sales >= 200:
        demand += 15; reasoning.append(f"ML: ~{ml_sales:,} ventas/mes → demanda media (+15).")
    elif ml_listings > 0:
        demand += 8;  reasoning.append(f"ML: {ml_listings} publicaciones pero pocas ventas registradas (+8).")

    # Ads: si hay anunciantes activos = demanda probada
    if ads_sellers >= 20:
        demand += 30; reasoning.append(f"FB Ads: {ads_sellers} anunciantes pagando = demanda validada con inversión (+30).")
    elif ads_sellers >= 8:
        demand += 20; reasoning.append(f"FB Ads: {ads_sellers} anunciantes activos (+20).")
    elif ads_sellers >= 3:
        demand += 10; reasoning.append(f"FB Ads: {ads_sellers} anunciantes (+10).")

    # Ads: antigüedad = rentabilidad demostrada
    if oldest_days >= 90:
        demand += 20; reasoning.append(f"El anunciante más veterano lleva {oldest_days} días → el producto es rentable (+20).")
    elif oldest_days >= 30:
        demand += 10; reasoning.append(f"Anuncios con {oldest_days} días de antigüedad (+10).")

    # Marketplace: listings locales
    if mkt_listings >= 100:
        demand += 15; reasoning.append(f"FB Marketplace: {mkt_listings} publicaciones locales (+15).")
    elif mkt_listings >= 30:
        demand += 8;  reasoning.append(f"FB Marketplace: {mkt_listings} publicaciones (+8).")

    demand = min(100, demand)

    # ── SATURACIÓN (0–100) ────────────────────────────────
    # Reutilizamos el score calculado por el analizador de ads
    # y lo combinamos con el número de vendedores en ML
    ads_sat = ads.saturation_score if ads else 0

    ml_sat = 0
    if ml_sellers >= 500:
        ml_sat = 40
    elif ml_sellers >= 200:
        ml_sat = 30
    elif ml_sellers >= 80:
        ml_sat = 20
    elif ml_sellers >= 30:
        ml_sat = 10
    elif ml_sellers >= 10:
        ml_sat = 5

    # Promedio ponderado: 60% ads (más indicativo para dropshipping) + 40% ML
    if ads and ads.total_ads > 0:
        saturation = int(ads_sat * 0.6 + ml_sat * 0.4)
    else:
        # Sin datos de ads, solo ML
        saturation = ml_sat

    saturation = min(100, saturation)

    # ── Recomendación ─────────────────────────────────────
    sources_available = sum([ml is not None, ads is not None, mkt is not None])
    if sources_available == 0 or (ml_listings == 0 and ads_count == 0 and mkt_listings == 0):
        level = "SIN_DATOS"
        rec = (
            "SIN DATOS — No se encontró información en ninguna fuente. "
            "Prueba con sinónimos o verifica que el producto exista en tu mercado."
        )
    elif saturation >= 75:
        level = "EVITAR"
        rec = (
            "EVITAR / PIVOTAR — Mercado saturado. "
            f"Hay {total_sellers} vendedores identificados y el CPA será elevado. "
            "Busca variantes del producto, un nicho más específico, o un producto complementario."
        )
    elif saturation >= 50:
        level = "TESTEAR_DIFERENCIACION"
        rec = (
            "TESTEAR CON DIFERENCIACIÓN — Mercado activo y competido. "
            "Tienes espacio si entras con un ángulo único: mejor creative, "
            "bundle exclusivo o un nicho demográfico sin explotar."
        )
    elif demand >= 30:
        level = "TESTEAR"
        rec = (
            "TESTEAR — Sweet spot. Hay demanda validada y poca saturación. "
            "Entra con presupuesto controlado, mide el CPA y escala si funciona."
        )
    else:
        level = "TESTEAR"
        rec = (
            "TESTEAR CON CAUTELA — Mercado emergente o con poca validación. "
            "Alto potencial si eres de los primeros, alto riesgo si el producto no engancha. "
            "Prueba con un presupuesto bajo y una métrica de CPA clara."
        )

    return TriangulationResult(
        query=query,
        country=country,
        mercadolibre=ml,
        ads_library=ads,
        marketplace=mkt,
        demand_score=demand,
        saturation_score=saturation,
        total_sellers=total_sellers,
        total_ads=total_ads,
        oldest_ad_days=oldest_days,
        recommendation=rec,
        recommendation_level=level,
        reasoning=reasoning,
    )
