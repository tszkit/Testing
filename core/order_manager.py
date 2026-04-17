"""Order manager: simulates paper fills or routes live orders."""
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from config.settings import TRADING_MODE

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    symbol: str
    shares: float
    order_type: str          # "BUY" | "SELL"
    limit_price: Optional[float]
    stop_loss: float
    take_profit: float
    strategy: str
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class OrderManager:
    def __init__(self):
        self.pending_orders: list[Order] = []

    def submit_buy(
        self,
        symbol: str,
        shares: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        strategy: str,
    ) -> Order:
        order = Order(
            symbol=symbol,
            shares=shares,
            order_type="BUY",
            limit_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
        )

        if TRADING_MODE == "paper":
            order.status = OrderStatus.FILLED
            order.fill_price = entry_price
            logger.info(
                "[PAPER] BUY %g %s @ $%.4f | stop=$%.4f | tp=$%.4f",
                shares, symbol, entry_price, stop_loss, take_profit,
            )
        elif TRADING_MODE == "live":
            # Placeholder: integrate broker SDK here (e.g. Alpaca, IBKR)
            raise NotImplementedError("Live order routing not yet configured. Set TRADING_MODE=paper.")
        else:
            logger.info("[BACKTEST] BUY %g %s @ $%.4f", shares, symbol, entry_price)
            order.status = OrderStatus.FILLED
            order.fill_price = entry_price

        return order

    def submit_sell(self, symbol: str, shares: float, exit_price: float, reason: str) -> Order:
        order = Order(
            symbol=symbol,
            shares=shares,
            order_type="SELL",
            limit_price=exit_price,
            stop_loss=0.0,
            take_profit=0.0,
            strategy=reason,
        )

        if TRADING_MODE in ("paper", "backtest"):
            order.status = OrderStatus.FILLED
            order.fill_price = exit_price
            logger.info("[%s] SELL %g %s @ $%.4f (%s)", TRADING_MODE.upper(), shares, symbol, exit_price, reason)
        elif TRADING_MODE == "live":
            raise NotImplementedError("Live order routing not yet configured.")

        return order
