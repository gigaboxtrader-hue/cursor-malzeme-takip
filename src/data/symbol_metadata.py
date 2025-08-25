"""
Symbol Metadata and Data Collection Module
Handles symbol information, leverage tiers, and data fetching from Binance
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd
import numpy as np
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException
import redis
import json

from ..config import config, SYMBOL_CLASSIFICATION

logger = logging.getLogger(__name__)

@dataclass
class SymbolMetadata:
    """Symbol metadata structure"""
    symbol: str
    base_asset: str
    quote_asset: str
    price_precision: int
    quantity_precision: int
    min_notional: float
    tick_size: float
    step_size: float
    allowed_leverage_tiers: List[Dict]
    maintenance_margin_tiers: List[Dict]
    max_leverage: int
    margin_type: str = "isolated"
    
    def get_leverage_tier(self, leverage: int) -> Optional[Dict]:
        """Get leverage tier information"""
        for tier in self.allowed_leverage_tiers:
            if tier['leverage'] == leverage:
                return tier
        return None
    
    def get_maintenance_margin(self, leverage: int, notional: float) -> float:
        """Get maintenance margin requirement"""
        for tier in self.maintenance_margin_tiers:
            if (tier['leverage'] == leverage and 
                tier['notionalFloor'] <= notional <= tier['notionalCap']):
                return tier['maintenanceMarginRate']
        return 0.0

class SymbolMetadataManager:
    """Manages symbol metadata and caching"""
    
    def __init__(self):
        self.client = Client(config.binance.api_key, config.binance.api_secret)
        self.client.API_URL = config.binance.base_url
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.metadata_cache: Dict[str, SymbolMetadata] = {}
        self.last_update = 0
        self.cache_ttl = config.cache_ttl_seconds
        
    def _get_cache_key(self, symbol: str, data_type: str) -> str:
        """Generate cache key"""
        return f"binance:{symbol}:{data_type}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid"""
        if not self.redis_client.exists(cache_key):
            return False
        
        cache_time = self.redis_client.hget(cache_key, "timestamp")
        if not cache_time:
            return False
            
        return (time.time() - float(cache_time)) < self.cache_ttl
    
    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Set cache with timestamp"""
        cache_data = {
            "data": json.dumps(data),
            "timestamp": str(time.time())
        }
        self.redis_client.hmset(cache_key, cache_data)
        self.redis_client.expire(cache_key, self.cache_ttl)
    
    def _get_cache(self, cache_key: str) -> Optional[Any]:
        """Get cached data"""
        if not self._is_cache_valid(cache_key):
            return None
            
        data = self.redis_client.hget(cache_key, "data")
        return json.loads(data) if data else None
    
    async def get_exchange_info(self) -> Dict:
        """Get exchange information from Binance"""
        cache_key = self._get_cache_key("exchange", "info")
        cached_data = self._get_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        try:
            exchange_info = self.client.futures_exchange_info()
            self._set_cache(cache_key, exchange_info)
            return exchange_info
        except BinanceAPIException as e:
            logger.error(f"Failed to get exchange info: {e}")
            raise
    
    async def get_symbol_metadata(self, symbol: str) -> SymbolMetadata:
        """Get metadata for a specific symbol"""
        if symbol in self.metadata_cache:
            return self.metadata_cache[symbol]
        
        cache_key = self._get_cache_key(symbol, "metadata")
        cached_data = self._get_cache(cache_key)
        
        if cached_data:
            metadata = SymbolMetadata(**cached_data)
            self.metadata_cache[symbol] = metadata
            return metadata
        
        try:
            # Get exchange info
            exchange_info = await self.get_exchange_info()
            
            # Find symbol info
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break
            
            if not symbol_info:
                raise ValueError(f"Symbol {symbol} not found")
            
            # Get leverage brackets
            leverage_brackets = await self.get_leverage_brackets(symbol)
            
            # Create metadata
            metadata = SymbolMetadata(
                symbol=symbol,
                base_asset=symbol_info['baseAsset'],
                quote_asset=symbol_info['quoteAsset'],
                price_precision=symbol_info['pricePrecision'],
                quantity_precision=symbol_info['quantityPrecision'],
                min_notional=float(symbol_info['filters'][0]['minNotional']),
                tick_size=float(symbol_info['filters'][1]['tickSize']),
                step_size=float(symbol_info['filters'][2]['stepSize']),
                allowed_leverage_tiers=leverage_brackets,
                maintenance_margin_tiers=leverage_brackets,
                max_leverage=max(tier['leverage'] for tier in leverage_brackets)
            )
            
            # Cache metadata
            self._set_cache(cache_key, metadata.__dict__)
            self.metadata_cache[symbol] = metadata
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get metadata for {symbol}: {e}")
            raise
    
    async def get_leverage_brackets(self, symbol: str) -> List[Dict]:
        """Get leverage brackets for a symbol"""
        cache_key = self._get_cache_key(symbol, "leverage_brackets")
        cached_data = self._get_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        try:
            leverage_brackets = self.client.futures_leverage_bracket(symbol=symbol)
            brackets = leverage_brackets[0]['brackets']
            self._set_cache(cache_key, brackets)
            return brackets
        except BinanceAPIException as e:
            logger.error(f"Failed to get leverage brackets for {symbol}: {e}")
            raise
    
    async def get_all_usdt_symbols(self) -> List[str]:
        """Get all USDT perpetual symbols"""
        exchange_info = await self.get_exchange_info()
        usdt_symbols = []
        
        for symbol_info in exchange_info['symbols']:
            if (symbol_info['symbol'].endswith('USDT') and 
                symbol_info['status'] == 'TRADING' and
                symbol_info['contractType'] == 'PERPETUAL'):
                usdt_symbols.append(symbol_info['symbol'])
        
        return usdt_symbols
    
    def classify_symbol(self, symbol: str) -> str:
        """Classify symbol into tier"""
        if symbol in SYMBOL_CLASSIFICATION["CORE"]:
            return "CORE"
        elif symbol in SYMBOL_CLASSIFICATION["MAJOR"]:
            return "MAJOR"
        else:
            return "ALT"
    
    def get_max_leverage_for_symbol(self, symbol: str) -> int:
        """Get maximum allowed leverage for symbol"""
        classification = self.classify_symbol(symbol)
        
        if classification == "CORE":
            return config.risk.max_leverage_core
        elif classification == "MAJOR":
            return config.risk.max_leverage_major
        else:
            return config.risk.max_leverage_alt

class DataCollector:
    """Handles data collection from Binance"""
    
    def __init__(self):
        self.client = Client(config.binance.api_key, config.binance.api_secret)
        self.client.API_URL = config.binance.base_url
        self.metadata_manager = SymbolMetadataManager()
        
    async def get_ohlcv_data(self, symbol: str, interval: str, 
                           limit: int = 1000, start_time: Optional[int] = None,
                           end_time: Optional[int] = None) -> pd.DataFrame:
        """Get OHLCV data from Binance"""
        try:
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                startTime=start_time,
                endTime=end_time
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Convert types
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'quote_volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get OHLCV data for {symbol}: {e}")
            raise
    
    async def get_funding_rate_history(self, symbol: str, 
                                     limit: int = 1000) -> pd.DataFrame:
        """Get funding rate history"""
        try:
            funding_rates = self.client.futures_funding_rate(
                symbol=symbol, limit=limit
            )
            
            df = pd.DataFrame(funding_rates)
            df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
            df['fundingRate'] = pd.to_numeric(df['fundingRate'])
            df.set_index('fundingTime', inplace=True)
            
            return df
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get funding rate for {symbol}: {e}")
            raise
    
    async def get_open_interest(self, symbol: str) -> Dict:
        """Get open interest data"""
        try:
            open_interest = self.client.futures_open_interest(symbol=symbol)
            return open_interest
        except BinanceAPIException as e:
            logger.error(f"Failed to get open interest for {symbol}: {e}")
            raise
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Dict:
        """Get order book data"""
        try:
            orderbook = self.client.futures_order_book(symbol=symbol, limit=limit)
            return orderbook
        except BinanceAPIException as e:
            logger.error(f"Failed to get orderbook for {symbol}: {e}")
            raise
    
    async def get_ticker_24hr(self, symbol: str) -> Dict:
        """Get 24hr ticker statistics"""
        try:
            ticker = self.client.futures_ticker(symbol=symbol)
            return ticker
        except BinanceAPIException as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            raise
    
    def clean_ohlcv_data(self, df: pd.DataFrame, 
                        outlier_filter: bool = True) -> pd.DataFrame:
        """Clean OHLCV data"""
        # Remove rows with NaN values
        df = df.dropna()
        
        # Remove duplicate timestamps
        df = df[~df.index.duplicated(keep='first')]
        
        if outlier_filter:
            # Filter extreme wicks (optional)
            for col in ['high', 'low']:
                q1 = df[col].quantile(0.01)
                q99 = df[col].quantile(0.99)
                df = df[(df[col] >= q1) & (df[col] <= q99)]
        
        # Ensure chronological order
        df = df.sort_index()
        
        return df
    
    def fill_missing_bars(self, df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """Fill missing bars with forward fill"""
        # Create complete time index
        if interval == '5m':
            freq = '5T'
        elif interval == '15m':
            freq = '15T'
        elif interval == '1h':
            freq = 'H'
        elif interval == '4h':
            freq = '4H'
        elif interval == '1d':
            freq = 'D'
        else:
            freq = '1H'  # Default
        
        complete_index = pd.date_range(
            start=df.index.min(),
            end=df.index.max(),
            freq=freq
        )
        
        # Reindex and forward fill
        df = df.reindex(complete_index)
        df = df.fillna(method='ffill')
        
        return df
    
    async def get_multi_timeframe_data(self, symbol: str, 
                                     timeframes: List[str] = None) -> Dict[str, pd.DataFrame]:
        """Get data for multiple timeframes"""
        if timeframes is None:
            timeframes = config.trading.timeframes
        
        data = {}
        for tf in timeframes:
            try:
                df = await self.get_ohlcv_data(symbol, tf)
                df = self.clean_ohlcv_data(df)
                df = self.fill_missing_bars(df, tf)
                data[tf] = df
            except Exception as e:
                logger.error(f"Failed to get {tf} data for {symbol}: {e}")
                continue
        
        return data

# Global instances
metadata_manager = SymbolMetadataManager()
data_collector = DataCollector()