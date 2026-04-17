"""Backtesting engine: simulate strategies on historical data."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Type

import pandas as pd
import numpy as np

from config.settings import COMMISSION_PCT, INITIAL_CAPITAL
from core.portfolio import Portfolio, Trade
from core.risk_manager import RiskManager
from data.fetcher import DataFetcher
from data.processor import add_indicators
from strategies.base_strategy import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    total_pnl_pct: float
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trades: List[Trade] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            k: v for k, v in self.__dict__.items() if k != "trades"
        }

    def __str__(self) -> str:
        return (
            f"\n{'='*55}\n"
            f"  Backtest: {self.strategy_name} | {self.symbol}\n"
            f"  Period  : {self.start_date} → {self.end_date}\n"
            f"{'='*55}\n"
            f"  Capital : ${self.initial_capital:,.2f} → ${self.final_equity:,.2f}\n"
            f"  PnL     : ${self.total_pnl:+,.2f}  ({self.total_pnl_pct:+.2f}%)\n"
            f"  Trades  : {self.total_trades}  |  Win Rate: {self.win_rate:.1f}%\n"
            f"  Avg Win : {self.avg_win_pct:+.2f}%  |  Avg Loss: {self.avg_loss_pct:+.2f}%\n"
            f"  PF      : {self.profit_factor:.2f}  |  MaxDD: {self.max_drawdown_pct:.2f}%\n"
            f"  Sharpe  : {self.sharpe_ratio:.2f}\n"
            f"{'='*55}"
        )


class BacktestEngine:
    """
    Single-symbol backtester.  Walks through bars one at a time,
    generates signals at bar close, and fills at next bar's open.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float = INITIAL_CAPITAL,
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital

    def run(self, symbol: str, df: pd.DataFrame) -> Optional[BacktestResult]:
        df = add_indicators(df)
        if len(df) < 60:
            logger.warning("Not enough bars to backtest %s", symbol)
            return None

        capital = self.initial_capital
        cash = capital
        position_shares = 0.0
        entry_price = 0.0
        stop_loss = 0.0
        take_profit = 0.0
        entry_date = None
        highest_price = 0.0
        trailing_stop = None

        trades: List[dict] = []
        equity_curve: List[float] = []
        TRAIL_ACTIVATE_PCT = 3.0
        TRAIL_PCT = 1.5

        for i in range(50, len(df)):
            window = df.iloc[: i + 1]
            row = df.iloc[i]
            price = row["Close"]

            # Mark-to-market equity
            pos_value = position_shares * price
            equity = cash + pos_value
            equity_curve.append(equity)

            if position_shares > 0:
                # Update trailing stop
                if price > highest_price:
                    highest_price = price
                profit_pct = (highest_price - entry_price) / entry_price * 100
                if profit_pct >= TRAIL_ACTIVATE_PCT:
                    new_ts = highest_price * (1 - TRAIL_PCT / 100)
                    if trailing_stop is None or new_ts > trailing_stop:
                        trailing_stop = new_ts

                # Check exits
                exit_reason = None
                if price <= stop_loss:
                    exit_reason = "stop_loss"
                elif trailing_stop and price <= trailing_stop:
                    exit_reason = "trailing_stop"
                elif price >= take_profit:
                    exit_reason = "take_profit"

                if exit_reason:
                    proceeds = price * position_shares * (1 - COMMISSION_PCT / 100)
                    pnl = proceeds - (entry_price * position_shares * (1 + COMMISSION_PCT / 100))
                    cash += proceeds
                    trades.append({
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "exit_price": price,
                        "shares": position_shares,
                        "pnl": pnl,
                        "pnl_pct": (price - entry_price) / entry_price * 100,
                        "exit_reason": exit_reason,
                        "entry_date": entry_date,
                        "exit_date": row.name,
                    })
                    position_shares = 0.0
                    trailing_stop = None
                    highest_price = 0.0
                    continue

            # Generate signal only when flat
            if position_shares == 0:
                signal = self.strategy.generate_signal(symbol, window)
                if signal and signal.signal_type == SignalType.BUY:
                    # Size: risk 1% of current equity
                    risk_per_share = abs(signal.entry_price - signal.stop_loss)
                    if risk_per_share <= 0:
                        continue
                    dollar_risk = equity * 0.01
                    shares = int(dollar_risk / risk_per_share)
                    cost = signal.entry_price * shares * (1 + COMMISSION_PCT / 100)
                    if shares > 0 and cost <= cash * 0.95:
                        cash -= cost
                        position_shares = shares
                        entry_price = signal.entry_price
                        stop_loss = signal.stop_loss
                        take_profit = signal.take_profit
                        highest_price = entry_price
                        trailing_stop = None
                        entry_date = row.name

        # Close any open position at end of test
        if position_shares > 0:
            last_price = df.iloc[-1]["Close"]
            proceeds = last_price * position_shares * (1 - COMMISSION_PCT / 100)
            pnl = proceeds - (entry_price * position_shares * (1 + COMMISSION_PCT / 100))
            cash += proceeds
            trades.append({
                "symbol": symbol,
                "entry_price": entry_price,
                "exit_price": last_price,
                "shares": position_shares,
                "pnl": pnl,
                "pnl_pct": (last_price - entry_price) / entry_price * 100,
                "exit_reason": "end_of_test",
                "entry_date": entry_date,
                "exit_date": df.index[-1],
            })
            cash += 0  # already added above

        final_equity = cash
        total_pnl = final_equity - self.initial_capital

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win_pct = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss_pct = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        max_dd = _max_drawdown(equity_curve)
        sharpe = _sharpe(equity_curve)

        return BacktestResult(
            strategy_name=self.strategy.name,
            symbol=symbol,
            start_date=str(df.index[50].date()),
            end_date=str(df.index[-1].date()),
            initial_capital=self.initial_capital,
            final_equity=round(final_equity, 2),
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl / self.initial_capital * 100, 2),
            win_rate=round(win_rate, 1),
            avg_win_pct=round(avg_win_pct, 2),
            avg_loss_pct=round(avg_loss_pct, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 2),
        )


def _max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0
    arr = np.array(equity_curve)
    peak = np.maximum.accumulate(arr)
    dd = (peak - arr) / peak * 100
    return float(dd.max())


def _sharpe(equity_curve: List[float], risk_free_daily: float = 0.0) -> float:
    if len(equity_curve) < 2:
        return 0.0
    returns = np.diff(equity_curve) / equity_curve[:-1]
    excess = returns - risk_free_daily
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(252))
