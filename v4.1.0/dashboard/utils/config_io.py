"""
Manejo del archivo de configuración de commodities.

Estructura esperada del JSON:
{
    "oro":      {"queries": ["gold price", "gold market"], "label": "Oro"},
    "petroleo": {"queries": ["crude oil", "WTI"],         "label": "Petróleo"},
    ...
}
"""

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


def load_commodities(config_path: Path) -> Dict[str, dict]:
    """Carga el dict de commodities. Devuelve {} si no existe."""
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_commodities(config_path: Path, commodities: Dict[str, dict]) -> None:
    """Guarda el dict de commodities, creando carpetas si hace falta."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(commodities, f, indent=2, ensure_ascii=False)


def add_commodity(
    config_path: Path,
    key: str,
    label: str,
    queries: List[str],
) -> None:
    """Añade o sobrescribe un commodity."""
    commodities = load_commodities(config_path)
    commodities[key] = {"label": label, "queries": queries}
    save_commodities(config_path, commodities)


def get_last_update_date(key: str, project_root: Path) -> Optional[date]:
    """Returns the latest published_date in data/processed/<key>/processed_news.xlsx, or None."""
    processed_file = project_root / "data" / "processed" / key / "processed_news.xlsx"
    if not processed_file.exists():
        return None
    try:
        df = pd.read_excel(processed_file, usecols=["published_date"])
        last = pd.to_datetime(df["published_date"]).max()
        return None if pd.isna(last) else last.date()
    except Exception:
        return None


def update_queries(config_path: Path, key: str, queries: List[str]) -> None:
    """Actualiza solo los queries de un commodity existente."""
    commodities = load_commodities(config_path)
    if key not in commodities:
        raise KeyError(f"Commodity '{key}' no existe en el config.")
    commodities[key]["queries"] = queries
    save_commodities(config_path, commodities)
