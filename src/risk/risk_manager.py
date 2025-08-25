"""
Risk Manager Module
Handles position sizing, dynamic leverage, and liquidation protection
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime

from ..config import config
from ..data.symbol_metadata import metadata_manager

logger = logging.getLogger(__name__)

@dataclass
class PositionSizing:
    """Position sizing calculation result"""
    symbol: str
    entry_price: float
    stop_loss: float
    position_size_usdt: float
    quantity: float
    leverage: int
    risk_amount: float
    risk_percentage: float
    liquidation_price: float
    distance_to_liquidation: float
    is_valid: bool
    reason: str = ""

@dataclass
class PortfolioRisk:
    """Portfolio risk metrics"""
    total_equity: float
    total_margin_used: float
    total_unrealized_pnl: float
    total_risk_exposure: float
    max_concurrent_positions: int
    current_positions: int
    risk_percentage: float
    margin_ratio: float
    is_within_limits: bool

class RiskManager:
    """Main risk management engine"""
    
    def __init__(self):
        self.current_positions: Dict[str, Dict] = {}
        self.daily_pnl = 0.0
        self.daily_risk_used = 0.0
        self.consecutive_losses = 0
        
    def calculate_position_size(self, symbol: str, entry_price: float, stop_loss: float,
                              equity: float, risk_percentage: float = None) -> PositionSizing:
        """Calculate position size based on risk parameters"""
        try:
            if risk_percentage is None:
                risk_percentage = config.risk.max_risk_per_trade
            
            # Get symbol metadata
            metadata = metadata_manager.get_symbol_metadata(symbol)
            
            # Calculate risk amount
            risk_amount = equity * risk_percentage
            
            # Calculate stop loss distance
            if entry_price > stop_loss:  # Long position
                sl_distance = entry_price - stop_loss
                position_direction = "LONG"
            else:  # Short position
                sl_distance = stop_loss - entry_price
                position_direction = "SHORT"
            
            # Calculate position size
            position_size_usdt = risk_amount / (sl_distance / entry_price)
            
            # Calculate quantity
            quantity = position_size_usdt / entry_price
            
            # Round quantity to step size
            step_size = metadata.step_size
            quantity = round(quantity / step_size) * step_size
            
            # Recalculate position size with rounded quantity
            position_size_usdt = quantity * entry_price
            
            # Calculate effective leverage
            effective_leverage = position_size_usdt / equity
            
            # Get maximum allowed leverage for symbol
            max_leverage = metadata_manager.get_max_leverage_for_symbol(symbol)
            
            # Adjust leverage if needed
            leverage = min(int(effective_leverage), max_leverage)
            
            # Recalculate position size with adjusted leverage
            if leverage < effective_leverage:
                position_size_usdt = equity * leverage
                quantity = position_size_usdt / entry_price
                quantity = round(quantity / step_size) * step_size
                position_size_usdt = quantity * entry_price
            
            # Calculate liquidation price
            liquidation_price = self._calculate_liquidation_price(
                symbol, entry_price, position_direction, leverage, position_size_usdt
            )
            
            # Calculate distance to liquidation
            if position_direction == "LONG":
                distance_to_liquidation = (entry_price - liquidation_price) / entry_price
            else:
                distance_to_liquidation = (liquidation_price - entry_price) / entry_price
            
            # Validate liquidation buffer
            is_valid, reason = self._validate_liquidation_buffer(
                symbol, entry_price, stop_loss, liquidation_price, distance_to_liquidation
            )
            
            return PositionSizing(
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                position_size_usdt=position_size_usdt,
                quantity=quantity,
                leverage=leverage,
                risk_amount=risk_amount,
                risk_percentage=risk_percentage,
                liquidation_price=liquidation_price,
                distance_to_liquidation=distance_to_liquidation,
                is_valid=is_valid,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"Error calculating position size for {symbol}: {e}")
            return PositionSizing(
                symbol=symbol,
                entry_price=entry_price,
                stop_loss=stop_loss,
                position_size_usdt=0,
                quantity=0,
                leverage=0,
                risk_amount=0,
                risk_percentage=risk_percentage or 0,
                liquidation_price=0,
                distance_to_liquidation=0,
                is_valid=False,
                reason=f"Error: {str(e)}"
            )
    
    def _calculate_liquidation_price(self, symbol: str, entry_price: float, 
                                   direction: str, leverage: int, 
                                   position_size_usdt: float) -> float:
        """Calculate liquidation price for a position"""
        try:
            metadata = metadata_manager.get_symbol_metadata(symbol)
            
            # Get maintenance margin rate
            maintenance_margin = metadata.get_maintenance_margin(leverage, position_size_usdt)
            
            if maintenance_margin == 0:
                # Fallback calculation
                maintenance_margin = 0.004  # 0.4% default
            
            # Calculate liquidation price
            if direction == "LONG":
                liquidation_price = entry_price * (1 - 1/leverage + maintenance_margin)
            else:  # SHORT
                liquidation_price = entry_price * (1 + 1/leverage - maintenance_margin)
            
            return liquidation_price
            
        except Exception as e:
            logger.error(f"Error calculating liquidation price: {e}")
            # Fallback calculation
            if direction == "LONG":
                return entry_price * 0.9  # 10% buffer
            else:
                return entry_price * 1.1  # 10% buffer
    
    def _validate_liquidation_buffer(self, symbol: str, entry_price: float, 
                                   stop_loss: float, liquidation_price: float,
                                   distance_to_liquidation: float) -> Tuple[bool, str]:
        """Validate liquidation buffer requirements"""
        try:
            # Get current ATR for volatility-based buffer
            # This would typically come from market data
            atr = entry_price * 0.02  # 2% default ATR
            
            # Calculate required buffer
            required_buffer_atr = config.risk.liquidation_buffer_atr_multiplier * atr / entry_price
            required_buffer_percent = config.risk.liquidation_buffer_percent
            
            required_buffer = max(required_buffer_atr, required_buffer_percent)
            
            # Check if distance to liquidation meets requirements
            if distance_to_liquidation < required_buffer:
                return False, f"Distance to liquidation {distance_to_liquidation:.4f} < required {required_buffer:.4f}"
            
            # Check stop loss distance from liquidation
            if entry_price > stop_loss:  # Long position
                sl_distance_from_liq = (stop_loss - liquidation_price) / entry_price
            else:  # Short position
                sl_distance_from_liq = (liquidation_price - stop_loss) / entry_price
            
            required_sl_buffer = config.risk.sl_liquidation_buffer_atr * atr / entry_price
            
            if sl_distance_from_liq < required_sl_buffer:
                return False, f"Stop loss too close to liquidation: {sl_distance_from_liq:.4f} < {required_sl_buffer:.4f}"
            
            return True, "Valid"
            
        except Exception as e:
            logger.error(f"Error validating liquidation buffer: {e}")
            return False, f"Validation error: {str(e)}"
    
    def adjust_position_for_volatility(self, sizing: PositionSizing, 
                                     volatility_percentile: float) -> PositionSizing:
        """Adjust position size based on volatility"""
        try:
            # Reduce leverage for high volatility
            if volatility_percentile > 0.8:  # Top 20% volatility
                reduction_factor = 0.7
            elif volatility_percentile > 0.6:  # Top 40% volatility
                reduction_factor = 0.85
            else:
                reduction_factor = 1.0
            
            # Apply reduction
            new_position_size = sizing.position_size_usdt * reduction_factor
            new_quantity = new_position_size / sizing.entry_price
            
            # Recalculate with new size
            return self.calculate_position_size(
                sizing.symbol, sizing.entry_price, sizing.stop_loss,
                new_position_size, sizing.risk_percentage
            )
            
        except Exception as e:
            logger.error(f"Error adjusting position for volatility: {e}")
            return sizing
    
    def check_portfolio_risk(self, equity: float, new_position_risk: float = 0) -> PortfolioRisk:
        """Check portfolio risk limits"""
        try:
            # Calculate current portfolio metrics
            total_margin_used = sum(pos.get('margin_used', 0) for pos in self.current_positions.values())
            total_unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in self.current_positions.values())
            
            # Calculate total risk exposure
            total_risk_exposure = sum(pos.get('risk_amount', 0) for pos in self.current_positions.values())
            total_risk_exposure += new_position_risk
            
            # Calculate risk percentage
            risk_percentage = total_risk_exposure / equity if equity > 0 else 0
            
            # Calculate margin ratio
            margin_ratio = total_margin_used / equity if equity > 0 else 0
            
            # Check limits
            is_within_limits = (
                risk_percentage <= config.risk.max_portfolio_risk and
                len(self.current_positions) < config.risk.max_concurrent_positions and
                margin_ratio < 0.8  # 80% margin usage limit
            )
            
            return PortfolioRisk(
                total_equity=equity,
                total_margin_used=total_margin_used,
                total_unrealized_pnl=total_unrealized_pnl,
                total_risk_exposure=total_risk_exposure,
                max_concurrent_positions=config.risk.max_concurrent_positions,
                current_positions=len(self.current_positions),
                risk_percentage=risk_percentage,
                margin_ratio=margin_ratio,
                is_within_limits=is_within_limits
            )
            
        except Exception as e:
            logger.error(f"Error checking portfolio risk: {e}")
            return PortfolioRisk(
                total_equity=equity,
                total_margin_used=0,
                total_unrealized_pnl=0,
                total_risk_exposure=0,
                max_concurrent_positions=config.risk.max_concurrent_positions,
                current_positions=0,
                risk_percentage=0,
                margin_ratio=0,
                is_within_limits=False
            )
    
    def add_position(self, symbol: str, position_data: Dict) -> None:
        """Add position to tracking"""
        self.current_positions[symbol] = position_data
    
    def remove_position(self, symbol: str) -> None:
        """Remove position from tracking"""
        if symbol in self.current_positions:
            del self.current_positions[symbol]
    
    def update_position(self, symbol: str, updates: Dict) -> None:
        """Update position data"""
        if symbol in self.current_positions:
            self.current_positions[symbol].update(updates)
    
    def check_daily_limits(self, daily_pnl: float, daily_risk: float) -> Tuple[bool, str]:
        """Check daily risk and PnL limits"""
        # Check daily drawdown
        if daily_pnl < -config.monitoring.max_daily_drawdown:
            return False, f"Daily drawdown limit exceeded: {daily_pnl:.2%}"
        
        # Check consecutive losses
        if self.consecutive_losses >= config.monitoring.max_consecutive_losses:
            return False, f"Max consecutive losses reached: {self.consecutive_losses}"
        
        return True, "Within limits"
    
    def calculate_dynamic_leverage(self, symbol: str, volatility: float, 
                                 market_regime: str) -> int:
        """Calculate dynamic leverage based on market conditions"""
        try:
            # Base leverage from symbol classification
            base_leverage = metadata_manager.get_max_leverage_for_symbol(symbol)
            
            # Volatility adjustment
            if volatility > 0.1:  # High volatility
                volatility_multiplier = 0.5
            elif volatility > 0.05:  # Medium volatility
                volatility_multiplier = 0.8
            else:  # Low volatility
                volatility_multiplier = 1.0
            
            # Market regime adjustment
            regime_multipliers = {
                'trend_low_vol': 1.0,
                'trend_high_vol': 0.7,
                'range_low_vol': 0.8,
                'range_high_vol': 0.3
            }
            
            regime_multiplier = regime_multipliers.get(market_regime, 0.8)
            
            # Calculate final leverage
            final_leverage = int(base_leverage * volatility_multiplier * regime_multiplier)
            
            # Ensure minimum leverage
            final_leverage = max(final_leverage, 1)
            
            return final_leverage
            
        except Exception as e:
            logger.error(f"Error calculating dynamic leverage: {e}")
            return 1  # Conservative default
    
    def get_risk_report(self) -> Dict:
        """Generate risk report"""
        try:
            total_positions = len(self.current_positions)
            total_risk = sum(pos.get('risk_amount', 0) for pos in self.current_positions.values())
            
            # Calculate average distance to liquidation
            distances = []
            for pos in self.current_positions.values():
                if 'distance_to_liquidation' in pos:
                    distances.append(pos['distance_to_liquidation'])
            
            avg_distance_to_liq = np.mean(distances) if distances else 0
            
            return {
                'total_positions': total_positions,
                'total_risk_exposure': total_risk,
                'consecutive_losses': self.consecutive_losses,
                'daily_pnl': self.daily_pnl,
                'daily_risk_used': self.daily_risk_used,
                'avg_distance_to_liquidation': avg_distance_to_liq,
                'positions': list(self.current_positions.keys())
            }
            
        except Exception as e:
            logger.error(f"Error generating risk report: {e}")
            return {}
    
    def reset_daily_metrics(self) -> None:
        """Reset daily risk metrics"""
        self.daily_pnl = 0.0
        self.daily_risk_used = 0.0
    
    def update_consecutive_losses(self, trade_pnl: float) -> None:
        """Update consecutive losses counter"""
        if trade_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

# Global instance
risk_manager = RiskManager()