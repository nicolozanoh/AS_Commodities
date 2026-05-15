import json
import pandas as pd
import time
from tqdm import tqdm
from google import genai
from  .base_model import BaseModel, SentimentResult, DailyRateLimitException
from config import GEMINI_CONFIG, ROOT
from datetime import datetime
from google.genai import types

class GeminiModel(BaseModel):
    MODEL = "gemini"
    api_key_index = 0
    calls_made_minute = 0
    calls_made_day = 0
    tokens_used = 0

    def __init__(self):
        super().__init__(self.MODEL)

    def load(self):
        try:
            self.model = genai.Client(api_key=GEMINI_CONFIG["api_key"][self.api_key_index])
            print(f"[GeminiModel] Modelo cargado  (key #{self.api_key_index + 1})")
        except Exception as e:
            print(f"[GeminiModel] Error al cargar el modelo: {e}")

    def predict(self, prompt: str, instructions: str) -> str:
        self.tokens_used += self.count_tokens(prompt, instructions)

        if self.calls_made_day >= GEMINI_CONFIG["requests_per_day"]:
            if self.api_key_index + 1 < len(GEMINI_CONFIG["api_key"]):
                print(f"[GeminiModel] Limite diario alcanzado para key #{self.api_key_index + 1}. Cambiando a siguiente...")
                self.api_key_index += 1
                self.calls_made_day = 0
                self.calls_made_minute = 0
                self.tokens_used = 0
                self.load()
            else:
                print(f"[GeminiModel] Limite alcanzado para todas las api keys.")
                raise DailyRateLimitException("[GeminiModel] Limite alcanzado para todas las api keys.")

        if self.tokens_used >= GEMINI_CONFIG["tokens_per_minute"] or self.calls_made_minute >= GEMINI_CONFIG["requests_per_minute"]:
            print(f"[GeminiModel] Limite por minuto alcanzado. Esperando 60 segundos...")
            time.sleep(60)
            self.calls_made_minute = 0
            self.tokens_used = 0

        response = self.model.models.generate_content(
            model=f"models/{GEMINI_CONFIG['model']}",
            config=types.GenerateContentConfig(system_instruction=instructions),
            contents=[{"parts": [{"text": prompt}]}]
        )

        label = response.text.strip().upper()
        return label

    def predict_batch(self, data):
        timeout = False

        if GEMINI_CONFIG['try_batch']:
            print(f"[GeminiModel] Construyendo archivo batch  ({len(data)} articulos)...")
            jsonl_path = self.build_batch_file(data)

            print(f"[GeminiModel] Subiendo archivo a la API...")
            uploaded_file = self.model.files.upload(file=jsonl_path, config={"mime_type": "application/jsonl"})
            print(f"[GeminiModel] Archivo subido: {uploaded_file.name}")

            job = self.model.batches.create(
                model=f"{GEMINI_CONFIG['model']}",
                src=uploaded_file.name
            )
            print(f"[GeminiModel] Job enviado: {job.name}  |  Estado: {job.state}")

            completed = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED"}
            start_time = datetime.now()

            with tqdm(desc="[GeminiModel] Esperando batch", unit="poll", bar_format="{desc}: {elapsed} transcurrido{postfix}") as pbar:
                while job.state not in completed:
                    time.sleep(30)
                    job = self.model.batches.get(name=job.name)
                    elapsed = (datetime.now() - start_time).seconds // 60
                    pbar.set_postfix_str(f"Estado: {job.state}")
                    pbar.update(1)

                    if (datetime.now() - start_time).total_seconds() > 6 * 3600:
                        self.model.batches.cancel(name=job.name)
                        timeout = True
                        tqdm.write(f"[GeminiModel] Timeout alcanzado. Job cancelado. Se realizaran llamados individuales.")
                        break

            print(f"[GeminiModel] Job finalizado con estado: {job.state}")

            if not timeout:
                print(f"[GeminiModel] Descargando resultados...")
                result_file_name = job.dest.file_name
                file_content_bytes = self.model.files.download(file=result_file_name)
                file_content = file_content_bytes.decode('utf-8')

                sentiments = {}
                for line in file_content.splitlines():
                    if not line.strip():
                        continue
                    result = json.loads(line)
                    article_id = result["key"]
                    try:
                        text = result["response"]["candidates"][0]["content"]["parts"][0]["text"].strip()
                        sentiments[article_id] = text
                    except Exception:
                        sentiments[article_id] = "ERROR"

                print(f"[GeminiModel] Resultados recibidos: {len(sentiments)} articulos")

        if not GEMINI_CONFIG['try_batch'] or timeout:
            print(f"[GeminiModel] Iniciando llamados individuales  ({len(data)} articulos)...")
            sentiments = {}

            for _, article in tqdm(data.iterrows(), total=len(data), desc="[GeminiModel] Analizando", unit="noticia"):
                prompt = f"**Headline:** {article['title']}\n**Summary:** {article['summary']}"
                label = self.predict(prompt, GEMINI_CONFIG['prompt'])
                sentiments[article['id']] = label

        return [(sentiments[key], None) for key in sorted(sentiments, key=lambda x: int(x))]

    def count_tokens(self, prompt: str, instructions: str) -> float:
        response = self.model.models.count_tokens(
            model=f"models/{GEMINI_CONFIG['model']}",
            contents=[
                {"parts": [{"text": instructions}]},
                {"parts": [{"text": prompt}]}
            ]
        )
        return response.total_tokens

    def build_batch_file(self, df: pd.DataFrame, output_path=None):
        if output_path is None:
            output_path = ROOT / "inputs" / "gemini_batch_input.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for _, article in df.iterrows():
                prompt = f"**Headline:** {article['title']}\n**Summary:** {article['summary']}"
                entry = {
                    "key": str(article["id"]),
                    "request": {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "systemInstruction": {"parts": [{"text": GEMINI_CONFIG["prompt"]}]},
                    }
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"[GeminiModel] Archivo batch escrito: {len(df)} solicitudes en {output_path}")
        return output_path

    def classify_temporal_batch(self, data):
        """Classifies each news article as PRESENTE (current price) or FUTURO (expected/future price)."""
        timeout = False

        if GEMINI_CONFIG['try_batch']:
            print(f"[GeminiModel] Construyendo archivo batch temporal  ({len(data)} articulos)...")
            jsonl_path = self.build_batch_temporal_file(data)

            print(f"[GeminiModel] Subiendo archivo a la API...")
            uploaded_file = self.model.files.upload(file=jsonl_path, config={"mime_type": "application/jsonl"})
            print(f"[GeminiModel] Archivo subido: {uploaded_file.name}")

            job = self.model.batches.create(
                model=f"{GEMINI_CONFIG['model']}",
                src=uploaded_file.name
            )
            print(f"[GeminiModel] Job enviado: {job.name}  |  Estado: {job.state}")

            completed = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED"}
            start_time = datetime.now()

            with tqdm(desc="[GeminiModel] Esperando batch temporal", unit="poll", bar_format="{desc}: {elapsed} transcurrido{postfix}") as pbar:
                while job.state not in completed:
                    time.sleep(30)
                    job = self.model.batches.get(name=job.name)
                    pbar.set_postfix_str(f"Estado: {job.state}")
                    pbar.update(1)

                    if (datetime.now() - start_time).total_seconds() > 6 * 3600:
                        self.model.batches.cancel(name=job.name)
                        timeout = True
                        tqdm.write(f"[GeminiModel] Timeout alcanzado. Job cancelado. Se realizaran llamados individuales.")
                        break

            print(f"[GeminiModel] Job finalizado con estado: {job.state}")

            if not timeout:
                print(f"[GeminiModel] Descargando resultados...")
                result_file_name = job.dest.file_name
                file_content_bytes = self.model.files.download(file=result_file_name)
                file_content = file_content_bytes.decode('utf-8')

                results = {}
                for line in file_content.splitlines():
                    if not line.strip():
                        continue
                    result = json.loads(line)
                    article_id = result["key"]
                    try:
                        text = result["response"]["candidates"][0]["content"]["parts"][0]["text"].strip()
                        results[article_id] = text
                    except Exception:
                        results[article_id] = "ERROR"

                print(f"[GeminiModel] Resultados temporales recibidos: {len(results)} articulos")

        if not GEMINI_CONFIG['try_batch'] or timeout:
            print(f"[GeminiModel] Iniciando llamados individuales  ({len(data)} articulos)...")
            results = {}

            for _, article in tqdm(data.iterrows(), total=len(data), desc="[GeminiModel] Clasificando temporal", unit="noticia"):
                prompt = f"**Headline:** {article['title']}\n**Summary:** {article['summary']}"
                label = self.predict(prompt, GEMINI_CONFIG['prompt_futuro'])
                results[str(article['id'])] = label

        return [(results[key], None) for key in sorted(results, key=lambda x: int(x))]

    def build_batch_temporal_file(self, df: pd.DataFrame, output_path=None):
        if output_path is None:
            output_path = ROOT / "inputs" / "gemini_batch_temporal_input.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for _, article in df.iterrows():
                prompt = f"**Headline:** {article['title']}\n**Summary:** {article['summary']}"
                entry = {
                    "key": str(article["id"]),
                    "request": {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "systemInstruction": {"parts": [{"text": GEMINI_CONFIG["prompt_futuro"]}]},
                    }
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"[GeminiModel] Archivo batch temporal escrito: {len(df)} solicitudes en {output_path}")
        return output_path

    def resumen(self, commodity, no_noticias, textos):
        timeout = False

        if GEMINI_CONFIG['try_batch']:
            print(f"[GeminiModel] Construyendo archivo batch para resumen...")
            jsonl_path = self.build_batch_resumen(commodity, no_noticias, textos)

            print(f"[GeminiModel] Subiendo archivo a la API...")
            uploaded_file = self.model.files.upload(file=jsonl_path, config={"mime_type": "application/jsonl"})
            print(f"[GeminiModel] Archivo subido: {uploaded_file.name}")

            job = self.model.batches.create(
                model=f"{GEMINI_CONFIG['model']}",
                src=uploaded_file.name
            )
            print(f"[GeminiModel] Job enviado: {job.name}  |  Estado: {job.state}")

            completed = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED"}
            start_time = datetime.now()

            with tqdm(desc="[GeminiModel] Esperando batch resumen", unit="poll", bar_format="{desc}: {elapsed} transcurrido") as pbar:
                while job.state not in completed:
                    time.sleep(30)
                    job = self.model.batches.get(name=job.name)
                    elapsed = (datetime.now() - start_time).seconds // 60
                    pbar.set_postfix_str(f"estado={job.state}  elapsed={elapsed}m")
                    pbar.update(1)

                    if (datetime.now() - start_time).total_seconds() > 6 * 3600:
                        self.model.batches.cancel(name=job.name)
                        timeout = True
                        tqdm.write(f"[GeminiModel] Timeout alcanzado. Job cancelado. Se realizara llamado individual.")
                        break

            print(f"[GeminiModel] Job finalizado con estado: {job.state}")

            if not timeout:
                print(f"[GeminiModel] Descargando resultado del resumen...")
                result_file_name = job.dest.file_name
                file_content_bytes = self.model.files.download(file=result_file_name)
                file_content = file_content_bytes.decode('utf-8')

                resumen = ""
                for line in file_content.splitlines():
                    if not line.strip():
                        continue
                    result = json.loads(line)
                    try:
                        text = result["response"]["candidates"][0]["content"]["parts"][0]["text"].strip()
                        resumen = text if resumen == "" else resumen + "\n" + text
                    except Exception:
                        resumen = "ERROR"

        if not GEMINI_CONFIG['try_batch'] or timeout:
            print(f"[GeminiModel] Generando resumen via llamado individual...")
            formatted_prompt = (GEMINI_CONFIG["prompt_resumen"]
                                .replace("<COMMODITY>", commodity.upper())
                                .replace("<NO_NOTICIAS>", str(no_noticias)))
            prompt = f"**News Collection to Analyze:** {textos}"
            resumen = self.predict(prompt, formatted_prompt)

        return resumen

    def build_batch_resumen(self, commodity: str, no_noticias: int, textos, output_path=None):
        if output_path is None:
            output_path = ROOT / "inputs" / "gemini_batch_resumen_input.jsonl"
        base_prompt = GEMINI_CONFIG["prompt_resumen"]
        prompt = base_prompt.replace("<COMMODITY>", commodity.upper())
        prompt = prompt.replace("<NO_NOTICIAS>", str(no_noticias))

        with open(output_path, "w", encoding="utf-8") as f:
            prompt2 = f"**News Collection to Analyze:** {textos}"
            entry = {
                "request": {
                    "contents": [{"parts": [{"text": prompt2}]}],
                    "systemInstruction": {"parts": [{"text": prompt}]},
                }
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"[GeminiModel] Archivo batch resumen escrito en {output_path}")
        return output_path
