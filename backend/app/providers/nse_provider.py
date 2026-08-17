# backend/app/providers/nse_provider.py
import requests
import logging
from datetime import datetime
from typing import Optional, List
from ..core.models import MarketData

logger = logging.getLogger(__name__)

class NSEProvider:
    """
    Free NSE India API provider
    No rate limits, no IP blocking
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/'
        })
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 30
        
        # Initialize session with cookies
        try:
            self.session.get('https://www.nseindia.com', timeout=10)
            logger.info("NSE Provider initialized successfully")
        except Exception as e:
            logger.warning(f"NSE initialization warning: {e}")
    
    def get_ltp(self, symbol: str = "NIFTY") -> Optional[float]:
        """Get live price from NSE"""
        try:
            cache_key = f"ltp_{symbol}"
            if cache_key in self._cache and self._cache_time.get(cache_key):
                age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
                if age < self._cache_ttl:
                    return self._cache[cache_key]
            
            indices = {
                "NIFTY": "NIFTY 50",
                "BANKNIFTY": "NIFTY BANK"
            }
            
            url = "https://www.nseindia.com/api/equity-stockIndices"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for index in data.get('data', []):
                    if indices.get(symbol) == index.get('indexName'):
                        ltp = float(index.get('last', 0))
                        if ltp:
                            self._cache[cache_key] = ltp
                            self._cache_time[cache_key] = datetime.now()
                            return ltp
            
            return None
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {e}")
            return None
    
    def get_market_data(self, symbol: str = "NIFTY", days: int = 5) -> List[MarketData]:
        """Get market data from NSE"""
        try:
            url = "https://www.nseindia.com/api/equity-stockIndices"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                indices = {
                    "NIFTY": "NIFTY 50",
                    "BANKNIFTY": "NIFTY BANK"
                }
                
                for index in data.get('data', []):
                    if indices.get(symbol) == index.get('indexName'):
                        return [MarketData(
                            symbol=symbol,
                            market_type="NIFTY" if "NIFTY" in symbol else "BANK_NIFTY",
                            timestamp=datetime.now(),
                            open=float(index.get('open', 0)),
                            high=float(index.get('dayHigh', 0)),
                            low=float(index.get('dayLow', 0)),
                            close=float(index.get('last', 0)),
                            volume=int(index.get('totalTradedVolume', 0)),
                            vwap=float(index.get('last', 0)),
                            trend="Sideways"
                        )]
            
            return []
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return []
    
    def clear_cache(self):
        """Clear cache"""
        self._cache.clear()
        self._cache_time.clear()
        logger.info("NSE cache cleared")