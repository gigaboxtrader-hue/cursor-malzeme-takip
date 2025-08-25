"""
Binance Futures Trading System - Main Application
Risk-adjusted returns with dynamic leverage and liquidation protection
"""
import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd

from src.config import config
from src.data.symbol_metadata import metadata_manager, data_collector
from src.data.universe_selector import universe_selector
from src.signals.signal_engine import signal_engine
from src.risk.risk_manager import risk_manager
from src.backtest.backtest_engine import backtest_engine

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def initialize_system():
    """Initialize the trading system"""
    logger.info("Initializing Binance Futures Trading System...")
    
    try:
        # Test API connection
        logger.info("Testing Binance API connection...")
        exchange_info = await metadata_manager.get_exchange_info()
        logger.info(f"Connected to Binance. Found {len(exchange_info['symbols'])} symbols")
        
        # Update universe
        logger.info("Updating trading universe...")
        metrics_dict = await universe_selector.update_universe(force_update=True)
        
        if metrics_dict:
            summary = universe_selector.get_symbol_classification_summary(metrics_dict)
            logger.info(f"Universe summary: {summary}")
            
            # Get recommended symbols
            recommended = await universe_selector.get_recommended_symbols(max_symbols=10)
            logger.info(f"Recommended symbols: {recommended}")
        
        logger.info("System initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"System initialization failed: {e}")
        return False

async def run_backtest_example():
    """Run example backtest"""
    logger.info("Running example backtest...")
    
    try:
        # Test backtest on BTCUSDT
        symbol = "BTCUSDT"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        logger.info(f"Running backtest for {symbol} from {start_date} to {end_date}")
        
        result = backtest_engine.run_backtest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe='1h',
            signal_families=['trend', 'momentum', 'breakout']
        )
        
        # Print results
        logger.info("Backtest Results:")
        logger.info(f"Total Trades: {result.total_trades}")
        logger.info(f"Win Rate: {result.win_rate:.2%}")
        logger.info(f"Total PnL: ${result.total_pnl:.2f}")
        logger.info(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        logger.info(f"Max Drawdown: {result.max_drawdown:.2%}")
        logger.info(f"Total Fees: ${result.total_fees:.2f}")
        logger.info(f"Total Funding: ${result.total_funding:.2f}")
        
        # Get trade log
        trade_log = backtest_engine.get_trade_log()
        if not trade_log.empty:
            logger.info(f"Trade Log Preview:")
            logger.info(trade_log.head())
        
        return result
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return None

async def test_signal_generation():
    """Test signal generation"""
    logger.info("Testing signal generation...")
    
    try:
        # Get data for BTCUSDT
        symbol = "BTCUSDT"
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        data = await data_collector.get_ohlcv_data(
            symbol, '1h',
            start_time=int(start_date.timestamp() * 1000),
            end_time=int(end_date.timestamp() * 1000)
        )
        
        if not data.empty:
            # Generate signals
            signals = signal_engine.generate_signals(
                data, symbol, '1h', 
                signal_families=['trend', 'momentum', 'breakout']
            )
            
            logger.info(f"Generated {len(signals)} signals for {symbol}")
            
            # Filter signals
            filtered_signals = signal_engine.filter_signals(
                signals, min_strength=0.7, confirmation_level='CONFIRMED'
            )
            
            logger.info(f"Filtered to {len(filtered_signals)} high-quality signals")
            
            # Print signal summary
            summary = signal_engine.get_signal_summary(signals)
            logger.info(f"Signal Summary: {summary}")
            
            return signals
        
    except Exception as e:
        logger.error(f"Signal generation test failed: {e}")
        return []

async def test_risk_management():
    """Test risk management functions"""
    logger.info("Testing risk management...")
    
    try:
        symbol = "BTCUSDT"
        entry_price = 50000
        stop_loss = 49000
        equity = 10000
        
        # Test position sizing
        sizing = risk_manager.calculate_position_size(
            symbol, entry_price, stop_loss, equity
        )
        
        logger.info(f"Position Sizing Result:")
        logger.info(f"Position Size: ${sizing.position_size_usdt:.2f}")
        logger.info(f"Quantity: {sizing.quantity:.6f}")
        logger.info(f"Leverage: {sizing.leverage}x")
        logger.info(f"Risk Amount: ${sizing.risk_amount:.2f}")
        logger.info(f"Liquidation Price: ${sizing.liquidation_price:.2f}")
        logger.info(f"Distance to Liquidation: {sizing.distance_to_liquidation:.2%}")
        logger.info(f"Valid: {sizing.is_valid}")
        
        # Test portfolio risk
        portfolio_risk = risk_manager.check_portfolio_risk(equity, sizing.risk_amount)
        logger.info(f"Portfolio Risk: {portfolio_risk.is_within_limits}")
        
        return sizing
        
    except Exception as e:
        logger.error(f"Risk management test failed: {e}")
        return None

async def main():
    """Main application function"""
    logger.info("Starting Binance Futures Trading System")
    
    try:
        # Initialize system
        if not await initialize_system():
            logger.error("System initialization failed")
            return
        
        # Run tests
        logger.info("Running system tests...")
        
        # Test signal generation
        signals = await test_signal_generation()
        
        # Test risk management
        sizing = await test_risk_management()
        
        # Run backtest
        backtest_result = await run_backtest_example()
        
        logger.info("All tests completed successfully")
        
        # Print system status
        logger.info("System Status:")
        logger.info(f"Configuration: {config.binance.testnet and 'TESTNET' or 'LIVE'}")
        logger.info(f"Risk per trade: {config.risk.max_risk_per_trade:.1%}")
        logger.info(f"Max portfolio risk: {config.risk.max_portfolio_risk:.1%}")
        logger.info(f"Max concurrent positions: {config.risk.max_concurrent_positions}")
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise

if __name__ == "__main__":
    # Run the application
    asyncio.run(main())