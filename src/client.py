import os
import time
from datetime import datetime
from typing import Iterator, Optional

import requests
from dotenv import load_dotenv

from .models import Ad

load_dotenv()

META_BASE_URL = "https://graph.facebook.com"


class MetaAdLibraryError(Exception):
    pass


class MetaAdLibraryClient:
    def __init__(
        self,
        access_token: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout: int = 30,
    ):
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN")
        if not self.access_token:
            raise MetaAdLibraryError(
                "Falta META_ACCESS_TOKEN. Configuralo en .env o pasalo explicitamente."
            )
        self.api_version = api_version or os.getenv("META_API_VERSION", "v21.0")
        self.timeout = timeout
        self.session = requests.Session()

    def _endpoint(self) -> str:
        return f"{META_BASE_URL}/{self.api_version}/ads_archive"

    def search(
        self,
        query: str,
        country: str = "CO",
        ad_type: str = "ALL",
        active_status: str = "ACTIVE",
        limit: int = 100,
        max_pages: int = 10,
    ) -> Iterator[Ad]:
        fields = ",".join([
            "id",
            "page_id",
            "page_name",
            "ad_creation_time",
            "ad_delivery_start_time",
            "ad_delivery_stop_time",
            "ad_creative_bodies",
            "ad_creative_link_titles",
            "ad_creative_link_descriptions",
            "ad_creative_link_captions",
            "ad_snapshot_url",
            "publisher_platforms",
            "languages",
        ])
        params = {
            "access_token": self.access_token,
            "search_terms": query,
            "ad_reached_countries": f"['{country}']",
            "ad_type": ad_type,
            "ad_active_status": active_status,
            "fields": fields,
            "limit": limit,
        }
        url = self._endpoint()
        pages = 0
        while url and pages < max_pages:
            resp = self.session.get(url, params=params if pages == 0 else None, timeout=self.timeout)
            if resp.status_code == 429:
                time.sleep(5)
                continue
            if not resp.ok:
                raise MetaAdLibraryError(
                    f"Meta API error {resp.status_code}: {resp.text[:500]}"
                )
            data = resp.json()
            if "error" in data:
                raise MetaAdLibraryError(f"Meta API error: {data['error']}")
            for raw in data.get("data", []):
                yield _parse_ad(raw)
            url = data.get("paging", {}).get("next")
            params = None
            pages += 1


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_ad(raw: dict) -> Ad:
    start = _parse_datetime(raw.get("ad_delivery_start_time"))
    stop = _parse_datetime(raw.get("ad_delivery_stop_time"))
    return Ad(
        ad_id=str(raw.get("id", "")),
        page_id=str(raw.get("page_id", "")),
        page_name=raw.get("page_name", ""),
        start_date=start,
        stop_date=stop,
        is_active=stop is None,
        creative_bodies=raw.get("ad_creative_bodies", []) or [],
        creative_link_titles=raw.get("ad_creative_link_titles", []) or [],
        creative_link_descriptions=raw.get("ad_creative_link_descriptions", []) or [],
        creative_link_captions=raw.get("ad_creative_link_captions", []) or [],
        publisher_platforms=raw.get("publisher_platforms", []) or [],
        languages=raw.get("languages", []) or [],
        snapshot_url=raw.get("ad_snapshot_url"),
    )
