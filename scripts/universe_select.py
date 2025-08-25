#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from quant_futures.data.binance_client import BinancePublicClient
from quant_futures.data.market_data import MarketDataService
from quant_futures.universe.selector import UniverseSelector, UniverseCriteria


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser()
	p.add_argument("--interval", default="1h")
	p.add_argument("--csv30", type=str, default=None, help="Dir containing 30d OHLCV csvs per symbol")
	p.add_argument("--csv90", type=str, default=None, help="Dir containing 90d OHLCV csvs per symbol")
	p.add_argument("--min30", type=float, default=50_000_000)
	p.add_argument("--min90", type=float, default=100_000_000)
	p.add_argument("--spread", type=float, default=0.001)
	p.add_argument("--depth", type=float, default=200_000)
	return p.parse_args()


def main() -> None:
	args = parse_args()
	client = BinancePublicClient()
	market = MarketDataService(client)
	selector = UniverseSelector(client, market)
	crit = UniverseCriteria(
		min_notional_30d=args.min30,
		min_notional_90d=args.min90,
		spread_within_pct=args.spread,
		depth_min_usdt=args.depth,
		interval=args.interval,
	)
	csv30 = Path(args.csv30) if args.csv30 else None
	csv90 = Path(args.csv90) if args.csv90 else None
	decisions = selector.select(crit, csv_dir_30d=csv30, csv_dir_90d=csv90)
	accepted = [d.symbol for d in decisions if d.accepted]
	print("ACCEPTED:", accepted)
	for d in decisions:
		print(d.symbol, d.accepted, d.reasons, d.notional_30d, d.notional_90d, d.spread, d.bid_notional_within, d.ask_notional_within)


if __name__ == "__main__":
	main()