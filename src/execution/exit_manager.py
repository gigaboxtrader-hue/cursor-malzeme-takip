"""
Exit Manager Module
Handles take profit, stop loss, trailing stops, and exit strategies
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ..config import config

logger = logging.getLogger(__name__)

@dataclass
class ExitStrategy:
    """Exit strategy configuration"""
    symbol: str
    position_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float
    trailing_enabled: bool = False
    trailing_atr_multiplier: float = 2.0
    partial_exit_enabled: bool = False
    partial_exit_ratio: float = 0.5
    partial_exit_target: float = 0.0
    time_based_exit: bool = False
    max_duration_hours: int = 48
    entry_time: datetime = None
    
    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()

@dataclass
class ExitSignal:
    """Exit signal structure"""
    symbol: str
    exit_type: str  # 'TP', 'SL', 'TRAILING', 'TIME', 'MANUAL', 'PARTIAL'
    exit_price: float
    exit_quantity: float
    exit_reason: str
    timestamp: datetime
    pnl: float
    pnl_percentage: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ExitManager:
    """Manages exit strategies and signals"""
    
    def __init__(self):
        self.active_exits: Dict[str, ExitStrategy] = {}
        self.trailing_stops: Dict[str, float] = {}
        self.partial_exits: Dict[str, Dict] = {}
        
    def create_exit_strategy(self, symbol: str, position_type: str, entry_price: float,
                           stop_loss: float, take_profit: float, 
                           trailing_enabled: bool = False) -> ExitStrategy:
        """Create exit strategy for a position"""
        try:
            # Calculate partial exit target (R1)
            if position_type == 'LONG':
                partial_exit_target = entry_price + (take_profit - entry_price) * 0.5
            else:  # SHORT
                partial_exit_target = entry_price - (entry_price - take_profit) * 0.5
            
            strategy = ExitStrategy(
                symbol=symbol,
                position_type=position_type,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_enabled=trailing_enabled,
                trailing_atr_multiplier=config.trading.trailing_atr_multiplier,
                partial_exit_enabled=config.trading.partial_exit_ratio > 0,
                partial_exit_ratio=config.trading.partial_exit_ratio,
                partial_exit_target=partial_exit_target,
                time_based_exit=True,
                max_duration_hours=config.trading.max_trade_duration_hours
            )
            
            self.active_exits[symbol] = strategy
            
            # Initialize trailing stop
            if trailing_enabled:
                self.trailing_stops[symbol] = stop_loss
            
            # Initialize partial exit tracking
            if strategy.partial_exit_enabled:
                self.partial_exits[symbol] = {
                    'executed': False,
                    'quantity': 0,
                    'price': 0
                }
            
            logger.info(f"Created exit strategy for {symbol}: SL={stop_loss:.4f}, TP={take_profit:.4f}")
            return strategy
            
        except Exception as e:
            logger.error(f"Error creating exit strategy for {symbol}: {e}")
            raise
    
    def check_exit_signals(self, symbol: str, current_price: float, 
                          current_quantity: float, atr: float = None) -> List[ExitSignal]:
        """Check for exit signals based on current price"""
        signals = []
        
        if symbol not in self.active_exits:
            return signals
        
        strategy = self.active_exits[symbol]
        
        try:
            # Check stop loss
            sl_signal = self._check_stop_loss(symbol, current_price, current_quantity, strategy)
            if sl_signal:
                signals.append(sl_signal)
                return signals  # Stop loss takes priority
            
            # Check take profit
            tp_signal = self._check_take_profit(symbol, current_price, current_quantity, strategy)
            if tp_signal:
                signals.append(tp_signal)
                return signals  # Take profit takes priority
            
            # Check partial exit
            if strategy.partial_exit_enabled:
                partial_signal = self._check_partial_exit(symbol, current_price, current_quantity, strategy)
                if partial_signal:
                    signals.append(partial_signal)
            
            # Check trailing stop
            if strategy.trailing_enabled and atr:
                trailing_signal = self._check_trailing_stop(symbol, current_price, current_quantity, strategy, atr)
                if trailing_signal:
                    signals.append(trailing_signal)
            
            # Check time-based exit
            time_signal = self._check_time_based_exit(symbol, current_price, current_quantity, strategy)
            if time_signal:
                signals.append(time_signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking exit signals for {symbol}: {e}")
            return signals
    
    def _check_stop_loss(self, symbol: str, current_price: float, 
                        current_quantity: float, strategy: ExitStrategy) -> Optional[ExitSignal]:
        """Check if stop loss is triggered"""
        try:
            if strategy.position_type == 'LONG':
                if current_price <= strategy.stop_loss:
                    pnl = (current_price - strategy.entry_price) * current_quantity
                    pnl_percentage = (current_price - strategy.entry_price) / strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='SL',
                        exit_price=current_price,
                        exit_quantity=current_quantity,
                        exit_reason='Stop Loss triggered',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'original_sl': strategy.stop_loss}
                    )
            
            else:  # SHORT
                if current_price >= strategy.stop_loss:
                    pnl = (strategy.entry_price - current_price) * current_quantity
                    pnl_percentage = (strategy.entry_price - current_price) / strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='SL',
                        exit_price=current_price,
                        exit_quantity=current_quantity,
                        exit_reason='Stop Loss triggered',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'original_sl': strategy.stop_loss}
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking stop loss for {symbol}: {e}")
            return None
    
    def _check_take_profit(self, symbol: str, current_price: float,
                          current_quantity: float, strategy: ExitStrategy) -> Optional[ExitSignal]:
        """Check if take profit is triggered"""
        try:
            if strategy.position_type == 'LONG':
                if current_price >= strategy.take_profit:
                    pnl = (current_price - strategy.entry_price) * current_quantity
                    pnl_percentage = (current_price - strategy.entry_price) / strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='TP',
                        exit_price=current_price,
                        exit_quantity=current_quantity,
                        exit_reason='Take Profit triggered',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'original_tp': strategy.take_profit}
                    )
            
            else:  # SHORT
                if current_price <= strategy.take_profit:
                    pnl = (strategy.entry_price - current_price) * current_quantity
                    pnl_percentage = (strategy.entry_price - current_price) / strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='TP',
                        exit_price=current_price,
                        exit_quantity=current_quantity,
                        exit_reason='Take Profit triggered',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'original_tp': strategy.take_profit}
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking take profit for {symbol}: {e}")
            return None
    
    def _check_partial_exit(self, symbol: str, current_price: float,
                           current_quantity: float, strategy: ExitStrategy) -> Optional[ExitSignal]:
        """Check if partial exit should be executed"""
        try:
            if symbol not in self.partial_exits or self.partial_exits[symbol]['executed']:
                return None
            
            if strategy.position_type == 'LONG':
                if current_price >= strategy.partial_exit_target:
                    exit_quantity = current_quantity * strategy.partial_exit_ratio
                    pnl = (current_price - strategy.entry_price) * exit_quantity
                    pnl_percentage = (current_price - strategy.entry_price) / strategy.entry_price
                    
                    # Mark partial exit as executed
                    self.partial_exits[symbol]['executed'] = True
                    self.partial_exits[symbol]['quantity'] = exit_quantity
                    self.partial_exits[symbol]['price'] = current_price
                    
                    # Update stop loss to break-even
                    strategy.stop_loss = strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='PARTIAL',
                        exit_price=current_price,
                        exit_quantity=exit_quantity,
                        exit_reason='Partial exit at R1 target',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'partial_target': strategy.partial_exit_target}
                    )
            
            else:  # SHORT
                if current_price <= strategy.partial_exit_target:
                    exit_quantity = current_quantity * strategy.partial_exit_ratio
                    pnl = (strategy.entry_price - current_price) * exit_quantity
                    pnl_percentage = (strategy.entry_price - current_price) / strategy.entry_price
                    
                    # Mark partial exit as executed
                    self.partial_exits[symbol]['executed'] = True
                    self.partial_exits[symbol]['quantity'] = exit_quantity
                    self.partial_exits[symbol]['price'] = current_price
                    
                    # Update stop loss to break-even
                    strategy.stop_loss = strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='PARTIAL',
                        exit_price=current_price,
                        exit_quantity=exit_quantity,
                        exit_reason='Partial exit at R1 target',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'partial_target': strategy.partial_exit_target}
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking partial exit for {symbol}: {e}")
            return None
    
    def _check_trailing_stop(self, symbol: str, current_price: float,
                            current_quantity: float, strategy: ExitStrategy, 
                            atr: float) -> Optional[ExitSignal]:
        """Check if trailing stop is triggered"""
        try:
            if not strategy.trailing_enabled:
                return None
            
            # Update trailing stop level
            if strategy.position_type == 'LONG':
                new_trailing_stop = current_price - (strategy.trailing_atr_multiplier * atr)
                
                if symbol in self.trailing_stops:
                    # Only move trailing stop up for long positions
                    if new_trailing_stop > self.trailing_stops[symbol]:
                        self.trailing_stops[symbol] = new_trailing_stop
                        strategy.stop_loss = new_trailing_stop
                        logger.info(f"Updated trailing stop for {symbol}: {new_trailing_stop:.4f}")
                
                # Check if trailing stop is triggered
                if current_price <= self.trailing_stops[symbol]:
                    pnl = (current_price - strategy.entry_price) * current_quantity
                    pnl_percentage = (current_price - strategy.entry_price) / strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='TRAILING',
                        exit_price=current_price,
                        exit_quantity=current_quantity,
                        exit_reason='Trailing stop triggered',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'trailing_stop': self.trailing_stops[symbol]}
                    )
            
            else:  # SHORT
                new_trailing_stop = current_price + (strategy.trailing_atr_multiplier * atr)
                
                if symbol in self.trailing_stops:
                    # Only move trailing stop down for short positions
                    if new_trailing_stop < self.trailing_stops[symbol]:
                        self.trailing_stops[symbol] = new_trailing_stop
                        strategy.stop_loss = new_trailing_stop
                        logger.info(f"Updated trailing stop for {symbol}: {new_trailing_stop:.4f}")
                
                # Check if trailing stop is triggered
                if current_price >= self.trailing_stops[symbol]:
                    pnl = (strategy.entry_price - current_price) * current_quantity
                    pnl_percentage = (strategy.entry_price - current_price) / strategy.entry_price
                    
                    return ExitSignal(
                        symbol=symbol,
                        exit_type='TRAILING',
                        exit_price=current_price,
                        exit_quantity=current_quantity,
                        exit_reason='Trailing stop triggered',
                        timestamp=datetime.now(),
                        pnl=pnl,
                        pnl_percentage=pnl_percentage,
                        metadata={'trailing_stop': self.trailing_stops[symbol]}
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking trailing stop for {symbol}: {e}")
            return None
    
    def _check_time_based_exit(self, symbol: str, current_price: float,
                              current_quantity: float, strategy: ExitStrategy) -> Optional[ExitSignal]:
        """Check if time-based exit should be triggered"""
        try:
            if not strategy.time_based_exit:
                return None
            
            current_time = datetime.now()
            duration = current_time - strategy.entry_time
            max_duration = timedelta(hours=strategy.max_duration_hours)
            
            if duration >= max_duration:
                if strategy.position_type == 'LONG':
                    pnl = (current_price - strategy.entry_price) * current_quantity
                    pnl_percentage = (current_price - strategy.entry_price) / strategy.entry_price
                else:  # SHORT
                    pnl = (strategy.entry_price - current_price) * current_quantity
                    pnl_percentage = (strategy.entry_price - current_price) / strategy.entry_price
                
                return ExitSignal(
                    symbol=symbol,
                    exit_type='TIME',
                    exit_price=current_price,
                    exit_quantity=current_quantity,
                    exit_reason=f'Time-based exit after {duration}',
                    timestamp=current_time,
                    pnl=pnl,
                    pnl_percentage=pnl_percentage,
                    metadata={'duration_hours': duration.total_seconds() / 3600}
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking time-based exit for {symbol}: {e}")
            return None
    
    def manual_exit(self, symbol: str, current_price: float, current_quantity: float,
                   reason: str = "Manual exit") -> Optional[ExitSignal]:
        """Execute manual exit"""
        try:
            if symbol not in self.active_exits:
                logger.warning(f"No active exit strategy for {symbol}")
                return None
            
            strategy = self.active_exits[symbol]
            
            if strategy.position_type == 'LONG':
                pnl = (current_price - strategy.entry_price) * current_quantity
                pnl_percentage = (current_price - strategy.entry_price) / strategy.entry_price
            else:  # SHORT
                pnl = (strategy.entry_price - current_price) * current_quantity
                pnl_percentage = (strategy.entry_price - current_price) / strategy.entry_price
            
            return ExitSignal(
                symbol=symbol,
                exit_type='MANUAL',
                exit_price=current_price,
                exit_quantity=current_quantity,
                exit_reason=reason,
                timestamp=datetime.now(),
                pnl=pnl,
                pnl_percentage=pnl_percentage
            )
            
        except Exception as e:
            logger.error(f"Error executing manual exit for {symbol}: {e}")
            return None
    
    def remove_exit_strategy(self, symbol: str) -> None:
        """Remove exit strategy for a symbol"""
        if symbol in self.active_exits:
            del self.active_exits[symbol]
        
        if symbol in self.trailing_stops:
            del self.trailing_stops[symbol]
        
        if symbol in self.partial_exits:
            del self.partial_exits[symbol]
        
        logger.info(f"Removed exit strategy for {symbol}")
    
    def update_exit_strategy(self, symbol: str, updates: Dict) -> None:
        """Update exit strategy parameters"""
        if symbol in self.active_exits:
            strategy = self.active_exits[symbol]
            
            for key, value in updates.items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)
            
            logger.info(f"Updated exit strategy for {symbol}: {updates}")
    
    def get_active_exits(self) -> Dict[str, ExitStrategy]:
        """Get all active exit strategies"""
        return self.active_exits.copy()
    
    def get_exit_summary(self) -> Dict:
        """Get summary of active exits"""
        summary = {
            'total_active': len(self.active_exits),
            'trailing_enabled': len([s for s in self.active_exits.values() if s.trailing_enabled]),
            'partial_exits_enabled': len([s for s in self.active_exits.values() if s.partial_exits_enabled]),
            'long_positions': len([s for s in self.active_exits.values() if s.position_type == 'LONG']),
            'short_positions': len([s for s in self.active_exits.values() if s.position_type == 'SHORT']),
            'symbols': list(self.active_exits.keys())
        }
        
        return summary

# Global instance
exit_manager = ExitManager()