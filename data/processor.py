"""Technical indicator computation."""
import numpy as np
import pandas as pd

from config.settings import (
    ATR_PERIOD, BB_PERIOD, BB_STD, FAST_MA, RSI_PERIOD, SLOW_MA, ADX_PERIOD
)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators and return enriched DataFrame."""
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # Moving averages
    df["ema_fast"] = close.ewm(span=FAST_MA, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=SLOW_MA, adjust=False).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(200).mean()

    # RSI
    df["rsi"] = _rsi(close, RSI_PERIOD)

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands
    bb_mid = close.rolling(BB_PERIOD).mean()
    bb_std = close.rolling(BB_PERIOD).std()
    df["bb_upper"] = bb_mid + BB_STD * bb_std
    df["bb_lower"] = bb_mid - BB_STD * bb_std
    df["bb_mid"] = bb_mid
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / bb_mid
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # ATR
    df["atr"] = _atr(high, low, close, ATR_PERIOD)

    # ADX / DI
    df["adx"], df["di_plus"], df["di_minus"] = _adx(high, low, close, ADX_PERIOD)

    # Volume
    df["vol_sma20"] = volume.rolling(20).mean()
    df["vol_ratio"] = volume / df["vol_sma20"]

    # Momentum
    df["roc_5"] = close.pct_change(5) * 100
    df["roc_20"] = close.pct_change(20) * 100

    # Donchian channels (for breakout)
    df["dc_high_20"] = high.rolling(20).max()
    df["dc_low_20"] = low.rolling(20).min()
    df["dc_range_pct"] = (df["dc_high_20"] - df["dc_low_20"]) / df["dc_low_20"] * 100

    return df.dropna()


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int):
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    dm_plus = np.where((high - prev_high) > (prev_low - low), (high - prev_high).clip(lower=0), 0)
    dm_minus = np.where((prev_low - low) > (high - prev_high), (prev_low - low).clip(lower=0), 0)

    dm_plus = pd.Series(dm_plus, index=high.index)
    dm_minus = pd.Series(dm_minus, index=high.index)
    atr = _atr(high, low, close, period)

    di_plus = 100 * dm_plus.ewm(com=period - 1, adjust=False).mean() / atr
    di_minus = 100 * dm_minus.ewm(com=period - 1, adjust=False).mean() / atr
    dx = (100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan))
    adx = dx.ewm(com=period - 1, adjust=False).mean()
    return adx, di_plus, di_minus
