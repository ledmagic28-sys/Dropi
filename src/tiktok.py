import time
from dataclasses import dataclass
from typing import Iterator, Optional

CREATIVE_CENTER_BASE = "https://ads.tiktok.com/business/creativecenter/inspiration"


class TikTokError(Exception):
    pass


@dataclass
class TikTokAd:
    ad_id: str
    brand_name: str
    country_code: str
    like: int = 0
    ctr: float = 0.0
    video_duration: int = 0
    industry: Optional[str] = None
    objective: Optional[str] = None
    title: Optional[str] = None
    cover_url: Optional[str] = None


@dataclass
class TikTokProduct:
    product_id: str
    name: str
    country_code: str
    category: Optional[str] = None
    rank: Optional[int] = None
    cost: Optional[float] = None
    cvr: Optional[float] = None
    ctr: Optional[float] = None
    ad_count: Optional[int] = None


class TikTokCreativeCenter:
    """Scraper del Creative Center via navegador headless (Playwright).

    Requiere: pip install playwright && playwright install chromium
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms

    def top_ads(
        self,
        country_code: str = "CO",
        period: int = 30,
        pages: int = 3,
        industry: Optional[str] = None,
        **_,
    ) -> Iterator[TikTokAd]:
        url = (
            f"{CREATIVE_CENTER_BASE}/topads/pad/en"
            f"?period={period}&region={country_code.upper()}"
        )
        for raw in self._collect(url, filter_substr="top_ads", pages=pages):
            ad = _parse_ad(raw, country_code)
            if industry and not _ad_matches_industry(ad, industry):
                continue
            yield ad

    def popular_products(
        self,
        country_code: str = "CO",
        period: int = 30,
        pages: int = 3,
        **_,
    ) -> Iterator[TikTokProduct]:
        url = (
            f"{CREATIVE_CENTER_BASE}/popular/product/pc/en"
            f"?period={period}&region={country_code.upper()}"
        )
        for raw in self._collect(url, filter_substr="popular_product", pages=pages):
            yield _parse_product(raw, country_code)

    def _collect(self, url: str, filter_substr: str, pages: int) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise TikTokError(
                "Playwright no instalado. Corre en Windows:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        materials: list[dict] = []
        seen: set[str] = set()
        industry_map: dict[str, str] = {}

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=self.headless)
            except Exception as e:
                raise TikTokError(
                    f"No se pudo lanzar Chromium: {e}. "
                    "Corre 'playwright install chromium' primero."
                )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1400, "height": 900},
                locale="en-US",
            )
            page = context.new_page()

            def on_response(response):
                url_str = response.url
                if "industry" in url_str.lower() and "list" in url_str.lower():
                    try:
                        data = response.json()
                        for item in _iter_industry_items(data):
                            key = str(item.get("value") or item.get("key") or item.get("id") or "")
                            label = item.get("label") or item.get("name") or ""
                            if key and label:
                                industry_map[key] = label
                    except Exception:
                        pass
                    return
                if filter_substr not in url_str:
                    return
                try:
                    data = response.json()
                except Exception:
                    return
                if data.get("code", 0) != 0:
                    return
                d = data.get("data", {}) or {}
                for key in ("materials", "products", "list", "creatives"):
                    items = d.get(key) or []
                    for item in items:
                        item_id = str(
                            item.get("id")
                            or item.get("product_id")
                            or item.get("material_id")
                            or item.get("creative_id")
                            or ""
                        )
                        if item_id and item_id not in seen:
                            seen.add(item_id)
                            materials.append(item)

            page.on("response", on_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            except Exception as e:
                browser.close()
                raise TikTokError(f"Error cargando {url}: {e}")

            page.wait_for_timeout(5000)

            for i in range(max(0, pages - 1)):
                try:
                    page.evaluate(
                        "() => window.scrollTo(0, document.body.scrollHeight)"
                    )
                    page.wait_for_timeout(2500)
                    try:
                        btn = page.query_selector(
                            "div[class*='ViewMore'], button:has-text('View more'), "
                            "button:has-text('Ver más'), button:has-text('Load more')"
                        )
                        if btn:
                            btn.click(timeout=2000)
                            page.wait_for_timeout(2500)
                    except Exception:
                        pass
                except Exception:
                    break

            browser.close()

        if industry_map:
            for m in materials:
                key = str(m.get("industry_key") or "")
                if key in industry_map and not m.get("industry_label_name"):
                    m["industry_label_name"] = industry_map[key]

        if not materials:
            raise TikTokError(
                "No se capturaron datos. TikTok pudo mostrar challenge, cambiar estructura, "
                "o no haber resultados para ese pais/periodo. Prueba otro pais."
            )
        return materials


def _parse_ad(raw: dict, country: str) -> TikTokAd:
    video_info = raw.get("video_info") or {}
    return TikTokAd(
        ad_id=str(raw.get("id", "") or raw.get("material_id", "")),
        brand_name=(
            raw.get("brand_name")
            or raw.get("brand")
            or raw.get("advertiser_name")
            or raw.get("account_name")
            or ""
        ),
        country_code=country,
        like=int(raw.get("like", 0) or 0),
        ctr=float(raw.get("ctr", 0) or 0),
        video_duration=int(video_info.get("duration", 0) or 0),
        industry=(
            raw.get("industry_label_name")
            or raw.get("industry_name")
            or raw.get("industry")
            or _clean_label(raw.get("industry_key"))
        ),
        objective=(
            raw.get("objective_name")
            or raw.get("objective_key")
            or raw.get("objective")
        ),
        title=(
            raw.get("ad_title")
            or raw.get("highlight_text")
            or raw.get("title")
            or raw.get("objective_desc")
            or raw.get("description")
            or ""
        ),
        cover_url=(
            video_info.get("cover")
            or raw.get("cover_url")
            or raw.get("cover")
        ),
    )


def _clean_label(label) -> Optional[str]:
    if not label or not isinstance(label, str):
        return None
    if label.startswith("label_"):
        code = label.replace("label_", "").rstrip("0")
        return f"cat-{code}" if code else None
    return label


def _parse_product(raw: dict, country: str) -> TikTokProduct:
    return TikTokProduct(
        product_id=str(raw.get("id", "") or raw.get("product_id", "")),
        name=raw.get("name") or raw.get("title") or raw.get("product_name", ""),
        country_code=country,
        category=raw.get("category_name") or raw.get("category"),
        rank=int(raw.get("rank")) if raw.get("rank") else None,
        cost=_try_float(raw.get("cost")),
        cvr=_try_float(raw.get("cvr")),
        ctr=_try_float(raw.get("ctr")),
        ad_count=int(raw.get("ad_cnt")) if raw.get("ad_cnt") else None,
    )


def _try_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _iter_industry_items(data):
    if not isinstance(data, dict):
        return
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if ("value" in node or "key" in node) and ("label" in node or "name" in node):
                yield node
            for v in node.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(node, list):
            for v in node:
                if isinstance(v, (dict, list)):
                    stack.append(v)


INDUSTRIES_HINT = {
    "apparel": ["apparel", "clothing", "fashion", "wear", "17"],
    "beauty": ["beauty", "cosmetic", "makeup", "20104", "20100"],
    "personal_care": ["personal care", "hygien", "20105"],
    "food": ["food", "beverage", "drink", "22108"],
    "electronics": ["electron", "gadget", "device", "21"],
    "home": ["home", "household", "kitchen", "furniture", "decor", "22"],
    "auto": ["auto", "car", "vehicle", "11"],
    "sports": ["sport", "fitness", "outdoor", "24"],
    "education": ["educat", "learning", "23110"],
    "finance": ["financ", "invest", "bank", "23103"],
    "travel": ["travel", "tourism", "hotel", "23102"],
    "entertainment": ["entertain", "game", "media", "23100"],
    "pet": ["pet", "animal", "dog", "cat"],
    "baby": ["baby", "infant", "kid", "child"],
}


def _ad_matches_industry(ad, filter_value: str) -> bool:
    fv = filter_value.lower().strip()
    ad_industry_text = f"{ad.industry or ''} {ad.title or ''} {ad.brand_name or ''}".lower()
    keywords = INDUSTRIES_HINT.get(fv, [fv])
    return any(kw in ad_industry_text for kw in keywords)
