---
title: AS Commodities
emoji: 📈
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.36.0
app_file: v4.1.0/dashboard/app.py
pinned: false
license: mit
---

# AS Commodities — Análisis de Sentimientos

Dashboard de Streamlit para análisis de sentimiento de noticias sobre commodities.
Desplegable en Hugging Face Spaces.

El código fuente, el pipeline y la documentación detallada están en [`v4.1.0/`](./v4.1.0).
Ver [v4.1.0/README.md](./v4.1.0/README.md) para detalles del CLI y la arquitectura.

## Despliegue en Hugging Face Spaces

Este repositorio está configurado para correr como un **Streamlit Space**:

- `requirements.txt` — dependencias Python (incluye `torch`/`transformers` para los modelos locales).
- `packages.txt` — `chromium` + `chromium-driver` para el scraper de Google News.
- `app_file` (frontmatter) — apunta a `v4.1.0/dashboard/app.py`.

### Secrets requeridos

En **Settings → Variables and secrets** del Space, configura:

| Nombre | Uso |
|---|---|
| `GEMINI_API_KEY` | Resúmenes y modelo Gemini de sentimiento |
| `CLAUDE_API_KEY` | Modelo Claude de sentimiento (opcional) |

Las claves también pueden ingresarse en la UI en cada corrida del pipeline.

### Persistencia

El tier gratuito de HF Spaces tiene almacenamiento **efímero**: los archivos
`data/processed/` y `output/` se pierden al reiniciar el contenedor. Para
persistir resultados entre reinicios, activa **Persistent Storage** ($9/mo) en
los settings del Space, o haz commit de los resultados al repo después de cada
corrida.

## Desarrollo local

```bash
cd v4.1.0
pip install -r ../requirements.txt
streamlit run dashboard/app.py
```

El proyecto detecta automáticamente Windows (usa Edge) vs Linux (usa Chromium).
