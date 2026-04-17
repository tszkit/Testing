"""Central configuration for the auto trading system."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Trading mode: 'backtest', 'paper', 'live'
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

# Target performance
MONTHLY_TARGET_PCT = 10.0          # 10% per month target
MAX_MONTHLY_DRAWDOWN_PCT = 5.0     # stop trading if drawdown exceeds this
DAILY_LOSS_LIMIT_PCT = 2.0         # halt for the day if daily loss exceeds this

# Portfolio settings
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "10000"))
MAX_POSITION_SIZE_PCT = 20.0       # max 20% of portfolio in one position
MAX_OPEN_POSITIONS = 5
COMMISSION_PCT = 0.1               # 0.1% per trade (both sides)

# Risk management
RISK_PER_TRADE_PCT = 1.0           # risk 1% of portfolio per trade
DEFAULT_STOP_LOSS_PCT = 2.0        # 2% stop loss
DEFAULT_TAKE_PROFIT_PCT = 6.0      # 6% take profit (3:1 R/R ratio)
TRAILING_STOP_PCT = 1.5            # trailing stop activates after 3% profit

# Watchlist — diversified across sectors
WATCHLIST = [
    # Tech
    "AAPL", "MSFT", "NVDA", "META", "GOOGL",
    # Finance
    "JPM", "V", "MA",
    # Consumer
    "AMZN", "TSLA",
    # ETFs
    "SPY", "QQQ", "IWM",
]

# Strategy weights (must sum to 1.0)
STRATEGY_WEIGHTS = {
    "momentum":      0.40,
    "mean_reversion": 0.30,
    "breakout":      0.30,
}

# Data settings
DATA_INTERVAL = "1d"               # daily bars for swing trading
LOOKBACK_DAYS = 252                # 1 year of history for indicators
FAST_MA = 9
SLOW_MA = 21
SIGNAL_MA = 9
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
ATR_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2.0
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 25

# Paths
LOG_DIR = BASE_DIR / "logs"
RESULTS_DIR = BASE_DIR / "results"
