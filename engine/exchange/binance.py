from __future__ import annotations
import httpx
from typing import Any, Dict, List, Optional


class BinanceUMClient:
	"""Minimal Binance USDT-M Futures REST client for meta and klines."""

	def __init__(self, base_url: str = "https://fapi.binance.com", api_key: Optional[str] = None, api_secret: Optional[str] = None):
		self.base_url = base_url.rstrip('/')
		self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
		self.api_key = api_key
		self.api_secret = api_secret

	async def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
		resp = await self._client.get(path, params=params)
		resp.raise_for_status()
		return resp.json()

	async def exchange_info(self) -> Dict[str, Any]:
		return await self._get("/fapi/v1/exchangeInfo")

	async def leverage_brackets(self, symbol: str) -> List[Dict[str, Any]]:
		# https://binance-docs.github.io/apidocs/futures/en/#initial-leverage-brackets
		data = await self._get("/fapi/v1/leverageBracket", params={"symbol": symbol})
		# API returns a list with one entry per symbol, brackets under 'brackets'
		if isinstance(data, list) and data:
			return data[0].get('brackets', [])
		return data.get('brackets', [])

	async def klines(self, symbol: str, interval: str, start_ms: Optional[int] = None, end_ms: Optional[int] = None, limit: int = 1500) -> List[List[Any]]:
		params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
		if start_ms is not None:
			params["startTime"] = start_ms
		if end_ms is not None:
			params["endTime"] = end_ms
		return await self._get("/fapi/v1/klines", params=params)

	async def funding_rate_history(self, symbol: str, start_ms: Optional[int] = None, end_ms: Optional[int] = None, limit: int = 1000) -> List[Dict[str, Any]]:
		params: Dict[str, Any] = {"symbol": symbol, "limit": limit}
		if start_ms is not None:
			params["startTime"] = start_ms
		if end_ms is not None:
			params["endTime"] = end_ms
		return await self._get("/fapi/v1/fundingRate", params=params)

	async def close(self) -> None:
		await self._client.aclose()


async def get_symbol_meta(client: BinanceUMClient, symbol: str) -> Dict[str, Any]:
	info = await client.exchange_info()
	for s in info.get('symbols', []):
		if s.get('symbol') == symbol:
			return s
	return {}
