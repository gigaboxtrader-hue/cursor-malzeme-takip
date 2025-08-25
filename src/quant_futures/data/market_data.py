from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .binance_client import BinancePublicClient
from ..utils.cache import FileCache
from ..utils.time import interval_to_timedelta


@dataclass
class OhlcvParams:
	symbol: str
	interval: str
	start_time_ms: Optional[int] = None
	end_time_ms: Optional[int] = None
	limit: int = 1500
	fill_missing: bool = True
	remove_outlier_wicks: bool = False
	outlier_k: float = 6.0


class MarketDataService:
	def __init__(self, client: BinancePublicClient, cache: Optional[FileCache] = None) -> None:
		self.client = client
		self.cache = cache or FileCache()

	def klines(self, params: OhlcvParams) -> List[Dict[str, Any]]:
		query: Dict[str, Any] = {
			"symbol": params.symbol,
			"interval": params.interval,
			"limit": params.limit,
		}
		if params.start_time_ms is not None:
			query["startTime"] = int(params.start_time_ms)
		if params.end_time_ms is not None:
			query["endTime"] = int(params.end_time_ms)

		raw = self.client.get("/fapi/v1/continuousKlines", params={**query, "contractType": "PERPETUAL"})
		if isinstance(raw, dict) and raw.get("code"):
			raw = self.client.get("/fapi/v1/klines", params=query)

		rows = self._klines_to_rows(raw)
		if params.fill_missing and rows:
			rows = self._forward_fill_missing(rows, params.interval)
		if params.remove_outlier_wicks and rows:
			rows = self._filter_outlier_wicks(rows, k=params.outlier_k)
		return rows

	def funding_rates(self, symbol: str, start_time_ms: Optional[int] = None, end_time_ms: Optional[int] = None, limit: int = 1000) -> List[Dict[str, Any]]:
		query: Dict[str, Any] = {"symbol": symbol, "limit": limit}
		if start_time_ms is not None:
			query["startTime"] = int(start_time_ms)
		if end_time_ms is not None:
			query["endTime"] = int(end_time_ms)
		data = self.client.get("/fapi/v1/fundingRate", params=query)
		rows: List[Dict[str, Any]] = []
		for r in data or []:
			try:
				rows.append({
					"fundingTime": int(r.get("fundingTime")),
					"fundingRate": float(r.get("fundingRate", 0.0)),
				})
			except Exception:
				continue
		rows.sort(key=lambda x: x["fundingTime"])
		return rows

	def mark_index_price(self, symbol: str) -> Dict[str, float]:
		resp = self.client.get("/fapi/v1/premiumIndex", params={"symbol": symbol})
		return {
			"markPrice": float(resp.get("markPrice", 0.0)),
			"indexPrice": float(resp.get("indexPrice", 0.0)),
		}

	def book_ticker(self, symbol: str) -> Dict[str, float]:
		resp = self.client.get("/fapi/v1/ticker/bookTicker", params={"symbol": symbol})
		return {
			"bidPrice": float(resp.get("bidPrice", 0.0)),
			"bidQty": float(resp.get("bidQty", 0.0)),
			"askPrice": float(resp.get("askPrice", 0.0)),
			"askQty": float(resp.get("askQty", 0.0)),
		}

	def depth(self, symbol: str, limit: int = 100) -> Dict[str, List[Tuple[float, float]]]:
		resp = self.client.get("/fapi/v1/depth", params={"symbol": symbol, "limit": limit})
		bids = [(float(p), float(q)) for p, q in resp.get("bids", [])]
		asks = [(float(p), float(q)) for p, q in resp.get("asks", [])]
		return {"bids": bids, "asks": asks}

	def spread_and_depth_within(self, symbol: str, pct: float = 0.001, limit: int = 100) -> Dict[str, float]:
		bt = self.book_ticker(symbol)
		spread = (bt["askPrice"] - bt["bidPrice"]) / ((bt["askPrice"] + bt["bidPrice"]) / 2.0)
		orderbook = self.depth(symbol, limit=limit)
		mid = (bt["askPrice"] + bt["bidPrice"]) / 2.0
		low = mid * (1 - pct)
		high = mid * (1 + pct)
		bid_notional = 0.0
		for price, qty in orderbook["bids"]:
			if price < low:
				break
			bid_notional += price * qty
		ask_notional = 0.0
		for price, qty in orderbook["asks"]:
			if price > high:
				break
			ask_notional += price * qty
		return {"spread": spread, "bidNotionalWithin": bid_notional, "askNotionalWithin": ask_notional}

	def _klines_to_rows(self, raw: List[List[Any]]) -> List[Dict[str, Any]]:
		rows: List[Dict[str, Any]] = []
		for r in raw or []:
			try:
				rows.append({
					"open_time": int(r[0]),
					"open": float(r[1]),
					"high": float(r[2]),
					"low": float(r[3]),
					"close": float(r[4]),
					"volume": float(r[5]),
					"close_time": int(r[6]),
					"quote_asset_volume": float(r[7]),
					"number_of_trades": int(r[8]),
					"taker_buy_base": float(r[9]),
					"taker_buy_quote": float(r[10]),
				})
			except Exception:
				continue
		return rows

	def _forward_fill_missing(self, rows: List[Dict[str, Any]], interval: str) -> List[Dict[str, Any]]:
		if not rows:
			return rows
		rows_sorted = sorted(rows, key=lambda x: x["open_time"]) 
		delta = interval_to_timedelta(interval)
		step_ms = int(delta.total_seconds() * 1000)
		filled: List[Dict[str, Any]] = []
		cursor = rows_sorted[0]["open_time"]
		index = 0
		prev_close: Optional[float] = None
		while cursor <= rows_sorted[-1]["open_time"]:
			if index < len(rows_sorted) and rows_sorted[index]["open_time"] == cursor:
				bar = rows_sorted[index]
				filled.append(bar)
				prev_close = bar["close"]
				index += 1
			else:
				if prev_close is None:
					cursor += step_ms
					continue
				filled.append({
					"open_time": cursor,
					"open": prev_close,
					"high": prev_close,
					"low": prev_close,
					"close": prev_close,
					"volume": 0.0,
					"close_time": cursor + step_ms - 1,
					"quote_asset_volume": 0.0,
					"number_of_trades": 0,
					"taker_buy_base": 0.0,
					"taker_buy_quote": 0.0,
				})
			cursor += step_ms
		return filled

	def _filter_outlier_wicks(self, rows: List[Dict[str, Any]], k: float = 6.0) -> List[Dict[str, Any]]:
		if not rows:
			return rows
		wick_vals: List[float] = []
		for b in rows:
			upper = abs(b["high"] - b["close"]) 
			lower = abs(b["close"] - b["low"]) 
			wick_vals.append(max(upper, lower))
		median = sorted(wick_vals)[len(wick_vals)//2]
		mad = sorted([abs(w - median) for w in wick_vals])[len(wick_vals)//2]
		std_proxy = mad if mad > 0 else (sum((w - median) ** 2 for w in wick_vals) / max(len(wick_vals), 1)) ** 0.5
		threshold = median + k * std_proxy
		return [b for b in rows if max(abs(b["high"] - b["close"]), abs(b["close"] - b["low"])) <= threshold]