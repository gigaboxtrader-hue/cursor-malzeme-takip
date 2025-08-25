from __future__ import annotations
import asyncio
from typing import Optional, Dict, Any
import pandas as pd

from ..exchange.binance import BinanceUMClient
from ..utils.time import parse_utc


class DataLoader:
	def __init__(self, base_url: str):
		self.client = BinanceUMClient(base_url=base_url)

	async def fetch_ohlcv(self, symbol: str, timeframe: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 1500) -> pd.DataFrame:
		start_ms = int(parse_utc(start).timestamp() * 1000) if start else None
		end_ms = int(parse_utc(end).timestamp() * 1000) if end else None
		rows = await self.client.klines(symbol, timeframe, start_ms, end_ms, limit)
		cols = [
			'open_time','open','high','low','close','volume','close_time','quote_asset_volume',
			'number_of_trades','taker_buy_base','taker_buy_quote','ignore'
		]
		df = pd.DataFrame(rows, columns=cols)
		df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
		df['close_time'] = pd.to_datetime(df['close_time'], unit='ms', utc=True)
		for c in ['open','high','low','close','volume','quote_asset_volume','taker_buy_base','taker_buy_quote']:
			df[c] = pd.to_numeric(df[c], errors='coerce')
		return df[['open_time','open','high','low','close','volume']]

	async def fetch_symbol_meta(self, symbol: str) -> Dict[str, Any]:
		return await self.client.leverage_brackets(symbol)

	async def close(self) -> None:
		await self.client.close()
