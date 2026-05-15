import streamlit as st

st.title("Análisis de Sentimientos — Commodities")
st.markdown(
    """
    Dashboard para ejecutar y visualizar el pipeline de análisis de sentimientos
    sobre noticias de commodities (oro, petróleo, café, etc.).

    ### Páginas disponibles

    - **Ejecutar pipeline** — Selecciona un commodity (o crea uno nuevo),
      define los queries de búsqueda, el rango de fechas y lanza la ejecución.
    - **Visualizar resultados** — Carga los resultados procesados y explora
      series de tiempo, distribución de etiquetas y noticias individuales.

    ---
    Usa el menú de la izquierda para navegar.
    """
)
