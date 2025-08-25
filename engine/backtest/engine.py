from __future__ import annotations
from typing import Optional
import pandas as pd

from ..config import Config
from ..data.loader import DataLoader
from ..utils.indicators import atr
from ..risk.manager import RiskManager


class BacktestEngine:
	def __init__(self, cfg: Config):
		self.cfg = cfg

	def run_single(self, symbol: str, timeframe: str, start_date: Optional[str], end_date: Optional[str]) -> None:
		# Load data
		loader = DataLoader(base_url=self.cfg.exchange.base_url)
		import asyncio
		df = asyncio.run(loader.fetch_ohlcv(symbol, timeframe, start_date, end_date))
		# Compute ATR for sizing sanity check (no trades yet)
		df['atr'] = atr(df, period=14)
		print(f"Loaded {len(df)} candles for {symbol} {timeframe}")
		print(df.tail(3)[['open_time','open','high','low','close','atr']])

		# RiskManager demo sizing using last row
		if len(df) > 20:
			last = df.iloc[-1]
			risk = RiskManager(self.cfg)
			result = risk.compute_position(
				equity_usdt=self.cfg.backtest.initial_equity_usdt,
				entry_price=float(last['close']),
				side='LONG',
				atr_value=float(last['atr']),
				tick_size=0.1,
				step_size=0.001,
			)
			print("Sizing sample:", result)
