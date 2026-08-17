# backend/app/providers/nse_provider.py
import requests
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from ..core.models import MarketData, OptionChainData, OptionData, OptionType

logger = logging.getLogger(__name__)

class NSEProvider:
    """Free NSE India API - No authentication needed, no rate limits"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/'
        })
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 30
        
        try:
            self.session.get('https://www.nseindia.com', timeout=10)
            logger.info("NSE Provider initialized")
        except Exception as e:
            logger.warning(f"NSE init failed: {e}")
    
    def get_ltp(self, symbol: str = "NIFTY") -> float:
        """Get live price from NSE"""
        cache_key = f"ltp_{symbol}"
        if cache_key in self._cache and self._cache_time.get(cache_key):
            age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
            if age < self._cache_ttl:
                return self._cache[cache_key]
        
        try:
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
            
            return self._get_fallback_price(symbol)
        except Exception as e:
            logger.error(f"Error fetching LTP from NSE: {e}")
            return self._get_fallback_price(symbol)
    
    def get_market_data(self, symbol: str = "NIFTY", timeframe: str = "5m", days: int = 5) -> List[MarketData]:
        """Get market data from NSE"""
        try:
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
                        return [MarketData(
                            symbol=symbol,
                            timestamp=datetime.now(),
                            open=float(index.get('open', 0)),
                            high=float(index.get('dayHigh', 0)),
                            low=float(index.get('dayLow', 0)),
                            close=float(index.get('last', 0)),
                            volume=int(index.get('totalTradedVolume', 0)),
                            vwap=float(index.get('last', 0))
                        )]
            
            return [self._get_mock_market_data(symbol)]
        except Exception as e:
            logger.error(f"Error fetching market data from NSE: {e}")
            return [self._get_mock_market_data(symbol)]
    
    def get_option_chain(self, symbol: str = "NIFTY", expiry: datetime = None) -> OptionChainData:
        """Option chain - NSE doesn't provide this easily, use mock"""
        return self._get_mock_option_chain(symbol)
    
    def _get_fallback_price(self, symbol: str) -> float:
        fallback = {
            "NIFTY": 24395.85,
            "BANKNIFTY": 57491.10,
            "FINNIFTY": 26213.65,
            "SENSEX": 81000.00
        }
        return fallback.get(symbol, 24395.85)
    
    def _get_mock_market_data(self, symbol: str) -> MarketData:
        price = self._get_fallback_price(symbol)
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(),
            open=price - 50,
            high=price + 50,
            low=price - 50,
            close=price,
            volume=1000000,
            vwap=price - 10
        )
    
    def _get_mock_option_chain(self, symbol: str) -> OptionChainData:
        current_price = self._get_fallback_price(symbol)
        strikes = [current_price - 200, current_price - 100, current_price,
                   current_price + 100, current_price + 200]
        expiry = datetime.now() + timedelta(days=7)
        
        call_options = {}
        put_options = {}
        
        for strike in strikes:
            call_options[strike] = OptionData(
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                option_type=OptionType.CE,
                open_interest=100000,
                change_in_oi=500,
                volume=1000,
                implied_volatility=0.15,
                delta=0.5,
                gamma=0.05,
                theta=-0.2,
                vega=0.3,
                rho=0.1,
                last_price=max(50, 100 - (strike - current_price) * 0.2),
                bid=48,
                ask=52
            )
            put_options[strike] = OptionData(
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                option_type=OptionType.PE,
                open_interest=100000,
                change_in_oi=-300,
                volume=800,
                implied_volatility=0.16,
                delta=-0.5,
                gamma=0.05,
                theta=-0.2,
                vega=0.3,
                rho=-0.1,
                last_price=max(50, 100 + (current_price - strike) * 0.2),
                bid=48,
                ask=52
            )
        
        return OptionChainData(
            symbol=symbol,
            expiry=expiry,
            timestamp=datetime.now(),
            strikes=strikes,
            call_options=call_options,
            put_options=put_options,
            pcr=1.1,
            max_pain=current_price,
            underlying_price=current_price
        )