# backend/app/providers/free_data_provider.py
import yfinance as yf
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from ..core.models import MarketData

logger = logging.getLogger(__name__)

class FreeDataProvider:
    """
    Free market data provider using yfinance
    NO rate limits - use this for all market data
    """
    
    def __init__(self):
        self.symbol_map = {
            "NIFTY": "^NSEI",
            "BANKNIFTY": "^NSEBANK",
            "FINNIFTY": "^NSEBANK",  # yfinance may not have FINNIFTY
            "SENSEX": "^BSESN"
        }
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 30  # 30 seconds cache
    
    def get_ltp(self, symbol: str = "NIFTY") -> Optional[float]:
        """Get live price from Yahoo Finance"""
        try:
            ticker = self.symbol_map.get(symbol, symbol)
            
            # Check cache
            cache_key = f"ltp_{symbol}"
            if cache_key in self._cache and cache_key in self._cache_time:
                age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
                if age < self._cache_ttl:
                    return self._cache[cache_key]
            
            stock = yf.Ticker(ticker)
            data = stock.history(period="1d")
            
            if not data.empty:
                ltp = float(data['Close'].iloc[-1])
                self._cache[cache_key] = ltp
                self._cache_time[cache_key] = datetime.now()
                return ltp
            
            return None
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {e}")
            return None
    
    def get_market_data(self, symbol: str = "NIFTY", days: int = 5) -> List[MarketData]:
        """Get historical market data"""
        try:
            ticker = self.symbol_map.get(symbol, symbol)
            stock = yf.Ticker(ticker)
            data = stock.history(period=f"{days}d")
            
            market_data = []
            for idx, row in data.iterrows():
                market_data.append(MarketData(
                    symbol=symbol,
                    market_type="NIFTY" if "NIFTY" in symbol else "BANK_NIFTY",
                    timestamp=idx.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    vwap=float(row['Close']),
                    trend="Sideways"
                ))
            return market_data
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return []
    
    def clear_cache(self):
        """Clear the cache"""
        self._cache.clear()
        self._cache_time.clear()
        logger.info("Free data cache cleared")