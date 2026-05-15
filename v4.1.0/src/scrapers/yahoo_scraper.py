import pandas as pd
import yfinance as yf
from pathlib import Path
from .base_scraper import BaseScraper, NewsArticle
from datetime import datetime


class YahooScraper(BaseScraper):
    SCRAPPER = "YAHOO"

    def __init__(self, commodity):
        super().__init__(commodity, self.SCRAPPER)

    # ------------------------------------------------------------------
    # BaseScraper interface
    # ------------------------------------------------------------------

    def fetch(self):
        """Fetches close prices and analyst sentiment for the commodity."""
        ticker_symbol = self.commodity.get("ticker", "")
        if not ticker_symbol:
            print(f"[YahooScraper] No ticker configured for '{self.commodity['name']}', skipping.")
            return

        print(f"\n[YahooScraper] Fetching data for {self.commodity['name']} ({ticker_symbol})")

        prices_df = self.get_close_prices()
        if prices_df is not None and not prices_df.empty:
            self._save(prices_df, "precios.xlsx")
            print(f"[YahooScraper] Close prices saved  ({len(prices_df)} rows)")
        else:
            print(f"[YahooScraper] No price data available for {ticker_symbol}")

        sentiment_df = self.get_analyst_sentiment()
        if sentiment_df is not None and not sentiment_df.empty:
            self._save(sentiment_df, "analisis_analistas.xlsx")
            print(f"[YahooScraper] Analyst sentiment saved  ({len(sentiment_df)} rows)")
        else:
            print(f"[YahooScraper] No analyst sentiment data available for {ticker_symbol}")

    def parse(self, raw_data) -> NewsArticle:
        raise NotImplementedError("YahooScraper.parse() is not applicable for financial data.")

    # ------------------------------------------------------------------
    # Public data methods
    # ------------------------------------------------------------------

    def get_close_prices(self) -> pd.DataFrame | None:
        """
        Returns daily OHLCV data for the commodity over the configured date range.

        Columns: date, open, high, low, close, volume, commodity, ticker
        """
        ticker_symbol = self.commodity.get("ticker", "")
        if not ticker_symbol:
            return None

        try:
            ticker = yf.Ticker(ticker_symbol)
            raw = ticker.history(
                start=self.commodity["start_date"],
                end=self.commodity["end_date"],
                auto_adjust=True
            )

            if raw.empty:
                return None

            df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
            df = df.reset_index()
            df.columns = ["date", "open", "high", "low", "close", "volume"]

            # Strip timezone so Excel serialisation doesn't fail
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.date

            df["commodity"] = self.commodity["name"]
            df["ticker"] = ticker_symbol

            return df.sort_values("date").reset_index(drop=True)

        except Exception as e:
            print(f"[YahooScraper] Error fetching close prices for {ticker_symbol}: {e}")
            return None

    def get_analyst_sentiment(self) -> pd.DataFrame | None:
        """
        Returns analyst recommendations for the commodity ticker.

        For equity-based tickers this produces a period-level summary with columns:
            period, strongBuy, buy, hold, sell, strongSell, commodity, ticker

        For commodity futures (e.g. KC=F, BZ=F) Yahoo Finance does not publish
        analyst ratings, so this will return None.
        """
        ticker_symbol = self.commodity.get("ticker", "")
        if not ticker_symbol:
            return None

        try:
            ticker = yf.Ticker(ticker_symbol)

            # --- Option 1: aggregated period summary (most common for equities) ---
            recs = ticker.recommendations_summary
            if recs is not None and not recs.empty:
                df = recs.copy()
                df["commodity"] = self.commodity["name"]
                df["ticker"] = ticker_symbol
                return df

            # --- Option 2: individual analyst upgrades / downgrades ---
            upgrades = ticker.upgrades_downgrades
            if upgrades is not None and not upgrades.empty:
                df = upgrades.reset_index()
                # Filter to configured date window when a date column is present
                date_col = next((c for c in df.columns if "date" in c.lower()), None)
                if date_col:
                    df[date_col] = pd.to_datetime(df[date_col]).dt.tz_localize(None)
                    start = pd.Timestamp(self.commodity["start_date"])
                    end = pd.Timestamp(self.commodity["end_date"])
                    df = df[(df[date_col] >= start) & (df[date_col] <= end)]
                df["commodity"] = self.commodity["name"]
                df["ticker"] = ticker_symbol
                return df if not df.empty else None

            return None

        except Exception as e:
            print(f"[YahooScraper] Error fetching analyst sentiment for {ticker_symbol}: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self, df: pd.DataFrame, filename: str):
        """Saves a DataFrame to the commodity's raw_path as Excel."""
        path = Path(self.commodity["raw_path"])
        path.mkdir(parents=True, exist_ok=True)
        output = path / filename
        df.to_excel(output, index=False)
