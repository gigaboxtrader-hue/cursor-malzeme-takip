from __future__ import annotations
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
	return series.ewm(span=span, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
	high, low, close = df['high'], df['low'], df['close']
	prev_close = close.shift(1)
	return pd.concat([
		(high - low).abs(),
		(high - prev_close).abs(),
		(low - prev_close).abs(),
	], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
	tr = true_range(df)
	return tr.rolling(window=period, min_periods=period).mean()
