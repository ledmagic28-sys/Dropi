import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .analyzer import analyze
from .arbitrage import find_opportunities
from .client import MetaAdLibraryClient, MetaAdLibraryError
from .csv_loader import CsvLoaderError, load_ads_from_csv
from .mercadolibre import MercadoLibreResult
from .models import Ad, MarketAnalysis
from .scraper import MetaAdLibraryScraper, ScraperError
from .tiktok import INDUSTRIES_HINT, TikTokCreativeCenter, TikTokError
from .triangulator import Triangulator, TriangulationResult

console = Console()


@click.group()
def cli():
    """Dropi Ads — analisis de competencia en Meta Ad Library."""
    pass


@cli.command()
@click.argument("query")
@click.option("--country", "-c", default="CO", help="Codigo ISO del pais (CO, MX, ES, US...).")
@click.option("--active/--all", default=True, help="Solo anuncios activos (default) o todos.")
@click.option("--max-pages", default=5, type=int, help="Paginas maximas a traer.")
@click.option("--limit", default=100, type=int, help="Anuncios por pagina.")
@click.option("--export", type=click.Path(), help="Exportar anuncios crudos a archivo JSON.")
def search(query: str, country: str, active: bool, max_pages: int, limit: int, export: str):
    """Busca anuncios y analiza saturacion del mercado."""
    active_status = "ACTIVE" if active else "ALL"
    try:
        client = MetaAdLibraryClient()
    except MetaAdLibraryError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Crea .env desde .env.example y agrega tu token.")
        sys.exit(1)

    with console.status(f"Consultando Meta Ad Library para '[bold]{query}[/bold]' en {country}..."):
        try:
            ads = list(
                client.search(
                    query=query,
                    country=country,
                    active_status=active_status,
                    limit=limit,
                    max_pages=max_pages,
                )
            )
        except MetaAdLibraryError as e:
            console.print(f"[red]Error API:[/red] {e}")
            sys.exit(1)

    console.print(f"[green]OK[/green] {len(ads)} anuncios encontrados.\n")

    analysis = analyze(ads, query=query, country=country)
    _render_analysis(analysis)
    _render_top_ads(ads)

    if export:
        _export_ads(ads, Path(export))
        console.print(f"\n[dim]Exportado a {export}[/dim]")


@cli.command()
@click.argument("query")
@click.option("--country", "-c", default="CO", help="Codigo ISO del pais.")
@click.option("--active/--all", default=True, help="Solo anuncios activos o todos.")
@click.option("--max-pages", default=3, type=int)
@click.option("--export", type=click.Path(), help="Exportar anuncios a JSON.")
def scrape(query: str, country: str, active: bool, max_pages: int, export: str):
    """Scraping directo del Ad Library publico (sin token). Best-effort."""
    scraper = MetaAdLibraryScraper()
    with console.status(f"Scrapeando '{query}' en {country}..."):
        try:
            ads = list(scraper.search(query=query, country=country, active=active, max_pages=max_pages))
        except ScraperError as e:
            console.print(f"[red]Scraper fallo:[/red] {e}")
            console.print(
                "[yellow]Alternativa:[/yellow] usa 'analyze-csv' con datos exportados "
                "desde una extension de Chrome tipo Ad Library Data Extractor."
            )
            sys.exit(1)

    console.print(f"[green]OK[/green] {len(ads)} anuncios encontrados.\n")
    analysis = analyze(ads, query=query, country=country)
    _render_analysis(analysis)
    _render_top_ads(ads)
    if export:
        _export_ads(ads, Path(export))
        console.print(f"\n[dim]Exportado a {export}[/dim]")


@cli.command(name="analyze-csv")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--query", default="(csv)", help="Etiqueta de la busqueda.")
@click.option("--country", "-c", default="CO", help="Pais analizado.")
def analyze_csv(csv_path: str, query: str, country: str):
    """Analiza anuncios desde un CSV exportado manualmente.

    Formato esperado: columnas como page_name, start_date, copy, etc.
    Sirve cualquier CSV exportado de extensiones del Ad Library.
    """
    try:
        ads = load_ads_from_csv(Path(csv_path))
    except CsvLoaderError as e:
        console.print(f"[red]Error cargando CSV:[/red] {e}")
        sys.exit(1)

    console.print(f"[green]OK[/green] {len(ads)} anuncios cargados desde CSV.\n")
    analysis = analyze(ads, query=query, country=country)
    _render_analysis(analysis)
    _render_top_ads(ads)


@cli.command()
@click.option("--country", "-c", default="CO", help="Pais (CO, MX, US, BR, ES...).")
@click.option("--period", default=30, type=click.Choice(["7", "30", "120"]), help="Dias.")
@click.option("--pages", default=6, type=int, help="Paginas a traer (mas = mas resultados).")
@click.option(
    "--industry",
    "-i",
    default=None,
    help=(
        "Filtrar por industria. Usa alias (apparel, beauty, food, home, auto, sports, "
        "electronics, personal_care, finance, travel, education, entertainment) "
        "o codigo completo (ej: 22108000000)."
    ),
)
def discover(country: str, period: str, pages: int, industry: Optional[str]):
    """Descubre top anuncios trending en TikTok (sin token)."""
    tt = TikTokCreativeCenter()
    period_int = int(period)
    industry_code = _resolve_industry(industry) if industry else None

    status_msg = f"Cargando top anuncios en {country} (ultimos {period}d"
    if industry_code:
        status_msg += f", industria={industry})"
    else:
        status_msg += ")"

    with console.status(status_msg + "..."):
        try:
            ads = list(tt.top_ads(
                country_code=country, period=period_int, pages=pages, industry=industry_code
            ))
        except TikTokError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

    if not ads:
        console.print(
            "[yellow]Sin datos.[/yellow] TikTok pudo mostrar challenge. "
            "Prueba otro pais o periodo."
        )
        return

    console.print(f"[green]OK[/green] {len(ads)} anuncios trending en {country}.\n")

    t = Table(
        title=f"Top anuncios en {country} (ultimos {period}d)",
        header_style="bold",
        show_lines=False,
    )
    t.add_column("#", justify="right", style="dim")
    t.add_column("Marca / Anunciante", style="cyan", max_width=25)
    t.add_column("Titulo del anuncio", max_width=50)
    t.add_column("Industria", max_width=20)
    t.add_column("Likes", justify="right")
    t.add_column("CTR%", justify="right")
    t.add_column("Dur", justify="right")
    for i, ad in enumerate(ads[:40], 1):
        t.add_row(
            str(i),
            (ad.brand_name or "-")[:25],
            (ad.title or "-")[:50],
            (ad.industry or "-")[:20],
            _humanize(ad.like),
            f"{ad.ctr:.2f}" if ad.ctr else "-",
            f"{ad.video_duration}s" if ad.video_duration else "-",
        )
    console.print(t)

    from collections import Counter
    brand_counts = Counter(a.brand_name for a in ads if a.brand_name).most_common(10)
    industry_counts = Counter(a.industry for a in ads if a.industry).most_common(10)

    if brand_counts:
        t2 = Table(title="Anunciantes con mas anuncios trending", header_style="bold")
        t2.add_column("Marca", style="cyan")
        t2.add_column("# anuncios", justify="right")
        for brand, n in brand_counts:
            t2.add_row(brand, str(n))
        console.print(t2)

    if industry_counts:
        t3 = Table(title="Industrias dominantes", header_style="bold")
        t3.add_column("Industria", style="cyan")
        t3.add_column("# anuncios", justify="right")
        for ind, n in industry_counts:
            t3.add_row(ind, str(n))
        console.print(t3)


@cli.command()
@click.option("--source", "-s", required=True, help="Pais fuente (donde ya pega).")
@click.option("--target", "-t", required=True, help="Pais objetivo (donde llevar el producto).")
@click.option("--period", default=30, type=click.Choice(["7", "30", "120"]))
@click.option("--pages", default=6, type=int, help="Paginas por pais.")
@click.option(
    "--industry",
    "-i",
    default=None,
    help="Filtrar por industria (apparel, beauty, food, home, auto, sports...).",
)
def arbitrage(source: str, target: str, period: str, pages: int, industry: Optional[str]):
    """Anunciantes/productos hot en pais FUENTE con poca presencia en pais OBJETIVO.

    Ejemplo:
      python -m src.cli arbitrage -s US -t CO -i beauty
    """
    tt = TikTokCreativeCenter()
    period_int = int(period)
    industry_code = _resolve_industry(industry) if industry else None

    with console.status(f"Cargando anuncios en {source}..."):
        try:
            source_ads = list(
                tt.top_ads(
                    country_code=source, period=period_int, pages=pages, industry=industry_code
                )
            )
        except TikTokError as e:
            console.print(f"[red]Error cargando {source}:[/red] {e}")
            sys.exit(1)

    with console.status(f"Cargando anuncios en {target}..."):
        try:
            target_ads = list(
                tt.top_ads(
                    country_code=target, period=period_int, pages=pages, industry=industry_code
                )
            )
        except TikTokError as e:
            console.print(f"[yellow]No se pudo cargar {target}:[/yellow] {e}")
            target_ads = []

    console.print(
        f"[green]OK[/green] {len(source_ads)} anuncios en {source}, "
        f"{len(target_ads)} en {target}.\n"
    )

    target_brands = {(a.brand_name or "").strip().lower() for a in target_ads if a.brand_name}
    target_titles = [(a.title or "").strip().lower() for a in target_ads if a.title]

    from collections import defaultdict

    groups = defaultdict(list)
    for ad in source_ads:
        key = (ad.brand_name or "").strip().lower()
        if not key:
            key = ((ad.title or "")[:30]).strip().lower()
        if not key:
            continue
        groups[key].append(ad)

    opportunities = []
    for brand_key, ads_group in groups.items():
        if brand_key in target_brands:
            continue
        sample = ads_group[0]
        display_title = sample.title or sample.brand_name or "(sin titulo)"
        if any(brand_key in t for t in target_titles if t):
            continue

        total_likes = sum(a.like for a in ads_group)
        avg_ctr = sum(a.ctr for a in ads_group) / len(ads_group) if ads_group else 0
        num_ads = len(ads_group)

        score = 0
        if num_ads >= 5:
            score += 30
        elif num_ads >= 3:
            score += 20
        elif num_ads >= 2:
            score += 10
        else:
            score += 5

        if total_likes >= 10000:
            score += 35
        elif total_likes >= 1000:
            score += 25
        elif total_likes >= 100:
            score += 15
        elif total_likes >= 10:
            score += 5

        if avg_ctr >= 1.0:
            score += 20
        elif avg_ctr >= 0.5:
            score += 10
        elif avg_ctr >= 0.2:
            score += 5

        industries = {a.industry for a in ads_group if a.industry}
        industry = ", ".join(list(industries)[:2]) if industries else "-"

        opportunities.append({
            "brand": sample.brand_name or "(sin marca)",
            "title": display_title[:55],
            "industry": industry,
            "num_ads": num_ads,
            "likes": total_likes,
            "ctr": avg_ctr,
            "score": min(100, score),
        })

    opportunities.sort(key=lambda x: x["score"], reverse=True)

    if not opportunities:
        console.print(
            "[yellow]No se encontraron oportunidades claras.[/yellow] "
            "Los anunciantes top del fuente ya aparecen en el objetivo, o "
            "el target no devolvio datos suficientes."
        )
        return

    t = Table(
        title=f"Oportunidades de arbitraje: {source} -> {target}",
        header_style="bold",
    )
    t.add_column("#", justify="right", style="dim")
    t.add_column("Marca / Titulo", style="cyan", max_width=40)
    t.add_column("Industria", max_width=20)
    t.add_column("Ads", justify="right")
    t.add_column("Likes", justify="right")
    t.add_column("CTR%", justify="right")
    t.add_column("Score", justify="right")
    for i, op in enumerate(opportunities[:30], 1):
        color = "green" if op["score"] >= 70 else "yellow" if op["score"] >= 40 else "white"
        display = op["brand"] if op["brand"] != "(sin marca)" else op["title"]
        t.add_row(
            str(i),
            display[:40],
            op["industry"][:20],
            str(op["num_ads"]),
            _humanize(op["likes"]),
            f"{op['ctr']:.2f}" if op["ctr"] else "-",
            f"[{color}]{op['score']}[/{color}]",
        )
    console.print(t)

    console.print(
        "\n[bold]Interpretacion:[/bold]\n"
        "  - Score >=70 [green]verde[/green]: fuerte candidato, priorizar\n"
        "  - Score 40-69 [yellow]amarillo[/yellow]: viable con creative propio\n"
        "  - Score <40: debil (moda pasajera o volumen muy bajo)\n\n"
        "[dim]Comparacion basada en marcas/titulos de anuncios trending en TikTok.\n"
        "Falsos positivos posibles si el anunciante usa otro nombre en {target}.\n"
        "Cruza con Meta Ad Library cuando tengas token aprobado.[/dim]".format(target=target)
    )


@cli.command()
@click.argument("query")
@click.option("--pais", "-p", default="CO", help="Codigo ISO del pais (CO, MX, AR, CL, PE...).")
@click.option("--export", type=click.Path(), help="Exportar resultado a JSON.")
def triangulate(query: str, pais: str, export: Optional[str]):
    """Triangula un producto en Mercado Libre + FB Ads Library + FB Marketplace.

    Ejemplo:
      dropi triangulate "masajeador cuello electrico" --pais CO
    """
    console.print(
        f"\n[bold cyan]Triangulando[/bold cyan] '[bold]{query}[/bold]' en [bold]{pais}[/bold]...\n"
        "Consultando 3 fuentes en paralelo, espera unos segundos.\n"
    )

    import os
    engine = Triangulator(
        meta_token=os.getenv("META_ACCESS_TOKEN"),
        ml_max_results=100,
        ads_max_pages=5,
        use_scraper_fallback=True,
    )

    with console.status("Consultando Mercado Libre, Meta Ad Library y Facebook Marketplace..."):
        result = engine.run(query=query, country=pais)

    _render_triangulation(result)

    if export:
        _export_triangulation(result, Path(export))
        console.print(f"\n[dim]Exportado a {export}[/dim]")


def _render_triangulation(r: TriangulationResult):
    # ── Resumen de fuentes ─────────────────────────────────
    sources_table = Table(title="Datos por fuente", header_style="bold", show_lines=True)
    sources_table.add_column("Fuente", style="cyan", min_width=22)
    sources_table.add_column("Vendedores / Anunciantes", justify="right")
    sources_table.add_column("Publicaciones / Anuncios", justify="right")
    sources_table.add_column("Detalle")

    if r.mercadolibre:
        ml = r.mercadolibre
        currency = ml.currency
        price_str = (
            f"${ml.min_price:,.0f}–${ml.max_price:,.0f} {currency}"
            if ml.min_price > 0 else "N/D"
        )
        sources_table.add_row(
            "🟡  Mercado Libre",
            str(ml.unique_sellers),
            str(ml.total_listings),
            f"Precio: {price_str} · Ventas/mes est.: {ml.estimated_monthly_sales:,}",
        )
    else:
        sources_table.add_row("🟡  Mercado Libre", "—", "—", "[dim]Sin datos[/dim]")

    if r.ads_library:
        ads = r.ads_library
        sources_table.add_row(
            "🔵  Facebook Ad Library",
            str(ads.unique_advertisers),
            str(ads.total_ads),
            f"Anuncio mas viejo: {ads.oldest_ad_days}d · Nuevos 7d: {ads.new_entrants_7d}",
        )
    else:
        sources_table.add_row("🔵  Facebook Ad Library", "—", "—", "[dim]Sin datos[/dim]")

    if r.marketplace and r.marketplace.available:
        mkt = r.marketplace
        price_mkt = (
            f"${mkt.min_price:,.0f}–${mkt.max_price:,.0f} {mkt.currency}"
            if mkt.min_price > 0 else "N/D"
        )
        sources_table.add_row(
            "🟢  Facebook Marketplace",
            "—",
            str(mkt.total_listings),
            f"Precio: {price_mkt}",
        )
    else:
        mkt_note = "[dim]Requiere Playwright instalado[/dim]"
        if r.marketplace and r.marketplace.error:
            mkt_note = f"[dim]{r.marketplace.error[:60]}[/dim]"
        sources_table.add_row("🟢  Facebook Marketplace", "—", "—", mkt_note)

    console.print(sources_table)

    # ── Scores combinados ─────────────────────────────────
    demand_color = "green" if r.demand_score >= 60 else "yellow" if r.demand_score >= 30 else "red"
    sat_color    = "green" if r.saturation_score < 35 else "yellow" if r.saturation_score < 65 else "red"

    summary = Table.grid(padding=(0, 3))
    summary.add_column(style="bold", min_width=28)
    summary.add_column()
    summary.add_row("Demanda del mercado:",    f"[bold {demand_color}]{r.demand_score}/100[/bold {demand_color}]")
    summary.add_row("Saturacion:",             f"[bold {sat_color}]{r.saturation_score}/100[/bold {sat_color}]")
    summary.add_row("Vendedores totales:",     str(r.total_sellers))
    summary.add_row("Anuncios pagados activos:", str(r.total_ads))
    if r.oldest_ad_days > 0:
        summary.add_row("Veterano mas antiguo:", f"{r.oldest_ad_days} dias corriendo")

    console.print(Panel(summary, title="[bold]Resumen triangulado[/bold]", border_style="cyan"))

    # ── Recomendación ─────────────────────────────────────
    level_color = {
        "TESTEAR":               "green",
        "TESTEAR_DIFERENCIACION": "yellow",
        "EVITAR":                "red",
        "SIN_DATOS":             "dim",
    }.get(r.recommendation_level, "white")

    console.print(Panel(
        f"[bold {level_color}]{r.recommendation}[/bold {level_color}]",
        title="[bold]Recomendacion[/bold]",
        border_style=level_color,
    ))

    if r.reasoning:
        console.print("[bold]Por que:[/bold]")
        for line in r.reasoning:
            console.print(f"  - {line}")
        console.print()


def _export_triangulation(r: TriangulationResult, path: Path):
    import dataclasses
    data = {
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
        "mercadolibre": None,
        "ads_library": None,
        "marketplace": None,
    }
    if r.mercadolibre:
        ml = r.mercadolibre
        data["mercadolibre"] = {
            "total_listings": ml.total_listings,
            "unique_sellers": ml.unique_sellers,
            "avg_price": ml.avg_price,
            "min_price": ml.min_price,
            "max_price": ml.max_price,
            "currency": ml.currency,
            "estimated_monthly_sales": ml.estimated_monthly_sales,
        }
    if r.ads_library:
        ads = r.ads_library
        data["ads_library"] = {
            "total_ads": ads.total_ads,
            "unique_advertisers": ads.unique_advertisers,
            "oldest_ad_days": ads.oldest_ad_days,
            "newest_ad_days": ads.newest_ad_days,
            "avg_days_running": ads.avg_days_running,
            "new_entrants_7d": ads.new_entrants_7d,
            "saturation_score": ads.saturation_score,
        }
    if r.marketplace:
        mkt = r.marketplace
        data["marketplace"] = {
            "total_listings": mkt.total_listings,
            "min_price": mkt.min_price,
            "max_price": mkt.max_price,
            "currency": mkt.currency,
            "available": mkt.available,
        }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_industry(value: str) -> str:
    v = value.strip().lower()
    if v in INDUSTRIES_HINT:
        return INDUSTRIES_HINT[v]
    return value.strip()


def _humanize(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _render_analysis(a: MarketAnalysis):
    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold cyan")
    header.add_column()
    header.add_row("Busqueda:", f"{a.query}  ({a.country})")
    header.add_row("Total anuncios:", str(a.total_ads))
    header.add_row("Anunciantes unicos:", str(a.unique_advertisers))
    header.add_row("Anuncio mas viejo:", f"{a.oldest_ad_days} dias")
    header.add_row("Promedio corriendo:", f"{a.avg_days_running} dias")
    header.add_row("Nuevos (7d):", f"{a.new_entrants_7d} ({int(a.new_entrants_ratio*100)}%)")
    if a.platforms:
        plats = ", ".join(f"{k}:{v}" for k, v in a.platforms.items())
        header.add_row("Plataformas:", plats)
    console.print(Panel(header, title="[bold]Resumen de mercado[/bold]", border_style="cyan"))

    color = _score_color(a.saturation_score)
    score_panel = Panel(
        f"[bold {color}]Saturacion: {a.saturation_score}/100[/bold {color}]\n\n"
        f"[bold]{a.recommendation}[/bold]",
        title="[bold]Recomendacion[/bold]",
        border_style=color,
    )
    console.print(score_panel)

    if a.reasoning:
        console.print("[bold]Por que:[/bold]")
        for r in a.reasoning:
            console.print(f"  - {r}")
        console.print()

    if a.top_advertisers:
        t = Table(title="Top anunciantes", show_header=True, header_style="bold")
        t.add_column("Pagina")
        t.add_column("Anuncios", justify="right")
        for name, count in a.top_advertisers:
            t.add_row(name, str(count))
        console.print(t)


def _render_top_ads(ads: list[Ad], n: int = 5):
    if not ads:
        return
    longest = sorted(ads, key=lambda x: x.days_running, reverse=True)[:n]
    t = Table(title=f"Top {n} anuncios con mas tiempo corriendo", show_header=True, header_style="bold")
    t.add_column("Pagina", style="cyan")
    t.add_column("Dias", justify="right")
    t.add_column("Copy (preview)")
    for ad in longest:
        copy = ad.primary_copy[:80].replace("\n", " ")
        t.add_row(ad.page_name, str(ad.days_running), copy + ("..." if len(ad.primary_copy) > 80 else ""))
    console.print(t)


def _export_ads(ads: list[Ad], path: Path):
    data = []
    for a in ads:
        data.append({
            "ad_id": a.ad_id,
            "page_name": a.page_name,
            "page_id": a.page_id,
            "start_date": a.start_date.isoformat() if a.start_date else None,
            "stop_date": a.stop_date.isoformat() if a.stop_date else None,
            "days_running": a.days_running,
            "copy": a.primary_copy,
            "title": a.primary_title,
            "platforms": a.publisher_platforms,
            "snapshot_url": a.snapshot_url,
        })
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _score_color(score: int) -> str:
    if score < 25:
        return "yellow"
    if score < 50:
        return "green"
    if score < 75:
        return "orange3"
    return "red"


if __name__ == "__main__":
    cli()
