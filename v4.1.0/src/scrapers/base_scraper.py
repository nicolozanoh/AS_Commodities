import src.utils.file_utils as file_utils
import os
import pandas as pd
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class NewsArticle:
    title: str
    source: str
    commodity: str
    published_date: datetime
    link: str
    summary: str

class BaseScraper(ABC):

    def __init__(self, commodity: dict, scr: str):
        self.commodity = commodity
        self.articles: list[NewsArticle] = []
        self.SCRAPPER = scr

    @abstractmethod
    def fetch(self):
        """Cada web scraper implementa este metodo para buscar las noticias."""

    @abstractmethod
    def parse(self, raw_data) -> NewsArticle:
        """Transforma la data de la web en articulos estandarizados."""

    def save(self):
        """Guarda los articulos en formato excel."""
        path: Path = self.commodity["raw_path"] / "noticias.xlsx"

        file_exists = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)

        new_articles = pd.DataFrame([asdict(x) for x in self.articles])
        new_articles["buscador"] = self.SCRAPPER
        new_articles["processed"] = 0

        if file_exists:
            existing_articles = pd.read_excel(path)
            articles = pd.concat([existing_articles, new_articles], ignore_index=True)
        else:
            articles = new_articles

        # Normalize published_date to a consistent string format before dedup so
        # that datetime objects (from Excel reads) and strings (freshly scraped)
        # are treated as equal when they represent the same date.
        articles["published_date"] = pd.to_datetime(articles["published_date"]).dt.strftime("%Y-%m-%d")
        articles.drop_duplicates(subset=["title", "published_date"], inplace=True)

        articles.to_excel(path, index=False)
