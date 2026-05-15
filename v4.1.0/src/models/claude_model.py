import json
import os
import pandas as pd
import time
from tqdm import tqdm
from anthropic import Anthropic
from  .base_model import BaseModel, SentimentResult, DailyRateLimitException
from config import CLAUDE_CONFIG

class ClaudeModel(BaseModel):
    MODEL = "claude"
    api_key_index = 0
    calls_made_minute = 0
    calls_made_day = 0
    tokens_used = 0

    def __init__(self):
        super().__init__(self.MODEL)

    def load(self):
        try:
            self.model = Anthropic(api_key=CLAUDE_CONFIG["api_key"][self.api_key_index])
            print(f"[ClaudeModel] Modelo cargado  (key #{self.api_key_index + 1})")
        except Exception as e:
            print(f"[ClaudeModel] Error al cargar el modelo: {e}")

    def predict(self, title: str, summary: str) -> SentimentResult:
        if self.calls_made_day >= CLAUDE_CONFIG["requests_per_day"]:
            if self.api_key_index + 1 < len(CLAUDE_CONFIG["api_key"]):
                print(f"[ClaudeModel] Limite diario alcanzado para key #{self.api_key_index + 1}. Cambiando a siguiente...")
                self.api_key_index += 1
                self.calls_made_day = 0
                self.calls_made_minute = 0
                self.tokens_used = 0
                self.load()
            else:
                print(f"[ClaudeModel] Limite alcanzado para todas las api keys.")
                raise DailyRateLimitException("[ClaudeModel] Limite alcanzado para todas las api keys.")

        if self.calls_made_minute >= CLAUDE_CONFIG["requests_per_minute"]:
            print(f"[ClaudeModel] Limite por minuto alcanzado. Esperando 60 segundos...")
            time.sleep(60)
            self.calls_made_minute = 0
            self.tokens_used = 0

        prompt = f"**Headline:** {title}\n**Summary:** {summary}"
        response = self.model.messages.create(
            model=CLAUDE_CONFIG["model"],
            max_tokens=10,
            system=CLAUDE_CONFIG["prompt"],
            messages=[{"role": "user", "content": prompt}]
        )

        self.calls_made_minute += 1
        self.calls_made_day += 1
        self.tokens_used += response.usage.input_tokens + response.usage.output_tokens

        label = response.content[0].text.strip().upper()
        return SentimentResult(label=label, score=None)

    def predict_batch(self, data: pd.DataFrame):
        """
        Uses Anthropic's Message Batches API (50% cheaper, async).
        """
        print(f"[ClaudeModel] Construyendo batch  ({len(data)} articulos)...")
        requests = self._build_batch_requests(data)

        batch = self.model.messages.batches.create(requests=requests)
        print(f"[ClaudeModel] Batch enviado: {batch.id}  |  Estado: {batch.processing_status}")

        completed = {"ended"}
        with tqdm(desc="[ClaudeModel] Esperando batch", unit="poll", bar_format="{desc}: {elapsed} transcurrido") as pbar:
            while batch.processing_status not in completed:
                time.sleep(30)
                batch = self.model.messages.batches.retrieve(batch.id)
                pbar.set_postfix_str(f"estado={batch.processing_status}")
                pbar.update(1)

        print(f"[ClaudeModel] Batch finalizado: {batch.processing_status}")

        print(f"[ClaudeModel] Recuperando resultados...")
        sentiments = {}
        for result in self.model.messages.batches.results(batch.id):
            article_id = result.custom_id
            try:
                text = result.result.message.content[0].text.strip().upper()
                sentiments[article_id] = text
            except Exception:
                sentiments[article_id] = "ERROR"

        print(f"[ClaudeModel] Resultados recibidos: {len(sentiments)} articulos")
        return [(sentiments[key], None) for key in sorted(sentiments, key=lambda x: int(x))]

    def _build_batch_requests(self, df: pd.DataFrame) -> list:
        requests = []
        for row in df.itertuples():
            prompt = f"**Headline:** {row.title}\n**Summary:** {row.summary}"
            requests.append({
                "custom_id": str(row.id),
                "params": {
                    "model": CLAUDE_CONFIG["model"],
                    "max_tokens": 10,
                    "system": CLAUDE_CONFIG["prompt"],
                    "messages": [{"role": "user", "content": prompt}]
                }
            })
        return requests

    def count_tokens(self, title: str, summary: str) -> int:
        prompt = f"**Headline:** {title}\n**Summary:** {summary}"
        response = self.model.messages.count_tokens(
            model=CLAUDE_CONFIG["model"],
            system=CLAUDE_CONFIG["prompt"],
            messages=[{"role": "user", "content": prompt}]
        )
        return response.input_tokens
