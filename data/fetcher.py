"""Market data fetcher using yfinance."""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from config.settings import DATA_INTERVAL, LOOKBACK_DAYS

logger = logging.getLogger(__name__)


class DataFetcher:
    def __init__(self):
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl_minutes = 60

    def fetch(self, symbol: str, days: int = LOOKBACK_DAYS, interval: str = DATA_INTERVAL) -> Optional[pd.DataFrame]:
        cache_key = f"{symbol}_{interval}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            end = datetime.now()
            start = end - timedelta(days=days + 30)  # buffer for weekends/holidays
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=interval)
            if df.empty:
                logger.warning("No data returned for %s", symbol)
                return None
            df.index = pd.to_datetime(df.index)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df = df.tail(days)
            self._cache[cache_key] = df
            self._cache_time[cache_key] = datetime.now()
            logger.info("Fetched %d bars for %s", len(df), symbol)
            return df
        except Exception as e:
            logger.error("Failed to fetch %s: %s", symbol, e)
            return None

    def fetch_multiple(self, symbols: List[str], days: int = LOOKBACK_DAYS) -> Dict[str, pd.DataFrame]:
        results = {}
        for symbol in symbols:
            data = self.fetch(symbol, days)
            if data is not None:
                results[symbol] = data
        return results

    def _is_cached(self, key: str) -> bool:
        if key not in self._cache:
            return False
        age = (datetime.now() - self._cache_time[key]).total_seconds() / 60
        return age < self._cache_ttl_minutes

    def clear_cache(self):
        self._cache.clear()
        self._cache_time.clear()
