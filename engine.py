"""
Main trading engine.

Modes
-----
paper     : simulates fills at current prices, no real money
backtest  : runs strategies against historical data and reports results
"""
import logging
from pathlib import Path
from typing import Dict, List

from config.settings import (
    INITIAL_CAPITAL,
    STRATEGY_WEIGHTS,
    TRADING_MODE,
    WATCHLIST,
)
from core.order_manager import OrderManager, OrderStatus
from core.performance import PerformanceTracker
from core.portfolio import Portfolio
from core.risk_manager import RiskManager
from data.fetcher import DataFetcher
from data.processor import add_indicators
from strategies.base_strategy import Signal, SignalType
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy
from utils.helpers import load_strategy_configs

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "config" / "strategies_config.yaml"


def _build_strategies(cfg: dict) -> List:
    return [
        MomentumStrategy(cfg.get("momentum", {})),
        MeanReversionStrategy(cfg.get("mean_reversion", {})),
        BreakoutStrategy(cfg.get("breakout", {})),
    ]


class TradingEngine:
    def __init__(self, capital: float = INITIAL_CAPITAL):
        cfg = load_strategy_configs(_CONFIG_PATH)
        self.strategies = _build_strategies(cfg)
        self.portfolio = Portfolio(capital)
        self.risk_manager = RiskManager(capital)
        self.order_manager = OrderManager()
        self.perf_tracker = PerformanceTracker(capital)
        self.fetcher = DataFetcher()

    # ------------------------------------------------------------------
    # Paper trading
    # ------------------------------------------------------------------

    def run_paper_cycle(self):
        """One scan cycle: fetch latest data, generate signals, manage positions."""
        logger.info("=== Paper trading cycle start ===")
        data = self.fetcher.fetch_multiple(WATCHLIST)

        prices = {sym: df.iloc[-1]["Close"] for sym, df in data.items()}

        # 1. Update existing positions (check exit conditions)
        closed = self.portfolio.update_positions(prices)
        for trade in closed:
            self.risk_manager.record_pnl(trade.pnl, self.portfolio.equity_at_prices(prices))

        # 2. Scan for new entries
        open_symbols = list(self.portfolio.positions.keys())
        all_signals: List[Signal] = []

        for sym, df in data.items():
            df_ind = add_indicators(df)
            for strategy in self.strategies:
                signal = strategy.generate_signal(sym, df_ind)
                if signal and signal.signal_type == SignalType.BUY:
                    all_signals.append(signal)

        # Sort by confidence (best first)
        all_signals.sort(key=lambda s: s.confidence, reverse=True)

        equity = self.portfolio.equity_at_prices(prices)
        for signal in all_signals:
            check = self.risk_manager.evaluate(signal, equity, open_symbols)
            if not check.approved:
                logger.debug("Signal rejected (%s): %s", signal.symbol, check.reason)
                continue
            order = self.order_manager.submit_buy(
                symbol=signal.symbol,
                shares=check.position_size,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                strategy=signal.strategy,
            )
            if order.status == OrderStatus.FILLED:
                self.portfolio.open_position(
                    symbol=signal.symbol,
                    shares=check.position_size,
                    price=order.fill_price,
                    stop=signal.stop_loss,
                    tp=signal.take_profit,
                    strategy=signal.strategy,
                )
                open_symbols.append(signal.symbol)

        # 3. Record performance
        equity = self.portfolio.equity_at_prices(prices)
        self.perf_tracker.record(equity)

        summary = self.portfolio.summary(prices)
        progress = self.perf_tracker.monthly_progress(equity)

        logger.info("Portfolio | Equity=$%.2f | Positions=%d | PnL=$%.2f (%.2f%%)",
                    summary["equity"], summary["open_positions"],
                    summary["total_pnl"], summary["total_pnl_pct"])
        logger.info("Monthly   | PnL=%.2f%% | Target=%.1f%% | Remaining=%.2f%%",
                    progress["month_pnl_pct"], progress["target_pct"],
                    progress["remaining_to_target_pct"])

        return summary, progress

    # ------------------------------------------------------------------
    # Backtesting
    # ------------------------------------------------------------------

    def run_backtest(self, symbols: List[str] = None, days: int = 365):
        from backtester.engine import BacktestEngine
        symbols = symbols or WATCHLIST
        data = self.fetcher.fetch_multiple(symbols, days=days)

        all_results = []
        for strategy in self.strategies:
            engine = BacktestEngine(strategy, self.portfolio.initial_capital)
            for sym, df in data.items():
                result = engine.run(sym, df.copy())
                if result:
                    print(result)
                    all_results.append(result)

        return all_results
