import os
import time
from dataclasses import dataclass
from typing import Optional

import requests
from dotenv import load_dotenv

from .dropi_client import DropiProduct

load_dotenv()

SHOPIFY_API_VERSION = "2024-01"


class ShopifyError(Exception):
    pass


@dataclass
class ShopifyPublishResult:
    product_id: str
    product_handle: str
    product_url: str
    landing_page_id: Optional[str]
    landing_page_url: Optional[str]
    store_domain: str


class ShopifyClient:
    """Cliente para Shopify Admin REST API.

    Necesita:
      SHOPIFY_STORE_DOMAIN  → ej: mi-tienda.myshopify.com
      SHOPIFY_ACCESS_TOKEN  → token de app privada o custom app
    """

    def __init__(
        self,
        store_domain: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: int = 30,
    ):
        self.domain = (store_domain or os.getenv("SHOPIFY_STORE_DOMAIN", "")).rstrip("/")
        self.token = access_token or os.getenv("SHOPIFY_ACCESS_TOKEN")
        self.api_version = os.getenv("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION)
        self.timeout = timeout

        if not self.domain:
            raise ShopifyError(
                "Falta SHOPIFY_STORE_DOMAIN. Ejemplo: mi-tienda.myshopify.com"
            )
        if not self.token:
            raise ShopifyError(
                "Falta SHOPIFY_ACCESS_TOKEN. "
                "Crea una app privada en Shopify Admin → Apps → Develop apps."
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Shopify-Access-Token": self.token,
                "Content-Type": "application/json",
            }
        )
        self._base = f"https://{self.domain}/admin/api/{self.api_version}"

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self._base}{path}"
        for attempt in range(4):
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 2 ** attempt))
                time.sleep(retry_after)
                continue
            if not resp.ok:
                raise ShopifyError(
                    f"Shopify API {resp.status_code} [{path}]: {resp.text[:500]}"
                )
            return resp.json()
        raise ShopifyError("Demasiados reintentos en Shopify API (rate limit).")

    def _put(self, path: str, payload: dict) -> dict:
        url = f"{self._base}{path}"
        resp = self.session.put(url, json=payload, timeout=self.timeout)
        if not resp.ok:
            raise ShopifyError(
                f"Shopify API {resp.status_code} [{path}]: {resp.text[:500]}"
            )
        return resp.json()

    def create_product(self, dropi: DropiProduct, published: bool = True) -> dict:
        """Crea el producto en Shopify y retorna el objeto product de la API."""
        price_str = f"{dropi.price:.2f}"
        compare_str = (
            f"{dropi.compare_at_price:.2f}" if dropi.compare_at_price else None
        )

        variant: dict = {
            "price": price_str,
            "inventory_management": "shopify",
            "inventory_quantity": dropi.stock,
            "sku": dropi.sku or "",
        }
        if compare_str:
            variant["compare_at_price"] = compare_str

        images = [{"src": url, "alt": dropi.name} for url in dropi.images[:10]]

        payload = {
            "product": {
                "title": dropi.name,
                "body_html": _sanitize_html(dropi.description),
                "vendor": dropi.brand or "Dropi",
                "product_type": dropi.category or "",
                "status": "active" if published else "draft",
                "variants": [variant],
                "images": images,
                "tags": _build_tags(dropi),
            }
        }

        data = self._post("/products.json", payload)
        return data.get("product", data)

    def create_landing_page(
        self,
        dropi: DropiProduct,
        shopify_product: dict,
        published: bool = True,
    ) -> dict:
        """Crea una landing page en Shopify (recurso Page) para el producto."""
        handle = shopify_product.get("handle", "")
        product_url = f"/products/{handle}"
        image_url = dropi.primary_image or ""

        price_display = _format_price(dropi.price)
        compare_display = (
            _format_price(dropi.compare_at_price) if dropi.compare_at_price else ""
        )
        discount_badge = ""
        if dropi.compare_at_price and dropi.compare_at_price > dropi.price:
            pct = int(dropi.margin_pct)
            discount_badge = f'<span class="badge">-{pct}%</span>'

        html = _build_landing_html(
            name=dropi.name,
            description=_sanitize_html(dropi.description),
            image_url=image_url,
            product_url=product_url,
            price_display=price_display,
            compare_display=compare_display,
            discount_badge=discount_badge,
            score=dropi.score,
            orders_count=dropi.orders_count,
        )

        payload = {
            "page": {
                "title": dropi.name,
                "handle": f"landing-{handle}",
                "body_html": html,
                "published": published,
            }
        }

        data = self._post("/pages.json", payload)
        return data.get("page", data)

    def publish_dropi_product(
        self,
        dropi: DropiProduct,
        create_landing: bool = True,
        published: bool = True,
    ) -> ShopifyPublishResult:
        """Pipeline completo: crea producto + landing page en Shopify."""
        shopify_product = self.create_product(dropi, published=published)
        product_id = str(shopify_product.get("id", ""))
        handle = shopify_product.get("handle", "")
        product_url = f"https://{self.domain}/products/{handle}"

        landing_id = None
        landing_url = None

        if create_landing:
            page = self.create_landing_page(dropi, shopify_product, published=published)
            landing_id = str(page.get("id", ""))
            landing_handle = page.get("handle", "")
            landing_url = f"https://{self.domain}/pages/{landing_handle}"

        return ShopifyPublishResult(
            product_id=product_id,
            product_handle=handle,
            product_url=product_url,
            landing_page_id=landing_id,
            landing_page_url=landing_url,
            store_domain=self.domain,
        )


def _sanitize_html(html: str) -> str:
    if not html:
        return ""
    # Elimina scripts e iframes por seguridad
    import re
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<iframe[^>]*>.*?</iframe>", "", html, flags=re.DOTALL | re.IGNORECASE)
    return html.strip()


def _format_price(price: Optional[float]) -> str:
    if price is None:
        return ""
    if price >= 1000:
        return f"${price:,.0f}"
    return f"${price:.2f}"


def _build_tags(dropi: DropiProduct) -> str:
    tags = ["dropi"]
    if dropi.category:
        tags.append(dropi.category.lower())
    if dropi.score >= 80:
        tags.append("winner")
    elif dropi.score >= 60:
        tags.append("trending")
    if dropi.orders_count >= 200:
        tags.append("bestseller")
    return ", ".join(tags)


def _build_landing_html(
    name: str,
    description: str,
    image_url: str,
    product_url: str,
    price_display: str,
    compare_display: str,
    discount_badge: str,
    score: int,
    orders_count: int,
) -> str:
    score_color = "#e74c3c" if score >= 80 else "#f39c12" if score >= 60 else "#27ae60"
    orders_text = f"+{orders_count:,} pedidos realizados" if orders_count else ""

    return f"""
<style>
  .dropi-landing {{
    max-width: 800px;
    margin: 0 auto;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #222;
  }}
  .dropi-hero {{
    display: flex;
    gap: 32px;
    align-items: flex-start;
    flex-wrap: wrap;
    margin-bottom: 40px;
  }}
  .dropi-hero img {{
    width: 100%;
    max-width: 380px;
    border-radius: 12px;
    object-fit: cover;
  }}
  .dropi-info {{ flex: 1; min-width: 260px; }}
  .dropi-info h1 {{ font-size: 1.8rem; margin-bottom: 12px; }}
  .dropi-price {{ font-size: 2rem; font-weight: 700; color: #e74c3c; }}
  .dropi-compare {{ font-size: 1.1rem; color: #999; text-decoration: line-through; margin-left: 8px; }}
  .badge {{
    background: #e74c3c;
    color: white;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
    margin-left: 8px;
    vertical-align: middle;
  }}
  .score-pill {{
    display: inline-block;
    background: {score_color};
    color: white;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
    margin-bottom: 12px;
  }}
  .orders-badge {{
    font-size: 0.9rem;
    color: #555;
    margin-bottom: 16px;
  }}
  .cta-btn {{
    display: inline-block;
    background: #27ae60;
    color: white !important;
    padding: 14px 36px;
    border-radius: 8px;
    font-size: 1.1rem;
    font-weight: 700;
    text-decoration: none;
    margin-top: 16px;
    transition: background 0.2s;
  }}
  .cta-btn:hover {{ background: #219150; }}
  .benefits {{
    background: #f8f9fa;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 32px;
  }}
  .benefits h2 {{ margin-top: 0; font-size: 1.2rem; }}
  .benefits ul {{ padding-left: 20px; margin: 0; }}
  .benefits li {{ margin-bottom: 8px; }}
  .dropi-description {{ line-height: 1.7; }}
</style>

<div class="dropi-landing">
  <div class="dropi-hero">
    {'<img src="' + image_url + '" alt="' + name + '" />' if image_url else ''}
    <div class="dropi-info">
      <div class="score-pill">Score ganador: {score}/100</div>
      <h1>{name}</h1>
      {'<p class="orders-badge">&#128230; ' + orders_text + '</p>' if orders_text else ''}
      <div>
        <span class="dropi-price">{price_display}</span>
        {'<span class="dropi-compare">' + compare_display + '</span>' if compare_display else ''}
        {discount_badge}
      </div>
      <a href="{product_url}" class="cta-btn">&#128722; Comprar Ahora</a>
    </div>
  </div>

  <div class="benefits">
    <h2>&#10003; Por qué este producto es un ganador</h2>
    <ul>
      <li>Alta demanda comprobada con {orders_count:,}+ pedidos</li>
      <li>Envio rapido y seguimiento en tiempo real</li>
      <li>Garantia de satisfaccion o devolucion</li>
      <li>Atencion al cliente 24/7</li>
    </ul>
  </div>

  <div class="dropi-description">
    {description}
  </div>
</div>
""".strip()
