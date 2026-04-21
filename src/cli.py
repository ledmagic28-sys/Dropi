import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .analyzer import analyze
from .client import MetaAdLibraryClient, MetaAdLibraryError
from .models import Ad, MarketAnalysis

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
