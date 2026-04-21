import json
import re
import time
from datetime import datetime, timezone
from typing import Iterator, Optional

import requests

from .models import Ad

LIBRARY_URL = "https://www.facebook.com/ads/library/"
ASYNC_URL = "https://www.facebook.com/ads/library/async/search_ads/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class ScraperError(Exception):
    pass


class MetaAdLibraryScraper:
    """Best-effort scraper del Ad Library publico (sin token).

    Depende de endpoints internos de Meta que pueden cambiar sin aviso.
    Si falla, usa el comando analyze-csv con datos exportados manualmente.
    """

    def __init__(self, timeout: int = 30, rate_limit_sec: float = 1.5):
        self.timeout = timeout
        self.rate_limit_sec = rate_limit_sec
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _warm_up(self, query: str, country: str, active: bool) -> str:
        params = {
            "active_status": "active" if active else "all",
            "ad_type": "all",
            "country": country,
            "q": query,
            "search_type": "keyword_unordered",
            "media_type": "all",
        }
        resp = self.session.get(LIBRARY_URL, params=params, timeout=self.timeout)
        if not resp.ok:
            raise ScraperError(f"No se pudo cargar la pagina inicial: HTTP {resp.status_code}")
        return resp.text

    def _extract_from_initial_html(self, html: str) -> list[dict]:
        patterns = [
            r'"results":\s*(\[[^\]]*\])',
            r'"ad_archive_id":"(\d+)".*?"page_name":"([^"]+)".*?"ad_delivery_start_time":"?(\d+)"?',
        ]
        raw_ads: list[dict] = []
        block_pattern = re.compile(
            r'"ad_archive_id":"(?P<id>\d+)"[^}]*?'
            r'"page_id":"(?P<page_id>\d+)"[^}]*?'
            r'"page_name":"(?P<page_name>[^"]+)"[^}]*?'
            r'"ad_delivery_start_time":"?(?P<start>\d+)"?'
            r'(?:[^}]*?"ad_delivery_stop_time":"?(?P<stop>\d+)"?)?',
            re.DOTALL,
        )
        for m in block_pattern.finditer(html):
            raw_ads.append(m.groupdict())
        return raw_ads

    def search(
        self,
        query: str,
        country: str = "CO",
        active: bool = True,
        max_pages: int = 3,
    ) -> Iterator[Ad]:
        html = self._warm_up(query, country, active)
        raw = self._extract_from_initial_html(html)
        if not raw:
            raise ScraperError(
                "No se extrajeron anuncios del HTML. Meta cambio su estructura o "
                "bloqueo la peticion. Usa 'analyze-csv' como alternativa."
            )
        for item in raw:
            yield _raw_to_ad(item)
        time.sleep(self.rate_limit_sec)


def _raw_to_ad(raw: dict) -> Ad:
    def _ts_to_dt(ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (ValueError, TypeError):
            return None

    start = _ts_to_dt(raw.get("start"))
    stop = _ts_to_dt(raw.get("stop"))
    return Ad(
        ad_id=raw.get("id", ""),
        page_id=raw.get("page_id", ""),
        page_name=raw.get("page_name", ""),
        start_date=start,
        stop_date=stop,
        is_active=stop is None,
    )
