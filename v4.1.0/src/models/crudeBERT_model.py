import torch
import pandas as pd
import numpy as np
from tqdm import tqdm
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from  .base_model import BaseModel, SentimentResult
from datetime import datetime

class CrudeBERTModel(BaseModel):
    MODEL = 'CrudeBERT'

    def __init__(self):
        super().__init__(self.MODEL)

    def load(self):
        fallback_tokenizer_name = 'bert-base-uncased'
        tokenizer = None

        print(f"[CrudeBERTModel] Cargando tokenizer...")
        try:
            tokenizer = AutoTokenizer.from_pretrained('Captain-1337/CrudeBERT', revision='main')
            print(f"[CrudeBERTModel] Tokenizer cargado.")
        except Exception as e_tok:
            print(f"[CrudeBERTModel] No se pudo cargar el tokenizer original: {e_tok}")
            print(f"[CrudeBERTModel] Usando tokenizer de respaldo: {fallback_tokenizer_name}")
            try:
                tokenizer = AutoTokenizer.from_pretrained(fallback_tokenizer_name)
                print(f"[CrudeBERTModel] Tokenizer de respaldo cargado.")
            except Exception as e_fall:
                print(f"[CrudeBERTModel] Error critico: no se pudo cargar ningun tokenizer: {e_fall}")

        if tokenizer is not None:
            self.tokenizer = tokenizer
            model_crude = None
            print(f"[CrudeBERTModel] Cargando pesos del modelo...")
            try:
                model_crude = AutoModelForSequenceClassification.from_pretrained('Captain-1337/CrudeBERT', revision='main')
                self.model = model_crude
            except Exception as e_mod:
                print(f"[CrudeBERTModel] Error al cargar el modelo: {e_mod}")
                self.model = None

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            if model_crude is not None:
                model_crude.to(device)
                self.model = model_crude
                self.device = device
                print(f"[CrudeBERTModel] Modelo cargado correctamente  (dispositivo: {device.type.upper()}).")

    def predict(self, text: str) -> SentimentResult:
        if self.model is None:
            raise ValueError("[CrudeBERTModel] El modelo no ha sido cargado. Llama a load() antes de predecir.")

        mapa_indice_a_espanol = {0: 'ALCISTA', 1: 'BAJISTA', 2: 'NEUTRO'}

        if not text.strip():
            return SentimentResult(text=text, score=0.0, label='NEUTRO', confidence=0.0, model=self.name)

        try:
            enc = self.tokenizer(text, truncation=True, padding=True, return_tensors="pt", max_length=512).to(self.device)
            with torch.no_grad():
                out = self.model(**enc)

            probs = torch.softmax(out.logits, dim=-1).cpu().numpy()[0]
            idx = int(np.argmax(probs))
            score = float(np.max(probs))

            return SentimentResult(text=text, score=score, label=mapa_indice_a_espanol.get(idx, 'NEUTRO'), confidence=score, model=self.name)

        except Exception as e:
            print(f"[CrudeBERTModel] Error analizando texto: '{text[:50]}...'. Error: {e}")
            return SentimentResult(text=text, score=0.0, label='ERROR', confidence=0.0, model=self.name)

    def predict_batch(self, noticias: pd.DataFrame) -> list[tuple[str, float]]:
        if self.model is None:
            raise ValueError("[CrudeBERTModel] El modelo no ha sido cargado.")

        mapa_indice_a_espanol = {0: "ALCISTA", 1: "BAJISTA", 2: "NEUTRO"}
        texts = (noticias["title"] + " - " + noticias["summary"]).tolist()
        batch_size = 32
        results = []

        print(f"[CrudeBERTModel] Analizando {len(texts)} textos (batch_size={batch_size})...")

        batches = range(0, len(texts), batch_size)
        for i in tqdm(batches, desc="[CrudeBERTModel] Clasificando", unit="batch"):
            batch_texts = texts[i:i + batch_size]

            encodings = self.tokenizer(
                batch_texts,
                truncation=True,
                padding=True,
                max_length=512,
                return_tensors="pt"
            )
            encodings = {k: v.to(self.device) for k, v in encodings.items()}

            with torch.no_grad():
                outputs = self.model(**encodings)

            probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()

            for prob_vector in probs:
                idx = int(np.argmax(prob_vector))
                score = float(np.max(prob_vector))
                results.append((mapa_indice_a_espanol.get(idx, "NEUTRO"), round(score, 4)))

        print(f"[CrudeBERTModel] Analisis completado  ({len(results)} resultados)")
        return results
