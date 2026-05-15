import src.utils.file_utils as file_utils
from datetime import date, datetime
from pathlib import Path

##############################################################################################
################################## CONFIGURACION GENERAL #####################################
##############################################################################################

# Absolute path to the project root (v1.0.1/). All other paths are derived from this.
ROOT = file_utils.get_project_root()

# Funciones que debe ejecutar el codigo.

FUNCIONES = []

FUNCIONES.append("TRAER NOTICIAS")
#FUNCIONES.append("TRAER PRECIOS")
FUNCIONES.append("ANALIZAR SENTIMIENTOS")
FUNCIONES.append("AGREGAR RESULTADOS")
#FUNCIONES.append("RESUMEN")
#FUNCIONES.append("CATALOGAR")
FUNCIONES.append("PRECIO FUTURO")

# Modelos que se utilizaran para el analisis de las noticias.

MODELS = []
MODELS.append("ZERO-SHOT")
MODELS.append("CRUDEBERT")
MODELS.append("FINBERT")
MODELS.append("ROBERTUITO")
MODELS.append("GEMINI")
MODELS.append("CLAUDE")

LLMS = ["ZERO-SHOT", "CRUDEBERT", "FINBERT", "ROBERTUITO"]
GPTS = ["GEMINI", "CLAUDE"]

##############################################################################################
####################################### COMMODITIES ##########################################
##############################################################################################

COMMODITIES = []

# COMMODITIES.append({
#     "name": "oro",
#     "ticker": "GC=F",           # COMEX Gold Futures
#     "search_query": ["gold price"],
#     "scraper": "google",
#     "news_number": 4,
#     "start_date": date(2026, 4, 27),
#     "end_date": date(2026, 5, 12),
#     "summary_window": 30,
#     "summary_date": datetime.now(),
#     "recuperar_batch_gemini": True,
#     "batch_name": "batches/29xsig4yfg5vyecz1c28d4qiwt5woc682uuy"
# })

# COMMODITIES.append({
#     "name": "cafe",
#     "ticker": "KC=F",           # Coffee C Futures
#     "search_query": ["international coffee price", 
#                      "Brazil coffee production", 
#                      "Vietnam coffee production", 
#                      "Colombia coffe production",
#                      "Arabica coffee price",
#                      "Robusta coffe price"],
#     "scraper": "google",
#     "news_number": 4,
#     "start_date": date(2026, 4, 27),
#     "end_date": date(2026, 5, 12),
#     "summary_window": 30,
#     "summary_date": datetime.now()
# })

COMMODITIES.append({
    "name": "petroleo",
    "ticker": "BZ=F",           # Brent Crude Futures
    "search_query": ["oil price -palm"],
    "scraper": "google",
    "news_number": 4,
    "start_date": date(2026, 5, 13),
    "end_date": date(2026, 5, 14),
    "summary_window": 30,
    "summary_date": datetime.now()
})

# COMMODITIES.append({
#     "name": "niquel",
#     "ticker": "",               # LME Nickel futures not available on Yahoo Finance
#     "search_query": ["nickel price",
#                      "Indonesia nickel production",
#                      "China nickel demand"],
#     "scraper": "google",
#     "news_number": 4,
#     "start_date": date(2026, 4, 27),
#     "end_date": date(2026, 5, 12),
#     "summary_window": 30,
#     "summary_date": datetime.now()
# })

# COMMODITIES.append({
#     "name": "carbon",
#     "ticker": "COAL",           # Range Global Coal Index ETF (best available proxy on Yahoo Finance)
#     "search_query": ["coal price",
#                      "Indonesia coal production",
#                      "China coal production",
#                      "Russia coal production"],
#     "scraper": "google",
#     "news_number": 4,
#     "start_date": date(2026, 4, 27),
#     "end_date": date(2026, 5, 12),
#     "summary_window": 30,
#     "summary_date": datetime.now()
# })

# Auto-generate absolute paths for every commodity from its name.
# raw_path       -> ROOT/data/raw/<name>/
# processed_path -> ROOT/data/processed/<name>/
# output_path    -> ROOT/output/<name>/

for _c in COMMODITIES:
    _n = _c["name"]
    _c["raw_path"]       = ROOT / "data"   / "raw"       / _n
    _c["processed_path"] = ROOT / "data"   / "processed" / _n
    _c["output_path"]    = ROOT / "output"               / _n


##############################################################################################
##################################### SCRAPER GOOGLE #########################################
##############################################################################################

# GOOGLE_CSS_CONFIG = {
#     "noticias":  "SoaBEf",
#     "titulo":    "ynAwRc",
#     "fuente":    "MgUUmf",
#     "resumen":   "UqSP2b",
#     "tiempo":    "LfVVr",
#     "no_results":"JPMJ2c"
# }

GOOGLE_CSS_CONFIG = {
    "noticias":  "SoAPf",
    "titulo":    "ynAwRc",
    "fuente":    "MgUUmf",
    "resumen":   "UqSP2b",
    "tiempo":    "LfVVr",
    "no_results":"JPMJ2c"
}


# Títulos a ignorar en el scraper de Google (match case-insensitive, exacto tras strip).
GOOGLE_TITLE_BLOCKLIST = {
    "good morning, nickel city! here are stories to start your day",
}

##############################################################################################
####################################### API CONFIG ###########################################
##############################################################################################

## OJO LLAVE CON BILLING ACTIVA, USAR CON CUIDADO. RECOMIENDO CREAR UNA CUENTA NUEVA SOLO PARA PRUEBAS.
GEMINI_CONFIG = {
    "model": "gemini-2.5-flash",
    "requests_per_minute": 1000,
    "requests_per_day": 10000,
    "tokens_per_minute": 1000000,
    "api_key": [""],
    "try_batch": True,
    "billing": True,
    "prompt": f"""
                **Role:** You are a financial analyst specializing in interpreting the tone and market sentiment of news headlines related to commodities, international prices, and the global economy.

                **Task:** Analyze the following news headline and summary. Classify their implied short-term price effect as **ALCISTA** (bullish), **BAJISTA** (bearish), or **NEUTRO** (neutral).

                **Analysis Framework:**
                - **ALCISTA (Bullish):** If the text suggests rising prices due to supply deficits, supply disruptions, falling inventories, strong demand, or robust economic growth.
                - **BAJISTA (Bearish):** If the text suggests falling prices due to supply surpluses, rising inventories, weak demand, economic slowdown, or explicit price declines.
                - **NEUTRO (Neutral):** If the text is purely informational, reports on stability, or lacks clear directional bias regarding supply/demand dynamics.

                Respond with ONLY ONE WORD: "ALCISTA", "BAJISTA" or "NEUTRO".
            """,
    "prompt_futuro": f"""
                **Role:** You are a financial analyst specializing in commodity market news.

                **Task:** Determine whether the following news headline and summary discusses the **CURRENT** state of the commodity price (recent price moves, what just happened, current market events already realized) OR what is **EXPECTED** to happen with the commodity price in the future (forecasts, projections, analyst expectations, anticipated supply/demand changes, scheduled future events, forward-looking outlook).

                **Classification Framework:**
                - **PRESENTE:** News reports on current/recent price action, today's market movements, events that have already happened, or factual descriptions of the present market state. Past-tense reporting is PRESENTE.
                - **FUTURO:** News discusses forecasts, projections, expectations, analyst price targets, anticipated supply/demand shifts, planned policy actions, scheduled future events that could affect prices, or any forward-looking commentary.

                If the news mixes both, classify by the dominant focus. If genuinely unclear, default to PRESENTE.

                Respond with ONLY ONE WORD: "PRESENTE" or "FUTURO".
            """,
    "prompt_resumen": f"""
            **Role:** You are a senior financial analyst specialized in global commodity markets and international economics.
            **Task:** Analyze the following collection of <NO_NOTICIAS> news articles about commodity prices and international markets to identify the overall market sentiment and direction of the <COMMODITY> price.
            **Analysis Instructions:**
            1. **Overall Market Direction Assessment:** Determine if the collective sentiment points to BULLISH, BEARISH, or MIXED/NEUTRAL conditions specifically for the <COMMODITY> prices.
            2. **Key Driving Factors:** Identify the main factors mentioned influencing the prices (supply, demand, geopolitics, economic data, inventories, OPEC decisions, main etc.)
            3. **Trend Analysis:** Note consistent patterns or emerging trends for <COMMODITY>.
            **Required Output Format:**
            Provide a comprehensive executive summary in SPANISH that includes:
            - Clear conclusion about <COMMODITY> market direction (alcista/bajista/neutral/mixto)
            - DO NOT invent dates, recipients, or sender information
            - Specific reasons and factors driving this sentiment FOR <COMMODITY>
            - Key trends observed across the news spectrum FOR <COMMODITY>
            - Professional tone suitable for financial decision-making

            **Important:** Write your complete analysis and summary in SPANISH, focusing specifically on the implications for <COMMODITY> prices based on the provided news.
            """
}

CLAUDE_CONFIG = {
    "model": "claude-sonnet-4-6",
    "requests_per_minute": 5,
    "requests_per_day": 20,
    "tokens_per_minute": 250000,
    "api_key": [""],
    "prompt": f"""
                **Role:** You are a financial analyst specializing in interpreting the tone and market sentiment of news headlines related to commodities, international prices, and the global economy.

                **Task:** Analyze the following news headline and summary. Classify their implied short-term price effect as **ALCISTA** (bullish), **BAJISTA** (bearish), or **NEUTRO** (neutral).

                **Analysis Framework:**
                - **ALCISTA (Bullish):** If the text suggests rising prices due to supply deficits, supply disruptions, falling inventories, strong demand, or robust economic growth.
                - **BAJISTA (Bearish):** If the text suggests falling prices due to supply surpluses, rising inventories, weak demand, economic slowdown, or explicit price declines.
                - **NEUTRO (Neutral):** If the text is purely informational, reports on stability, or lacks clear directional bias regarding supply/demand dynamics.

                **Headline:** headline_noticia
                **Summary:** summary_noticia

                Respond with ONLY ONE WORD: "ALCISTA", "BAJISTA" or "NEUTRO".
            """
}
