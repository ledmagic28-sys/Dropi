"""
Cliente para la API pública de Mercado Libre.

Documentación: https://developers.mercadolibre.com/es_ar/items-y-busquedas
Sitios soportados: MLCo (Colombia), MLM (México), MLA (Argentina), MLB (Brasil)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator

import requests

ML_BASE = "https://api.mercadolibre.com"

SITE_IDS = {
    "CO": "MCO",
    "MX": "MLM",
    "AR": "MLA",
    "BR": "MLB",
    "CL": "MLC",
    "PE": "MPE",
    "VE": "MLV",
    "UY": "MLU",
    "BO": "MBO",
    "EC": "MEC",
    "PY": "MPY",
    "CR": "MCR",
    "PA": "MPA",
    "DO": "MRD",
    "GT": "MGT",
    "HN": "MHN",
    "NI": "MNI",
    "SV": "MSV",
    "ES": "MLA",  # España no tiene ML propio; usamos Argentina como proxy
}


class MercadoLibreError(Exception):
    pass


@dataclass
class MercadoLibreListing:
    listing_id: str
    title: str
    price: float
    currency: str
    sold_quantity: int
    seller_id: str
    condition: str          # "new" | "used"
    listing_type: str       # "gold_special" | "gold_pro" | ...
    thumbnail: str


@dataclass
class MercadoLibreResult:
    query: str
    country: str
    site_id: str
    total_listings: int
    unique_sellers: int
    avg_price: float
    min_price: float
    max_price: float
    currency: str
    estimated_monthly_sales: int
    top_sellers: list[tuple[str, int]]      # (seller_id, listing_count)
    listings: list[MercadoLibreListing] = field(default_factory=list)


class MercadoLibreClient:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Dropi-MarketRadar/1.0"

    def _site(self, country: str) -> str:
        site = SITE_IDS.get(country.upper())
        if not site:
            raise MercadoLibreError(
                f"País '{country}' no soportado. Usa: {', '.join(SITE_IDS)}"
            )
        return site

    def _get(self, url: str, **params) -> dict:
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt == 2:
                    raise MercadoLibreError(f"Error de red: {exc}") from exc
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 429:
                time.sleep(5)
                continue
            if not resp.ok:
                raise MercadoLibreError(
                    f"ML API {resp.status_code}: {resp.text[:300]}"
                )
            return resp.json()
        raise MercadoLibreError("Máximo de reintentos alcanzado.")

    def search(
        self,
        query: str,
        country: str = "CO",
        max_results: int = 200,
    ) -> MercadoLibreResult:
        """
        Busca un producto y devuelve métricas de mercado: vendedores,
        precios, volumen de ventas estimado.
        """
        site = self._site(country)
        url = f"{ML_BASE}/sites/{site}/search"

        listings: list[MercadoLibreListing] = []
        offset = 0
        limit = 50
        total_api = None

        while len(listings) < max_results:
            data = self._get(url, q=query, limit=limit, offset=offset)

            if total_api is None:
                total_api = data.get("paging", {}).get("total", 0)

            results = data.get("results", [])
            if not results:
                break

            for item in results:
                listings.append(
                    MercadoLibreListing(
                        listing_id=item.get("id", ""),
                        title=item.get("title", ""),
                        price=float(item.get("price", 0)),
                        currency=item.get("currency_id", ""),
                        sold_quantity=item.get("sold_quantity", 0),
                        seller_id=str(item.get("seller", {}).get("id", "")),
                        condition=item.get("condition", ""),
                        listing_type=item.get("listing_type_id", ""),
                        thumbnail=item.get("thumbnail", ""),
                    )
                )

            offset += limit
            if offset >= (total_api or 0):
                break

        return _build_result(query, country, site, total_api or 0, listings)

    def iter_listings(
        self,
        query: str,
        country: str = "CO",
        max_pages: int = 4,
    ) -> Iterator[MercadoLibreListing]:
        """Generador que itera publicaciones página a página."""
        site = self._site(country)
        url = f"{ML_BASE}/sites/{site}/search"
        offset = 0
        limit = 50
        pages = 0

        while pages < max_pages:
            data = self._get(url, q=query, limit=limit, offset=offset)
            results = data.get("results", [])
            if not results:
                break
            for item in results:
                yield MercadoLibreListing(
                    listing_id=item.get("id", ""),
                    title=item.get("title", ""),
                    price=float(item.get("price", 0)),
                    currency=item.get("currency_id", ""),
                    sold_quantity=item.get("sold_quantity", 0),
                    seller_id=str(item.get("seller", {}).get("id", "")),
                    condition=item.get("condition", ""),
                    listing_type=item.get("listing_type_id", ""),
                    thumbnail=item.get("thumbnail", ""),
                )
            total = data.get("paging", {}).get("total", 0)
            offset += limit
            pages += 1
            if offset >= total:
                break


def _build_result(
    query: str,
    country: str,
    site_id: str,
    total_listings: int,
    listings: list[MercadoLibreListing],
) -> MercadoLibreResult:
    from collections import Counter

    if not listings:
        return MercadoLibreResult(
            query=query,
            country=country,
            site_id=site_id,
            total_listings=total_listings,
            unique_sellers=0,
            avg_price=0.0,
            min_price=0.0,
            max_price=0.0,
            currency="",
            estimated_monthly_sales=0,
            top_sellers=[],
            listings=[],
        )

    prices = [l.price for l in listings if l.price > 0]
    seller_counts: Counter[str] = Counter(l.seller_id for l in listings)
    monthly_sales = sum(l.sold_quantity for l in listings)
    currency = listings[0].currency if listings else ""

    return MercadoLibreResult(
        query=query,
        country=country,
        site_id=site_id,
        total_listings=total_listings,
        unique_sellers=len(seller_counts),
        avg_price=round(sum(prices) / len(prices), 0) if prices else 0.0,
        min_price=min(prices) if prices else 0.0,
        max_price=max(prices) if prices else 0.0,
        currency=currency,
        estimated_monthly_sales=monthly_sales,
        top_sellers=seller_counts.most_common(10),
        listings=listings,
    )
