import random
import os
import io
import sys
import contextlib
import pandas as pd
from tqdm import tqdm
from time import sleep
from bs4 import BeautifulSoup
from  .base_scraper import BaseScraper, NewsArticle
from datetime import datetime, date, timedelta, time
from config import ROOT, GOOGLE_CSS_CONFIG, GOOGLE_TITLE_BLOCKLIST
from urllib.parse import unquote, urlencode, urljoin, quote
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service as EdgeService

import src.utils.date_utils as date_utils

class GoogleScraper(BaseScraper):

    URL_BASE = "https://www.google.com"
    SCRAPPER = "GOOGLE"

    _BLOCK_MARKERS = (
        'id="captcha-form"',
        'g-recaptcha',
        'solveSimpleChallenge',
        'data-sitekey="6LdLLIMbAAAAAIl-KLj9p1ePhM-4LCCDbjtJLqRO"',
    )

    _BLOCK_TEXTS = (
        "unusual traffic",
        "tráfico inusual",
        "trafico inusual",  # por si el HTML viene sin acentos
    )

    def __init__(self, commodity):
        super().__init__(commodity, self.SCRAPPER)

    def fetch(self):
        driver = None
        #retries = 5
        try:
            start = self.commodity["start_date"]
            end = self.commodity["end_date"]
            query_number = len(self.commodity["search_query"])
            news_number = self.commodity["news_number"]
            total_days = (end - start).days + 1

            # Count articles already saved per day to avoid over-fetching on reruns
            raw_path = self.commodity["raw_path"] / "noticias.xlsx"
            existing_per_day: dict[str, int] = {}
            if raw_path.exists():
                _existing = pd.read_excel(raw_path)
                _existing["published_date"] = pd.to_datetime(_existing["published_date"]).dt.strftime("%Y-%m-%d")
                existing_per_day = _existing.groupby("published_date").size().to_dict()

            days = [start + timedelta(days=i) for i in range(total_days)]

            total_noticias = query_number * news_number * len(days)
            day_total_target = news_number * query_number

            print(f"[GoogleScraper] Commodity  : {self.commodity['name']}")
            print(f"[GoogleScraper] Periodo    : {start} -> {end}  ({total_days} dias)")
            print(f"[GoogleScraper] Query Number      : {query_number}")
            print(f"[GoogleScraper] Noticias   : {news_number}/query/dia  ({total_noticias} pendientes)")

            driver = self._create_driver()
            #self._warm_up(driver)
            #sleep(random.uniform(5, 12))

            with tqdm(total=total_noticias, desc=f"Google News - {self.commodity['name'].upper()}", unit="noticia") as pbar:
                for query in self.commodity["search_query"]:
                    d = start
                    while d <= end:
                        date_key = d.strftime("%Y-%m-%d")
                        tqdm.write(f"[GoogleScraper] Obteniendo noticias {date_key}.")
                        already_have = existing_per_day.get(date_key, 0)
                        if already_have >= day_total_target:
                            tqdm.write(f"[GoogleScraper] {date_key}: ya tiene {already_have} noticias, se omite.")
                            d += timedelta(days=1)
                            continue

                        remaining = news_number

                        page_index = 0
                        articulos_dia: list[NewsArticle] = []

                        while len(articulos_dia) < remaining:
                            date_str = d.strftime("%m/%d/%Y")
                            soup, blocked = self.selenium_request(driver, query, date_str, page_index)
                            
                            cards = soup.find_all('div', class_=GOOGLE_CSS_CONFIG["noticias"])

                            # if blocked:
                            #     for attempt in range(retries):
                            #         tqdm.write(f"[GoogleScraper] Bot detected retry {attempt + 1} of {retries}.")
                            #         driver.quit()
                            #         wait = (2 ** attempt) * 60 + random.uniform(0, 30)
                            #         sleep(wait)
                            #         driver = self._create_driver()

                            #         soup, blocked = self.selenium_request(driver, query, date_str, page_index)
                            #         cards = soup.find_all('div', class_=GOOGLE_CSS_CONFIG["noticias"])

                            #         if not blocked:
                            #             break
                            
                            if not cards:
                                now = datetime.now().strftime("%Y-%m-%dT%H%M%S")
                                filename = ROOT / "log" / "debug" / f"html_google_news_{now}.html"
                                filename.parent.mkdir(parents=True, exist_ok=True)

                                no_results = soup.find('div', class_=GOOGLE_CSS_CONFIG["no_results"])
                                
                                if no_results:
                                    texto = no_results.find("p")
                                    if texto and "No se han encontrado noticias para tu busqueda (" in texto.get_text():
                                        tqdm.write(f"[GoogleScraper] Sin resultados para {d.strftime('%Y-%m-%d')} - {query}")
                                        break

                                if not blocked:
                                    with open(filename, "w", encoding='utf-8') as f:
                                        f.write(str(soup))

                                    tqdm.write(f"[GoogleScraper] HTML de depuracion guardado en {filename}")
                                    break

                                if blocked:
                                    tqdm.write(f"[GoogleScraper] Bot detected.")
                                
                                

                            i = 0
                            while i < len(cards) - 1 and len(articulos_dia) < remaining:
                                articulo = self.parse(cards[i], d.strftime("%Y-%m-%d"))
                                if articulo:
                                    articulos_dia.append(articulo)
                                    pbar.update(1)
                                i += 1

                            sleep(random.uniform(3, 6))
                            page_index += 1

                        self.articles.extend(articulos_dia[:remaining])
                        d += timedelta(days=1)

                self.save()

            print(f"[GoogleScraper] Extraccion completada - {self.commodity['name'].upper()}  ({len(self.articles)} noticias guardadas)")
            driver.quit()

        except Exception as e:
            if len(self.articles) > 0:
                tqdm.write(f"[GoogleScraper] Error durante extraccion. Guardando {len(self.articles)} noticias obtenidas...")
                self.save()
            raise Exception(f"[GoogleScraper] Error en scraping: {str(e)}")

        finally:
            if driver is not None:
                driver.quit()

    def _create_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--lang=es-ES")
        options.add_argument("--window-size=1920,1080")
        
        profile_dir = ROOT / "log" / "edge_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        #options.add_argument(f"--user-data-dir={profile_dir}")

        options.add_experimental_option("excludeSwitches", ['enable-logging', "enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        service = EdgeService(log_path=open(os.devnull, 'w'), log_output=open(os.devnull, 'w'))
        driver = webdriver.Edge(options=options, service=service)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def _warm_up(self, driver):
        """Visita Google de forma 'inocente' antes de las queries agresivas."""
        try:
            tqdm.write("[GoogleScraper] Warm-up: estableciendo sesion...")
            driver.get("https://www.google.com")
            sleep(random.uniform(3, 6))

            # Una búsqueda normal, sin tbm=nws ni operadores ni rango de fechas
            driver.get("https://www.google.com/search?q=noticias+colombia")
            sleep(random.uniform(4, 8))
        except Exception as e:
            # El warm-up es best-effort: si falla, no abortamos la corrida
            tqdm.write(f"[GoogleScraper] Warm-up fallido (se continua igual): {e}")

    def selenium_request(self, driver, query, date, index):
        try:
            query_encoded = query.replace(" ", "+")
            url = (f"https://www.google.com/search?q={query_encoded}"
                   f"&tbm=nws&tbs=cdr:1,cd_min:{date},cd_max:{date}&start={index}")
            driver.get(url)
            sleep(2)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            return soup, self._is_blocked(driver, soup)
        
        except Exception as e:
            raise Exception(f"[GoogleScraper] Error en la peticion: {str(e)}")

    def parse(self, raw_data, date) -> NewsArticle:
        card = raw_data

        titulo_elem = card.find('div', class_=GOOGLE_CSS_CONFIG["titulo"])
        titulo_texto = titulo_elem.get_text(strip=True) if titulo_elem else "Titulo no encontrado"

        if titulo_texto.strip().lower() in GOOGLE_TITLE_BLOCKLIST:
            return None

        fuente_elem = card.find('div', class_=GOOGLE_CSS_CONFIG["fuente"])
        fuente_texto = fuente_elem.get_text(strip=True) if fuente_elem else "Fuente no encontrada"

        a_tag = card.find_parent('a', href=True)
        #a_tag = card.find('a', href=True)
        enlace_texto = "No encontro enlace."
        if a_tag:
            href = a_tag.get('href', '')
            if href.startswith('/url?q='):
                try:
                    enlace_texto = unquote(href.split('/url?q=')[1].split('&')[0])
                except Exception:
                    enlace_texto = href
            else:
                enlace_texto = href

        resumen_elem = card.find('div', class_=GOOGLE_CSS_CONFIG["resumen"])
        resumen_texto = resumen_elem.get_text(strip=True) if resumen_elem else "Resumen no encontrado"

        tiempo = date

        if titulo_texto != "Titulo no encontrado":
            return NewsArticle(
                title=titulo_texto,
                source=fuente_texto,
                summary=resumen_texto,
                commodity=self.commodity["name"],
                published_date=tiempo,
                link=enlace_texto
            )
        return None
    
    def _is_blocked(self, driver, soup) -> bool:
        if "/sorry/" in (driver.current_url or ""):
            return True
        
        if soup.find("form", id="captcha-form") is not None:
            return True
        if soup.find("div", class_="g-recaptcha") is not None:
            return True
       
        html = str(soup).lower()
        if any(m.lower() in html for m in GoogleScraper._BLOCK_MARKERS):
            return True
        if any(t in html for t in GoogleScraper._BLOCK_TEXTS):
            return True
        return False
