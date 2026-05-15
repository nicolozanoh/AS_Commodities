"""
Página: Validación humana
==========================
Por cada commodity, muestra una tabla con 10 noticias aleatorias y un selector
para corregir la etiqueta predicha. Un único botón guarda todas las
validaciones en `data/validations/validaciones.csv`. Si no se elige etiqueta
correcta, se asume que la predicción era correcta.
"""

import csv
import random
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

_DASHBOARD_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT   = Path(__file__).resolve().parents[2]

if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

from utils.config_io import load_commodities


LABELS = ["alcista", "bajista", "neutro"]
IRRELEVANT_LABEL = "no relevante"
DROPDOWN_OPTIONS = LABELS + [IRRELEVANT_LABEL]
SAMPLE_SIZE = 10

VALIDATION_FILE = _PROJECT_ROOT / "data" / "validations" / "validaciones.csv"

VALIDATION_COLUMNS = [
    "validated_at",
    "commodity",
    "title",
    "source",
    "published_date",
    "link",
    "predicted_label",
    "correct_label",
    "is_correct",
    "is_relevant",
    "predicted_score",
]


# ─────────────────────────────────────────────────────────────────────────────
# Persistencia
# ─────────────────────────────────────────────────────────────────────────────
def append_validations(records: list[dict]) -> None:
    """Añade filas al CSV (lo crea con encabezado si no existe)."""
    if not records:
        return
    VALIDATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not VALIDATION_FILE.exists()
    with open(VALIDATION_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=VALIDATION_COLUMNS)
        if write_header:
            writer.writeheader()
        for rec in records:
            writer.writerow({c: rec.get(c, "") for c in VALIDATION_COLUMNS})


def load_validations() -> pd.DataFrame:
    if not VALIDATION_FILE.exists():
        return pd.DataFrame(columns=VALIDATION_COLUMNS)
    return pd.read_csv(VALIDATION_FILE, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Carga / muestreo
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_commodity_news(detail_path: Path, news_path: Path, _mtime: float) -> pd.DataFrame:
    df = pd.read_excel(detail_path)
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["overall_label"])

    if news_path.exists():
        extras = pd.read_excel(news_path, usecols=["title", "link", "summary"])
        df = df.merge(extras.drop_duplicates(subset=["title"]), on="title", how="left")
    else:
        df["link"] = ""
        df["summary"] = ""
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def sample_for_editor(
    detail_path: Path, news_path: Path, mtime: float, n: int, seed: int
) -> pd.DataFrame:
    """Devuelve la muestra lista para mostrar en el data_editor."""
    df = load_commodity_news(detail_path, news_path, mtime)
    if df.empty:
        return df
    sample = df.sample(n=min(n, len(df)), random_state=seed).reset_index(drop=True)

    out = pd.DataFrame({
        "title":           sample.get("title", ""),
        "summary":         sample.get("summary", "").fillna(""),
        "predicted_label": sample["overall_label"].astype(str).str.lower(),
        "score":           pd.to_numeric(sample.get("overall_sentiment"), errors="coerce"),
        "correct_label":   pd.Series([None] * len(sample), dtype="object"),
        # columnas auxiliares (ocultas en el editor)
        "source":          sample.get("source", "").fillna("") if "source" in sample.columns else "",
        "published_date":  sample.get("published_date", "").astype(str) if "published_date" in sample.columns else "",
        "link":            sample.get("link", "").fillna("") if "link" in sample.columns else "",
    })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────
st.title("Validación de etiquetas")

config_path: Path = st.session_state.get(
    "config_path", _DASHBOARD_ROOT / "config" / "commodities.json"
)
commodities = load_commodities(config_path)

if not commodities:
    st.warning(f"No hay commodities en `{config_path}`.")
    st.stop()

if "validation_seed" not in st.session_state:
    st.session_state.validation_seed = random.randint(0, 10**6)

intro_col, action_col = st.columns([3, 1])
with intro_col:
    st.caption(
        f"Muestra de {SAMPLE_SIZE} noticias aleatorias por commodity. "
        "Si una noticia está bien etiquetada, deja la columna **Etiqueta correcta** vacía. "
        f"Las validaciones se guardan en `{VALIDATION_FILE.relative_to(_PROJECT_ROOT)}`."
    )
with action_col:
    if st.button("Nueva muestra aleatoria", use_container_width=True):
        st.session_state.validation_seed = random.randint(0, 10**6)
        st.rerun()

existing = load_validations()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Validaciones guardadas", len(existing))
if not existing.empty and "is_correct" in existing.columns:
    correct = existing["is_correct"].astype(str).str.lower().eq("true").sum()
    pct = (correct / len(existing) * 100) if len(existing) else 0
    m2.metric("Etiquetas correctas", f"{correct} ({pct:.1f}%)")
    if "is_relevant" in existing.columns:
        relevant = existing["is_relevant"].astype(str).str.lower().eq("true").sum()
        pct_r = (relevant / len(existing) * 100) if len(existing) else 0
        m3.metric("Relevantes", f"{relevant} ({pct_r:.1f}%)")
    m4.metric("Commodities validados", existing["commodity"].nunique())

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Tablas por commodity
# ─────────────────────────────────────────────────────────────────────────────
keys = list(commodities.keys())
tabs = st.tabs([commodities[k]["label"] for k in keys])

EDITOR_COLUMN_ORDER = ["title", "summary", "predicted_label", "score", "correct_label"]
EDITOR_COLUMN_CONFIG = {
    "title":           st.column_config.TextColumn("Título", width="large", disabled=True),
    "summary":         st.column_config.TextColumn("Resumen", width="large", disabled=True),
    "predicted_label": st.column_config.TextColumn("Etiqueta predicha", disabled=True),
    "score":           st.column_config.NumberColumn("Score", format="%.3f", disabled=True),
    "correct_label":   st.column_config.SelectboxColumn(
        "Etiqueta correcta",
        options=DROPDOWN_OPTIONS,
        required=False,
        help=(
            "Déjala vacía si la predicción es correcta. "
            f"Selecciona «{IRRELEVANT_LABEL}» si la noticia no aplica a este commodity."
        ),
    ),
}


def build_records(commodity_key: str, df_edit: pd.DataFrame) -> list[dict]:
    now = datetime.now().isoformat(timespec="seconds")
    records: list[dict] = []
    for _, row in df_edit.iterrows():
        pred = str(row.get("predicted_label", "")).strip().lower()
        chosen_raw = row.get("correct_label")
        if chosen_raw is None or (isinstance(chosen_raw, float) and pd.isna(chosen_raw)) or str(chosen_raw).strip() == "":
            chosen = ""
        else:
            chosen = str(chosen_raw).strip().lower()

        if chosen == IRRELEVANT_LABEL:
            is_relevant = False
            correct = pred  # sin corrección de sentimiento cuando la noticia es irrelevante
        else:
            is_relevant = True
            correct = chosen if chosen else pred

        score = row.get("score")
        records.append({
            "validated_at":    now,
            "commodity":       commodity_key,
            "title":           str(row.get("title", "")),
            "source":          str(row.get("source", "")),
            "published_date":  str(row.get("published_date", "")),
            "link":            str(row.get("link", "")),
            "predicted_label": pred,
            "correct_label":   correct,
            "is_correct":      pred == correct,
            "is_relevant":     is_relevant,
            "predicted_score": float(score) if pd.notna(score) else "",
        })
    return records


for tab, key in zip(tabs, keys):
    with tab:
        label = commodities[key]["label"]
        detail_path = _PROJECT_ROOT / "data" / "processed" / key / "analisis_detallado_all_models.xlsx"
        news_path   = _PROJECT_ROOT / "data" / "processed" / key / "processed_news.xlsx"

        if not detail_path.exists():
            st.info(
                f"No hay análisis detallado para **{label}** en "
                f"`{detail_path.relative_to(_PROJECT_ROOT)}`. "
                "Ejecuta primero el pipeline para este commodity."
            )
            continue

        sample = sample_for_editor(
            detail_path,
            news_path,
            detail_path.stat().st_mtime,
            SAMPLE_SIZE,
            st.session_state.validation_seed,
        )
        if sample.empty:
            st.info(f"No hay noticias etiquetadas para **{label}**.")
            continue

        # incluimos el seed en el key para que el editor se reinicie con cada muestra
        editor_key = f"editor_{key}_{st.session_state.validation_seed}"
        edited = st.data_editor(
            sample,
            column_config=EDITOR_COLUMN_CONFIG,
            column_order=EDITOR_COLUMN_ORDER,
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            key=editor_key,
        )

        save_col, info_col = st.columns([1, 3])
        with save_col:
            save_clicked = st.button(
                f"Guardar validaciones de {label}",
                type="primary",
                use_container_width=True,
                key=f"save_{key}",
            )
        with info_col:
            st.caption(
                "Filas sin **Etiqueta correcta** se registran como predicción confirmada."
            )

        if save_clicked:
            records = build_records(key, edited)
            if not records:
                st.warning("No hay noticias para guardar.")
            else:
                append_validations(records)
                corregidas = sum(1 for r in records if not r["is_correct"])
                irrelevantes = sum(1 for r in records if not r["is_relevant"])
                st.success(
                    f"Guardadas {len(records)} validaciones de {label} "
                    f"({corregidas} corregidas, {len(records) - corregidas} confirmadas, "
                    f"{irrelevantes} no relevantes)."
                )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Vista previa / descarga
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("Validaciones recientes")

existing = load_validations()
if existing.empty:
    st.info("Aún no se han guardado validaciones.")
else:
    st.dataframe(
        existing.tail(20).iloc[::-1],
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "Descargar todas las validaciones (CSV)",
        data=existing.to_csv(index=False).encode("utf-8"),
        file_name="validaciones.csv",
        mime="text/csv",
    )
