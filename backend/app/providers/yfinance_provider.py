# backend/app/providers/yfinance_provider.py
import yfinance as yf
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from ..core.models import MarketData, OptionChainData, OptionData, OptionType

logger = logging.getLogger(__name__)

class YahooFinanceProvider:
    """Yahoo Finance - Free, reliable, no rate limits"""
    
    def __init__(self):
        self.symbol_map = {
            "NIFTY": "^NSEI",
            "BANKNIFTY": "^NSEBANK",
            "FINNIFTY": "^NSEBANK",
            "SENSEX": "^BSESN"
        }
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 30
    
    def get_ltp(self, symbol: str = "NIFTY") -> float:
        """Get live price from Yahoo Finance"""
        cache_key = f"ltp_{symbol}"
        if cache_key in self._cache and self._cache_time.get(cache_key):
            age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
            if age < self._cache_ttl:
                return self._cache[cache_key]
        
        try:
            ticker = self.symbol_map.get(symbol, symbol)
            stock = yf.Ticker(ticker)
            data = stock.history(period="1d")
            
            if not data.empty:
                ltp = float(data['Close'].iloc[-1])
                self._cache[cache_key] = ltp
                self._cache_time[cache_key] = datetime.now()
                return ltp
            
            return self._get_fallback_price(symbol)
        except Exception as e:
            logger.error(f"Error fetching LTP from Yahoo: {e}")
            return self._get_fallback_price(symbol)
    
    def get_market_data(self, symbol: str = "NIFTY", timeframe: str = "5m", days: int = 5) -> List[MarketData]:
        """Get historical market data"""
        try:
            ticker = self.symbol_map.get(symbol, symbol)
            stock = yf.Ticker(ticker)
            data = stock.history(period=f"{days}d")
            
            market_data = []
            for idx, row in data.iterrows():
                market_data.append(MarketData(
                    symbol=symbol,
                    timestamp=idx.to_pydatetime(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    vwap=float(row['Close'])
                ))
            return market_data
        except Exception as e:
            logger.error(f"Error fetching market data from Yahoo: {e}")
            return [self._get_mock_market_data(symbol)]
    
    def get_option_chain(self, symbol: str = "NIFTY", expiry: datetime = None) -> OptionChainData:
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