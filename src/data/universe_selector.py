"""
Universe Selector Module
Handles symbol filtering and whitelist management based on volume, liquidity, and spread criteria
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from .symbol_metadata import data_collector, metadata_manager
from ..config import config, SYMBOL_CLASSIFICATION

logger = logging.getLogger(__name__)

@dataclass
class SymbolMetrics:
    """Symbol liquidity and volume metrics"""
    symbol: str
    avg_daily_volume_30d: float
    avg_daily_volume_90d: float
    avg_spread_percent: float
    orderbook_depth_usdt: float
    avg_trades_per_day: int
    price_volatility: float
    classification: str
    is_eligible: bool
    reason: str = ""

class UniverseSelector:
    """Manages symbol universe selection and filtering"""
    
    def __init__(self):
        self.whitelist: Set[str] = set()
        self.blacklist: Set[str] = set()
        self.last_update = None
        self.update_interval = timedelta(hours=6)  # Update every 6 hours
        
    async def calculate_symbol_metrics(self, symbol: str) -> SymbolMetrics:
        """Calculate comprehensive metrics for a symbol"""
        try:
            # Get 24hr ticker for current metrics
            ticker = await data_collector.get_ticker_24hr(symbol)
            
            # Get historical data for volume calculation
            end_time = datetime.now()
            start_time_30d = end_time - timedelta(days=30)
            start_time_90d = end_time - timedelta(days=90)
            
            # Get daily data for volume calculation
            daily_data_30d = await data_collector.get_ohlcv_data(
                symbol, '1d', 
                start_time=int(start_time_30d.timestamp() * 1000),
                end_time=int(end_time.timestamp() * 1000)
            )
            
            daily_data_90d = await data_collector.get_ohlcv_data(
                symbol, '1d',
                start_time=int(start_time_90d.timestamp() * 1000),
                end_time=int(end_time.timestamp() * 1000)
            )
            
            # Calculate volume metrics
            avg_volume_30d = daily_data_30d['quote_volume'].mean() if not daily_data_30d.empty else 0
            avg_volume_90d = daily_data_90d['quote_volume'].mean() if not daily_data_90d.empty else 0
            
            # Calculate spread
            bid_price = float(ticker['bidPrice'])
            ask_price = float(ticker['askPrice'])
            mid_price = (bid_price + ask_price) / 2
            spread_percent = (ask_price - bid_price) / mid_price if mid_price > 0 else float('inf')
            
            # Get orderbook depth
            orderbook = await data_collector.get_orderbook(symbol, limit=20)
            depth_usdt = self._calculate_orderbook_depth(orderbook, mid_price)
            
            # Calculate volatility
            price_volatility = float(ticker['priceChangePercent'])
            
            # Get classification
            classification = metadata_manager.classify_symbol(symbol)
            
            # Determine eligibility
            is_eligible, reason = self._check_eligibility(
                symbol, avg_volume_30d, avg_volume_90d, spread_percent, 
                depth_usdt, price_volatility, classification
            )
            
            return SymbolMetrics(
                symbol=symbol,
                avg_daily_volume_30d=avg_volume_30d,
                avg_daily_volume_90d=avg_volume_90d,
                avg_spread_percent=spread_percent,
                orderbook_depth_usdt=depth_usdt,
                avg_trades_per_day=int(ticker['count']),
                price_volatility=price_volatility,
                classification=classification,
                is_eligible=is_eligible,
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate metrics for {symbol}: {e}")
            return SymbolMetrics(
                symbol=symbol,
                avg_daily_volume_30d=0,
                avg_daily_volume_90d=0,
                avg_spread_percent=float('inf'),
                orderbook_depth_usdt=0,
                avg_trades_per_day=0,
                price_volatility=0,
                classification="UNKNOWN",
                is_eligible=False,
                reason=f"Error: {str(e)}"
            )
    
    def _calculate_orderbook_depth(self, orderbook: Dict, mid_price: float) -> float:
        """Calculate orderbook depth in USDT within 0.1% of mid price"""
        depth_limit = mid_price * 0.001  # 0.1% from mid price
        
        total_depth = 0.0
        
        # Calculate bid depth
        for bid in orderbook['bids']:
            price = float(bid[0])
            quantity = float(bid[1])
            
            if mid_price - price <= depth_limit:
                total_depth += price * quantity
            else:
                break
        
        # Calculate ask depth
        for ask in orderbook['asks']:
            price = float(ask[0])
            quantity = float(ask[1])
            
            if price - mid_price <= depth_limit:
                total_depth += price * quantity
            else:
                break
        
        return total_depth
    
    def _check_eligibility(self, symbol: str, volume_30d: float, volume_90d: float,
                          spread: float, depth: float, volatility: float, 
                          classification: str) -> Tuple[bool, str]:
        """Check if symbol meets eligibility criteria"""
        reasons = []
        
        # Volume criteria
        if volume_30d < config.trading.min_daily_volume_usdt:
            reasons.append(f"30d volume {volume_30d:,.0f} < {config.trading.min_daily_volume_usdt:,.0f}")
        
        if volume_90d < config.trading.min_daily_volume_usdt * 0.8:  # Allow some flexibility for 90d
            reasons.append(f"90d volume {volume_90d:,.0f} < {config.trading.min_daily_volume_usdt * 0.8:,.0f}")
        
        # Spread criteria
        if spread > config.trading.min_spread_percent:
            reasons.append(f"Spread {spread:.4f} > {config.trading.min_spread_percent:.4f}")
        
        # Orderbook depth criteria
        if depth < config.trading.min_orderbook_depth_usdt:
            reasons.append(f"Depth {depth:,.0f} < {config.trading.min_orderbook_depth_usdt:,.0f}")
        
        # Classification-based criteria
        if classification == "ALT":
            # Stricter criteria for altcoins
            if volume_30d < config.trading.min_daily_volume_usdt * 1.5:
                reasons.append(f"ALT: volume {volume_30d:,.0f} < {config.trading.min_daily_volume_usdt * 1.5:,.0f}")
            
            if spread > config.trading.min_spread_percent * 0.5:  # Tighter spread for alts
                reasons.append(f"ALT: spread {spread:.4f} > {config.trading.min_spread_percent * 0.5:.4f}")
        
        # Volatility filter (optional)
        if abs(volatility) > 50:  # 50% daily change is extreme
            reasons.append(f"High volatility: {volatility:.2f}%")
        
        # Manual blacklist check
        if symbol in self.blacklist:
            reasons.append("Symbol in blacklist")
        
        if reasons:
            return False, "; ".join(reasons)
        else:
            return True, "Eligible"
    
    async def update_universe(self, force_update: bool = False) -> Dict[str, SymbolMetrics]:
        """Update the trading universe"""
        current_time = datetime.now()
        
        # Check if update is needed
        if (not force_update and self.last_update and 
            current_time - self.last_update < self.update_interval):
            logger.info("Universe update not needed yet")
            return {}
        
        logger.info("Updating trading universe...")
        
        # Get all USDT symbols
        all_symbols = await metadata_manager.get_all_usdt_symbols()
        logger.info(f"Found {len(all_symbols)} USDT perpetual symbols")
        
        # Calculate metrics for all symbols
        metrics_dict = {}
        tasks = []
        
        for symbol in all_symbols:
            task = self.calculate_symbol_metrics(symbol)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing {all_symbols[i]}: {result}")
                continue
            
            metrics_dict[result.symbol] = result
        
        # Update whitelist
        eligible_symbols = {symbol for symbol, metrics in metrics_dict.items() 
                          if metrics.is_eligible}
        
        # Always include core symbols
        core_symbols = set(SYMBOL_CLASSIFICATION["CORE"])
        eligible_symbols.update(core_symbols)
        
        # Update whitelist
        self.whitelist = eligible_symbols
        self.last_update = current_time
        
        # Log results
        eligible_count = len([m for m in metrics_dict.values() if m.is_eligible])
        logger.info(f"Universe update complete: {eligible_count}/{len(metrics_dict)} symbols eligible")
        
        return metrics_dict
    
    def get_whitelist(self) -> List[str]:
        """Get current whitelist"""
        return list(self.whitelist)
    
    def is_symbol_eligible(self, symbol: str) -> bool:
        """Check if symbol is in whitelist"""
        return symbol in self.whitelist
    
    def add_to_blacklist(self, symbol: str, reason: str = "") -> None:
        """Add symbol to blacklist"""
        self.blacklist.add(symbol)
        if symbol in self.whitelist:
            self.whitelist.remove(symbol)
        logger.warning(f"Added {symbol} to blacklist: {reason}")
    
    def remove_from_blacklist(self, symbol: str) -> None:
        """Remove symbol from blacklist"""
        if symbol in self.blacklist:
            self.blacklist.remove(symbol)
            logger.info(f"Removed {symbol} from blacklist")
    
    def get_universe_report(self, metrics_dict: Dict[str, SymbolMetrics]) -> pd.DataFrame:
        """Generate universe report"""
        if not metrics_dict:
            return pd.DataFrame()
        
        # Convert to DataFrame
        data = []
        for metrics in metrics_dict.values():
            data.append({
                'symbol': metrics.symbol,
                'classification': metrics.classification,
                'avg_volume_30d': metrics.avg_daily_volume_30d,
                'avg_volume_90d': metrics.avg_daily_volume_90d,
                'spread_percent': metrics.avg_spread_percent,
                'orderbook_depth': metrics.orderbook_depth_usdt,
                'trades_per_day': metrics.avg_trades_per_day,
                'volatility': metrics.price_volatility,
                'is_eligible': metrics.is_eligible,
                'reason': metrics.reason
            })
        
        df = pd.DataFrame(data)
        
        # Add formatting
        df['avg_volume_30d'] = df['avg_volume_30d'].apply(lambda x: f"{x:,.0f}")
        df['avg_volume_90d'] = df['avg_volume_90d'].apply(lambda x: f"{x:,.0f}")
        df['spread_percent'] = df['spread_percent'].apply(lambda x: f"{x:.4f}")
        df['orderbook_depth'] = df['orderbook_depth'].apply(lambda x: f"{x:,.0f}")
        df['volatility'] = df['volatility'].apply(lambda x: f"{x:.2f}%")
        
        return df.sort_values(['classification', 'avg_volume_30d'], ascending=[True, False])
    
    async def get_recommended_symbols(self, max_symbols: int = 20) -> List[str]:
        """Get recommended symbols for trading"""
        # Update universe if needed
        metrics_dict = await self.update_universe()
        
        if not metrics_dict:
            return []
        
        # Filter eligible symbols
        eligible_metrics = [m for m in metrics_dict.values() if m.is_eligible]
        
        # Sort by priority: Core > Major > Alt, then by volume
        def sort_key(metrics):
            priority = {"CORE": 3, "MAJOR": 2, "ALT": 1}
            return (priority.get(metrics.classification, 0), metrics.avg_daily_volume_30d)
        
        eligible_metrics.sort(key=sort_key, reverse=True)
        
        # Return top symbols
        return [m.symbol for m in eligible_metrics[:max_symbols]]
    
    def get_symbol_classification_summary(self, metrics_dict: Dict[str, SymbolMetrics]) -> Dict:
        """Get summary by symbol classification"""
        summary = {
            "CORE": {"total": 0, "eligible": 0, "avg_volume": 0},
            "MAJOR": {"total": 0, "eligible": 0, "avg_volume": 0},
            "ALT": {"total": 0, "eligible": 0, "avg_volume": 0}
        }
        
        for metrics in metrics_dict.values():
            classification = metrics.classification
            if classification in summary:
                summary[classification]["total"] += 1
                if metrics.is_eligible:
                    summary[classification]["eligible"] += 1
                    summary[classification]["avg_volume"] += metrics.avg_daily_volume_30d
        
        # Calculate averages
        for classification in summary:
            if summary[classification]["eligible"] > 0:
                summary[classification]["avg_volume"] /= summary[classification]["eligible"]
        
        return summary

# Global instance
universe_selector = UniverseSelector()