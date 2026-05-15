"""
Dashboard de Análisis de Sentimientos - Commodities
====================================================
Punto de entrada principal de la aplicación Streamlit.

Ejecutar con:
    streamlit run app.py
"""

import sys
import streamlit as st
from pathlib import Path

_DASHBOARD_ROOT = Path(__file__).resolve().parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

from utils.styles import apply_styles

_PROJECT_ROOT = _DASHBOARD_ROOT.parent
_LOGO = _DASHBOARD_ROOT / "assets" / "logo.png"

# --- Configuración de la página ---
st.set_page_config(
    page_title="Análisis de Sentimientos | Commodities",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Logo en la cabecera del sidebar ---
# if _LOGO.exists():
#     st.logo(str(_LOGO), size="large")

# --- Estilos corporativos (aplica a todas las páginas) ---
apply_styles()

# --- Estado inicial de la app ---
if "config_path" not in st.session_state:
    st.session_state.config_path = _DASHBOARD_ROOT / "config" / "commodities.json"
if "results_dir" not in st.session_state:
    st.session_state.results_dir = _PROJECT_ROOT / "output"
if "main_script" not in st.session_state:
    st.session_state.main_script = str(_PROJECT_ROOT / "main.py")
if "python_exec" not in st.session_state:
    st.session_state.python_exec = sys.executable

# --- Sidebar: rutas configurables (visible en todas las páginas) ---
with st.sidebar:
    st.header("Configuración")
    st.text_input(
        "Ruta de config de commodities",
        value=str(st.session_state.config_path),
        key="config_path_input",
        help="Archivo JSON con la lista de commodities y sus queries.",
    )
    st.text_input(
        "Carpeta de resultados",
        value=str(st.session_state.results_dir),
        key="results_dir_input",
        help="Carpeta donde se guardan los .xlsx por commodity.",
    )
    st.text_input(
        "Ruta de main.py",
        value=str(st.session_state.main_script),
        key="main_script_input",
        help="Ruta absoluta al archivo main.py del proyecto.",
    )
    st.text_input(
        "Python ejecutable (pipeline)",
        value=str(st.session_state.python_exec),
        key="python_exec_input",
        help="Python con PyTorch/dependencias instaladas (≤ 3.12). Ej: C:\\envs\\banrep\\python.exe",
    )
    if st.button("Aplicar"):
        st.session_state.config_path = Path(st.session_state.config_path_input)
        st.session_state.results_dir = Path(st.session_state.results_dir_input)
        st.session_state.main_script = st.session_state.main_script_input
        st.session_state.python_exec = st.session_state.python_exec_input
        st.success("Configuración actualizada.")

# --- Navegación con títulos personalizados ---
pg = st.navigation([
    st.Page("pages/inicio.py",                   title="Inicio"),
    st.Page("pages/1_Ejecutar_pipeline.py",       title="Ejecutar pipeline"),
    st.Page("pages/2_Visualizar_resultados.py",   title="Visualizar resultados"),
    st.Page("pages/3_Resumenes.py",               title="Resúmenes"),
    st.Page("pages/4_Validacion.py",              title="Validación"),
])
pg.run()
