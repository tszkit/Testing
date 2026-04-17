"""Momentum strategy: ride trending stocks with EMA cross + ADX + RSI filter."""
from typing import Optional

import pandas as pd

from config.settings import DEFAULT_STOP_LOSS_PCT, DEFAULT_TAKE_PROFIT_PCT
from strategies.base_strategy import BaseStrategy, Signal, SignalType


class MomentumStrategy(BaseStrategy):
    """
    Entry conditions (all must be true):
      - EMA(9) crosses above EMA(21)
      - Price above SMA(50)  — confirms uptrend
      - ADX > threshold      — trend is strong
      - RSI in [min, max]    — not overbought yet
      - Volume > vol_surge * 20-day avg
    """

    def __init__(self, config: dict):
        super().__init__("momentum", config)
        self.lookback = config.get("lookback", 20)
        self.min_adx = config.get("min_adx", 25)
        self.rsi_min = config.get("rsi_min", 45)
        self.rsi_max = config.get("rsi_max", 65)
        self.volume_surge = config.get("volume_surge", 1.5)

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        if len(df) < self._min_bars_required():
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # EMA crossover (fast crosses above slow on this bar)
        ema_cross = (prev["ema_fast"] <= prev["ema_slow"]) and (latest["ema_fast"] > latest["ema_slow"])
        if not ema_cross:
            return None

        # Trend filter
        if latest["Close"] < latest["sma_50"]:
            return None

        # ADX confirms trend strength
        if latest["adx"] < self.min_adx:
            return None

        # RSI filter — momentum but not overheated
        if not (self.rsi_min <= latest["rsi"] <= self.rsi_max):
            return None

        # Volume confirmation
        if latest["vol_ratio"] < self.volume_surge:
            return None

        entry = latest["Close"]
        atr = latest["atr"]
        stop_loss = entry - 1.5 * atr
        take_profit = entry + 4.5 * atr          # 3:1 R/R

        # Dynamic stop ensures we never risk more than the default %
        max_stop = entry * (1 - DEFAULT_STOP_LOSS_PCT / 100)
        stop_loss = max(stop_loss, max_stop)

        min_tp = entry * (1 + DEFAULT_TAKE_PROFIT_PCT / 100)
        take_profit = max(take_profit, min_tp)

        confidence = self._calc_confidence(latest)

        return Signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            strategy=self.name,
            confidence=confidence,
            entry_price=entry,
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            reason=f"EMA cross up | ADX={latest['adx']:.1f} | RSI={latest['rsi']:.1f} | VolRatio={latest['vol_ratio']:.2f}",
        )

    def _calc_confidence(self, row: pd.Series) -> float:
        score = 0.0
        # ADX strength
        score += min((row["adx"] - self.min_adx) / 20, 0.3)
        # RSI sweet spot (around 55)
        score += max(0, 0.2 - abs(row["rsi"] - 55) / 100)
        # Volume surge
        score += min((row["vol_ratio"] - self.volume_surge) / 4, 0.25)
        # ROC
        if row["roc_5"] > 0:
            score += min(row["roc_5"] / 20, 0.25)
        return min(round(score, 2), 1.0)
