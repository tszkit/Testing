"""Portfolio tracker: positions, cash, P&L, and trade history."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import COMMISSION_PCT, TRAILING_STOP_PCT

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    entry_price: float
    shares: float
    stop_loss: float
    take_profit: float
    strategy: str
    opened_at: datetime = field(default_factory=datetime.now)
    highest_price: float = 0.0
    trailing_stop: Optional[float] = None

    def __post_init__(self):
        self.highest_price = self.entry_price

    @property
    def cost_basis(self) -> float:
        return self.entry_price * self.shares

    def current_value(self, price: float) -> float:
        return price * self.shares

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.entry_price) * self.shares

    def unrealized_pnl_pct(self, price: float) -> float:
        return (price - self.entry_price) / self.entry_price * 100

    def update_trailing_stop(self, current_price: float):
        """Activate and ratchet trailing stop once position is profitable enough."""
        if current_price > self.highest_price:
            self.highest_price = current_price

        profit_pct = (self.highest_price - self.entry_price) / self.entry_price * 100
        if profit_pct >= 3.0:
            new_trailing = self.highest_price * (1 - TRAILING_STOP_PCT / 100)
            if self.trailing_stop is None or new_trailing > self.trailing_stop:
                self.trailing_stop = new_trailing

    def should_exit(self, current_price: float) -> tuple[bool, str]:
        self.update_trailing_stop(current_price)

        if current_price <= self.stop_loss:
            return True, "stop_loss"
        if self.trailing_stop and current_price <= self.trailing_stop:
            return True, "trailing_stop"
        if current_price >= self.take_profit:
            return True, "take_profit"
        return False, ""


@dataclass
class Trade:
    symbol: str
    entry_price: float
    exit_price: float
    shares: float
    strategy: str
    exit_reason: str
    opened_at: datetime
    closed_at: datetime = field(default_factory=datetime.now)

    @property
    def pnl(self) -> float:
        gross = (self.exit_price - self.entry_price) * self.shares
        commission = (self.entry_price + self.exit_price) * self.shares * (COMMISSION_PCT / 100)
        return gross - commission

    @property
    def pnl_pct(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price * 100

    @property
    def duration_days(self) -> int:
        return (self.closed_at - self.opened_at).days


class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []

    @property
    def equity(self) -> float:
        """Cash + market value of all positions (uses last known prices)."""
        return self.cash + sum(
            p.current_value(p.highest_price) for p in self.positions.values()
        )

    def equity_at_prices(self, prices: Dict[str, float]) -> float:
        pos_value = sum(
            p.current_value(prices.get(sym, p.entry_price))
            for sym, p in self.positions.items()
        )
        return self.cash + pos_value

    def open_position(self, symbol: str, shares: float, price: float, stop: float, tp: float, strategy: str) -> bool:
        cost = price * shares * (1 + COMMISSION_PCT / 100)
        if cost > self.cash:
            logger.warning("Insufficient cash to open %s (need $%.2f, have $%.2f)", symbol, cost, self.cash)
            return False
        self.cash -= cost
        self.positions[symbol] = Position(
            symbol=symbol, entry_price=price, shares=shares,
            stop_loss=stop, take_profit=tp, strategy=strategy,
        )
        logger.info("OPEN  %s | %g shares @ $%.2f | stop=$%.2f | tp=$%.2f", symbol, shares, price, stop, tp)
        return True

    def close_position(self, symbol: str, price: float, reason: str) -> Optional[Trade]:
        if symbol not in self.positions:
            return None
        pos = self.positions.pop(symbol)
        proceeds = price * pos.shares * (1 - COMMISSION_PCT / 100)
        self.cash += proceeds
        trade = Trade(
            symbol=symbol, entry_price=pos.entry_price, exit_price=price,
            shares=pos.shares, strategy=pos.strategy, exit_reason=reason,
            opened_at=pos.opened_at,
        )
        self.trade_history.append(trade)
        logger.info(
            "CLOSE %s @ $%.2f (%s) | PnL=$%.2f (%.2f%%)",
            symbol, price, reason, trade.pnl, trade.pnl_pct,
        )
        return trade

    def update_positions(self, prices: Dict[str, float]) -> List[Trade]:
        """Check exit conditions for all open positions; close if triggered."""
        closed = []
        for symbol, pos in list(self.positions.items()):
            price = prices.get(symbol)
            if price is None:
                continue
            should_exit, reason = pos.should_exit(price)
            if should_exit:
                trade = self.close_position(symbol, price, reason)
                if trade:
                    closed.append(trade)
        return closed

    def summary(self, prices: Optional[Dict[str, float]] = None) -> dict:
        equity = self.equity_at_prices(prices) if prices else self.equity
        total_pnl = equity - self.initial_capital
        wins = [t for t in self.trade_history if t.pnl > 0]
        losses = [t for t in self.trade_history if t.pnl <= 0]
        win_rate = len(wins) / len(self.trade_history) * 100 if self.trade_history else 0

        return {
            "equity": round(equity, 2),
            "cash": round(self.cash, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / self.initial_capital * 100, 2),
            "open_positions": len(self.positions),
            "total_trades": len(self.trade_history),
            "win_rate": round(win_rate, 1),
            "avg_win": round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0,
        }
