"""
Configuration settings for Binance Futures Trading System
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class BinanceConfig:
    """Binance API configuration"""
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    testnet: bool = os.getenv("BINANCE_TESTNET", "True").lower() == "true"
    base_url: str = "https://testnet.binancefuture.com" if testnet else "https://fapi.binance.com"
    ws_url: str = "wss://stream.binancefuture.com/ws" if not testnet else "wss://stream.binancefuture.com/ws"

@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Position sizing
    max_risk_per_trade: float = 0.01  # 1% per trade
    max_portfolio_risk: float = 0.03  # 3% total portfolio risk
    max_concurrent_positions: int = 5
    
    # Liquidation protection
    liquidation_buffer_atr_multiplier: float = 3.0  # Z×ATR
    liquidation_buffer_percent: float = 0.05  # 5% buffer
    sl_liquidation_buffer_atr: float = 2.0  # Y×ATR
    
    # Dynamic leverage limits
    max_leverage_core: int = 15  # BTC/ETH
    max_leverage_major: int = 6   # SOL/BNB/XRP
    max_leverage_alt: int = 3     # Other altcoins
    
    # Volatility filters
    max_body_atr_ratio: float = 2.0  # k×ATR for extreme moves
    volatility_threshold: float = 0.05  # 5% daily volatility threshold

@dataclass
class TradingConfig:
    """Trading strategy configuration"""
    # Timeframes
    timeframes: List[str] = None
    
    def __post_init__(self):
        if self.timeframes is None:
            self.timeframes = ["5m", "15m", "1h", "4h"]
    
    # Entry filters
    confirmation_threshold: float = 0.003  # 0.3% confirmation
    pullback_threshold: float = 0.02  # 2% pullback for limit entry
    max_slippage: float = 0.001  # 0.1% max slippage
    
    # Exit strategies
    risk_reward_ratio: float = 1.5  # Minimum R:R
    partial_exit_ratio: float = 0.5  # 50% at R1
    trailing_atr_multiplier: float = 2.0  # k×ATR for trailing
    max_trade_duration_hours: int = 48  # Time-based exit
    
    # Universe selection
    min_daily_volume_usdt: float = 50_000_000  # 50M USDT
    min_spread_percent: float = 0.001  # 0.1% max spread
    min_orderbook_depth_usdt: float = 100_000  # 100K USDT depth

@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    # Simulation settings
    maker_fee: float = 0.0002  # 0.02% maker fee
    taker_fee: float = 0.0004  # 0.04% taker fee
    slippage_model: str = "depth_based"  # depth_based, fixed, stochastic
    
    # Event simulation
    latency_ms: int = 50  # Order latency
    partial_fill_probability: float = 0.3  # 30% chance of partial fill
    max_partial_fills: int = 3
    
    # Funding simulation
    funding_interval_hours: int = 8
    funding_rate_volatility: float = 0.0001  # 0.01% funding rate volatility

@dataclass
class OptimizationConfig:
    """Optimization and validation configuration"""
    # Walk-forward settings
    training_window_days: int = 180  # 6 months
    validation_window_days: int = 90  # 3 months
    step_size_days: int = 30  # 1 month step
    
    # Search parameters
    max_iterations: int = 1000
    population_size: int = 50
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    
    # Penalty weights
    mdd_penalty_weight: float = 2.0
    trade_count_penalty_weight: float = 0.5
    parameter_sensitivity_penalty: float = 1.0

@dataclass
class MonitoringConfig:
    """Monitoring and operations configuration"""
    # Kill switch conditions
    max_daily_drawdown: float = 0.02  # 2% daily drawdown
    max_consecutive_losses: int = 5
    max_slippage_violations: int = 2
    
    # Alerts
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    email_alerts: bool = False
    
    # Health checks
    heartbeat_interval_seconds: int = 30
    reconciliation_interval_seconds: int = 300  # 5 minutes
    max_price_feed_delay_seconds: int = 5

@dataclass
class SystemConfig:
    """Main system configuration"""
    binance: BinanceConfig = BinanceConfig()
    risk: RiskConfig = RiskConfig()
    trading: TradingConfig = TradingConfig()
    backtest: BacktestConfig = BacktestConfig()
    optimization: OptimizationConfig = OptimizationConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    
    # Database
    database_url: str = "sqlite:///trading_system.db"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "trading_system.log"
    
    # Cache settings
    cache_ttl_seconds: int = 300  # 5 minutes
    max_cache_size: int = 1000

# Global configuration instance
config = SystemConfig()

# Symbol classification for leverage tiers
SYMBOL_CLASSIFICATION = {
    "CORE": ["BTCUSDT", "ETHUSDT"],
    "MAJOR": ["SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT"],
    "ALT": []  # Will be populated dynamically
}

# Regime detection parameters
REGIME_PARAMS = {
    "trend_threshold": 25,  # ADX threshold
    "volatility_threshold": 0.05,  # 5% daily volatility
    "hurst_threshold": 0.55,  # Hurst exponent threshold
    "rsi_range_threshold": 30,  # RSI range threshold
}

# Policy matrix for different regimes
REGIME_POLICIES = {
    "trend_low_vol": {
        "strategy": "breakout",
        "leverage_multiplier": 1.0,
        "entry_filter": "standard",
        "trailing_enabled": True
    },
    "trend_high_vol": {
        "strategy": "breakout",
        "leverage_multiplier": 0.7,
        "entry_filter": "conservative",
        "trailing_enabled": True
    },
    "range_low_vol": {
        "strategy": "mean_reversion",
        "leverage_multiplier": 0.8,
        "entry_filter": "standard",
        "trailing_enabled": False
    },
    "range_high_vol": {
        "strategy": "reduced",
        "leverage_multiplier": 0.3,
        "entry_filter": "very_conservative",
        "trailing_enabled": False
    }
}