"""
Signal Engine Module
Handles multiple signal families, entry filters, and confirmation logic
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
from datetime import datetime

import ta
from ta.trend import EMAIndicator, SMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice

from ..config import config

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    """Signal structure"""
    symbol: str
    timeframe: str
    signal_type: str  # 'LONG', 'SHORT'
    signal_strength: float  # 0-1
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: datetime
    confirmation_level: str  # 'TRIGGER', 'CONFIRMED', 'STRONG'
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class SignalFilter:
    """Signal filter configuration"""
    volatility_filter: bool = True
    confirmation_required: bool = True
    extreme_move_filter: bool = True
    min_signal_strength: float = 0.6
    max_body_atr_ratio: float = 2.0
    confirmation_threshold: float = 0.003

class SignalEngine:
    """Main signal generation and filtering engine"""
    
    def __init__(self):
        self.filters = SignalFilter()
        self.signal_generators = {
            'trend': self._generate_trend_signals,
            'momentum': self._generate_momentum_signals,
            'breakout': self._generate_breakout_signals,
            'mean_reversion': self._generate_mean_reversion_signals,
            'volatility': self._generate_volatility_signals
        }
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators"""
        if df.empty:
            return df
        
        # Trend indicators
        df['ema_20'] = EMAIndicator(close=df['close'], window=20).ema_indicator()
        df['ema_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['sma_20'] = SMAIndicator(close=df['close'], window=20).sma_indicator()
        df['sma_50'] = SMAIndicator(close=df['close'], window=50).sma_indicator()
        
        # ADX for trend strength
        df['adx'] = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx()
        
        # Momentum indicators
        df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        # MACD
        macd = MACD(close=df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_histogram'] = macd.macd_diff()
        
        # Volatility indicators
        df['atr'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
        
        # Bollinger Bands
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Volume indicators
        df['vwap'] = VolumeWeightedAveragePrice(high=df['high'], low=df['low'], close=df['close'], volume=df['volume']).volume_weighted_average_price()
        
        # Price action
        df['body_size'] = abs(df['close'] - df['open'])
        df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
        df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
        df['body_atr_ratio'] = df['body_size'] / df['atr']
        
        # Support/Resistance levels (simplified)
        df['support'] = df['low'].rolling(window=20).min()
        df['resistance'] = df['high'].rolling(window=20).max()
        
        return df
    
    def _generate_trend_signals(self, df: pd.DataFrame, symbol: str, timeframe: str) -> List[Signal]:
        """Generate trend-following signals"""
        signals = []
        
        if len(df) < 50:
            return signals
        
        # EMA crossover signals
        df['ema_cross'] = np.where(df['ema_20'] > df['ema_50'], 1, -1)
        df['ema_cross_change'] = df['ema_cross'].diff()
        
        # Look for crossover signals
        for i in range(1, len(df)):
            if df['ema_cross_change'].iloc[i] == 2:  # Bullish crossover
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'LONG', 'trend_ema_cross',
                    strength=min(df['adx'].iloc[i] / 100, 1.0) if not pd.isna(df['adx'].iloc[i]) else 0.7
                )
                if signal:
                    signals.append(signal)
            
            elif df['ema_cross_change'].iloc[i] == -2:  # Bearish crossover
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'SHORT', 'trend_ema_cross',
                    strength=min(df['adx'].iloc[i] / 100, 1.0) if not pd.isna(df['adx'].iloc[i]) else 0.7
                )
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _generate_momentum_signals(self, df: pd.DataFrame, symbol: str, timeframe: str) -> List[Signal]:
        """Generate momentum-based signals"""
        signals = []
        
        if len(df) < 30:
            return signals
        
        # RSI signals
        for i in range(1, len(df)):
            rsi = df['rsi'].iloc[i]
            prev_rsi = df['rsi'].iloc[i-1]
            
            # RSI oversold bounce
            if prev_rsi < 30 and rsi > 30:
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'LONG', 'momentum_rsi_oversold',
                    strength=0.8
                )
                if signal:
                    signals.append(signal)
            
            # RSI overbought rejection
            elif prev_rsi > 70 and rsi < 70:
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'SHORT', 'momentum_rsi_overbought',
                    strength=0.8
                )
                if signal:
                    signals.append(signal)
        
        # MACD signals
        for i in range(1, len(df)):
            macd = df['macd'].iloc[i]
            macd_signal = df['macd_signal'].iloc[i]
            prev_macd = df['macd'].iloc[i-1]
            prev_macd_signal = df['macd_signal'].iloc[i-1]
            
            # MACD bullish crossover
            if (prev_macd < prev_macd_signal and macd > macd_signal):
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'LONG', 'momentum_macd_bullish',
                    strength=0.7
                )
                if signal:
                    signals.append(signal)
            
            # MACD bearish crossover
            elif (prev_macd > prev_macd_signal and macd < macd_signal):
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'SHORT', 'momentum_macd_bearish',
                    strength=0.7
                )
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _generate_breakout_signals(self, df: pd.DataFrame, symbol: str, timeframe: str) -> List[Signal]:
        """Generate breakout signals"""
        signals = []
        
        if len(df) < 30:
            return signals
        
        # Bollinger Band breakouts
        for i in range(1, len(df)):
            close = df['close'].iloc[i]
            bb_upper = df['bb_upper'].iloc[i]
            bb_lower = df['bb_lower'].iloc[i]
            prev_close = df['close'].iloc[i-1]
            prev_bb_upper = df['bb_upper'].iloc[i-1]
            prev_bb_lower = df['bb_lower'].iloc[i-1]
            
            # Bullish breakout
            if (prev_close <= prev_bb_upper and close > bb_upper):
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'LONG', 'breakout_bb_upper',
                    strength=0.8
                )
                if signal:
                    signals.append(signal)
            
            # Bearish breakout
            elif (prev_close >= prev_bb_lower and close < bb_lower):
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'SHORT', 'breakout_bb_lower',
                    strength=0.8
                )
                if signal:
                    signals.append(signal)
        
        # Support/Resistance breakouts
        for i in range(1, len(df)):
            close = df['close'].iloc[i]
            resistance = df['resistance'].iloc[i-1]
            support = df['support'].iloc[i-1]
            
            # Resistance breakout
            if close > resistance:
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'LONG', 'breakout_resistance',
                    strength=0.9
                )
                if signal:
                    signals.append(signal)
            
            # Support breakdown
            elif close < support:
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'SHORT', 'breakout_support',
                    strength=0.9
                )
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _generate_mean_reversion_signals(self, df: pd.DataFrame, symbol: str, timeframe: str) -> List[Signal]:
        """Generate mean reversion signals"""
        signals = []
        
        if len(df) < 30:
            return signals
        
        # VWAP mean reversion
        for i in range(1, len(df)):
            close = df['close'].iloc[i]
            vwap = df['vwap'].iloc[i]
            atr = df['atr'].iloc[i]
            
            # Price significantly below VWAP
            if close < vwap - 1.5 * atr:
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'LONG', 'mean_reversion_vwap_oversold',
                    strength=0.7
                )
                if signal:
                    signals.append(signal)
            
            # Price significantly above VWAP
            elif close > vwap + 1.5 * atr:
                signal = self._create_signal(
                    df, i, symbol, timeframe, 'SHORT', 'mean_reversion_vwap_overbought',
                    strength=0.7
                )
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _generate_volatility_signals(self, df: pd.DataFrame, symbol: str, timeframe: str) -> List[Signal]:
        """Generate volatility-based signals"""
        signals = []
        
        if len(df) < 30:
            return signals
        
        # ATR expansion/contraction signals
        df['atr_ma'] = df['atr'].rolling(window=20).mean()
        df['atr_ratio'] = df['atr'] / df['atr_ma']
        
        for i in range(1, len(df)):
            atr_ratio = df['atr_ratio'].iloc[i]
            prev_atr_ratio = df['atr_ratio'].iloc[i-1]
            
            # Volatility expansion (potential breakout)
            if atr_ratio > 1.5 and prev_atr_ratio <= 1.5:
                # Determine direction based on price action
                close = df['close'].iloc[i]
                open_price = df['open'].iloc[i]
                
                if close > open_price:
                    signal = self._create_signal(
                        df, i, symbol, timeframe, 'LONG', 'volatility_expansion_bullish',
                        strength=0.6
                    )
                    if signal:
                        signals.append(signal)
                else:
                    signal = self._create_signal(
                        df, i, symbol, timeframe, 'SHORT', 'volatility_expansion_bearish',
                        strength=0.6
                    )
                    if signal:
                        signals.append(signal)
        
        return signals
    
    def _create_signal(self, df: pd.DataFrame, index: int, symbol: str, timeframe: str,
                      signal_type: str, signal_name: str, strength: float) -> Optional[Signal]:
        """Create a signal with proper filtering"""
        try:
            row = df.iloc[index]
            
            # Basic filtering
            if strength < self.filters.min_signal_strength:
                return None
            
            # Volatility filter
            if self.filters.volatility_filter:
                if pd.isna(row['atr']) or row['atr'] == 0:
                    return None
                
                # Check for extreme moves
                if self.filters.extreme_move_filter:
                    if row['body_atr_ratio'] > self.filters.max_body_atr_ratio:
                        return None
            
            # Calculate entry price
            entry_price = row['close']
            
            # Calculate stop loss and take profit
            atr = row['atr']
            if pd.isna(atr) or atr == 0:
                atr = row['close'] * 0.02  # 2% default
            
            if signal_type == 'LONG':
                stop_loss = entry_price - 2 * atr
                take_profit = entry_price + 3 * atr  # 1.5:1 R:R
            else:  # SHORT
                stop_loss = entry_price + 2 * atr
                take_profit = entry_price - 3 * atr
            
            # Determine confirmation level
            confirmation_level = 'TRIGGER'
            if self.filters.confirmation_required:
                # Check if next bar confirms the signal
                if index + 1 < len(df):
                    next_row = df.iloc[index + 1]
                    if signal_type == 'LONG':
                        if next_row['close'] > entry_price * (1 + self.filters.confirmation_threshold):
                            confirmation_level = 'CONFIRMED'
                        elif next_row['close'] > entry_price:
                            confirmation_level = 'WEAK'
                    else:  # SHORT
                        if next_row['close'] < entry_price * (1 - self.filters.confirmation_threshold):
                            confirmation_level = 'CONFIRMED'
                        elif next_row['close'] < entry_price:
                            confirmation_level = 'WEAK'
            
            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                signal_type=signal_type,
                signal_strength=strength,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timestamp=row.name,
                confirmation_level=confirmation_level,
                metadata={
                    'signal_name': signal_name,
                    'atr': atr,
                    'rsi': row.get('rsi', None),
                    'adx': row.get('adx', None),
                    'body_atr_ratio': row.get('body_atr_ratio', None)
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating signal: {e}")
            return None
    
    def generate_signals(self, df: pd.DataFrame, symbol: str, timeframe: str,
                        signal_families: List[str] = None) -> List[Signal]:
        """Generate signals for all specified families"""
        if signal_families is None:
            signal_families = list(self.signal_generators.keys())
        
        # Calculate indicators
        df = self.calculate_technical_indicators(df)
        
        all_signals = []
        
        for family in signal_families:
            if family in self.signal_generators:
                try:
                    signals = self.signal_generators[family](df, symbol, timeframe)
                    all_signals.extend(signals)
                except Exception as e:
                    logger.error(f"Error generating {family} signals: {e}")
        
        # Sort by signal strength and timestamp
        all_signals.sort(key=lambda x: (x.signal_strength, x.timestamp), reverse=True)
        
        return all_signals
    
    def filter_signals(self, signals: List[Signal], 
                      min_strength: float = None,
                      confirmation_level: str = None) -> List[Signal]:
        """Filter signals based on criteria"""
        if min_strength is None:
            min_strength = self.filters.min_signal_strength
        
        filtered_signals = []
        
        for signal in signals:
            # Strength filter
            if signal.signal_strength < min_strength:
                continue
            
            # Confirmation level filter
            if confirmation_level:
                if signal.confirmation_level != confirmation_level:
                    continue
            
            filtered_signals.append(signal)
        
        return filtered_signals
    
    def get_signal_summary(self, signals: List[Signal]) -> Dict:
        """Get summary statistics for signals"""
        if not signals:
            return {}
        
        summary = {
            'total_signals': len(signals),
            'long_signals': len([s for s in signals if s.signal_type == 'LONG']),
            'short_signals': len([s for s in signals if s.signal_type == 'SHORT']),
            'avg_strength': np.mean([s.signal_strength for s in signals]),
            'confirmation_levels': {},
            'signal_families': {}
        }
        
        # Confirmation levels
        for signal in signals:
            level = signal.confirmation_level
            summary['confirmation_levels'][level] = summary['confirmation_levels'].get(level, 0) + 1
        
        # Signal families
        for signal in signals:
            family = signal.metadata.get('signal_name', 'unknown').split('_')[0]
            summary['signal_families'][family] = summary['signal_families'].get(family, 0) + 1
        
        return summary

# Global instance
signal_engine = SignalEngine()