"""Abstract base class for all trading strategies."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    symbol: str
    signal_type: SignalType
    strategy: str
    confidence: float           # 0.0 – 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return reward / risk if risk > 0 else 0.0


class BaseStrategy(ABC):
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[Signal]:
        """Analyse the latest bar and return a Signal or None."""
        ...

    def _min_bars_required(self) -> int:
        return 50
