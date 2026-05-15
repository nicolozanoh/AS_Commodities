import torch
from tqdm import tqdm
from transformers import BertForSequenceClassification, BertTokenizer, pipeline
import pandas as pd
from  .base_model import BaseModel, SentimentResult
from datetime import datetime

class FinBERTModel(BaseModel):
    MODEL = "finBERT"

    def __init__(self):
        super().__init__(self.MODEL)

    def load(self):
        device_id = 0 if torch.cuda.is_available() else -1
        device_label = "GPU" if device_id == 0 else "CPU"
        print(f"[FinBERTModel] Cargando modelo  (dispositivo: {device_label})...")
        try:
            tokenizer = BertTokenizer.from_pretrained("yiyanghkust/finbert-tone")
            model = BertForSequenceClassification.from_pretrained("yiyanghkust/finbert-tone")

            pipe_finbert = pipeline(
                "text-classification",
                model=model,
                tokenizer=tokenizer,
                device=device_id,
                top_k=None
            )

            self.model = pipe_finbert
            print(f"[FinBERTModel] Modelo cargado correctamente.")

        except Exception as e:
            print(f"[FinBERTModel] Error al cargar el modelo: {e}")
            self.model = None

    def predict(self, text) -> SentimentResult:
        if self.model is None:
            raise ValueError("[FinBERTModel] El modelo no ha sido cargado. Llama a load() antes de predecir.")

        mapa_etiquetas = {'Positive': 'ALCISTA', 'Negative': 'BAJISTA', 'Neutral': 'NEUTRO'}

        if not text.strip():
            return SentimentResult(text=text, score=0.0, label='NEUTRO', confidence=0.0, model=self.name)

        try:
            resultado = self.model(text)
            if resultado and resultado[0]:
                mejor = max(resultado[0], key=lambda x: x['score'])
                sentimiento = mapa_etiquetas.get(mejor['label'], 'NEUTRO')
                score = round(mejor['score'], 4)
            else:
                sentimiento = 'NEUTRO'
                score = 0.0

            return SentimentResult(text=text, score=score, label=sentimiento, confidence=score, model=self.name)

        except Exception as e:
            print(f"[FinBERTModel] Error analizando texto: '{text[:50]}...'. Error: {e}")
            return SentimentResult(text=text, score=0.0, label='ERROR', confidence=0.0, model=self.name)

    def predict_batch(self, noticias: pd.DataFrame):
        mapa_etiquetas = {'Positive': 'ALCISTA', 'Negative': 'BAJISTA', 'Neutral': 'NEUTRO'}

        texts = (noticias["title"] + " - " + noticias["summary"]).tolist()
        print(f"[FinBERTModel] Analizando {len(texts)} textos (batch_size=32)...")

        outputs = self.model(
            texts,
            batch_size=32
        )

        results = []
        for output in outputs:
            best = max(output, key=lambda x: x['score'])
            label = mapa_etiquetas.get(best['label'], 'NEUTRO')
            score = round(best['score'], 4)
            results.append((label, score))

        print(f"[FinBERTModel] Analisis completado  ({len(results)} resultados)")
        return results
