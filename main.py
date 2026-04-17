#!/usr/bin/env python3
"""
Auto Trading System — entry point.

Usage
-----
  # Run one paper-trading cycle immediately
  python main.py paper

  # Backtest all strategies on the watchlist (last 365 days)
  python main.py backtest

  # Backtest on specific tickers
  python main.py backtest --symbols AAPL MSFT NVDA

  # Schedule paper trading every market day at 09:35 ET
  python main.py schedule
"""
import argparse
import logging
import sys

from utils.helpers import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def cmd_paper(_args):
    from engine import TradingEngine
    bot = TradingEngine()
    summary, progress = bot.run_paper_cycle()
    print("\n--- Portfolio Summary ---")
    for k, v in summary.items():
        print(f"  {k:<22}: {v}")
    print("\n--- Monthly Progress ---")
    for k, v in progress.items():
        print(f"  {k:<30}: {v}")


def cmd_backtest(args):
    from engine import TradingEngine
    symbols = args.symbols if args.symbols else None
    days = args.days
    bot = TradingEngine()
    results = bot.run_backtest(symbols=symbols, days=days)
    if not results:
        print("No backtest results.")
        return
    # Aggregate stats
    total = len(results)
    profitable = sum(1 for r in results if r.total_pnl > 0)
    avg_pnl = sum(r.total_pnl_pct for r in results) / total
    print(f"\n{'='*55}")
    print(f"  AGGREGATE: {total} tests | {profitable} profitable | avg PnL={avg_pnl:.2f}%")
    print(f"{'='*55}")


def cmd_schedule(_args):
    import schedule
    import time
    from engine import TradingEngine

    bot = TradingEngine()

    def job():
        try:
            bot.run_paper_cycle()
        except Exception as e:
            logger.exception("Cycle error: %s", e)

    # Run at 09:35 and 15:50 ET (adjust timezone as needed)
    schedule.every().monday.at("09:35").do(job)
    schedule.every().tuesday.at("09:35").do(job)
    schedule.every().wednesday.at("09:35").do(job)
    schedule.every().thursday.at("09:35").do(job)
    schedule.every().friday.at("09:35").do(job)

    schedule.every().monday.at("15:50").do(job)
    schedule.every().tuesday.at("15:50").do(job)
    schedule.every().wednesday.at("15:50").do(job)
    schedule.every().thursday.at("15:50").do(job)
    schedule.every().friday.at("15:50").do(job)

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="Auto Trading System")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("paper", help="Run one paper-trading cycle")

    bt = sub.add_parser("backtest", help="Backtest all strategies")
    bt.add_argument("--symbols", nargs="+", help="Override watchlist symbols")
    bt.add_argument("--days", type=int, default=365, help="Lookback days (default 365)")

    sub.add_parser("schedule", help="Run paper trading on a schedule")

    args = parser.parse_args()
    if args.command == "paper":
        cmd_paper(args)
    elif args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
