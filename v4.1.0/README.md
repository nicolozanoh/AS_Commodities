# Análisis de Sentimientos — v4.0.0

Dashboard web (Streamlit) para operar el pipeline de análisis de sentimientos
de commodities sin tocar código, junto con una interfaz CLI que lo integra.

## Cambios respecto a v3.0.0

- **Dashboard Streamlit** (`dashboard/`): UI web para lanzar el pipeline,
  monitorear logs en vivo y explorar resultados.
- **CLI en `main.py`:** argumentos `--commodity`, `--start`, `--end`,
  `--queries`, `--funciones` y `--modelos` para ejecutar desde terminal o
  desde el dashboard sin editar `config.py`.
- **API keys por variable de entorno:** el dashboard inyecta `GEMINI_API_KEY`
  y `CLAUDE_API_KEY` al subproceso; ya no es necesario modificar `config.py`.
- **Resumen para dashboard:** `AGREGAR RESULTADOS` guarda adicionalmente
  `data/results/<commodity>.xlsx` que la página de visualización consume.

## Estructura

```
v4.0.0/
├── main.py              # Punto de entrada (CLI + I/O paralelo + cómputo secuencial)
├── config.py            # Commodities, modelos y claves de API (base)
├── dashboard/
│   ├── app.py           # Punto de entrada de Streamlit
│   ├── pages/
│   │   ├── inicio.py
│   │   ├── 1_Ejecutar_pipeline.py
│   │   └── 2_Visualizar_resultados.py
│   └── utils/
│       ├── config_io.py      # CRUD del JSON de commodities del dashboard
│       ├── pipeline_runner.py # Lanzar/detener pipeline + tail de logs
│       └── styles.py
└── src/
    ├── analisis/    # graficas_indices.py, nube_palabras.py
    ├── models/      # FinBERT, ZeroShot, CrudeBERT, Gemini, Claude (BaseModel)
    ├── pipeline/    # Clase Pipeline (run_io, run_compute, ...)
    ├── scrapers/    # GoogleScraper, YahooScraper (BaseScraper)
    └── utils/       # file_utils, aggregator, date_utils, text_preprocessing
```

## Cómo ejecutar

### Opción A — Dashboard (recomendado)

```
cd v4.0.0/dashboard
streamlit run app.py
```

El dashboard abre en el navegador. Desde la página **Ejecutar pipeline**:

1. Selecciona un commodity existente o crea uno nuevo.
2. Edita las queries de búsqueda si es necesario.
3. Define el rango de fechas (por defecto: desde la última actualización hasta ayer).
4. Elige funciones y modelos.
5. Ingresa las API keys de Gemini y/o Claude si los usas.
6. Pulsa **Ejecutar pipeline** y monitorea los logs en vivo.

Los resultados se visualizan en la página **Visualizar resultados**.

### Opción B — Terminal (pipeline completo, config.py)

```
python main.py
```

Ejecuta todos los commodities definidos en `config.py` con las funciones y
modelos habilitados en ese mismo archivo.

### Opción C — Terminal (commodity puntual, sin editar config.py)

```
python main.py \
  --commodity petroleo \
  --start 2026-01-01 \
  --end   2026-04-27 \
  --queries "oil price -palm" "Brent crude" \
  --funciones "TRAER NOTICIAS" "ANALIZAR SENTIMIENTOS" "AGREGAR RESULTADOS" \
  --modelos ZERO-SHOT CRUDEBERT FINBERT CLAUDE
```

## Configuración

### `config.py` (base del pipeline)

- **`FUNCIONES`** — pasos a ejecutar: `"TRAER NOTICIAS"`, `"TRAER PRECIOS"`,
  `"ANALIZAR SENTIMIENTOS"`, `"AGREGAR RESULTADOS"`, `"RESUMEN"`, `"CATALOGAR"`
- **`MODELS`** — modelos: `"FINBERT"`, `"ZERO-SHOT"`, `"CRUDEBERT"`, `"GEMINI"`, `"CLAUDE"`
- **`COMMODITIES`** — lista de dicts; las rutas (`raw_path`, `processed_path`,
  `output_path`) se generan automáticamente como `Path` absolutos desde `ROOT`

Campos por commodity:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `search_query` | `list[str]` | Queries de búsqueda (uno o más) |
| `summary_window` | `int` | Ventana en días hacia atrás para el resumen |
| `summary_date` | `datetime` | Fecha de referencia del resumen |
| `recuperar_batch_gemini` | `bool` | `True` para retomar un batch Gemini previo |
| `batch_name` | `str` | Identificador del batch Gemini a recuperar |

### `dashboard/config/commodities.json` (config del dashboard)

JSON creado y editado por la UI del dashboard. Estructura:

```json
{
  "oro":      { "label": "Oro",      "queries": ["gold price"] },
  "petroleo": { "label": "Petróleo", "queries": ["oil price -palm", "Brent crude"] }
}
```

Las API keys **no** se guardan en disco; se ingresan en la UI y se pasan como
variables de entorno al subproceso.

## Salidas

| Archivo | Ubicación | Descripción |
|---------|-----------|-------------|
| `noticias.xlsx` | `data/raw/<commodity>/` | Noticias crudas del scraper |
| `processed_news.xlsx` | `data/processed/<commodity>/` | Noticias con etiquetas de todos los modelos |
| `analisis_detallado.xlsx` | `data/processed/<commodity>/` | Scores numéricos por noticia |
| `sentimiento_diario_*.xlsx` | `output/<commodity>/excel/` | Índice diario (GPT / LLM / all_models) |
| `models_comparison.xlsx` | `output/<commodity>/excel/` | MA-7 de todos los tipos de modelo |
| `<commodity>.xlsx` | `data/results/` | Resumen diario para el dashboard |
| `indice_diario_*.png` | `output/<commodity>/grafs/` | Gráfica sentimiento + MA-7 |
| `model_comparisson.png` | `output/<commodity>/grafs/` | Comparación de modelos |
| `nube - <fecha>.png` | `output/<commodity>/resumen/nube/` | Nube de palabras |
| `resumen - <fecha>.txt` | `output/<commodity>/resumen/` | Resumen ejecutivo (Gemini) |
| `cataloged_news.xlsx` | `data/processed/<commodity>/` | Noticias con categoría temática |
| `current.log` | `data/runs/` | Log del último run del pipeline |
| `current.json` | `data/runs/` | Metadata del run activo (PID, fechas, modelos) |

## Modelos

| Modelo | Tipo | Fuente |
|--------|------|--------|
| FinBERT | BERT local | `yiyanghkust/finbert-tone` |
| Zero-Shot | BERT local | `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` |
| CrudeBERT | BERT local | `Captain-1337/CrudeBERT` |
| Gemini | LLM API | Google Generative AI (`gemini-2.5-flash`) |
| Claude | LLM API | Anthropic (`claude-sonnet-4-6`) |

## Commodities rastreados

oro, café, petróleo, níquel, carbón

## Tickers (Yahoo Finance)

| Commodity | Ticker | Instrumento |
|-----------|--------|-------------|
| Oro | `GC=F` | COMEX Gold Futures |
| Café | `KC=F` | Coffee C Futures |
| Petróleo | `BZ=F` | Brent Crude Futures |
| Níquel | — | No disponible en Yahoo Finance |
| Carbón | `COAL` | Range Global Coal Index ETF |

## Notas

- El dashboard lanza el pipeline como proceso desacoplado (no bloquea la UI) y
  permite detenerlo con el botón **Detener pipeline**.
- Los logs se acumulan en `data/runs/current.log` y el dashboard los muestra en
  vivo con auto-refresco cada 3 segundos.
- El campo `última actualización` en el dashboard se infiere de la fecha máxima
  en `processed_news.xlsx`; si no existe el archivo, el rango por defecto es
  los últimos 30 días.
- Los modelos se cargan una sola vez (`Pipeline.load_models()` estático) y se
  comparten entre todos los commodities.
- Gemini soporta modo batch (`try_batch: True`) con fallback automático a
  llamadas individuales si el batch tarda más de 30 h, y recuperación de
  batches previos con `recuperar_batch_gemini`.
- `CATALOGAR` y `RESUMEN` corren en la fase secuencial para evitar conflictos
  de GPU y límites de tasa de API.
