#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from quant_futures.data.binance_client import BinancePublicClient, BinanceRestrictedLocationError
from quant_futures.data.metadata import MetaService
from quant_futures.data.market_data import MarketDataService, OhlcvParams
from quant_futures.data.offline_provider import BinanceVisionProvider, VisionPaths


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser()
	p.add_argument("--symbols", nargs="+", required=True)
	p.add_argument("--interval", default="15m")
	p.add_argument("--days", type=int, default=7)
	p.add_argument("--outdir", default="data")
	p.add_argument("--vision-root", default=None, help="Binance Vision root for offline data fallback")
	return p.parse_args()


def write_csv(path: Path, rows: list[dict]) -> None:
	if not rows:
		return
	fieldnames = list(rows[0].keys())
	with path.open("w", newline="", encoding="utf-8") as f:
		w = csv.DictWriter(f, fieldnames=fieldnames)
		w.writeheader()
		w.writerows(rows)


def main() -> None:
	args = parse_args()
	outdir = Path(args.outdir)
	outdir.mkdir(parents=True, exist_ok=True)

	client = BinancePublicClient()
	meta_svc = MetaService(client)
	mkt = MarketDataService(client)
	vision = BinanceVisionProvider(VisionPaths(Path(args.vision_root))) if args.vision_root else None

	end = datetime.now(timezone.utc)
	start = end - timedelta(days=args.days)

	for sym in args.symbols:
		bars = []
		fund = []
		try:
			meta = meta_svc.symbol_meta(sym)
			print(f"Symbol: {sym} tick={meta.tick_size} step={meta.step_size} maxLev={meta.max_leverage}")

			bars = mkt.klines(
				OhlcvParams(
					symbol=sym,
					interval=args.interval,
					start_time_ms=int(start.timestamp() * 1000),
					end_time_ms=int(end.timestamp() * 1000),
					limit=1500,
					fill_missing=True,
					remove_outlier_wicks=False,
				)
			)
			fund = mkt.funding_rates(sym, start_time_ms=int(start.timestamp() * 1000), end_time_ms=int(end.timestamp() * 1000))
		except BinanceRestrictedLocationError as e:
			print("Live API restricted; attempting offline Binance Vision fallback...")
			if not vision:
				print("No Vision path provided; skip data fetch.")
			else:
				bars = vision.read_klines(sym, args.interval)
				fund = vision.read_funding(sym)

		if bars:
			fpath = outdir / f"{sym}_{args.interval}_ohlcv.csv"
			write_csv(fpath, bars)
			print(f"Saved OHLCV -> {fpath}")
		if fund:
			ff = outdir / f"{sym}_funding.csv"
			write_csv(ff, fund)
			print(f"Saved funding -> {ff}")


if __name__ == "__main__":
	main()