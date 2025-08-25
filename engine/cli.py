import typer
from typing import Optional

app = typer.Typer(help="Binance USDT-M Futures Strategy Engine CLI")


@app.command()
def backtest(
	config: str = typer.Option("config/default.yaml", help="Path to YAML config"),
	symbol: str = typer.Option("BTCUSDT", help="Symbol to backtest"),
	timeframe: str = typer.Option("15m", help="Timeframe, e.g., 5m,15m,1h,4h"),
	start: Optional[str] = typer.Option(None, help="Start date YYYY-MM-DD"),
	end: Optional[str] = typer.Option(None, help="End date YYYY-MM-DD"),
):
	"""Run event-driven backtest (minimal skeleton)."""
	from .config import load_config
	from .backtest.engine import BacktestEngine

	cfg = load_config(config)
	engine = BacktestEngine(cfg)
	engine.run_single(symbol=symbol, timeframe=timeframe, start_date=start, end_date=end)


@app.command()
def universe(config: str = typer.Option("config/default.yaml")):
	"""Compute active universe based on liquidity and spread constraints (stub)."""
	from .config import load_config
	from .universe.selector import UniverseSelector

	cfg = load_config(config)
	selector = UniverseSelector(cfg)
	active = selector.build_universe()
	for s in active:
		print(f"{s.symbol}\t{s.reason}")


@app.command()
def optimize(config: str = typer.Option("config/default.yaml")):
	"""Run walk-forward optimizer (stub)."""
	print("Optimizer stub - to be implemented (Kart G)")


@app.command()
def live(config: str = typer.Option("config/default.yaml")):
	"""Start live/shadow trading pipeline (stub)."""
	print("Live/shadow trading stub - to be implemented (Kart H)")


if __name__ == "__main__":
	app()