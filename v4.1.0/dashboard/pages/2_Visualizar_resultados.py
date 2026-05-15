"""
Página: Visualizar resultados
==============================
Carga el archivo Excel del commodity seleccionado y muestra:
- KPIs generales
- Serie de tiempo del sentimiento agregado
- Distribución de etiquetas
- Tabla de noticias filtrable
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config_io import load_commodities


st.title("Visualizar resultados")

config_path: Path = st.session_state.get("config_path", Path("config/commodities.json"))
_PAGE_ROOT   = Path(__file__).resolve().parents[2]
results_dir: Path = st.session_state.get("results_dir", _PAGE_ROOT / "output")

commodities = load_commodities(config_path)

# ─────────────────────────────────────────────────────────────────────────────
# Selección de commodity
# ─────────────────────────────────────────────────────────────────────────────
if not commodities:
    st.warning(f"No hay commodities en `{config_path}`.")
    st.stop()

opciones = {f"{v['label']} ({k})": k for k, v in commodities.items()}
sel = st.selectbox("Commodity", list(opciones.keys()))
key = opciones[sel]

xlsx_path = results_dir / key / "excel" / "sentimiento_diario_all_models.xlsx"
future_xlsx_path = results_dir / key / "excel" / "future_daily_all_models.xlsx"
if not xlsx_path.exists():
    st.warning(
        f"No encuentro resultados en `{xlsx_path}`. "
        "Ejecuta primero el pipeline para este commodity."
    )
    st.stop()


@st.cache_data(show_spinner=False)
def load_results(path: Path, mtime: float) -> pd.DataFrame:
    """Carga el Excel, normaliza a minúsculas y quita el sufijo _all_models."""
    df = pd.read_excel(path)
    df.columns = [c.lower().replace("_all_models", "") for c in df.columns]
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df


df = load_results(xlsx_path, xlsx_path.stat().st_mtime)
st.caption(
    f"Archivo: `{xlsx_path}` — {len(df):,} filas — "
    f"última modificación: {pd.Timestamp(xlsx_path.stat().st_mtime, unit='s')}"
)

df_future = (
    load_results(future_xlsx_path, future_xlsx_path.stat().st_mtime)
    if future_xlsx_path.exists()
    else None
)

# Columnas tras normalización (sin sufijo _all_models):
#   fecha | daily_sentiment | n_news | pct_alcista | pct_neutro | pct_bajista | daily_label | ma_7
COL_FECHA = "fecha"             if "fecha"             in df.columns else None
COL_SCORE = "daily_sentiment"   if "daily_sentiment"   in df.columns else None
COL_LABEL = "daily_label"       if "daily_label"       in df.columns else None
COL_MA7   = "ma_7"              if "ma_7"              in df.columns else None
COL_NNEWS = "n_news"            if "n_news"            in df.columns else None
COL_PCT_A = "pct_alcista"       if "pct_alcista"       in df.columns else None
COL_PCT_B = "pct_bajista"       if "pct_bajista"       in df.columns else None
COL_PCT_N = "pct_neutro"        if "pct_neutro"        in df.columns else None

# ─────────────────────────────────────────────────────────────────────────────
# Filtros de fechas (dentro de la página)
# ─────────────────────────────────────────────────────────────────────────────
if COL_FECHA and df[COL_FECHA].notna().any():
    fmin_data = df[COL_FECHA].min()
    fmax_data = df[COL_FECHA].max()

    col_a, col_b, col_sep, col_c, col_d = st.columns([2, 2, 0.3, 1.2, 2])

    with col_a:
        fecha_ini = st.date_input(
            "Desde",
            value=fmin_data.date(),
            min_value=fmin_data.date(),
            max_value=fmax_data.date(),
            key="fecha_ini",
        )
    with col_b:
        fecha_fin = st.date_input(
            "Hasta",
            value=fmax_data.date(),
            min_value=fmin_data.date(),
            max_value=fmax_data.date(),
            key="fecha_fin",
        )
    with col_sep:
        st.markdown("<div style='text-align:center; padding-top:32px; color:grey'>|</div>", unsafe_allow_html=True)
    with col_c:
        n_rel = st.number_input("Últimos", min_value=0, value=0, step=1, key="n_rel")
    with col_d:
        unidad = st.selectbox(
            "Unidad",
            ["Días", "Semanas", "Meses", "Trimestres", "Años"],
            key="unidad_rel",
        )

    # Filtro absoluto
    fecha_inicio = pd.Timestamp(fecha_ini)
    fecha_fin_ts = pd.Timestamp(fecha_fin)

    # Filtro relativo: si N > 0, reemplaza la fecha de inicio
    if n_rel > 0:
        offsets = {
            "Días":       pd.DateOffset(days=n_rel),
            "Semanas":    pd.DateOffset(weeks=n_rel),
            "Meses":      pd.DateOffset(months=n_rel),
            "Trimestres": pd.DateOffset(months=n_rel * 3),
            "Años":       pd.DateOffset(years=n_rel),
        }
        fecha_inicio = fmax_data - offsets[unidad]

    mask = (df[COL_FECHA] >= fecha_inicio) & (df[COL_FECHA] <= fecha_fin_ts)
    df = df[mask]

    if df_future is not None and COL_FECHA in df_future.columns:
        mask_fut = (df_future[COL_FECHA] >= fecha_inicio) & (df_future[COL_FECHA] <= fecha_fin_ts)
        df_future = df_future[mask_fut]

# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Dias", f"{len(df):,}")
if COL_NNEWS:
    c2.metric("Noticias totales", f"{int(df[COL_NNEWS].sum()):,}")
if COL_SCORE:
    c3.metric("Score promedio", f"{df[COL_SCORE].mean():.3f}")
if COL_LABEL:
    counts = df[COL_LABEL].value_counts()
    c4.metric("Alcista", int(counts.get("alcista", 0)))
    c5.metric("Bajista", int(counts.get("bajista", 0)))

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Serie de tiempo
# ─────────────────────────────────────────────────────────────────────────────
def _serie_tiempo(
    data: pd.DataFrame,
    title: str,
    color_raw: str,
    color_ma: str,
    key_suffix: str,
):
    """Render a sentiment time series with optional 7-day moving average."""
    if data is None or data.empty or COL_FECHA not in data.columns or COL_SCORE not in data.columns:
        st.info(f"No hay datos disponibles para «{title}».")
        return

    chart_cols = [COL_SCORE] + ([COL_MA7] if COL_MA7 and COL_MA7 in data.columns else [])
    chart_df = data.set_index(COL_FECHA)[chart_cols].dropna(how="all")
    chart_df.columns = ["Sentimiento"] + (["MA 7 días"] if len(chart_cols) > 1 else [])

    if chart_df.empty:
        st.info(f"No hay datos disponibles para «{title}».")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=chart_df.index, y=chart_df["Sentimiento"],
        name="Sentimiento", mode="lines",
        line=dict(color=color_raw, width=1.2),
        opacity=0.55,
    ))
    if "MA 7 días" in chart_df.columns:
        fig.add_trace(go.Scatter(
            x=chart_df.index, y=chart_df["MA 7 días"],
            name="MA 7 días", mode="lines",
            line=dict(color=color_ma, width=2.6),
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
    fig.update_layout(
        margin=dict(t=20, b=20),
        legend=dict(orientation="h", y=1.08),
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="#EEEEEE"),
        yaxis=dict(showgrid=True, gridcolor="#EEEEEE", zeroline=False),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"serie_{key_suffix}")


if COL_FECHA and COL_SCORE:
    st.subheader("Serie de tiempo — Sentimiento")
    _serie_tiempo(
        df,
        title="Sentimiento",
        color_raw="#5B9BD5",
        color_ma="#D35400",
        key_suffix="total",
    )

    if df_future is not None:
        st.subheader("Serie de tiempo — Sentimiento futuro")
        _serie_tiempo(
            df_future,
            title="Sentimiento futuro",
            color_raw="#7FB069",
            color_ma="#1F4E79",
            key_suffix="futuro",
        )

# ─────────────────────────────────────────────────────────────────────────────
# Distribución de etiquetas
# ─────────────────────────────────────────────────────────────────────────────
if COL_LABEL:
    st.subheader("Distribución de etiquetas")
    dist = df[COL_LABEL].value_counts().rename_axis("etiqueta").reset_index(name="conteo")
    st.bar_chart(dist, x="etiqueta", y="conteo")

# ─────────────────────────────────────────────────────────────────────────────
# Tabla diaria
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("Datos diarios")
cols_show = [c for c in [COL_FECHA, COL_LABEL, COL_SCORE, COL_MA7, COL_NNEWS, COL_PCT_A, COL_PCT_N, COL_PCT_B] if c]
st.dataframe(
    df[cols_show] if cols_show else df,
    width="stretch",
    hide_index=True,
    column_config={
        "fecha":            st.column_config.DateColumn("Fecha",          format="YYYY-MM-DD"),
        "daily_label":      st.column_config.TextColumn("Etiqueta"),
        "daily_sentiment":  st.column_config.NumberColumn("Sentimiento",  format="%.3f"),
        "ma_7":             st.column_config.NumberColumn("MA 7 días",    format="%.3f"),
        "n_news":           st.column_config.NumberColumn("Noticias"),
        "pct_alcista":      st.column_config.NumberColumn("% Alcista",    format="%.1f"),
        "pct_neutro":       st.column_config.NumberColumn("% Neutro",     format="%.1f"),
        "pct_bajista":      st.column_config.NumberColumn("% Bajista",    format="%.1f"),
    },
)

with st.expander("Descargar datos"):
    st.download_button(
        "Descargar CSV filtrado",
        data=df[cols_show].to_csv(index=False).encode("utf-8"),
        file_name=f"{key}_filtrado.csv",
        mime="text/csv",
    )
