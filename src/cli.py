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
from .dropi_client import DropiClient, DropiError, DropiProduct
from .models import Ad, MarketAnalysis
from .scraper import MetaAdLibraryScraper, ScraperError
from .shopify_client import ShopifyClient, ShopifyError, ShopifyPublishResult
from .tiktok import INDUSTRIES_HINT, TikTokCreativeCenter, TikTokError

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


@cli.command("dropi-products")
@click.option("--category", "-C", default=None, help="ID o nombre de categoria en Dropi.")
@click.option("--search", "-s", default=None, help="Texto de busqueda en el catalogo.")
@click.option("--min-score", default=60, type=int, show_default=True, help="Score minimo (0-100).")
@click.option("--limit", "-n", default=20, type=int, show_default=True, help="Maximo de productos a mostrar.")
@click.option("--export", type=click.Path(), default=None, help="Exportar resultados a JSON.")
def dropi_products(category: str, search: str, min_score: int, limit: int, export: str):
    """Busca productos ganadores en Dropi y los puntua (0-100)."""
    try:
        client = DropiClient()
    except DropiError as e:
        console.print(f"[red]Error Dropi:[/red] {e}")
        sys.exit(1)

    with console.status("Consultando catalogo de Dropi..."):
        try:
            products = list(
                client.get_winning_products(
                    category_id=category,
                    search=search,
                    min_score=min_score,
                    limit=limit,
                )
            )
        except DropiError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

    if not products:
        console.print(f"[yellow]Sin resultados con score >= {min_score}.[/yellow]")
        return

    console.print(f"[green]OK[/green] {len(products)} productos encontrados.\n")
    _render_dropi_products(products)

    if export:
        _export_dropi_products(products, Path(export))
        console.print(f"\n[dim]Exportado a {export}[/dim]")


@cli.command("publish-shopify")
@click.argument("product_id")
@click.option("--no-landing", is_flag=True, default=False, help="Solo crea el producto, sin landing page.")
@click.option("--draft", is_flag=True, default=False, help="Publica en borrador (no visible en tienda).")
def publish_shopify(product_id: str, no_landing: bool, draft: bool):
    """Publica un producto de Dropi (por ID) en tu tienda Shopify con landing page."""
    try:
        dropi = DropiClient()
    except DropiError as e:
        console.print(f"[red]Error Dropi:[/red] {e}")
        sys.exit(1)

    try:
        shopify = ShopifyClient()
    except ShopifyError as e:
        console.print(f"[red]Error Shopify:[/red] {e}")
        sys.exit(1)

    with console.status(f"Obteniendo producto {product_id} de Dropi..."):
        try:
            product = dropi.get_product_detail(product_id)
        except DropiError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

    from .dropi_client import _score_product
    product.score = _score_product(product)

    console.print(f"[bold]{product.name}[/bold]  score={product.score}/100")

    with console.status("Publicando en Shopify..."):
        try:
            result = shopify.publish_dropi_product(
                product,
                create_landing=not no_landing,
                published=not draft,
            )
        except ShopifyError as e:
            console.print(f"[red]Error Shopify:[/red] {e}")
            sys.exit(1)

    _render_shopify_result(result)


@cli.command("auto-publish")
@click.option("--category", "-C", default=None, help="Categoria en Dropi.")
@click.option("--search", "-s", default=None, help="Texto de busqueda.")
@click.option("--min-score", default=70, type=int, show_default=True, help="Score minimo para publicar.")
@click.option("--limit", "-n", default=5, type=int, show_default=True, help="Maximo de productos a publicar.")
@click.option("--no-landing", is_flag=True, default=False, help="Omite la landing page.")
@click.option("--draft", is_flag=True, default=False, help="Publica en borrador.")
@click.option("--dry-run", is_flag=True, default=False, help="Muestra productos sin publicar.")
def auto_publish(
    category: str,
    search: str,
    min_score: int,
    limit: int,
    no_landing: bool,
    draft: bool,
    dry_run: bool,
):
    """Pipeline automatico: encuentra ganadores en Dropi y los publica en Shopify."""
    try:
        dropi = DropiClient()
    except DropiError as e:
        console.print(f"[red]Error Dropi:[/red] {e}")
        sys.exit(1)

    if not dry_run:
        try:
            shopify = ShopifyClient()
        except ShopifyError as e:
            console.print(f"[red]Error Shopify:[/red] {e}")
            sys.exit(1)
    else:
        shopify = None  # type: ignore[assignment]

    console.print(
        Panel(
            f"Buscando productos con score >= [bold]{min_score}[/bold]  |  limite={limit}  |  "
            + ("[yellow]DRY RUN[/yellow]" if dry_run else "[green]PUBLICANDO[/green]"),
            title="[bold]Auto-Publish Dropi → Shopify[/bold]",
        )
    )

    with console.status("Buscando productos ganadores en Dropi..."):
        try:
            winners = list(
                dropi.get_winning_products(
                    category_id=category,
                    search=search,
                    min_score=min_score,
                    limit=limit,
                )
            )
        except DropiError as e:
            console.print(f"[red]Error Dropi:[/red] {e}")
            sys.exit(1)

    if not winners:
        console.print(f"[yellow]Sin productos con score >= {min_score}.[/yellow]")
        return

    console.print(f"[green]{len(winners)} ganadores encontrados.[/green]\n")
    _render_dropi_products(winners)

    if dry_run:
        console.print("\n[dim]Modo dry-run: nada fue publicado.[/dim]")
        return

    results: list[ShopifyPublishResult] = []
    for i, product in enumerate(winners, 1):
        with console.status(f"[{i}/{len(winners)}] Publicando '{product.name}'..."):
            try:
                result = shopify.publish_dropi_product(
                    product,
                    create_landing=not no_landing,
                    published=not draft,
                )
                results.append(result)
                console.print(f"  [green]✓[/green] {product.name}")
            except ShopifyError as e:
                console.print(f"  [red]✗[/red] {product.name}: {e}")

    console.print(f"\n[bold green]{len(results)}/{len(winners)} productos publicados.[/bold green]")
    for r in results:
        console.print(f"  Producto: {r.product_url}")
        if r.landing_page_url:
            console.print(f"  Landing:  {r.landing_page_url}")


def _render_dropi_products(products: list[DropiProduct]):
    t = Table(
        title="Productos Ganadores Dropi",
        show_header=True,
        header_style="bold cyan",
    )
    t.add_column("ID", style="dim", width=8)
    t.add_column("Producto")
    t.add_column("Precio", justify="right")
    t.add_column("Margen %", justify="right")
    t.add_column("Pedidos", justify="right")
    t.add_column("Stock", justify="right")
    t.add_column("Score", justify="right")

    for p in products:
        score_style = "green" if p.score >= 80 else "yellow" if p.score >= 60 else "red"
        margin_str = f"{p.margin_pct:.0f}%" if p.margin_pct else "-"
        t.add_row(
            p.id,
            p.name[:45] + ("…" if len(p.name) > 45 else ""),
            f"${p.price:,.0f}",
            margin_str,
            f"{p.orders_count:,}",
            str(p.stock),
            f"[{score_style}]{p.score}[/{score_style}]",
        )
    console.print(t)


def _render_shopify_result(result: ShopifyPublishResult):
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan")
    grid.add_column()
    grid.add_row("Tienda:", result.store_domain)
    grid.add_row("Producto ID:", result.product_id)
    grid.add_row("Producto URL:", result.product_url)
    if result.landing_page_url:
        grid.add_row("Landing URL:", result.landing_page_url)
    console.print(
        Panel(grid, title="[bold green]Publicado en Shopify[/bold green]", border_style="green")
    )


def _export_dropi_products(products: list[DropiProduct], path: Path):
    data = [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "compare_at_price": p.compare_at_price,
            "margin_pct": round(p.margin_pct, 1),
            "stock": p.stock,
            "orders_count": p.orders_count,
            "rating": p.rating,
            "score": p.score,
            "category": p.category,
            "images": p.images,
        }
        for p in products
    ]
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
