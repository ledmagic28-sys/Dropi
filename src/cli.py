import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .analyzer import analyze
from .arbitrage import find_opportunities
from .client import MetaAdLibraryClient, MetaAdLibraryError
from .csv_loader import CsvLoaderError, load_ads_from_csv
from .models import Ad, MarketAnalysis
from .scraper import MetaAdLibraryScraper, ScraperError
from .tiktok import TikTokCreativeCenter, TikTokError

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
@click.option("--pages", default=3, type=int, help="Paginas a traer.")
def discover(country: str, period: str, pages: int):
    """Descubre top anuncios y productos trending en TikTok (sin token)."""
    tt = TikTokCreativeCenter()
    period_int = int(period)

    with console.status(f"Cargando top productos en {country} (ultimos {period}d)..."):
        try:
            products = list(tt.popular_products(country_code=country, period=period_int, pages=pages))
        except TikTokError as e:
            console.print(f"[red]TikTok error (productos):[/red] {e}")
            products = []

    with console.status(f"Cargando top anuncios en {country} (ultimos {period}d)..."):
        try:
            ads = list(tt.top_ads(country_code=country, period=period_int, pages=pages))
        except TikTokError as e:
            console.print(f"[red]TikTok error (anuncios):[/red] {e}")
            ads = []

    if not products and not ads:
        console.print(
            "[yellow]Sin datos.[/yellow] TikTok puede estar bloqueando la peticion. "
            "Prueba otro pais o cambia el periodo."
        )
        return

    if products:
        t = Table(title=f"Top productos trending en {country} ({period}d)", header_style="bold")
        t.add_column("#", justify="right")
        t.add_column("Producto", style="cyan")
        t.add_column("Categoria")
        t.add_column("CVR%", justify="right")
        t.add_column("# anuncios", justify="right")
        for i, p in enumerate(products[:50], 1):
            t.add_row(
                str(p.rank or i),
                (p.name or "")[:60],
                (p.category or "")[:25],
                f"{p.cvr:.2f}" if p.cvr else "-",
                str(p.ad_count) if p.ad_count else "-",
            )
        console.print(t)

    if ads:
        t = Table(title=f"Top anuncios en {country} ({period}d)", header_style="bold")
        t.add_column("Marca", style="cyan")
        t.add_column("Industria")
        t.add_column("Likes", justify="right")
        t.add_column("CTR%", justify="right")
        t.add_column("Duracion s", justify="right")
        for ad in ads[:30]:
            t.add_row(
                ad.brand_name[:30],
                (ad.industry or "")[:25],
                _humanize(ad.like),
                f"{ad.ctr:.2f}" if ad.ctr else "-",
                str(ad.video_duration) if ad.video_duration else "-",
            )
        console.print(t)


@cli.command()
@click.option("--source", "-s", required=True, help="Pais fuente (donde ya pega).")
@click.option("--target", "-t", required=True, help="Pais objetivo (donde llevar el producto).")
@click.option("--period", default=30, type=click.Choice(["7", "30", "120"]))
@click.option("--pages", default=4, type=int, help="Paginas por pais.")
def arbitrage(source: str, target: str, period: str, pages: int):
    """Productos hot en pais FUENTE con poca competencia en pais OBJETIVO.

    Ejemplo:
      python -m src.cli arbitrage -s US -t CO
    """
    tt = TikTokCreativeCenter()
    period_int = int(period)

    with console.status(f"Cargando productos en {source}..."):
        try:
            source_products = list(
                tt.popular_products(country_code=source, period=period_int, pages=pages)
            )
        except TikTokError as e:
            console.print(f"[red]Error cargando {source}:[/red] {e}")
            sys.exit(1)

    with console.status(f"Cargando productos en {target}..."):
        try:
            target_products = list(
                tt.popular_products(country_code=target, period=period_int, pages=pages)
            )
        except TikTokError as e:
            console.print(f"[yellow]No se pudo cargar {target}:[/yellow] {e}")
            target_products = []

    console.print(
        f"[green]OK[/green] {len(source_products)} productos en {source}, "
        f"{len(target_products)} en {target}.\n"
    )

    opportunities = find_opportunities(source_products, target_products)

    if not opportunities:
        console.print(
            "[yellow]No se encontraron oportunidades claras.[/yellow] "
            "Los productos top del fuente ya aparecen en el objetivo."
        )
        return

    t = Table(
        title=f"Oportunidades de arbitraje: {source} -> {target}",
        header_style="bold",
    )
    t.add_column("#", justify="right")
    t.add_column("Producto", style="cyan", max_width=40)
    t.add_column("Rank en " + source, justify="right")
    t.add_column("CVR%", justify="right")
    t.add_column("Ads", justify="right")
    t.add_column("Score", justify="right")
    t.add_column("Por que")
    for i, op in enumerate(opportunities[:30], 1):
        color = "green" if op.gap_score >= 70 else "yellow" if op.gap_score >= 40 else "white"
        t.add_row(
            str(i),
            op.product_name[:40],
            str(op.source_rank),
            f"{op.source_cvr:.1f}" if op.source_cvr else "-",
            str(op.source_ad_count) if op.source_ad_count else "-",
            f"[{color}]{op.gap_score}[/{color}]",
            op.reason,
        )
    console.print(t)

    console.print(
        "\n[bold]Interpretacion:[/bold]\n"
        "  - Score >=70 [green]verde[/green]: fuerte candidato, priorizar\n"
        "  - Score 40-69 [yellow]amarillo[/yellow]: viable, testear con creative propio\n"
        "  - Score <40: debil, probablemente nicho muy especifico o producto de moda pasajera\n\n"
        "[dim]Nota: 'sin presencia detectable' = no en top trending del objetivo. "
        "Aun puede haber competencia media. Cruza con Meta Ad Library cuando tengas token.[/dim]"
    )


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
