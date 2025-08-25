from __future__ import annotations

from typing import List, Dict, Any

from .binance_client import BinancePublicClient
from ..utils.cache import FileCache

CORE_WHITELIST = ["BTCUSDT", "ETHUSDT"]


def list_perpetual_usdt_symbols(client: BinancePublicClient, cache: FileCache | None = None) -> List[str]:
	cache = cache or FileCache()
	key = "perp_usdt_symbols"
	cached = cache.get(key)
	if cached is not None:
		return cached
	info: Dict[str, Any] = client.get("/fapi/v1/exchangeInfo")
	result: List[str] = []
	for s in info.get("symbols", []):
		if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
			result.append(s["symbol"])
	cache.set(key, result, ttl_sec=3600)
	return result


def default_universe(client: BinancePublicClient, extra: List[str] | None = None) -> List[str]:
	universe = list(set(CORE_WHITELIST + (extra or [])))
	available = set(list_perpetual_usdt_symbols(client))
	return [s for s in universe if s in available]