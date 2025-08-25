"""
Backtest Engine Module
Event-driven simulation with realistic fee, funding, and slippage modeling
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio

from ..config import config
from ..data.symbol_metadata import data_collector
from ..signals.signal_engine import signal_engine
from ..risk.risk_manager import risk_manager
from ..execution.exit_manager import exit_manager

logger = logging.getLogger(__name__)

@dataclass
class BacktestTrade:
    """Individual trade record"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    position_type: str  # 'LONG' or 'SHORT'
    pnl: float
    pnl_percentage: float
    fees: float
    funding_costs: float
    slippage: float
    exit_reason: str
    signal_strength: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class BacktestResult:
    """Backtest results summary"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_fees: float
    total_funding: float
    total_slippage: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    avg_trade_duration: timedelta
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_consecutive_losses: int
    trades: List[BacktestTrade]
    equity_curve: pd.DataFrame
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class BacktestEngine:
    """Main backtesting engine"""
    
    def __init__(self, initial_equity: float = 10000):
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        self.trades: List[BacktestTrade] = []
        self.equity_curve = []
        self.current_positions: Dict[str, Dict] = {}
        self.funding_payments = []
        
    def run_backtest(self, symbol: str, start_date: datetime, end_date: datetime,
                    timeframe: str = '1h', signal_families: List[str] = None) -> BacktestResult:
        """Run backtest for a single symbol"""
        try:
            logger.info(f"Starting backtest for {symbol} from {start_date} to {end_date}")
            
            # Get historical data
            data = asyncio.run(data_collector.get_ohlcv_data(
                symbol, timeframe, 
                start_time=int(start_date.timestamp() * 1000),
                end_time=int(end_date.timestamp() * 1000)
            ))
            
            if data.empty:
                logger.warning(f"No data available for {symbol}")
                return self._create_empty_result()
            
            # Calculate technical indicators
            data = signal_engine.calculate_technical_indicators(data)
            
            # Initialize equity tracking
            self.current_equity = self.initial_equity
            self.equity_curve = []
            self.trades = []
            self.current_positions = {}
            
            # Process each bar
            for i in range(len(data)):
                current_bar = data.iloc[i]
                current_time = current_bar.name
                
                # Update equity curve
                self.equity_curve.append({
                    'timestamp': current_time,
                    'equity': self.current_equity,
                    'open_positions': len(self.current_positions)
                })
                
                # Check for exit signals on existing positions
                self._check_exits(symbol, current_bar)
                
                # Generate new signals
                if i > 0:  # Skip first bar for signal generation
                    signals = signal_engine.generate_signals(
                        data.iloc[:i+1], symbol, timeframe, signal_families
                    )
                    
                    # Filter signals
                    filtered_signals = signal_engine.filter_signals(
                        signals, min_strength=0.7, confirmation_level='CONFIRMED'
                    )
                    
                    # Execute signals
                    for signal in filtered_signals:
                        if symbol not in self.current_positions:
                            self._execute_signal(signal, current_bar)
                
                # Apply funding costs
                self._apply_funding_costs(symbol, current_time)
            
            # Close any remaining positions
            self._close_all_positions(data.iloc[-1])
            
            # Calculate results
            return self._calculate_results()
            
        except Exception as e:
            logger.error(f"Error running backtest for {symbol}: {e}")
            return self._create_empty_result()
    
    def _execute_signal(self, signal, current_bar):
        """Execute a trading signal"""
        try:
            symbol = signal.symbol
            current_price = current_bar['close']
            
            # Calculate position size
            sizing = risk_manager.calculate_position_size(
                symbol, signal.entry_price, signal.stop_loss,
                self.current_equity, config.risk.max_risk_per_trade
            )
            
            if not sizing.is_valid:
                logger.warning(f"Position sizing invalid for {symbol}: {sizing.reason}")
                return
            
            # Check portfolio risk
            portfolio_risk = risk_manager.check_portfolio_risk(
                self.current_equity, sizing.risk_amount
            )
            
            if not portfolio_risk.is_within_limits:
                logger.warning(f"Portfolio risk limit exceeded for {symbol}")
                return
            
            # Calculate slippage
            slippage = self._calculate_slippage(symbol, current_price, sizing.quantity)
            
            # Calculate fees
            fees = self._calculate_fees(sizing.position_size_usdt)
            
            # Execute entry
            entry_price = current_price + slippage if signal.signal_type == 'LONG' else current_price - slippage
            
            # Record position
            self.current_positions[symbol] = {
                'entry_time': current_bar.name,
                'entry_price': entry_price,
                'quantity': sizing.quantity,
                'position_type': signal.signal_type,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'fees_paid': fees,
                'slippage': slippage,
                'signal_strength': signal.signal_strength
            }
            
            # Create exit strategy
            exit_manager.create_exit_strategy(
                symbol, signal.signal_type, entry_price,
                signal.stop_loss, signal.take_profit,
                trailing_enabled=True
            )
            
            # Update equity
            self.current_equity -= fees
            
            logger.info(f"Opened {signal.signal_type} position in {symbol} at {entry_price:.4f}")
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
    
    def _check_exits(self, symbol: str, current_bar):
        """Check for exit signals"""
        if symbol not in self.current_positions:
            return
        
        position = self.current_positions[symbol]
        current_price = current_bar['close']
        current_quantity = position['quantity']
        atr = current_bar.get('atr', current_price * 0.02)  # Default ATR
        
        # Check exit signals
        exit_signals = exit_manager.check_exit_signals(
            symbol, current_price, current_quantity, atr
        )
        
        for exit_signal in exit_signals:
            self._execute_exit(exit_signal, current_bar)
    
    def _execute_exit(self, exit_signal, current_bar):
        """Execute an exit signal"""
        try:
            symbol = exit_signal.symbol
            position = self.current_positions[symbol]
            
            # Calculate slippage
            slippage = self._calculate_slippage(symbol, current_bar['close'], exit_signal.exit_quantity)
            
            # Calculate fees
            fees = self._calculate_fees(exit_signal.exit_price * exit_signal.exit_quantity)
            
            # Calculate funding costs
            funding_costs = self._calculate_funding_costs(symbol, position['entry_time'], current_bar.name)
            
            # Calculate final exit price
            if position['position_type'] == 'LONG':
                exit_price = current_bar['close'] - slippage
            else:
                exit_price = current_bar['close'] + slippage
            
            # Calculate PnL
            if position['position_type'] == 'LONG':
                pnl = (exit_price - position['entry_price']) * exit_signal.exit_quantity
            else:
                pnl = (position['entry_price'] - exit_price) * exit_signal.exit_quantity
            
            # Create trade record
            trade = BacktestTrade(
                symbol=symbol,
                entry_time=position['entry_time'],
                exit_time=current_bar.name,
                entry_price=position['entry_price'],
                exit_price=exit_price,
                quantity=exit_signal.exit_quantity,
                position_type=position['position_type'],
                pnl=pnl,
                pnl_percentage=pnl / (position['entry_price'] * exit_signal.exit_quantity),
                fees=position['fees_paid'] + fees,
                funding_costs=funding_costs,
                slippage=position['slippage'] + slippage,
                exit_reason=exit_signal.exit_reason,
                signal_strength=position['signal_strength'],
                metadata={
                    'exit_type': exit_signal.exit_type,
                    'atr': current_bar.get('atr', 0)
                }
            )
            
            self.trades.append(trade)
            
            # Update equity
            self.current_equity += pnl - fees - funding_costs
            
            # Remove position
            del self.current_positions[symbol]
            exit_manager.remove_exit_strategy(symbol)
            
            logger.info(f"Closed {position['position_type']} position in {symbol} at {exit_price:.4f}, PnL: {pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error executing exit: {e}")
    
    def _calculate_slippage(self, symbol: str, price: float, quantity: float) -> float:
        """Calculate slippage based on order size and market conditions"""
        try:
            # Base slippage model (simplified)
            # In reality, this would depend on orderbook depth and volatility
            
            # Get symbol metadata for tick size
            metadata = data_collector.metadata_manager.get_symbol_metadata(symbol)
            tick_size = metadata.tick_size
            
            # Calculate slippage based on quantity and price
            # Larger orders = more slippage
            slippage_factor = min(quantity * price / 1000000, 0.001)  # Max 0.1%
            
            # Add some randomness
            random_factor = np.random.normal(1, 0.2)
            slippage = slippage_factor * random_factor * tick_size
            
            return max(slippage, tick_size)  # Minimum one tick
            
        except Exception as e:
            logger.error(f"Error calculating slippage: {e}")
            return price * 0.0001  # 0.01% default
    
    def _calculate_fees(self, notional_value: float) -> float:
        """Calculate trading fees"""
        # Use maker fee for backtesting (assuming limit orders)
        return notional_value * config.backtest.maker_fee
    
    def _calculate_funding_costs(self, symbol: str, entry_time: datetime, 
                               current_time: datetime) -> float:
        """Calculate funding costs for the period"""
        try:
            # Simplified funding calculation
            # In reality, this would use actual funding rates
            
            duration_hours = (current_time - entry_time).total_seconds() / 3600
            funding_intervals = duration_hours / config.backtest.funding_interval_hours
            
            # Assume average funding rate of 0.01% per 8 hours
            avg_funding_rate = 0.0001
            
            # Get position size
            if symbol in self.current_positions:
                position = self.current_positions[symbol]
                position_value = position['entry_price'] * position['quantity']
                funding_cost = position_value * avg_funding_rate * funding_intervals
                return funding_cost
            
            return 0
            
        except Exception as e:
            logger.error(f"Error calculating funding costs: {e}")
            return 0
    
    def _apply_funding_costs(self, symbol: str, current_time: datetime):
        """Apply funding costs to current positions"""
        if symbol in self.current_positions:
            funding_cost = self._calculate_funding_costs(
                symbol, self.current_positions[symbol]['entry_time'], current_time
            )
            self.current_equity -= funding_cost
    
    def _close_all_positions(self, last_bar):
        """Close all remaining positions at the end of backtest"""
        for symbol in list(self.current_positions.keys()):
            position = self.current_positions[symbol]
            
            # Create exit signal for manual close
            exit_signal = exit_manager.manual_exit(
                symbol, last_bar['close'], position['quantity'], "Backtest end"
            )
            
            if exit_signal:
                self._execute_exit(exit_signal, last_bar)
    
    def _calculate_results(self) -> BacktestResult:
        """Calculate backtest results"""
        try:
            if not self.trades:
                return self._create_empty_result()
            
            # Basic statistics
            total_trades = len(self.trades)
            winning_trades = len([t for t in self.trades if t.pnl > 0])
            losing_trades = len([t for t in self.trades if t.pnl < 0])
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            # PnL statistics
            total_pnl = sum(t.pnl for t in self.trades)
            total_fees = sum(t.fees for t in self.trades)
            total_funding = sum(t.funding_costs for t in self.trades)
            total_slippage = sum(t.slippage for t in self.trades)
            
            # Calculate equity curve
            equity_df = pd.DataFrame(self.equity_curve)
            equity_df.set_index('timestamp', inplace=True)
            
            # Calculate drawdown
            equity_df['peak'] = equity_df['equity'].expanding().max()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']
            max_drawdown = equity_df['drawdown'].min()
            
            # Calculate returns
            equity_df['returns'] = equity_df['equity'].pct_change()
            
            # Risk metrics
            avg_return = equity_df['returns'].mean()
            std_return = equity_df['returns'].std()
            
            sharpe_ratio = avg_return / std_return * np.sqrt(252) if std_return > 0 else 0
            
            # Sortino ratio (downside deviation)
            downside_returns = equity_df['returns'][equity_df['returns'] < 0]
            downside_std = downside_returns.std()
            sortino_ratio = avg_return / downside_std * np.sqrt(252) if downside_std > 0 else 0
            
            # Calmar ratio
            calmar_ratio = (total_pnl / self.initial_equity) / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Trade statistics
            avg_trade_duration = np.mean([
                (t.exit_time - t.entry_time).total_seconds() / 3600 
                for t in self.trades
            ])
            
            winning_trades_list = [t for t in self.trades if t.pnl > 0]
            losing_trades_list = [t for t in self.trades if t.pnl < 0]
            
            avg_win = np.mean([t.pnl for t in winning_trades_list]) if winning_trades_list else 0
            avg_loss = np.mean([t.pnl for t in losing_trades_list]) if losing_trades_list else 0
            
            profit_factor = abs(avg_win * len(winning_trades_list) / (avg_loss * len(losing_trades_list))) if avg_loss != 0 else float('inf')
            
            # Consecutive losses
            consecutive_losses = 0
            max_consecutive_losses = 0
            for trade in self.trades:
                if trade.pnl < 0:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                else:
                    consecutive_losses = 0
            
            return BacktestResult(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                total_fees=total_fees,
                total_funding=total_funding,
                total_slippage=total_slippage,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                avg_trade_duration=timedelta(hours=avg_trade_duration),
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                max_consecutive_losses=max_consecutive_losses,
                trades=self.trades,
                equity_curve=equity_df,
                metadata={
                    'initial_equity': self.initial_equity,
                    'final_equity': self.current_equity,
                    'total_return': (self.current_equity - self.initial_equity) / self.initial_equity
                }
            )
            
        except Exception as e:
            logger.error(f"Error calculating results: {e}")
            return self._create_empty_result()
    
    def _create_empty_result(self) -> BacktestResult:
        """Create empty result when no trades"""
        return BacktestResult(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            total_pnl=0,
            total_fees=0,
            total_funding=0,
            total_slippage=0,
            max_drawdown=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            avg_trade_duration=timedelta(),
            avg_win=0,
            avg_loss=0,
            profit_factor=0,
            max_consecutive_losses=0,
            trades=[],
            equity_curve=pd.DataFrame(),
            metadata={'initial_equity': self.initial_equity, 'final_equity': self.initial_equity}
        )
    
    def get_trade_log(self) -> pd.DataFrame:
        """Get detailed trade log"""
        if not self.trades:
            return pd.DataFrame()
        
        data = []
        for trade in self.trades:
            data.append({
                'symbol': trade.symbol,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'quantity': trade.quantity,
                'position_type': trade.position_type,
                'pnl': trade.pnl,
                'pnl_percentage': trade.pnl_percentage,
                'fees': trade.fees,
                'funding_costs': trade.funding_costs,
                'slippage': trade.slippage,
                'exit_reason': trade.exit_reason,
                'signal_strength': trade.signal_strength,
                'duration_hours': (trade.exit_time - trade.entry_time).total_seconds() / 3600
            })
        
        return pd.DataFrame(data)

# Global instance
backtest_engine = BacktestEngine()