"""Breakout strategy: enter after a tight consolidation breaks with volume."""
from typing import Optional

import pandas as pd

from strategies.base_strategy import BaseStrategy, Signal, SignalType


class BreakoutStrategy(BaseStrategy):
    """
    Entry conditions:
      - Price breaks above the 20-bar Donchian high
      - Recent consolidation: range < range_max_pct over the last consolidation_bars
      - Volume on breakout bar > vol_confirm * 20-day avg
      - MACD histogram positive (momentum agrees)
    """

    def __init__(self, config: dict):
        super().__init__("breakout", config)
        self.consolidation_bars = config.get("consolidation_bars", 10)
        self.range_max_pct = config.get("range_max_pct", 3.0)
        self.vol_confirm = config.get("volume_confirm", 2.0)
        self.atr_multiplier = config.get("atr_multiplier", 1.0)

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        if len(df) < max(self._min_bars_required(), self.consolidation_bars + 5):
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        recent = df.iloc[-(self.consolidation_bars + 1):-1]

        # Price breaks above the prior 20-bar high on this bar
        breakout = (prev["Close"] <= prev["dc_high_20"]) and (latest["Close"] > prev["dc_high_20"])
        if not breakout:
            return None

        # Measure consolidation range of the prior N bars
        consolidation_high = recent["High"].max()
        consolidation_low = recent["Low"].min()
        range_pct = (consolidation_high - consolidation_low) / consolidation_low * 100
        if range_pct > self.range_max_pct:
            return None

        # Volume confirmation
        if latest["vol_ratio"] < self.vol_confirm:
            return None

        # MACD confirms upward momentum
        if latest["macd_hist"] <= 0:
            return None

        entry = latest["Close"]
        atr = latest["atr"]
        stop_loss = consolidation_low - atr * self.atr_multiplier
        take_profit = entry + (entry - stop_loss) * 3.0     # 3:1 R/R

        confidence = self._calc_confidence(latest, range_pct)

        return Signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            strategy=self.name,
            confidence=confidence,
            entry_price=round(entry, 4),
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            reason=(
                f"Donchian breakout | Range={range_pct:.1f}% | "
                f"VolRatio={latest['vol_ratio']:.2f} | MACD_hist={latest['macd_hist']:.3f}"
            ),
        )

    def _calc_confidence(self, row: pd.Series, range_pct: float) -> float:
        score = 0.0
        # Tighter consolidation = stronger breakout
        score += max(0, (self.range_max_pct - range_pct) / self.range_max_pct * 0.4)
        # Volume surge
        score += min((row["vol_ratio"] - self.vol_confirm) / 4, 0.35)
        # MACD histogram magnitude
        score += min(row["macd_hist"] / (row["Close"] * 0.01), 0.25)
        return min(round(score, 2), 1.0)
