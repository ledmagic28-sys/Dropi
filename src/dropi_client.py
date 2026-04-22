import os
import time
from dataclasses import dataclass, field
from typing import Iterator, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

DROPI_BASE_URL = "https://app.dropi.co"


class DropiError(Exception):
    pass


@dataclass
class DropiProduct:
    id: str
    name: str
    description: str
    price: float
    compare_at_price: Optional[float]
    sku: Optional[str]
    stock: int
    images: list[str] = field(default_factory=list)
    category: Optional[str] = None
    brand: Optional[str] = None
    orders_count: int = 0
    rating: Optional[float] = None
    commission: Optional[float] = None
    is_available: bool = True
    score: int = 0

    @property
    def margin_pct(self) -> float:
        if self.compare_at_price and self.compare_at_price > self.price:
            return (self.compare_at_price - self.price) / self.compare_at_price * 100
        return 0.0

    @property
    def primary_image(self) -> Optional[str]:
        return self.images[0] if self.images else None


class DropiClient:
    """Cliente para la API de Dropi.co.

    Autenticacion: genera un token en Dropi → Integraciones y ponlo
    en DROPI_INTEGRATION_KEY en tu .env.
    """

    def __init__(
        self,
        integration_key: Optional[str] = None,
        timeout: int = 30,
    ):
        self.base_url = os.getenv("DROPI_BASE_URL", DROPI_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

        key = integration_key or os.getenv("DROPI_INTEGRATION_KEY")
        if not key:
            raise DropiError(
                "Falta DROPI_INTEGRATION_KEY. "
                "Ve a Dropi → Integraciones y copia tu token."
            )
        self.session.headers.update(
            {
                "dropi-integration-key": key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        for attempt in range(3):
            resp = self.session.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if not resp.ok:
                raise DropiError(
                    f"Error Dropi API {resp.status_code} [{path}]: {resp.text[:400]}"
                )
            return resp.json()
        raise DropiError("Demasiados reintentos en Dropi API (rate limit).")

    def get_categories(self) -> list[dict]:
        data = self._get("/api/v1/categories")
        return data.get("data", data.get("categories", []))

    def get_products(
        self,
        category_id: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "orders_count",
        sort_order: str = "desc",
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[DropiProduct], int]:
        """Devuelve (lista_de_productos, total_paginas)."""
        params: dict = {
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "per_page": per_page,
        }
        if category_id:
            params["category_id"] = category_id
        if search:
            params["search"] = search

        data = self._get("/api/v1/products", params=params)
        raw_list = data.get("data", data.get("products", []))
        total_pages = (
            data.get("meta", {}).get("last_page")
            or data.get("last_page")
            or 1
        )
        products = [_parse_product(r) for r in raw_list]
        return products, int(total_pages)

    def get_winning_products(
        self,
        category_id: Optional[str] = None,
        search: Optional[str] = None,
        min_score: int = 60,
        limit: int = 20,
        max_pages: int = 5,
    ) -> Iterator[DropiProduct]:
        """Itera sobre productos con score >= min_score ordenados por pedidos."""
        seen = 0
        for page in range(1, max_pages + 1):
            products, total_pages = self.get_products(
                category_id=category_id,
                search=search,
                sort_by="orders_count",
                sort_order="desc",
                page=page,
                per_page=50,
            )
            if not products:
                break
            for product in products:
                product.score = _score_product(product)
                if product.score >= min_score:
                    yield product
                    seen += 1
                    if seen >= limit:
                        return
            if page >= total_pages:
                break

    def get_product_detail(self, product_id: str) -> DropiProduct:
        data = self._get(f"/api/v1/products/{product_id}")
        raw = data.get("data", data)
        return _parse_product(raw)


def _score_product(p: DropiProduct) -> int:
    """Puntua 0-100 un producto de Dropi segun su potencial de venta."""
    score = 0

    # Pedidos historicos (max 40 pts)
    if p.orders_count >= 500:
        score += 40
    elif p.orders_count >= 200:
        score += 30
    elif p.orders_count >= 50:
        score += 20
    elif p.orders_count >= 10:
        score += 10

    # Margen de ganancia (max 30 pts)
    margin = p.margin_pct
    if margin >= 50:
        score += 30
    elif margin >= 30:
        score += 20
    elif margin >= 15:
        score += 10

    # Stock disponible (max 15 pts)
    if p.stock >= 100:
        score += 15
    elif p.stock >= 20:
        score += 10
    elif p.stock >= 5:
        score += 5

    # Rating/resenas (max 15 pts)
    if p.rating:
        if p.rating >= 4.5:
            score += 15
        elif p.rating >= 4.0:
            score += 10
        elif p.rating >= 3.5:
            score += 5
    else:
        score += 7  # sin rating = neutral

    return min(score, 100)


def _parse_product(raw: dict) -> DropiProduct:
    images: list[str] = []
    for img in raw.get("images", raw.get("gallery", [])):
        if isinstance(img, dict):
            url = img.get("url") or img.get("src") or img.get("path", "")
            if url:
                images.append(url)
        elif isinstance(img, str):
            images.append(img)

    price = float(raw.get("price", raw.get("sale_price", 0)) or 0)
    compare = raw.get("compare_at_price") or raw.get("regular_price")
    compare_float = float(compare) if compare else None

    return DropiProduct(
        id=str(raw.get("id", "")),
        name=raw.get("name", raw.get("title", "")),
        description=raw.get("description", raw.get("body_html", "")),
        price=price,
        compare_at_price=compare_float,
        sku=raw.get("sku"),
        stock=int(raw.get("stock", raw.get("quantity", 0)) or 0),
        images=images,
        category=raw.get("category", raw.get("category_name")),
        brand=raw.get("brand"),
        orders_count=int(raw.get("orders_count", raw.get("total_orders", 0)) or 0),
        rating=float(raw.get("rating", 0) or 0) or None,
        commission=float(raw.get("commission", 0) or 0) or None,
        is_available=bool(raw.get("is_available", True)),
    )
