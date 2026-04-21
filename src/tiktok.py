import time
from dataclasses import dataclass
from typing import Iterator, Optional

import requests

CREATIVE_CENTER_BASE = "https://ads.tiktok.com/creative_radar_api/v1"
REFERER = "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pad/en"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": REFERER,
    "Origin": "https://ads.tiktok.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Timezone-Name": "America/Bogota",
    "Web-Id": "7000000000000000000",
}


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
    """Cliente publico del Creative Center de TikTok (sin auth)."""

    def __init__(self, timeout: int = 30, rate_limit: float = 1.0):
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, path: str, params: dict) -> dict:
        url = f"{CREATIVE_CENTER_BASE}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if not resp.ok:
            raise TikTokError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError:
            raise TikTokError(f"Respuesta no-JSON: {resp.text[:300]}")
        code = data.get("code")
        if code not in (0, None):
            raise TikTokError(f"TikTok API code={code}: {data.get('msg', data)}")
        return data

    def top_ads(
        self,
        country_code: str = "CO",
        period: int = 30,
        industry: Optional[str] = None,
        pages: int = 3,
        limit: int = 20,
    ) -> Iterator[TikTokAd]:
        for page in range(1, pages + 1):
            params = {
                "period": period,
                "page": page,
                "limit": limit,
                "order_by": "for_you",
                "country_code": country_code,
            }
            if industry:
                params["industry"] = industry
            try:
                data = self._get("/top_ads/v2/list", params)
            except TikTokError:
                if page == 1:
                    raise
                return
            materials = data.get("data", {}).get("materials", [])
            if not materials:
                return
            for raw in materials:
                yield _parse_ad(raw, country_code)
            time.sleep(self.rate_limit)

    def popular_products(
        self,
        country_code: str = "CO",
        period: int = 30,
        pages: int = 3,
        limit: int = 20,
    ) -> Iterator[TikTokProduct]:
        paths = ["/popular_products/list", "/popular_product/list"]
        for page in range(1, pages + 1):
            params = {
                "period": period,
                "page": page,
                "limit": limit,
                "country_code": country_code,
                "sort_by": "vv_growth_rate",
            }
            data = None
            last_err: Optional[Exception] = None
            for p in paths:
                try:
                    data = self._get(p, params)
                    break
                except TikTokError as e:
                    last_err = e
            if data is None:
                if page == 1 and last_err:
                    raise last_err
                return
            materials = (
                data.get("data", {}).get("products")
                or data.get("data", {}).get("materials")
                or []
            )
            if not materials:
                return
            for raw in materials:
                yield _parse_product(raw, country_code)
            time.sleep(self.rate_limit)


def _parse_ad(raw: dict, country: str) -> TikTokAd:
    video_info = raw.get("video_info") or {}
    return TikTokAd(
        ad_id=str(raw.get("id", "") or raw.get("material_id", "")),
        brand_name=raw.get("brand_name") or raw.get("brand", "") or "",
        country_code=country,
        like=int(raw.get("like", 0) or 0),
        ctr=float(raw.get("ctr", 0) or 0),
        video_duration=int(video_info.get("duration", 0) or 0),
        industry=raw.get("industry_key") or raw.get("industry"),
        objective=raw.get("objective_key") or raw.get("objective"),
        title=raw.get("objective_desc") or raw.get("title") or raw.get("ad_title"),
        cover_url=video_info.get("cover") or raw.get("cover"),
    )


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
