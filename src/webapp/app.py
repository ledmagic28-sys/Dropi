"""
Dashboard web de Dropi Market Radar.

- GET  /                → Dashboard HTML
- POST /api/triangulate → ejecuta la triangulación y devuelve JSON
- GET  /api/health      → health check
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from .demo_data import fake_triangulation


def create_app(demo: bool = False) -> Flask:
    base = Path(__file__).parent
    app = Flask(
        __name__,
        template_folder=str(base / "templates"),
        static_folder=str(base / "static"),
    )
    app.config["DEMO"] = demo or os.getenv("DROPI_DEMO", "").lower() in ("1", "true", "yes")

    # ── Páginas ──────────────────────────────────────────

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html", demo=app.config["DEMO"])

    # ── API ──────────────────────────────────────────────

    @app.route("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "mode": "demo" if app.config["DEMO"] else "live",
        })

    @app.route("/api/triangulate", methods=["POST"])
    def triangulate_endpoint():
        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "").strip()
        country = (payload.get("country") or "CO").strip().upper()

        if not query:
            return jsonify({"error": "Falta el parámetro 'query'."}), 400
        if len(query) > 120:
            return jsonify({"error": "El query es demasiado largo (máx 120 caracteres)."}), 400

        if app.config["DEMO"]:
            result = fake_triangulation(query, country=country)
            return jsonify(result)

        # Modo real: usa el triangulador con APIs de verdad
        try:
            result = _run_real_triangulation(query, country)
            return jsonify(result)
        except Exception as exc:
            return jsonify({
                "error": f"Fallo al consultar las fuentes: {exc}",
                "hint": "Verifica que META_ACCESS_TOKEN esté configurado y que tu IP tenga acceso a las APIs.",
            }), 502

    return app


def _run_real_triangulation(query: str, country: str) -> dict[str, Any]:
    """Ejecuta el triangulador real y aplana el resultado a JSON serializable."""
    from ..triangulator import Triangulator

    engine = Triangulator(
        meta_token=os.getenv("META_ACCESS_TOKEN"),
        ml_max_results=100,
        ads_max_pages=5,
        use_scraper_fallback=True,
    )
    r = engine.run(query=query, country=country)

    out: dict[str, Any] = {
        "query": r.query,
        "country": r.country,
        "demand_score": r.demand_score,
        "saturation_score": r.saturation_score,
        "total_sellers": r.total_sellers,
        "total_ads": r.total_ads,
        "oldest_ad_days": r.oldest_ad_days,
        "recommendation": r.recommendation,
        "recommendation_level": r.recommendation_level,
        "reasoning": r.reasoning,
        "is_demo": False,
    }

    if r.mercadolibre:
        ml = r.mercadolibre
        out["mercadolibre"] = {
            "unique_sellers": ml.unique_sellers,
            "total_listings": ml.total_listings,
            "avg_price": ml.avg_price,
            "min_price": ml.min_price,
            "max_price": ml.max_price,
            "currency": ml.currency,
            "estimated_monthly_sales": ml.estimated_monthly_sales,
            "top_sellers": ml.top_sellers,
        }
    if r.ads_library:
        ads = r.ads_library
        out["ads_library"] = {
            "unique_advertisers": ads.unique_advertisers,
            "total_ads": ads.total_ads,
            "oldest_ad_days": ads.oldest_ad_days,
            "newest_ad_days": ads.newest_ad_days,
            "avg_days_running": ads.avg_days_running,
            "new_entrants_7d": ads.new_entrants_7d,
            "new_entrants_ratio": ads.new_entrants_ratio,
            "saturation_score": ads.saturation_score,
            "platforms": ads.platforms,
            "top_advertisers": ads.top_advertisers,
        }
    if r.marketplace:
        mkt = r.marketplace
        out["marketplace"] = {
            "total_listings": mkt.total_listings,
            "min_price": mkt.min_price,
            "max_price": mkt.max_price,
            "currency": mkt.currency,
            "available": mkt.available,
            "error": mkt.error,
        }

    return out
