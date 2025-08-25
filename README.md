### Binance USDT-M Futures Strategy Engine

This repository implements a risk-first, liquidation-averse strategy framework for Binance USDT-M futures with dynamic leverage, realistic event-driven backtesting, walk-forward validation, and deployment scaffolding.

#### Key Principles
- Avoid liquidation: enforce liquidation buffer and protective SL always-on
- Dynamic leverage sizing based on volatility, liquidity class, and drawdown history
- Realistic backtests: fees, slippage, funding, partial fills, and latency modeled
- Portfolio limits: per-trade risk ≤ 1%, total concurrent risk ≤ 3% (configurable)

#### Quick Start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m engine.cli backtest --config config/default.yaml --symbol BTCUSDT --timeframe 15m --start 2023-01-01 --end 2023-06-30
```

#### Project Structure
```text
engine/
  backtest/      # Event-driven simulator (fills, slippage, fees, funding)
  data/          # Data access & caching (OHLCV, funding, meta)
  exchange/      # Binance REST/WS wrappers (meta, brackets, depth)
  execution/     # Live/paper order routing (OCO emulation)
  monitoring/    # Dashboard & alerts
  optimizer/     # Grid/Random/Bayesian search, walk-forward
  portfolio/     # Portfolio risk budgeting
  risk/          # Position sizing, dynamic leverage, liquidation buffer
  universe/      # Universe filter by volume/spread/depth
  utils/         # Indicators, timeframes, math helpers
config/
  default.yaml   # Global settings and policy thresholds
```

#### Safety
- Kill-switches for daily DD, feed divergence, order rejections
- Liquidation buffer verified pre-trade using leverage brackets and ATR buffers

#### License
MIT
