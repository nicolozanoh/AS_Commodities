"""
Página: Resúmenes ejecutivos
=============================
Muestra los resúmenes de noticias guardados en output/<commodity>/resumen/,
permite navegar entre fechas y al final muestra una tabla con las últimas
noticias procesadas.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_DASHBOARD_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT   = Path(__file__).resolve().parents[2]

for _p in (_DASHBOARD_ROOT, _PROJECT_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from utils.config_io import load_commodities
from src.utils.aggregator import compute_news_sentiment


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_label(stem: str, prefix: str) -> str:
    """Extrae la parte de fecha del stem del archivo, ej. 'resumen - 04apr2026' → '04apr2026'."""
    return stem.replace(prefix, "").strip()


@st.cache_data(show_spinner=False)
def _load_news(path: Path, mtime: float) -> pd.DataFrame:
    """Carga processed_news, calcula overall_label y overall_sentiment, y devuelve
    las columnas solicitadas. mtime se usa solo para invalidar la caché."""
    df = pd.read_excel(path)
    df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")

    news_df = compute_news_sentiment(df.copy())
    news_df = news_df.reset_index(drop=True)

    summary_col = df.reset_index(drop=True)["summary"] if "summary" in df.columns else pd.Series([""] * len(news_df))
    news_df["summary"] = summary_col

    keep = ["published_date", "title", "summary", "overall_label", "overall_sentiment"]
    return news_df[[c for c in keep if c in news_df.columns]]


# ─────────────────────────────────────────────────────────────────────────────
# Encabezado
# ─────────────────────────────────────────────────────────────────────────────

st.title("Resúmenes ejecutivos")

config_path = st.session_state.get("config_path", _DASHBOARD_ROOT / "config" / "commodities.json")
commodities = load_commodities(config_path)

if not commodities:
    st.warning(f"No hay commodities en `{config_path}`. Agrega uno desde la página **Ejecutar pipeline**.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Selectores: commodity y fecha
# ─────────────────────────────────────────────────────────────────────────────

col_commodity, col_fecha = st.columns([1, 1])

with col_commodity:
    opciones = {f"{v['label']} ({k})": k for k, v in commodities.items()}
    sel = st.selectbox("Commodity", list(opciones.keys()))
    commodity_key = opciones[sel]

resumen_dir = _PROJECT_ROOT / "output" / commodity_key / "resumen"
txt_files   = sorted(resumen_dir.glob("resumen - *.txt"), reverse=True)

if not txt_files:
    st.warning(
        f"No hay resúmenes para **{sel}**. "
        "Ejecuta primero el paso `RESUMEN` en la página **Ejecutar pipeline**."
    )
    st.stop()

fecha_map = {_parse_label(f.stem, "resumen - "): f for f in txt_files}

with col_fecha:
    fecha_sel = st.selectbox("Fecha del resumen", list(fecha_map.keys()))

archivo = fecha_map[fecha_sel]

# ─────────────────────────────────────────────────────────────────────────────
# Contenido del resumen
# ─────────────────────────────────────────────────────────────────────────────

content = archivo.read_text(encoding="utf-8")
st.text_area(
    label="Resumen",
    value=content,
    height=420,
    disabled=True,
    label_visibility="collapsed",
)

nube_path = resumen_dir / "nube" / f"nube - {fecha_sel}.png"
if nube_path.exists():
    with st.expander("Ver nube de palabras"):
        st.image(str(nube_path), width="stretch")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Tabla: últimas noticias procesadas
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Últimas noticias procesadas")

processed_path = _PROJECT_ROOT / "data" / "processed" / commodity_key / "processed_news.xlsx"

if not processed_path.exists():
    st.info("No hay noticias procesadas para este commodity. Ejecuta el pipeline primero.")
    st.stop()

df_news = _load_news(processed_path, processed_path.stat().st_mtime)

# Filtros en la barra lateral
with st.sidebar:
    st.header("Filtros — noticias")

    if df_news["published_date"].notna().any():
        fmin = df_news["published_date"].min()
        fmax = df_news["published_date"].max()
        rango = st.date_input(
            "Rango de fechas",
            value=(fmin.date(), fmax.date()),
            min_value=fmin.date(),
            max_value=fmax.date(),
            key="rango_noticias",
        )
        if isinstance(rango, tuple) and len(rango) == 2:
            mask = (
                (df_news["published_date"] >= pd.Timestamp(rango[0])) &
                (df_news["published_date"] <= pd.Timestamp(rango[1]))
            )
            df_news = df_news[mask]

    etiquetas = ["Todas"] + sorted(df_news["overall_label"].dropna().unique().tolist())
    etiqueta_sel = st.selectbox("Etiqueta", etiquetas, key="etiqueta_noticias")
    if etiqueta_sel != "Todas":
        df_news = df_news[df_news["overall_label"] == etiqueta_sel]

    n_filas = st.number_input(
        "Mostrar últimas N noticias",
        min_value=10, max_value=1000, value=100, step=10,
        key="n_noticias",
    )

df_show = df_news.sort_values("published_date", ascending=False).head(n_filas)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Noticias", f"{len(df_show):,}")
if "overall_sentiment" in df_show.columns:
    c2.metric("Score promedio", f"{df_show['overall_sentiment'].mean():.3f}")
if "overall_label" in df_show.columns:
    counts = df_show["overall_label"].value_counts()
    c3.metric("Alcista", int(counts.get("alcista", 0)))
    c4.metric("Bajista", int(counts.get("bajista", 0)))

st.dataframe(
    df_show,
    width="stretch",
    hide_index=True,
    column_config={
        "title":              st.column_config.TextColumn("Título",    width="large"),
        "summary":            st.column_config.TextColumn("Resumen",   width="large"),
        "published_date":     st.column_config.DateColumn("Fecha",     format="YYYY-MM-DD"),
        "overall_label":      st.column_config.TextColumn("Etiqueta"),
        "overall_sentiment":  st.column_config.NumberColumn("Puntaje", format="%.3f"),
    },
)

with st.expander("Descargar datos"):
    st.download_button(
        "Descargar CSV filtrado",
        data=df_show.to_csv(index=False).encode("utf-8"),
        file_name=f"{commodity_key}_noticias_{fecha_sel}.csv",
        mime="text/csv",
    )
