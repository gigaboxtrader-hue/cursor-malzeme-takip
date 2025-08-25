#!/usr/bin/env python3
from __future__ import annotations

import argparse

from quant_futures.data.binance_client import BinancePublicClient, BinanceRestrictedLocationError
from quant_futures.data.metadata import MetaService
from quant_futures.risk.engine import RiskEngine, RiskConfig, PlannedTrade


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser()
	p.add_argument("--symbol", required=True)
	p.add_argument("--direction", choices=["long", "short"], required=True)
	p.add_argument("--entry", type=float, required=True)
	p.add_argument("--sl", type=float, required=True)
	p.add_argument("--atr", type=float, required=True)
	p.add_argument("--equity", type=float, default=10_000)
	p.add_argument("--risk", type=float, default=0.01)
	p.add_argument("--volclass", type=str, default="A")
	return p.parse_args()


def main() -> None:
	args = parse_args()
	client = BinancePublicClient()
	meta = MetaService(client)
	cfg = RiskConfig(
		equity_usdt=args.equity,
		risk_per_trade_pct=args.risk,
		vol_class_leverage_caps={"A": 15, "B": 6, "C": 3},
	)
	re = RiskEngine(meta, cfg)
	trade = PlannedTrade(symbol=args.symbol, direction=args.direction, entry=args.entry, sl=args.sl, atr=args.atr, vol_class=args.volclass)
	try:
		res = re.size_position(trade)
		print(res)
	except BinanceRestrictedLocationError as e:
		print("Live API restricted; cannot compute symbol meta now.")


if __name__ == "__main__":
	main()