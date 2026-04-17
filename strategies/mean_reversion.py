"""Mean reversion strategy: buy oversold dips in sideways/weak-trend markets."""
from typing import Optional

import pandas as pd

from strategies.base_strategy import BaseStrategy, Signal, SignalType


class MeanReversionStrategy(BaseStrategy):
    """
    Entry conditions:
      - Price touches/breaks below lower Bollinger Band
      - RSI < oversold threshold
      - ADX < max_adx (not a strong trend — avoid catching a falling knife)
      - Previous bar closed inside the band (first touch, not continuation)
    """

    def __init__(self, config: dict):
        super().__init__("mean_reversion", config)
        self.rsi_oversold = config.get("rsi_oversold", 30)
        self.rsi_overbought = config.get("rsi_overbought", 70)
        self.max_adx = config.get("max_adx", 30)
        self.min_reversion_pct = config.get("min_reversion_pct", 0.5)

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        if len(df) < self._min_bars_required():
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Only trade mean reversion in low-trend environments
        if latest["adx"] > self.max_adx:
            return None

        # Price broke below lower BB (first touch)
        below_band = latest["Close"] < latest["bb_lower"]
        prev_inside = prev["Close"] >= prev["bb_lower"]
        if not (below_band and prev_inside):
            return None

        # RSI confirms oversold
        if latest["rsi"] > self.rsi_oversold:
            return None

        # Ensure meaningful deviation
        deviation_pct = (latest["bb_lower"] - latest["Close"]) / latest["bb_lower"] * 100
        if deviation_pct < self.min_reversion_pct:
            return None

        entry = latest["Close"]
        target = latest["bb_mid"]          # mean is the first target
        risk = entry - (entry - latest["atr"] * 1.5)
        stop_loss = entry - latest["atr"] * 1.5
        take_profit = target

        # Require at least 1.5:1 R/R
        if (take_profit - entry) < 1.5 * (entry - stop_loss):
            take_profit = entry + 1.5 * (entry - stop_loss)

        confidence = self._calc_confidence(latest)

        return Signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            strategy=self.name,
            confidence=confidence,
            entry_price=round(entry, 4),
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            reason=f"BB lower touch | RSI={latest['rsi']:.1f} | ADX={latest['adx']:.1f} | Dev={deviation_pct:.2f}%",
        )

    def _calc_confidence(self, row: pd.Series) -> float:
        score = 0.0
        # Lower RSI = more oversold = higher confidence
        score += max(0, (self.rsi_oversold - row["rsi"]) / self.rsi_oversold * 0.5)
        # Lower ADX = cleaner range
        score += max(0, (self.max_adx - row["adx"]) / self.max_adx * 0.3)
        # BB percent (how far outside)
        score += min(max(0, -row["bb_pct"]) * 0.2, 0.2)
        return min(round(score, 2), 1.0)
