import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import config as _cfg
from config import COMMODITIES, ROOT
from src.scrapers.google_scraper import GoogleScraper
from src.scrapers.yahoo_scraper import YahooScraper
from src.pipeline.pipeline import Pipeline

_IO_STEPS     = {"TRAER NOTICIAS", "TRAER PRECIOS"}
_MAX_IO_WORKERS = 3   # max parallel scrapers / price fetches


def build_commodity_from_args(name: str, queries: list, start: str, end: str, summary_date: str = None, summary_window: int = None) -> dict:
    """Build a commodity dict from dashboard CLI args, inheriting ticker and settings from
    config.py when the commodity key matches an existing entry."""
    existing = next((c for c in COMMODITIES if c["name"] == name), None)

    default_window = existing["summary_window"] if existing else 30
    commodity = {
        "name": name,
        "ticker":        existing["ticker"]         if existing else "",
        "search_query":  queries,
        "scraper":       existing["scraper"]         if existing else "google",
        "news_number":   existing["news_number"]     if existing else 4,
        "start_date":    date.fromisoformat(start),
        "end_date":      date.fromisoformat(end),
        "summary_window": summary_window if summary_window is not None else default_window,
        "summary_date":   datetime.fromisoformat(summary_date) if summary_date else datetime.now(),
    }
    if existing:
        for key in ("recuperar_batch_gemini", "batch_name"):
            if key in existing:
                commodity[key] = existing[key]
    commodity["raw_path"]       = ROOT / "data" / "raw"       / name
    commodity["processed_path"] = ROOT / "data" / "processed" / name
    commodity["output_path"]    = ROOT / "output"              / name
    return commodity


def main():
    parser = argparse.ArgumentParser(description="Pipeline de análisis de sentimientos")
    parser.add_argument("--commodity", default=None, help="Nombre del commodity a procesar")
    parser.add_argument("--start",     default=None, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--end",       default=None, help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--queries",   nargs="+", default=None, help="Queries de búsqueda")
    parser.add_argument("--funciones",    nargs="+", default=None, help="Funciones a ejecutar")
    parser.add_argument("--modelos",      nargs="+", default=None, help="Modelos a utilizar")
    parser.add_argument("--summary-date",   default=None, help="Fecha del resumen YYYY-MM-DD")
    parser.add_argument("--summary-window", default=None, type=int, help="Días de noticias para el resumen")
    args = parser.parse_args()

    # Detectar modo de ejecución: dashboard (args completos) vs config.py (sin args).
    DASHBOARD_MODE = bool(args.commodity and args.start and args.end and args.queries)

    if DASHBOARD_MODE:
        # ── Modo dashboard ───────────────────────────────────────────────────
        # Todos los parámetros vienen del dashboard vía CLI / env vars.
        # Se muta en lugar de reasignar para que pipeline.py (que importó las
        # listas por referencia) vea los mismos valores actualizados.
        if args.funciones:
            _cfg.FUNCIONES.clear()
            _cfg.FUNCIONES.extend(args.funciones)
        if args.modelos:
            _cfg.MODELS.clear()
            _cfg.MODELS.extend(args.modelos)

        if os.environ.get("GEMINI_API_KEY"):
            _cfg.GEMINI_CONFIG["api_key"] = [os.environ["GEMINI_API_KEY"]]
        if os.environ.get("CLAUDE_API_KEY"):
            _cfg.CLAUDE_CONFIG["api_key"] = [os.environ["CLAUDE_API_KEY"]]

        commodities = [build_commodity_from_args(
            args.commodity, args.queries, args.start, args.end,
            args.summary_date, args.summary_window,
        )]
        print("[Main] Modo: DASHBOARD")
    else:
        # ── Modo config.py ───────────────────────────────────────────────────
        # Todo se lee directamente de config.py; no se toca ningún global.
        commodities = COMMODITIES
        print("[Main] Modo: CONFIG.PY")

    print("=" * 70)
    print("ANALISIS DE SENTIMIENTOS - INICIO DE EJECUCION")
    print("=" * 70)

    # Build one pipeline per commodity
    pipelines = [Pipeline(select_scraper(c), c) for c in commodities]
    total = len(pipelines)

    # ------------------------------------------------------------------
    # Phase 1 — I/O (parallel)
    #   TRAER NOTICIAS and TRAER PRECIOS are independent across commodities
    #   and consist entirely of network I/O, so they run concurrently.
    # ------------------------------------------------------------------
    if _IO_STEPS & set(_cfg.FUNCIONES):
        workers = min(total, _MAX_IO_WORKERS)
        print(f"\n[Main] Fase I/O  ({workers} workers en paralelo)")
        print("-" * 70)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(pipe.run_io): pipe.commodity["name"]
                for pipe in pipelines
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                    print(f"[Main] I/O completado para {name.upper()}")
                except Exception as e:
                    print(f"[Main] Error en I/O para {name.upper()}: {e}")

    # ------------------------------------------------------------------
    # Phase 2 — Models (loaded once, shared across all commodities)
    #   GPU/CPU-bound models are expensive to load; loading them once
    #   saves N-1 full load cycles compared to loading per commodity.
    # ------------------------------------------------------------------
    models = []
    if "ANALIZAR SENTIMIENTOS" in _cfg.FUNCIONES:
        print(f"\n[Main] Cargando modelos (una sola vez para todos los commodities)...")
        print("-" * 70)
        models = Pipeline.load_models()

    # ------------------------------------------------------------------
    # Phase 3 — Compute (sequential)
    #   Sentiment inference, aggregation, and summary run one commodity
    #   at a time to avoid GPU memory contention and API rate-limit issues.
    # ------------------------------------------------------------------
    compute_steps = {"ANALIZAR SENTIMIENTOS", "AGREGAR RESULTADOS", "RESUMEN", "CATALOGAR", "PRECIO FUTURO"}
    if compute_steps & set(_cfg.FUNCIONES):
        print(f"\n[Main] Fase de computo (secuencial)")
        print("-" * 70)

        for i, pipe in enumerate(pipelines, 1):
            name = pipe.commodity["name"].upper()
            print(f"\n[{i}/{total}] {name}")
            print("-" * 70)
            pipe.models = models
            pipe.run_compute()

    print("\n" + "=" * 70)
    print("EJECUCION COMPLETADA")
    print("=" * 70)


def select_scraper(commodity):
    scraper = commodity["scraper"].upper()
    if scraper == "GOOGLE":
        return GoogleScraper(commodity)
    if scraper == "YAHOO":
        return YahooScraper(commodity)
    raise ValueError(f"Scraper desconocido: '{commodity['scraper']}'. Opciones validas: GOOGLE, YAHOO.")


if __name__ == "__main__":
    main()
