# backend/app/services/historical_data.py
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from ..providers.groww import get_groww_provider
from ..core.models import MarketData

logger = logging.getLogger(__name__)

class HistoricalDataService:
    """
    Fetch and manage historical data from Groww (2020 onwards)
    """
    
    def __init__(self):
        self.provider = get_groww_provider()
        self._cache = {}
    
    def get_historical_candles(
        self, 
        symbol: str = "NIFTY", 
        start_date: datetime = None,
        end_date: datetime = None,
        interval: str = "1d"
    ) -> List[MarketData]:
        """
        Fetch historical candles from Groww
        
        Args:
            symbol: Trading symbol (NIFTY, BANKNIFTY, etc.)
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 1d)
        
        Returns:
            List of MarketData objects
        """
        try:
            if start_date is None:
                start_date = datetime.now() - timedelta(days=365)
            if end_date is None:
                end_date = datetime.now()
            
            # Calculate days difference
            days = (end_date - start_date).days
            
            # Cap at 180 days for 1d interval (Groww limit)
            if days > 180 and interval == "1d":
                days = 180
                start_date = end_date - timedelta(days=days)
            
            cache_key = f"{symbol}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{interval}"
            
            if cache_key in self._cache:
                logger.info(f"Using cached historical data for {symbol}")
                return self._cache[cache_key]
            
            logger.info(f"Fetching historical data for {symbol} from {start_date.date()} to {end_date.date()}")
            
            data = self.provider.get_market_data(symbol, interval, days)
            
            if data:
                self._cache[cache_key] = data
                logger.info(f"Fetched {len(data)} candles for {symbol}")
                return data
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return []
    
    def get_expiry_data(self, symbol: str = "NIFTY", months: int = 12) -> Dict[str, Any]:
        """
        Get expiry-specific data for backtesting expiry strategies
        """
        try:
            # Get expiry dates
            expiries = self.provider.get_expiries(symbol)
            
            if not expiries:
                logger.warning(f"No expiries found for {symbol}")
                return {}
            
            # Get data for each expiry
            expiry_data = {}
            for expiry in expiries[:months]:
                try:
                    data = self.provider.get_option_chain(symbol, datetime.fromisoformat(expiry))
                    expiry_data[expiry] = {
                        "strikes": data.strikes if data else [],
                        "pcr": data.pcr if data else None,
                        "max_pain": data.max_pain if data else None,
                        "underlying": data.underlying_price if data else None
                    }
                except Exception as e:
                    logger.error(f"Error fetching expiry data for {expiry}: {e}")
            
            return expiry_data
            
        except Exception as e:
            logger.error(f"Error fetching expiry data: {e}")
            return {}
    
    def clear_cache(self):
        """Clear the historical data cache"""
        self._cache.clear()
        logger.info("Historical data cache cleared")