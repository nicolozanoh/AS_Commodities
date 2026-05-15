"""
Página: Ejecutar pipeline
==========================
- Seleccionar un commodity existente o agregar uno nuevo
- Editar los queries de búsqueda
- Definir fecha inicial y final
- Lanzar la ejecución en background y ver logs en vivo
"""

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config_io import (
    load_commodities,
    add_commodity,
    update_queries,
    get_last_update_date,
)
from utils.pipeline_runner import (
    start_pipeline,
    stop_pipeline,
    is_running,
    tail_log,
    clear_log,
    get_current_run_meta,
)


st.title("Ejecutar pipeline")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
config_path: Path = st.session_state.get("config_path", ROOT / "config" / "commodities.json")
MAIN_SCRIPT = Path(st.session_state.get("main_script", str(PROJECT_ROOT / "main.py")))
PYTHON_EXEC: str = st.session_state.get("python_exec", sys.executable)

# ─────────────────────────────────────────────────────────────────────────────
# Sección 1: Selección o creación de commodity
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("1. Commodity")

commodities = load_commodities(config_path)

modo = st.radio(
    "¿Qué quieres hacer?",
    ["Usar commodity existente", "Agregar commodity nuevo"],
    horizontal=True,
)

selected_key = None
selected_label = None
queries: list[str] = []
last_update = None

if modo == "Usar commodity existente":
    if not commodities:
        st.warning(
            f"No hay commodities en `{config_path}`. "
            "Agrega uno nuevo para empezar."
        )
    else:
        opciones = {f"{v['label']} ({k})": k for k, v in commodities.items()}
        sel = st.selectbox("Commodity", list(opciones.keys()))
        selected_key = opciones[sel]
        selected_label = commodities[selected_key]["label"]
        existing_queries = commodities[selected_key].get("queries", [])

        last_update = get_last_update_date(selected_key, PROJECT_ROOT)
        if last_update:
            st.caption(f"Ultima actualizacion: **{last_update}**")
        else:
            st.caption("Sin datos previos — se usara el rango por defecto.")

        st.markdown("**Queries de búsqueda** (uno por línea):")
        queries_text = st.text_area(
            "Edita los queries para esta corrida",
            value="\n".join(existing_queries),
            height=140,
            label_visibility="collapsed",
        )
        queries = [q.strip() for q in queries_text.splitlines() if q.strip()]

        if queries != existing_queries:
            if st.button("💾 Guardar cambios en config", key="save_existing"):
                update_queries(config_path, selected_key, queries)
                st.success("Queries actualizados en el config.")

else:
    import re

    new_label = st.text_input("Nombre", placeholder="ej. Cobre").strip()
    new_key = re.sub(r"[^a-z0-9_]", "", new_label.lower().replace(" ", "_"))
    if new_label:
        st.caption(f"Identificador: `{new_key}`")

    new_queries_text = st.text_area(
        "Queries de búsqueda (uno por línea)",
        placeholder="copper price\ncopper market\nLME copper",
        height=140,
    )
    new_queries = [q.strip() for q in new_queries_text.splitlines() if q.strip()]

    can_add = bool(new_key and new_label and new_queries)
    if st.button("➕ Agregar al config", disabled=not can_add):
        if new_key in commodities:
            st.error(f"Ya existe un commodity con la key '{new_key}'.")
        else:
            add_commodity(config_path, new_key, new_label, new_queries)
            st.success(f"Commodity '{new_label}' agregado. Recarga para usarlo.")
            st.rerun()

    selected_key = new_key or None
    selected_label = new_label or None
    queries = new_queries

# ─────────────────────────────────────────────────────────────────────────────
# Sección 2: Rango de fechas
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("2. Rango de fechas")

hoy = date.today()
default_end   = hoy - timedelta(days=1)
default_start = (last_update + timedelta(days=1)) if last_update else (hoy - timedelta(days=30))
if default_start > default_end:
    default_start = default_end

col_a, col_b = st.columns(2)
with col_a:
    start_date = st.date_input(
        "Fecha inicial",
        value=default_start,
        max_value=default_end,
        key=f"start_{selected_key}",
    )
with col_b:
    end_date = st.date_input(
        "Fecha final",
        value=default_end,
        max_value=default_end,
        key=f"end_{selected_key}",
    )

if start_date > end_date:
    st.error("La fecha inicial debe ser anterior o igual a la fecha final.")

# ─────────────────────────────────────────────────────────────────────────────
# Sección 3: Funciones
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("3. Funciones y modelos")

col_func, col_mod = st.columns(2)

with col_func:
    st.markdown("**Funciones**")
    fn_noticias  = st.checkbox("Traer noticias",        value=True,  key="fn_noticias")
    fn_precios   = False
    fn_sentim    = st.checkbox("Analizar sentimientos", value=True,  key="fn_sentim")
    fn_agregar   = st.checkbox("Agregar resultados",    value=True,  key="fn_agregar")
    fn_resumen   = st.checkbox("Resumen",               value=True,  key="fn_resumen")
    fn_catalogar = False
    fn_futuro    = st.checkbox("Precio futuro",         value=False, key="fn_futuro")

    if fn_sentim:
        st.markdown("**Idioma del texto**")
        idioma = st.radio(
            "Idioma",
            ["Español", "Inglés"],
            horizontal=True,
            key="idioma_texto",
            label_visibility="collapsed",
        )
    else:
        idioma = "Español"

with col_mod:
    st.markdown("**Modelos**")
    if fn_sentim:
        st.caption("Multilingüe")
        mod_zeroshot = st.checkbox("Zero-Shot", value=True, key="mod_zeroshot")
        mod_gemini   = st.checkbox("Gemini",    value=True, key="mod_gemini")
        mod_claude   = st.checkbox("Claude",    value=True, key="mod_claude")

        if idioma == "Español":
            st.caption("Español")
            mod_robertuito = st.checkbox("Robertuito", value=True, key="mod_robertuito")
            mod_crudebert  = False
            mod_finbert    = False
        else:
            st.caption("Inglés")
            mod_crudebert  = st.checkbox("CrudeBERT", value=True, key="mod_crudebert")
            mod_finbert    = st.checkbox("FinBERT",   value=True, key="mod_finbert")
            mod_robertuito = False
    else:
        mod_zeroshot = mod_crudebert = mod_finbert = mod_robertuito = mod_gemini = mod_claude = False
        st.caption("Activa **Analizar sentimientos** para seleccionar modelos.")

funciones_sel = [f for f, on in [
    ("TRAER NOTICIAS",        fn_noticias),
    ("TRAER PRECIOS",         fn_precios),
    ("ANALIZAR SENTIMIENTOS", fn_sentim),
    ("AGREGAR RESULTADOS",    fn_agregar),
    ("RESUMEN",               fn_resumen),
    ("CATALOGAR",             fn_catalogar),
    ("PRECIO FUTURO",         fn_futuro),
] if on]

modelos_sel = [m for m, on in [
    ("ZERO-SHOT",   mod_zeroshot),
    ("CRUDEBERT",   mod_crudebert),
    ("FINBERT",     mod_finbert),
    ("ROBERTUITO",  mod_robertuito),
    ("GEMINI",      mod_gemini),
    ("CLAUDE",      mod_claude),
] if on]

if not funciones_sel:
    st.warning("Selecciona al menos una función para ejecutar.")
if fn_sentim and not modelos_sel:
    st.warning("Selecciona al menos un modelo.")

# ─────────────────────────────────────────────────────────────────────────────
# Opciones de resumen (solo si RESUMEN está activo)
# ─────────────────────────────────────────────────────────────────────────────
summary_date = None
summary_window = 30
if fn_resumen:
    st.subheader("3b. Opciones de resumen")
    col_sd, col_sw, _ = st.columns([1, 1, 1])
    with col_sd:
        summary_date = st.date_input(
            "Fecha del resumen",
            value=end_date,
            help="Fecha de referencia para el resumen ejecutivo. "
                 "El pipeline tomará las noticias de los últimos N días hasta esta fecha.",
            key="summary_date",
        )
    with col_sw:
        summary_window = st.number_input(
            "Días de noticias a incluir",
            min_value=1,
            max_value=365,
            value=30,
            step=1,
            help="Número de días hacia atrás desde la fecha del resumen.",
            key="summary_window",
        )

# ─────────────────────────────────────────────────────────────────────────────
# API Keys
# ─────────────────────────────────────────────────────────────────────────────
needs_gemini = fn_resumen or (fn_sentim and mod_gemini)
needs_claude = fn_sentim and mod_claude

api_keys: dict = {}
if needs_gemini or needs_claude:
    st.subheader("3c. API Keys")
    col_g, col_c = st.columns(2)
    with col_g:
        if needs_gemini:
            gemini_key = st.text_input(
                "Gemini API Key",
                type="password",
                placeholder="AIza...",
                key="gemini_api_key",
            )
            if gemini_key:
                api_keys["GEMINI_API_KEY"] = gemini_key
    with col_c:
        if needs_claude:
            claude_key = st.text_input(
                "Claude API Key",
                type="password",
                placeholder="sk-ant-...",
                key="claude_api_key",
            )
            if claude_key:
                api_keys["CLAUDE_API_KEY"] = claude_key

    missing_keys = []
    if needs_gemini and "GEMINI_API_KEY" not in api_keys:
        missing_keys.append("Gemini")
    if needs_claude and "CLAUDE_API_KEY" not in api_keys:
        missing_keys.append("Claude")
    if missing_keys:
        st.warning(f"Ingresa la API key para: {', '.join(missing_keys)}")

# ─────────────────────────────────────────────────────────────────────────────
# Sección 4: Lanzar pipeline
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("4. Ejecución")

running = is_running()
meta = get_current_run_meta()

if running and meta:
    st.info(
        f"⏳ Pipeline en ejecución desde **{meta['started_at']}** — "
        f"commodity: `{meta['commodity']}`, "
        f"rango: `{meta['start_date']}` → `{meta['end_date']}`"
    )
    if st.button("🛑 Detener pipeline", type="secondary"):
        if stop_pipeline():
            st.success("Pipeline detenido.")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("No se pudo detener el proceso.")
else:
    keys_ok = (
        (not needs_gemini or "GEMINI_API_KEY" in api_keys) and
        (not needs_claude or "CLAUDE_API_KEY" in api_keys)
    )
    can_run = (
        selected_key
        and queries
        and start_date <= end_date
        and MAIN_SCRIPT.exists()
        and bool(funciones_sel)
        and (not fn_sentim or bool(modelos_sel))
        and keys_ok
    )
    if not MAIN_SCRIPT.exists():
        st.warning(
            f"⚠️ No encuentro `{MAIN_SCRIPT}`. "
            "Configura la ruta correcta a tu `main.py` en la sidebar de la app."
        )

    btn_label = f"Ejecutar pipeline para {selected_label or '...'}"
    if st.button(btn_label, type="primary", disabled=not can_run):
        try:
            pid = start_pipeline(
                commodity=selected_key,
                queries=queries,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                main_script=MAIN_SCRIPT,
                funciones=funciones_sel,
                modelos=modelos_sel,
                api_keys=api_keys,
                python_exec=PYTHON_EXEC,
                summary_date=summary_date.isoformat() if summary_date else None,
                summary_window=summary_window if fn_resumen else None,
            )
            st.success(f"✅ Pipeline iniciado (PID {pid}).")
            time.sleep(0.5)
            st.rerun()
        except Exception as e:
            st.error(f"Error al iniciar: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Logs en vivo
# ─────────────────────────────────────────────────────────────────────────────
col_log_title, col_log_btn = st.columns([6, 1])
with col_log_title:
    st.subheader("Logs")
with col_log_btn:
    st.write("")  # align vertically with subheader
    if st.button("🗑️ Limpiar", key="clear_log", disabled=running, help="Limpia el contenido del log. No disponible mientras el pipeline está corriendo."):
        clear_log()
        st.rerun()

auto_refresh = st.toggle(
    "Auto-refrescar cada 3s",
    value=running,
    help="Útil mientras el pipeline está corriendo.",
)

log_text = tail_log(n_lines=300)
st.code(log_text, language="bash")

if auto_refresh and running:
    time.sleep(3)
    st.rerun()
