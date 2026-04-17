# Auto Trading System — 10% Monthly Target

A multi-strategy automated trading system built in Python, targeting **10% gain per month** through disciplined risk management.

## Strategies

| Strategy | Weight | Edge |
|---|---|---|
| **Momentum** | 40% | EMA cross + ADX trend filter + RSI zone |
| **Mean Reversion** | 30% | Bollinger Band lower touch + RSI oversold |
| **Breakout** | 30% | Donchian channel break after tight consolidation |

## Risk Management

- **1% risk per trade** — position sized by ATR-based stop loss
- **Max 5 open positions**, max 20% of portfolio per position
- **2% daily loss circuit breaker** — halts trading for the day
- **5% monthly drawdown circuit breaker** — halts all trading
- **Trailing stop** — activates at +3% profit, trails at 1.5%
- **Minimum 1.5:1 R/R** required before any entry

## Quick Start

```bash
pip install -r requirements.txt

# Backtest all strategies on the default watchlist (1 year)
python main.py backtest

# Backtest specific tickers
python main.py backtest --symbols AAPL NVDA MSFT --days 730

# Run a single paper-trading scan cycle
python main.py paper

# Run scheduled paper trading (09:35 + 15:50 each weekday)
python main.py schedule
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TRADING_MODE` | `paper` | `paper`, `backtest`, or `live` |
| `INITIAL_CAPITAL` | `10000` | Starting capital in USD |

## Project Structure

```
├── main.py                  # Entry point
├── engine.py                # TradingEngine orchestrator
├── config/
│   ├── settings.py          # All tunable parameters
│   └── strategies_config.yaml
├── strategies/
│   ├── momentum.py
│   ├── mean_reversion.py
│   └── breakout.py
├── core/
│   ├── risk_manager.py      # Position sizing + circuit breakers
│   ├── portfolio.py         # Position tracking + P&L
│   ├── order_manager.py     # Paper / live order routing
│   └── performance.py       # Monthly target tracking
├── data/
│   ├── fetcher.py           # yfinance with caching
│   └── processor.py         # All technical indicators
└── backtester/
    └── engine.py            # Historical simulation
```

## Disclaimer

This software is for educational and research purposes only. Past backtest performance does not guarantee future results. Never risk capital you cannot afford to lose.
