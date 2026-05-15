import torch
import pandas as pd
from tqdm import tqdm
from transformers import pipeline
from  .base_model import BaseModel, SentimentResult
from datetime import datetime

class ZeroShotModel(BaseModel):
    MODEL = "Zero-Shot"

    def __init__(self):
        super().__init__(self.MODEL)

    def load(self):
        device_id = 0 if torch.cuda.is_available() else -1
        device_label = "GPU" if device_id == 0 else "CPU"
        print(f"[ZeroShotModel] Cargando modelo  (dispositivo: {device_label})...")
        try:
            pipe_zero = pipeline(
                "zero-shot-classification",
                #model="joeddav/xlm-roberta-large-xnli",
                model="MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
                device=device_id
            )
            self.model = pipe_zero
            print(f"[ZeroShotModel] Modelo cargado correctamente.")

        except Exception as e:
            print(f"[ZeroShotModel] Error al cargar el modelo: {e}")
            self.model = None

    def predict(self, text: str, date: datetime) -> SentimentResult:
        if self.model is None:
            raise ValueError("[ZeroShotModel] El modelo no ha sido cargado. Llama a load() antes de predecir.")

        candidate_labels = ["alcista", "bajista", "neutral"]

        if not text.strip():
            return SentimentResult(text=text, score=0.0, label='NEUTRO', confidence=0.0, model=self.name)

        try:
            resultado = self.model(text, candidate_labels=candidate_labels)
            if resultado and 'labels' in resultado and 'scores' in resultado:
                top_label = resultado['labels'][0]
                score = round(resultado['scores'][0], 4)
                sentimiento = top_label.upper() if top_label in ("alcista", "bajista") else "NEUTRO"
            else:
                sentimiento = 'NEUTRO'
                score = 0.0

            return SentimentResult(text=text, score=score, label=sentimiento, confidence=score, model=self.name)

        except Exception as e:
            print(f"[ZeroShotModel] Error analizando texto: '{text[:50]}...'. Error: {e}")
            return SentimentResult(text=text, score=0.0, label='ERROR', confidence=0.0, model=self.name)

    def predict_batch(self, noticias: pd.DataFrame) -> list[tuple[str, float]]:
        if self.model is None:
            raise ValueError("[ZeroShotModel] El modelo no ha sido cargado.")

        candidate_labels = ["alcista", "bajista", "neutral"]
        texts = (noticias["title"] + " - " + noticias["summary"]).tolist()
        texts = [t if t.strip() else " " for t in texts]

        print(f"[ZeroShotModel] Analizando {len(texts)} textos (batch_size=16)...")

        try:
            outputs = self.model(
                texts,
                candidate_labels=candidate_labels,
                batch_size=16
            )

            results = []
            for result in outputs:
                if "labels" in result and "scores" in result:
                    top_label = result["labels"][0]
                    top_score = round(result["scores"][0], 4)
                    sentiment = top_label.upper() if top_label in ("alcista", "bajista") else "NEUTRO"
                else:
                    sentiment = "NEUTRO"
                    top_score = 0.0
                results.append((sentiment, top_score))

            print(f"[ZeroShotModel] Analisis completado  ({len(results)} resultados)")
            return results

        except Exception as e:
            print(f"[ZeroShotModel] Error en batch: {e}")
            return [("ERROR", 0.0) for _ in texts]
        
    def catalog_batch(self, noticias: pd.DataFrame):

        if self.model is None:
            raise ValueError("[ZeroShotModel] El modelo no ha sido cargado.")

        candidate_labels = ["supply disruption", "demand", "geopolitics", "OPEC/policy", "inventories", "macro/USD", "weather/climate", "other"]
        
        texts = (noticias["title"] + " - " + noticias["summary"]).tolist()
        texts = [t if t.strip() else " " for t in texts]

        print(f"[ZeroShotModel] Analizando {len(texts)} textos (batch_size=16)...")

        try:
            outputs = self.model(
                texts,
                candidate_labels=candidate_labels,
                batch_size=16
            )

            results = []
            for result in outputs:
                if "labels" in result and "scores" in result:
                    top_label = result["labels"][0]
                    top_score = round(result["scores"][0], 4)
                    sentiment = top_label.upper() if top_label in ("supply disruption", "demand", "geopolitics", "OPEC/policy", "inventories", "macro/USD", "weather/climate") else "other"
                else:
                    sentiment = "NEUTRO"
                    top_score = 0.0
                results.append((sentiment, top_score))

            print(f"[ZeroShotModel] Analisis completado  ({len(results)} resultados)")
            return results
        
        except Exception as e:
            print(f"[ZeroShotModel] Error en catalog batch: {e}")
            return [("ERROR", 0.0) for _ in texts]

        
