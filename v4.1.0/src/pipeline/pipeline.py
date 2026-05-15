import os

import pandas as pd
from tqdm import tqdm
from pathlib import Path
import src.utils.text_preprocessing as text_preprocessing
import src.analisis.nube_palabras as nube
import src.analisis.graficas_indices as graficas_indices
from config import FUNCIONES, MODELS, LLMS, ROOT
from ..scrapers.base_scraper import BaseScraper
from ..models.base_model import BaseModel, SentimentResult
from ..utils.aggregator import aggregate
from datetime import datetime, timedelta


class Pipeline:
    def __init__(
            self,
            scraper: BaseScraper,
            commodity: dict,
            models: list[BaseModel] = None
    ):
        self.scraper = scraper
        self.commodity = commodity
        self.models = models or []

    # ------------------------------------------------------------------
    # Execution entry points
    # ------------------------------------------------------------------

    def run(self):
        """Runs all enabled functions sequentially (convenience method)."""
        self.run_io()
        
        if ("ANALIZAR SENTIMIENTOS" in FUNCIONES) and not self.models:
            self.models = Pipeline.load_models()
        
        self.run_compute()

    def _print_step(self, step: str):
        name = self.commodity["name"].upper()
        label = f"  {step}  |  {name}  "
        border = "-" * max(len(label), 50)
        print(f"\n[Pipeline] {border}")
        print(f"[Pipeline] {label}")
        print(f"[Pipeline] {border}")

    def run_io(self):
        """
        Runs only I/O-bound steps.
        Safe to call in parallel across multiple Pipeline instances.
        """
        if "TRAER NOTICIAS" in FUNCIONES:
            self._print_step("TRAER NOTICIAS")
            self.scraper.fetch()

        if "TRAER PRECIOS" in FUNCIONES:
            self._print_step("TRAER PRECIOS")
            self.traer_precios()

    def run_compute(self):
        """
        Runs compute-heavy steps.
        Call after run_io() completes for all commodities.
        Expects self.models to be pre-loaded when ANALIZAR SENTIMIENTOS is active.
        """
        if "ANALIZAR SENTIMIENTOS" in FUNCIONES:
            self._print_step("ANALIZAR SENTIMIENTOS")
            self.analizar_sentimientos()

        if "AGREGAR RESULTADOS" in FUNCIONES:
            self._print_step("AGREGAR RESULTADOS")
            self.aggregar_resultados()

        if "RESUMEN" in FUNCIONES:
            self._print_step("RESUMEN")
            self.resumen()
        
        if "CATALOGAR" in FUNCIONES:
            self._print_step("CATALOGAR")
            self.catalogar()

        if "PRECIO FUTURO" in FUNCIONES:
            self._print_step("PRECIO FUTURO")
            self.precio_futuro()

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def traer_precios(self):
        from ..scrapers.yahoo_scraper import YahooScraper

        ticker = self.commodity.get("ticker", "")
        if not ticker:
            print(f"[Pipeline] '{self.commodity['name']}' no tiene ticker configurado, se omite TRAER PRECIOS.")
            return

        yahoo = YahooScraper(self.commodity)

        print(f"[Pipeline] Obteniendo precios de cierre  ({self.commodity['name']} - {ticker})")
        prices = yahoo.get_close_prices()
        if prices is not None and not prices.empty:
            yahoo._save(prices, "precios.xlsx")
            print(f"[Pipeline] precios.xlsx guardado  ({len(prices)} filas)")
        else:
            print(f"[Pipeline] No se encontraron datos de precios para {ticker}")

        print(f"[Pipeline] Obteniendo datos de analistas  ({self.commodity['name']} - {ticker})")
        sentiment = yahoo.get_analyst_sentiment()
        if sentiment is not None and not sentiment.empty:
            yahoo._save(sentiment, "analisis_analistas.xlsx")
            print(f"[Pipeline] analisis_analistas.xlsx guardado  ({len(sentiment)} filas)")
        else:
            print(f"[Pipeline] No hay datos de analistas disponibles para {ticker}")

    def precio_futuro(self):
        """Classify each processed news as PRESENTE vs FUTURO using Gemini,
        save the future-only subset, and aggregate a daily future-outlook score."""
        from ..models.gemini_model import GeminiModel

        processed_file = self.commodity["processed_path"] / "processed_news.xlsx"
        if not processed_file.exists():
            print(f"[Pipeline] No existe {processed_file}. Ejecuta ANALIZAR SENTIMIENTOS primero.")
            return

        print(f"[Pipeline] Cargando noticias procesadas...")
        noticias = pd.read_excel(processed_file)
        if noticias.empty:
            print(f"[Pipeline] processed_news.xlsx esta vacio, nada que clasificar.")
            return

        noticias["id"] = range(1, len(noticias) + 1)

        if "temporal_label" not in noticias.columns:
            noticias["temporal_label"] = pd.NA

        existing = noticias["temporal_label"].astype("string").str.strip().str.upper()
        pendiente_mask = existing.isna() | existing.eq("") | existing.eq("ERROR")
        pendientes = noticias[pendiente_mask]
        n_pendientes = len(pendientes)
        n_ya = len(noticias) - n_pendientes

        if n_pendientes == 0:
            print(f"[Pipeline] Todas las noticias ya tienen temporal_label ({n_ya}). Se omite la clasificacion.")
        else:
            print(f"[Pipeline] Cargando modelo Gemini...")
            modelo = GeminiModel()
            modelo.load()

            print(f"[Pipeline] Clasificando temporalidad (PRESENTE vs FUTURO)  "
                  f"({n_pendientes} pendientes, {n_ya} ya clasificadas)...")
            preds = modelo.classify_temporal_batch(pendientes)
            new_labels = [str(p[0]).strip().upper() for p in preds]
            noticias.loc[pendiente_mask, "temporal_label"] = new_labels

        noticias["temporal_label"] = noticias["temporal_label"].astype("string").str.strip().str.upper()

        noticias_to_save = noticias.drop(columns=["id"]).sort_values("published_date").reset_index(drop=True)
        self.commodity["processed_path"].mkdir(parents=True, exist_ok=True)
        noticias_to_save.to_excel(processed_file, index=False)
        print(f"[Pipeline] Columna 'temporal_label' actualizada en processed_news.xlsx")

        is_futuro = noticias["temporal_label"].str.startswith("FUTURO", na=False)
        futuro = noticias[is_futuro].drop(columns=["id"]).reset_index(drop=True)
        n_futuro, n_total = len(futuro), len(noticias)
        print(f"[Pipeline] Noticias FUTURO: {n_futuro} / {n_total}  ({(n_futuro/n_total*100 if n_total else 0):.1f}%)")

        future_news_file = self.commodity["processed_path"] / "future_news.xlsx"
        futuro.to_excel(future_news_file, index=False)
        print(f"[Pipeline] future_news.xlsx guardado")

        if futuro.empty:
            print(f"[Pipeline] Sin noticias FUTURO, no se genera indice diario.")
            return

        print(f"[Pipeline] Calculando indices diarios FUTURO  ({n_futuro} noticias)...")
        future_news_df, _ = aggregate(
            futuro,
            "published_date",
            self.commodity["processed_path"] / "future_analisis_detallado.xlsx",
            self.commodity["output_path"] / "excel" / "future_daily.xlsx",
            comparison_name="future_models_comparison.xlsx",
        )

        results_dir = ROOT / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        summary = future_news_df.rename(columns={
            "published_date": "fecha",
            "overall_label":  "label",
            "overall_sentiment": "score",
        })
        summary.to_excel(results_dir / f"{self.commodity['name']}_future.xlsx", index=False)
        print(f"[Pipeline] Resumen dashboard FUTURO guardado en data/results/{self.commodity['name']}_future.xlsx")

    def catalogar(self):
        from ..models.zero_shot_model import ZeroShotModel

        print(f"[Pipeline] Cargando modelo Gemini...")
        modelo = ZeroShotModel()
        modelo.load()
    
        processed_news = self.commodity["processed_path"] / "processed_news.xlsx"
        noticias = pd.read_excel(processed_news)
        noticias["id"] = range(1, len(noticias) + 1)
        #noticias = noticias[noticias["processed"] == 0]

        #print(f"[Pipeline] Noticias pendientes de analisis: {len(noticias)}")

        model_name = modelo.name.lower()
        print(f"[Pipeline] Analizando con {modelo.name}  ({len(noticias)} noticias)...")
        preds = modelo.catalog_batch(noticias)

        labels = [p[0] for p in preds]
        scores = [p[1] for p in preds]

        noticias[f"catalog_label"] = labels
        noticias[f"catalog_score"] = scores

        resultado = noticias

        resultado = resultado.drop(columns=["id"])
        resultado = resultado.sort_values("published_date").reset_index(drop=True)

        save_path = self.commodity["processed_path"] / "cataloged_news.xlsx"
        self.commodity["processed_path"].mkdir(parents=True, exist_ok=True)
        resultado.to_excel(save_path, index=False)
        print(f"[Pipeline] Resultados guardados  ({len(resultado)} noticias en total)")

    def resumen(self):
        from ..models.gemini_model import GeminiModel

        print(f"[Pipeline] Cargando modelo Gemini...")
        modelo_gemini = GeminiModel()
        modelo_gemini.load()

        processed_file = self.commodity["processed_path"] / "processed_news.xlsx"
        print(f"[Pipeline] Cargando noticias procesadas...")
        noticias = pd.read_excel(processed_file)
        fecha_resumen = datetime.now()

        if self.commodity.get("summary_date"):
            fecha_resumen = pd.to_datetime(self.commodity["summary_date"])

        fecha_inicio = fecha_resumen - timedelta(days=self.commodity["summary_window"])

        noticias["published_date"] = pd.to_datetime(noticias["published_date"])
        noticias = noticias[
            (noticias["published_date"] >= fecha_inicio) &
            (noticias["published_date"] <= fecha_resumen)
        ].reset_index(drop=True)

        print(f"[Pipeline] Noticias en ventana {fecha_inicio.strftime('%Y-%m-%d')} / {fecha_resumen.strftime('%Y-%m-%d')}: {len(noticias)}")

        texto = text_preprocessing.preprocess_wordcloud(noticias)
        if not texto.strip():
            print(f"[Pipeline] No hay texto suficiente para generar la nube de palabras.")
            return

        print(f"[Pipeline] Generando nube de palabras...")
        nube.crear_nube(texto, fecha_resumen, self.commodity["output_path"])

        no_noticias = len(noticias)
        texto_resumen = text_preprocessing.preprocess_resumen(noticias)

        print(f"[Pipeline] Generando resumen con Gemini  ({no_noticias} noticias)...")
        resumen = modelo_gemini.resumen(self.commodity["name"], no_noticias, texto_resumen)

        resumen_dir = self.commodity["output_path"] / "resumen"
        resumen_dir.mkdir(parents=True, exist_ok=True)

        output_file = resumen_dir / f"resumen - {fecha_resumen.strftime('%d%b%Y').lower()}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"RESUMEN DE NOTICIAS: {self.commodity['name'].upper()} - {datetime.now().strftime('%d%b%Y').lower()}\n")
            f.write("=" * 100 + "\n\n")
            f.write(f"Total de noticias: {no_noticias}\n")
            f.write(f"Periodo: {fecha_inicio.strftime('%Y-%m-%d')} a {fecha_resumen.strftime('%Y-%m-%d')}\n\n")
            f.write(resumen if resumen and "ERROR_" not in resumen else "Error al generar resumen.")

        print(f"[Pipeline] Resumen guardado en {output_file}")

    def aggregar_resultados(self):
        processed_file = self.commodity["processed_path"] / "processed_news.xlsx"
        print(f"[Pipeline] Cargando noticias procesadas...")
        noticias = pd.read_excel(processed_file)

        print(f"[Pipeline] Calculando indices de sentimiento  ({len(noticias)} noticias)...")
        news_df, _ = aggregate(
            noticias,
            "published_date",
            self.commodity["processed_path"] / "analisis_detallado.xlsx",
            self.commodity["output_path"] / "excel" / "sentimiento_diario.xlsx"
        )

        # Save a dashboard-compatible summary so the visualization page can find it
        results_dir = ROOT / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        summary = news_df.rename(columns={
            "published_date": "fecha",
            "overall_label":  "label",
            "overall_sentiment": "score",
        })
        summary.to_excel(results_dir / f"{self.commodity['name']}.xlsx", index=False)
        print(f"[Pipeline] Resumen dashboard guardado en data/results/{self.commodity['name']}.xlsx")

        print(f"[Pipeline] Generando graficas de comparacion de modelos...")
        graficas_indices.graficar_comparacion_modelos(self.commodity)

        print(f"[Pipeline] Generando graficas de indices diarios...")
        graficas_indices.graficar_indices(self.commodity)

        print(f"[Pipeline] Agregacion de resultados completada.")

    def analizar_sentimientos(self):
        raw_file = self.commodity["raw_path"] / "noticias.xlsx"
        noticias = pd.read_excel(raw_file)
        noticias["id"] = range(1, len(noticias) + 1)
        noticias = noticias[noticias["processed"] == 0]

        print(f"[Pipeline] Noticias pendientes de analisis: {len(noticias)}")

        for modelo in self.models:
            model_name = modelo.name.lower()
            print(f"[Pipeline] Analizando con {modelo.name}  ({len(noticias)} noticias)...")
            preds = modelo.predict_batch(noticias)

            labels = [p[0] for p in preds]
            scores = [p[1] for p in preds]

            if model_name.upper() in LLMS:
                noticias.loc[noticias["processed"] == 0, f"LLM_{model_name}_label"] = labels
                noticias.loc[noticias["processed"] == 0, f"LLM_{model_name}_score"] = scores
            else:
                noticias.loc[noticias["processed"] == 0, f"GPT_{model_name}_label"] = labels
                noticias.loc[noticias["processed"] == 0, f"GPT_{model_name}_score"] = scores

        noticias.loc[noticias["processed"] == 0, "processed"] = 1

        processed_file = self.commodity["processed_path"] / "processed_news.xlsx"
        if processed_file.exists():
            print(f"[Pipeline] Combinando con noticias ya procesadas...")
            existentes = pd.read_excel(processed_file)
            resultado = pd.concat([existentes, noticias], ignore_index=True)
        else:
            resultado = noticias

        if raw_file.exists():
            raw_file.unlink()

        resultado = resultado.drop(columns=["id"])
        resultado = resultado.sort_values("published_date").reset_index(drop=True)

        self.commodity["processed_path"].mkdir(parents=True, exist_ok=True)
        resultado.to_excel(processed_file, index=False)
        print(f"[Pipeline] Resultados guardados  ({len(resultado)} noticias en total)")

    # ------------------------------------------------------------------
    # Model loading (static — call once and share across Pipeline instances)
    # ------------------------------------------------------------------

    @staticmethod
    def load_models() -> list[BaseModel]:
        modelos_cargados = []
        print(f"[Pipeline] Cargando {len(MODELS)} modelo(s): {', '.join(MODELS)}")

        for modelo in MODELS:
            if modelo == "FINBERT":
                from ..models.finBERT_model import FinBERTModel
                print(f"[Pipeline] Cargando FinBERT...")
                m = FinBERTModel()
                m.load()
                modelos_cargados.append(m)

            elif modelo == "ZERO-SHOT":
                from ..models.zero_shot_model import ZeroShotModel
                print(f"[Pipeline] Cargando Zero-Shot...")
                m = ZeroShotModel()
                m.load()
                modelos_cargados.append(m)

            elif modelo == "CRUDEBERT":
                from ..models.crudeBERT_model import CrudeBERTModel
                print(f"[Pipeline] Cargando CrudeBERT...")
                m = CrudeBERTModel()
                m.load()
                modelos_cargados.append(m)

            elif modelo == "ROBERTUITO":
                from ..models.robertuito_model import RobertuiModel
                print(f"[Pipeline] Cargando Robertuito...")
                m = RobertuiModel()
                m.load()
                modelos_cargados.append(m)

            elif modelo == "GEMINI":
                from ..models.gemini_model import GeminiModel
                print(f"[Pipeline] Cargando Gemini...")
                m = GeminiModel()
                m.load()
                modelos_cargados.append(m)

            elif modelo == "CLAUDE":
                from ..models.claude_model import ClaudeModel
                print(f"[Pipeline] Cargando Claude...")
                m = ClaudeModel()
                m.load()
                modelos_cargados.append(m)

        print(f"[Pipeline] {len(modelos_cargados)} modelo(s) cargado(s).")
        return modelos_cargados
