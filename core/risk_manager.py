"""Risk manager: position sizing, exposure limits, and circuit breakers."""
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from config.settings import (
    DAILY_LOSS_LIMIT_PCT,
    MAX_MONTHLY_DRAWDOWN_PCT,
    MAX_OPEN_POSITIONS,
    MAX_POSITION_SIZE_PCT,
    RISK_PER_TRADE_PCT,
)
from strategies.base_strategy import Signal

logger = logging.getLogger(__name__)


@dataclass
class RiskCheck:
    approved: bool
    reason: str
    position_size: float = 0.0    # number of shares
    dollar_risk: float = 0.0


class RiskManager:
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self._daily_pnl: Dict[date, float] = {}
        self._monthly_peak: float = initial_capital
        self._halted_today: bool = False
        self._trading_halted: bool = False

    def evaluate(
        self,
        signal: Signal,
        portfolio_value: float,
        open_positions: List[str],
    ) -> RiskCheck:
        if self._trading_halted:
            return RiskCheck(False, "Trading halted — monthly drawdown limit hit")

        if self._halted_today:
            return RiskCheck(False, "Trading halted for today — daily loss limit hit")

        # Max open positions
        if signal.symbol not in open_positions and len(open_positions) >= MAX_OPEN_POSITIONS:
            return RiskCheck(False, f"Max open positions ({MAX_OPEN_POSITIONS}) reached")

        # Already have a position in this symbol
        if signal.symbol in open_positions:
            return RiskCheck(False, f"Already holding {signal.symbol}")

        # Position size by fixed-fractional risk
        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        if risk_per_share <= 0:
            return RiskCheck(False, "Invalid stop loss — no risk defined")

        dollar_risk = portfolio_value * (RISK_PER_TRADE_PCT / 100)
        shares = int(dollar_risk / risk_per_share)
        if shares < 1:
            return RiskCheck(False, "Position too small — insufficient capital")

        position_value = shares * signal.entry_price
        max_position_value = portfolio_value * (MAX_POSITION_SIZE_PCT / 100)
        if position_value > max_position_value:
            shares = int(max_position_value / signal.entry_price)
            position_value = shares * signal.entry_price

        if shares < 1:
            return RiskCheck(False, "Position too small after max-size cap")

        # Require minimum R/R ratio
        if signal.risk_reward < 1.5:
            return RiskCheck(False, f"R/R {signal.risk_reward:.2f} below 1.5 minimum")

        # Minimum confidence
        if signal.confidence < 0.15:
            return RiskCheck(False, f"Confidence {signal.confidence:.2f} too low")

        logger.info(
            "APPROVED %s: %d shares @ $%.2f | risk=$%.2f | R/R=%.2f",
            signal.symbol, shares, signal.entry_price, dollar_risk, signal.risk_reward,
        )
        return RiskCheck(True, "Approved", position_size=float(shares), dollar_risk=dollar_risk)

    def record_pnl(self, pnl: float, portfolio_value: float):
        today = date.today()
        self._daily_pnl[today] = self._daily_pnl.get(today, 0.0) + pnl

        # Update monthly peak
        if portfolio_value > self._monthly_peak:
            self._monthly_peak = portfolio_value

        # Daily circuit breaker
        daily_loss_pct = (self._daily_pnl[today] / portfolio_value) * 100
        if daily_loss_pct < -DAILY_LOSS_LIMIT_PCT:
            self._halted_today = True
            logger.warning("Daily loss limit hit (%.2f%%). Halting today.", daily_loss_pct)

        # Monthly drawdown circuit breaker
        drawdown_pct = (self._monthly_peak - portfolio_value) / self._monthly_peak * 100
        if drawdown_pct > MAX_MONTHLY_DRAWDOWN_PCT:
            self._trading_halted = True
            logger.critical(
                "Monthly drawdown limit hit (%.2f%%). All trading halted.", drawdown_pct
            )

    def reset_daily(self):
        self._halted_today = False

    def reset_monthly(self, new_peak: float):
        self._trading_halted = False
        self._monthly_peak = new_peak
        self._daily_pnl.clear()

    @property
    def is_halted(self) -> bool:
        return self._trading_halted or self._halted_today
