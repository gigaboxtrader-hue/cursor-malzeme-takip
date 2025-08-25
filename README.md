# Binance Futures Trading System

Risk-adjusted returns with dynamic leverage and liquidation protection for Binance Futures.

## Features

### Core Features
- **Risk Management**: Dynamic position sizing with liquidation buffer protection
- **Signal Generation**: Multiple signal families (trend, momentum, breakout, mean-reversion)
- **Universe Selection**: Automated symbol filtering based on volume, liquidity, and spread
- **Backtesting**: Event-driven simulation with realistic fee, funding, and slippage modeling
- **Exit Strategies**: OCO orders, trailing stops, partial exits, and time-based exits

### Risk Controls
- Maximum 1% risk per trade
- Maximum 3% total portfolio risk
- Dynamic leverage based on volatility and market regime
- Liquidation buffer validation (3×ATR minimum distance)
- Isolated margin mode for position isolation

### Signal Families
- **Trend**: EMA crossovers, ADX-based trend strength
- **Momentum**: RSI oversold/overbought, MACD crossovers
- **Breakout**: Bollinger Band breakouts, support/resistance levels
- **Mean Reversion**: VWAP-based mean reversion
- **Volatility**: ATR expansion/contraction signals

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd binance-futures-trading-system
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your Binance API credentials
```

4. Install Redis (for caching):
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# Download from https://redis.io/download
```

## Configuration

### API Setup
1. Create a Binance account
2. Generate API keys with futures trading permissions
3. Add keys to `.env` file:
```
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
BINANCE_TESTNET=True  # Set to False for live trading
```

### Risk Parameters
Key risk parameters can be adjusted in `src/config.py`:

```python
# Position sizing
max_risk_per_trade: float = 0.01  # 1% per trade
max_portfolio_risk: float = 0.03  # 3% total portfolio risk

# Liquidation protection
liquidation_buffer_atr_multiplier: float = 3.0  # Z×ATR
liquidation_buffer_percent: float = 0.05  # 5% buffer

# Dynamic leverage limits
max_leverage_core: int = 15  # BTC/ETH
max_leverage_major: int = 6   # SOL/BNB/XRP
max_leverage_alt: int = 3     # Other altcoins
```

## Usage

### Basic Usage

1. Run the main application:
```bash
python main.py
```

2. The system will:
   - Initialize and test API connection
   - Update trading universe
   - Run example backtest
   - Test signal generation and risk management

### Backtesting

```python
from src.backtest.backtest_engine import backtest_engine
from datetime import datetime, timedelta

# Run backtest
result = backtest_engine.run_backtest(
    symbol="BTCUSDT",
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now(),
    timeframe='1h',
    signal_families=['trend', 'momentum', 'breakout']
)

# View results
print(f"Total Trades: {result.total_trades}")
print(f"Win Rate: {result.win_rate:.2%}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.max_drawdown:.2%}")
```

### Signal Generation

```python
from src.signals.signal_engine import signal_engine
from src.data.symbol_metadata import data_collector

# Get market data
data = await data_collector.get_ohlcv_data("BTCUSDT", "1h")

# Generate signals
signals = signal_engine.generate_signals(
    data, "BTCUSDT", "1h", 
    signal_families=['trend', 'momentum', 'breakout']
)

# Filter high-quality signals
filtered_signals = signal_engine.filter_signals(
    signals, min_strength=0.7, confirmation_level='CONFIRMED'
)
```

### Risk Management

```python
from src.risk.risk_manager import risk_manager

# Calculate position size
sizing = risk_manager.calculate_position_size(
    symbol="BTCUSDT",
    entry_price=50000,
    stop_loss=49000,
    equity=10000
)

# Check portfolio risk
portfolio_risk = risk_manager.check_portfolio_risk(10000, sizing.risk_amount)
```

## System Architecture

### Modules

1. **Data Layer** (`src/data/`)
   - Symbol metadata management
   - Market data collection
   - Universe selection and filtering

2. **Signal Engine** (`src/signals/`)
   - Technical indicator calculation
   - Multi-family signal generation
   - Signal filtering and confirmation

3. **Risk Manager** (`src/risk/`)
   - Position sizing
   - Dynamic leverage calculation
   - Liquidation buffer validation
   - Portfolio risk monitoring

4. **Execution** (`src/execution/`)
   - Exit strategy management
   - OCO order handling
   - Trailing stop logic

5. **Backtesting** (`src/backtest/`)
   - Event-driven simulation
   - Realistic fee/funding modeling
   - Performance metrics calculation

### Data Flow

1. **Market Data** → Universe Selection → Symbol Whitelist
2. **Symbol Data** → Signal Generation → Filtered Signals
3. **Signals** → Risk Validation → Position Sizing
4. **Positions** → Exit Management → Trade Execution
5. **Trades** → Performance Analysis → Strategy Optimization

## Risk Warnings

⚠️ **IMPORTANT**: This system is for educational and research purposes only.

- **No Guarantee**: Past performance does not guarantee future results
- **Risk of Loss**: Trading futures involves substantial risk of loss
- **Leverage Risk**: High leverage can amplify both gains and losses
- **Market Risk**: Cryptocurrency markets are highly volatile
- **Technical Risk**: System failures can result in financial losses

## Testing

Run tests with:
```bash
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This software is provided "as is" without warranty of any kind. The authors are not responsible for any financial losses incurred through the use of this system. Always test thoroughly on testnet before using with real funds.
