from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class VisionPaths:
	root: Path
	kline_dir_name: str = "futures/um/daily/klines"  # e.g., root/futures/um/daily/klines/BTCUSDT/15m/BTCUSDT-15m-2024-01-01.csv
	funding_dir_name: str = "futures/um/fundingRate"  # e.g., root/futures/um/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2024-01.csv

	def kline_dir(self, symbol: str, interval: str) -> Path:
		return self.root / self.kline_dir_name / symbol / interval

	def funding_dir(self, symbol: str) -> Path:
		return self.root / self.funding_dir_name / symbol


class BinanceVisionProvider:
	def __init__(self, paths: VisionPaths) -> None:
		self.paths = paths

	def read_klines(self, symbol: str, interval: str) -> List[Dict[str, Any]]:
		d = self.paths.kline_dir(symbol, interval)
		if not d.exists():
			return []
		rows: List[Dict[str, Any]] = []
		for file in sorted(d.glob(f"{symbol}-{interval}-*.csv")):
			with file.open("r", encoding="utf-8") as f:
				reader = csv.reader(f)
				for r in reader:
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

	def read_funding(self, symbol: str) -> List[Dict[str, Any]]:
		d = self.paths.funding_dir(symbol)
		if not d.exists():
			return []
		rows: List[Dict[str, Any]] = []
		for file in sorted(d.glob(f"{symbol}-fundingRate-*.csv")):
			with file.open("r", encoding="utf-8") as f:
				reader = csv.DictReader(f)
				for r in reader:
					try:
						rows.append({
							"fundingTime": int(r["fundingTime"]),
							"fundingRate": float(r["fundingRate"]),
						})
					except Exception:
						continue
		return rows