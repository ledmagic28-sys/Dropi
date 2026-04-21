import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Ad


DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%b %d, %Y",
    "%d %b %Y",
]


class CsvLoaderError(Exception):
    pass


def load_ads_from_csv(path: Path) -> list[Ad]:
    """Carga anuncios desde un CSV.

    Columnas esperadas (flexibles, usa lo que encuentre):
      - page_name (o 'advertiser', 'anunciante')
      - page_id (opcional)
      - ad_id (opcional)
      - start_date (o 'started', 'fecha_inicio', 'date_started')
      - stop_date (opcional)
      - copy (o 'ad_text', 'texto', 'body')
      - title (opcional)
      - platforms (opcional, coma-separado)
      - snapshot_url (opcional)
    """
    if not path.exists():
        raise CsvLoaderError(f"No existe el archivo: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise CsvLoaderError("CSV vacio o sin encabezados.")
        headers = {h.lower().strip(): h for h in reader.fieldnames}
        ads = []
        for row in reader:
            ad = _row_to_ad(row, headers)
            if ad is not None:
                ads.append(ad)
        return ads


def _pick(row: dict, headers: dict, *candidates: str) -> Optional[str]:
    for c in candidates:
        key = headers.get(c.lower())
        if key and row.get(key):
            return row[key].strip()
    return None


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    v = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_to_ad(row: dict, headers: dict) -> Optional[Ad]:
    page_name = _pick(row, headers, "page_name", "advertiser", "anunciante", "page")
    if not page_name:
        return None
    start = _parse_date(
        _pick(row, headers, "start_date", "started", "fecha_inicio", "date_started", "ad_delivery_start_time")
    )
    stop = _parse_date(
        _pick(row, headers, "stop_date", "stopped", "fecha_fin", "ad_delivery_stop_time")
    )
    copy_text = _pick(row, headers, "copy", "ad_text", "texto", "body", "ad_creative_bodies")
    title = _pick(row, headers, "title", "titulo", "ad_creative_link_titles")
    platforms_raw = _pick(row, headers, "platforms", "plataformas", "publisher_platforms")
    platforms = (
        [p.strip() for p in platforms_raw.split(",") if p.strip()]
        if platforms_raw else []
    )
    return Ad(
        ad_id=_pick(row, headers, "ad_id", "id") or "",
        page_id=_pick(row, headers, "page_id") or "",
        page_name=page_name,
        start_date=start,
        stop_date=stop,
        is_active=stop is None,
        creative_bodies=[copy_text] if copy_text else [],
        creative_link_titles=[title] if title else [],
        publisher_platforms=platforms,
        snapshot_url=_pick(row, headers, "snapshot_url", "url"),
    )
