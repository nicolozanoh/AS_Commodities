"""
aggregator.py
-------------
Computes overall sentiment per news item and per day from wide-format
pipeline output. Place this file in src/utils/aggregator.py.

Label mapping (consistent across all models):
    "alcista"  -> +1
    "neutro"   ->  0
    "bajista"  -> -1
"""

import pandas as pd
from typing import Optional
from pathlib import Path


# ---------------------------------------------------------------------------
# Label mapping
# ---------------------------------------------------------------------------

LABEL_MAP = {
    # Spanish labels
    "alcista": 1,
    "neutro": 0,
    "bajista": -1,
    # English equivalents (in case some models return these)
    "positive": 1,
    "neutral": 0,
    "negative": -1,
    "bullish": 1,
    "bearish": -1,
}


def _map_label(label: str) -> Optional[float]:
    """Map a sentiment label string to a numeric score. Returns None if unknown."""
    if pd.isna(label):
        return None
    return LABEL_MAP.get(str(label).strip().lower(), None)


# ---------------------------------------------------------------------------
# Per-news aggregation
# ---------------------------------------------------------------------------

def compute_news_sentiment(df_origen: pd.DataFrame, mtype = "all_models") -> pd.DataFrame:
    """
    Adds an 'overall_sentiment' column to the DataFrame by averaging the
    numeric scores derived from all *_label columns.

    Parameters
    ----------
    df : pd.DataFrame
        Wide-format pipeline output. Must contain at least one column
        ending in '_label' (e.g. finbert_label, gemini_label, ...).

    Returns
    -------
    pd.DataFrame
        Original DataFrame with additional columns:
            - <model>_numeric  : numeric score for each label column
            - overall_sentiment: mean of all numeric scores (-1 to +1)
            - overall_label    : 'alcista' / 'neutro' / 'bajista'
    """
    df = df_origen.copy()

    prev_cols = [c for c in df.columns if c.endswith("_numeric")] + ["overall_sentiment", "overall_label"]
    df = df.drop(columns=[c for c in prev_cols if c in df.columns])

    if mtype == "all_models":
        label_cols = [c for c in df.columns if c.endswith("_label") and (c.startswith("LLM_") or c.startswith("GPT_"))]
    else:
        label_cols = [c for c in df.columns if c.endswith("_label") and c.startswith(mtype + "_")]

    if not label_cols:
        raise ValueError("No columns ending in '_label' found in DataFrame.")

    numeric_cols = []
    
    for col in label_cols:
        numeric_col = col.replace("_label", "_numeric")
        df[numeric_col] = df[col].apply(_map_label)
        numeric_cols.append(numeric_col)

    # Average across models, ignoring NaN (models that failed / returned unknown labels)
    df["overall_sentiment"] = df[numeric_cols].mean(axis=1)

    # Human-readable overall label
    df["overall_label"] = df["overall_sentiment"].apply(_score_to_label)

    df = df[['title', 'source', 'commodity', 'published_date'] + numeric_cols + ['overall_sentiment', 'overall_label']]

    return df


def _score_to_label(score: float) -> str:
    """Convert a continuous score to a directional label."""
    if pd.isna(score):
        return "sin_datos"
    if score > 0.15:
        return "alcista"
    elif score < -0.15:
        return "bajista"
    else:
        return "neutro"


# ---------------------------------------------------------------------------
# Daily aggregation
# ---------------------------------------------------------------------------

def compute_daily_sentiment(df: pd.DataFrame, date_col: str = "fecha", mtype = "all_models") -> pd.DataFrame:
    """
    Aggregates per-news sentiment to a daily level.

    Parameters
    ----------
    df : pd.DataFrame
        Output of compute_news_sentiment(). Must contain 'overall_sentiment'
        and 'overall_label' columns, plus a date column.
    date_col : str
        Name of the date column. Default: 'fecha'.

    Returns
    -------
    pd.DataFrame
        One row per day with columns:
            - fecha                  : date
            - daily_sentiment        : mean overall_sentiment for the day
            - daily_label            : directional label for the day
            - n_news                 : number of news items that day
            - pct_alcista            : % of news labelled alcista
            - pct_neutro             : % of news labelled neutro
            - pct_bajista            : % of news labelled bajista
    """
    if "overall_sentiment" not in df.columns:
        raise ValueError("Run compute_news_sentiment() before compute_daily_sentiment().")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col]).dt.date  # strip time component

    daily = (
        df.groupby(date_col)
        .agg(
            daily_sentiment=("overall_sentiment", "mean"),
            n_news=("overall_sentiment", "count"),
            n_alcista=("overall_label", lambda x: (x == "alcista").sum()),
            n_neutro=("overall_label", lambda x: (x == "neutro").sum()),
            n_bajista=("overall_label", lambda x: (x == "bajista").sum()),
        )
        .reset_index()
        .rename(columns={date_col: "fecha"})
    )

    daily = daily.rename(columns={'daily_sentiment': 'daily_sentiment_' + mtype})

    daily["pct_alcista_" + mtype] = (daily["n_alcista"] / daily["n_news"] * 100).round(1)
    daily["pct_neutro_" + mtype]  = (daily["n_neutro"]  / daily["n_news"] * 100).round(1)
    daily["pct_bajista_" + mtype] = (daily["n_bajista"] / daily["n_news"] * 100).round(1)
    daily["daily_label_" + mtype] = daily['daily_sentiment_' + mtype].apply(_score_to_label)

    daily["MA_7_" + mtype] = daily['daily_sentiment_' + mtype].rolling(window=7).mean()

    # Drop helper count columns
    daily = daily.drop(columns=["n_alcista", "n_neutro", "n_bajista"])

    return daily.sort_values("fecha").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Save to CSV
# ---------------------------------------------------------------------------

def save_results(
    news_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    news_path: str = "results_news.csv",
    daily_path: str = "results_daily.csv",
    mtype: str = "all_models"
) -> None:
    """
    Saves per-news and daily sentiment DataFrames to CSV.

    Parameters
    ----------
    news_df   : output of compute_news_sentiment()
    daily_df  : output of compute_daily_sentiment()
    news_path : file path for per-news CSV
    daily_path: file path for daily CSV
    """

    news_path  = Path(news_path)
    daily_path = Path(daily_path)

    news_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.parent.mkdir(parents=True, exist_ok=True)

    news_out  = news_path.parent  / f"{news_path.stem}_{mtype}.xlsx"
    daily_out = daily_path.parent / f"{daily_path.stem}_{mtype}.xlsx"

    news_df.to_excel(news_out, index=False)
    daily_df.to_excel(daily_out, index=False)

    print(f"[Aggregator] Guardado {news_out.name}")
    print(f"[Aggregator] Guardado {daily_out.name}")


# ---------------------------------------------------------------------------
# Convenience wrapper: run everything in one call
# ---------------------------------------------------------------------------

def aggregate(
    df: pd.DataFrame,
    date_col: str = "fecha",
    news_path: str = "results_news.csv",
    daily_path: str = "results_daily.csv",
    comparison_name: str = "models_comparison.xlsx"
):
    """
    Full aggregation pipeline: per-news -> daily -> optional CSV export.

    Usage in pipeline.py:
        from utils.aggregator import aggregate
        news_df, daily_df = aggregate(results_df)

    Returns
    -------
    (news_df, daily_df)
    """
    model_types = ["GPT", "LLM", "all_models"]
    resultados = {}

    for mtype in model_types:
        print(f"[Aggregator] Calculando sentimiento por noticia  (tipo: {mtype})...")
        news_df  = compute_news_sentiment(df, mtype)

        print(f"[Aggregator] Agregando sentimiento diario  (tipo: {mtype})...")
        daily_df = compute_daily_sentiment(news_df, date_col=date_col, mtype=mtype)

        save_results(news_df, daily_df, news_path, daily_path, mtype)
        resultados[mtype] = daily_df

    print(f"[Aggregator] Construyendo tabla comparativa de modelos...")
    models_comparisson = pd.DataFrame()

    for mtype in model_types:
        df = resultados[mtype]
        df = df.drop(columns=df.columns[df.columns.str.startswith('pct_')])
        df = df.drop(columns=df.columns[df.columns.str.startswith('daily_label_')])
        df = df.drop(columns=df.columns[df.columns.str.startswith('n_news')])

        if models_comparisson.empty:
            models_comparisson = df
        else:
            models_comparisson = pd.merge(models_comparisson, df, on='fecha')

    comparison_path = Path(daily_path).parent / comparison_name
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    models_comparisson.to_excel(comparison_path, index=False)
    print(f"[Aggregator] Tabla comparativa guardada en {comparison_path.name}")

    return news_df, daily_df