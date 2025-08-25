from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .binance_client import BinancePublicClient
from ..utils.cache import FileCache


@dataclass
class SymbolMeta:
	symbol: str
	tick_size: float
	step_size: float
	min_notional: float
	contract_size: float
	max_leverage: int
	quote_asset: str
	base_asset: str
	price_precision: int
	quantity_precision: int
	maint_margin_tiers: List[Dict[str, Any]]
	leverage_brackets: List[Dict[str, Any]]


class MetaService:
	def __init__(self, client: BinancePublicClient, cache: Optional[FileCache] = None) -> None:
		self.client = client
		self.cache = cache or FileCache()

	def _cache_key(self, name: str, **kwargs: Any) -> str:
		parts = [name] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
		return "|".join(parts)

	def exchange_info(self) -> Dict[str, Any]:
		key = self._cache_key("exchangeInfo")
		cached = self.cache.get(key)
		if cached is not None:
			return cached
		data = self.client.get("/fapi/v1/exchangeInfo")
		self.cache.set(key, data, ttl_sec=3600)
		return data

	def leverage_brackets(self, symbol: str) -> List[Dict[str, Any]]:
		key = self._cache_key("leverageBrackets", symbol=symbol)
		cached = self.cache.get(key)
		if cached is not None:
			return cached
		data = self.client.get("/fapi/v1/leverageBracket", params={"symbol": symbol})
		if isinstance(data, list):
			if data and isinstance(data[0], dict) and data[0].get("symbol") == symbol:
				result = data[0].get("brackets", [])
			else:
				result = []
		else:
			result = data.get("brackets", []) if isinstance(data, dict) else []
		self.cache.set(key, result, ttl_sec=3600)
		return result

	def maint_margin_tiers_from_brackets(self, symbol: str) -> List[Dict[str, Any]]:
		br = self.leverage_brackets(symbol)
		tiers: List[Dict[str, Any]] = []
		for b in br:
			# Binance fields: notionalFloor, notionalCap, maintMarginRatio, initialLeverage
			tiers.append({
				"notionalFloor": float(b.get("notionalFloor", 0)),
				"notionalCap": float(b.get("notionalCap", 0)),
				"maintMarginRatio": float(b.get("maintMarginRatio", 0)),
				"initialLeverage": int(b.get("initialLeverage", 1)),
			})
		return tiers

	def symbol_meta(self, symbol: str) -> SymbolMeta:
		ei = self.exchange_info()
		symbols = {s["symbol"]: s for s in ei.get("symbols", [])}
		if symbol not in symbols:
			raise ValueError(f"Symbol not found in exchangeInfo: {symbol}")
		info = symbols[symbol]
		filters = {f["filterType"]: f for f in info.get("filters", [])}
		price_filter = filters.get("PRICE_FILTER", {})
		lot_filter = filters.get("LOT_SIZE", {})
		min_notional_filter = filters.get("MIN_NOTIONAL", {})
		leverage_brackets = self.leverage_brackets(symbol)
		maint_tiers = self.maint_margin_tiers_from_brackets(symbol)

		max_lev = 125
		for b in leverage_brackets:
			try:
				max_lev = max(max_lev, int(b.get("initialLeverage", max_lev)))
			except Exception:
				pass

		return SymbolMeta(
			symbol=symbol,
			tick_size=float(price_filter.get("tickSize", "0.0")),
			step_size=float(lot_filter.get("stepSize", "0.0")),
			min_notional=float(min_notional_filter.get("notional", "0.0") or 0.0),
			contract_size=1.0,
			max_leverage=int(max_lev),
			quote_asset=info.get("quoteAsset", "USDT"),
			base_asset=info.get("baseAsset", ""),
			price_precision=int(info.get("pricePrecision", 2)),
			quantity_precision=int(info.get("quantityPrecision", 3)),
			maint_margin_tiers=maint_tiers,
			leverage_brackets=leverage_brackets,
		)