from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..data.market_data import MarketDataService
from ..data.symbols import list_perpetual_usdt_symbols, CORE_WHITELIST
from ..data.binance_client import BinancePublicClient, BinanceRestrictedLocationError


@dataclass
class UniverseCriteria:
	min_notional_30d: float = 50_000_000.0
	min_notional_90d: float = 100_000_000.0
	spread_within_pct: float = 0.001
	depth_min_usdt: float = 200_000.0
	interval: str = "1h"  # for notional calc when fetching live


@dataclass
class UniverseDecision:
	symbol: str
	accepted: bool
	reasons: List[str]
	notional_30d: float
	notional_90d: float
	spread: Optional[float] = None
	bid_notional_within: Optional[float] = None
	ask_notional_within: Optional[float] = None


class UniverseSelector:
	def __init__(self, client: BinancePublicClient, market: MarketDataService) -> None:
		self.client = client
		self.market = market

	def compute_notional_from_csv(self, csv_path: Path) -> float:
		total = 0.0
		with csv_path.open("r", encoding="utf-8") as f:
			reader = csv.DictReader(f)
			for r in reader:
				try:
					total += float(r["quote_asset_volume"])  # sum quote notional
				except Exception:
					continue
		return total

	def evaluate_symbol(self, symbol: str, criteria: UniverseCriteria, ohlcv_csv_30d: Optional[Path] = None, ohlcv_csv_90d: Optional[Path] = None) -> UniverseDecision:
		reasons: List[str] = []
		notional_30 = 0.0
		notional_90 = 0.0

		if ohlcv_csv_30d and ohlcv_csv_30d.exists():
			notional_30 = self.compute_notional_from_csv(ohlcv_csv_30d)
		else:
			# fallback: cannot fetch live klines here due to restrictions, set to 0
			reasons.append("no_30d_csv")
		if ohlcv_csv_90d and ohlcv_csv_90d.exists():
			notional_90 = self.compute_notional_from_csv(ohlcv_csv_90d)
		else:
			reasons.append("no_90d_csv")

		spread = None
		bid_within = None
		ask_within = None
		try:
			liquidity = self.market.spread_and_depth_within(symbol, pct=criteria.spread_within_pct)
			spread = liquidity["spread"]
			bid_within = liquidity["bidNotionalWithin"]
			ask_within = liquidity["askNotionalWithin"]
		except BinanceRestrictedLocationError:
			reasons.append("live_liquidity_restricted")
		except Exception:
			reasons.append("live_liquidity_error")

		ok_notional = (notional_30 >= criteria.min_notional_30d) and (notional_90 >= criteria.min_notional_90d)
		ok_liquidity = (spread is None or spread <= criteria.spread_within_pct) and ((bid_within is None or bid_within >= criteria.depth_min_usdt) and (ask_within is None or ask_within >= criteria.depth_min_usdt))

		accepted = ok_notional and ok_liquidity
		return UniverseDecision(
			symbol=symbol,
			accepted=accepted,
			reasons=reasons + (["ok_notional"] if ok_notional else ["low_notional"])
			+ (["ok_liquidity"] if ok_liquidity else ["low_liquidity"]),
			notional_30d=notional_30,
			notional_90d=notional_90,
			spread=spread,
			bid_notional_within=bid_within,
			ask_notional_within=ask_within,
		)

	def select(self, criteria: UniverseCriteria, csv_dir_30d: Optional[Path] = None, csv_dir_90d: Optional[Path] = None, symbols: Optional[List[str]] = None) -> List[UniverseDecision]:
		symbols = symbols or list_perpetual_usdt_symbols(self.client)
		decisions: List[UniverseDecision] = []
		for sym in symbols:
			csv30 = (csv_dir_30d / f"{sym}_{criteria.interval}_ohlcv.csv") if csv_dir_30d else None
			csv90 = (csv_dir_90d / f"{sym}_{criteria.interval}_ohlcv.csv") if csv_dir_90d else None
			decisions.append(self.evaluate_symbol(sym, criteria, csv30, csv90))
		return decisions