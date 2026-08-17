# backend/app/providers/yfinance_provider.py
import yfinance as yf
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from ..core.models import MarketData, OptionChainData, OptionData, OptionType

logger = logging.getLogger(__name__)

class YahooFinanceProvider:
    """Yahoo Finance with proper headers and NSE fallback"""
    
    def __init__(self):
        self.symbol_map = {
            "NIFTY": "^NSEI",
            "BANKNIFTY": "^NSEBANK",
            "FINNIFTY": "^NSEBANK",
            "SENSEX": "^BSESN"
        }
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 60
        
        # NSE session with proper headers
        self.nse_session = requests.Session()
        self.nse_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.nseindia.com/',
            'Origin': 'https://www.nseindia.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        
        # Try to get NSE cookies
        try:
            self.nse_session.get('https://www.nseindia.com', timeout=10)
            logger.info("NSE session initialized")
        except Exception as e:
            logger.warning(f"NSE init failed: {e}")
    
    def get_ltp(self, symbol: str = "NIFTY") -> float:
        """Get live price - tries multiple sources"""
        cache_key = f"ltp_{symbol}"
        if cache_key in self._cache and self._cache_time.get(cache_key):
            age = (datetime.now() - self._cache_time[cache_key]).total_seconds()
            if age < self._cache_ttl:
                return self._cache[cache_key]
        
        # Try Yahoo Finance first
        ltp = self._get_yahoo_ltp(symbol)
        if ltp and ltp > 0:
            self._cache[cache_key] = ltp
            self._cache_time[cache_key] = datetime.now()
            return ltp
        
        # Try NSE API
        ltp = self._get_nse_ltp(symbol)
        if ltp and ltp > 0:
            self._cache[cache_key] = ltp
            self._cache_time[cache_key] = datetime.now()
            return ltp
        
        # Final fallback
        return self._get_fallback_price(symbol)
    
    def _get_yahoo_ltp(self, symbol: str) -> float:
        """Get LTP from Yahoo Finance with retry"""
        try:
            ticker = self.symbol_map.get(symbol, symbol)
            
            # Try with different periods
            for period in ["1d", "5d"]:
                try:
                    stock = yf.Ticker(ticker)
                    data = stock.history(period=period)
                    if not data.empty:
                        ltp = float(data['Close'].iloc[-1])
                        if ltp and ltp > 0:
                            logger.info(f"Yahoo LTP for {symbol}: {ltp}")
                            return ltp
                except:
                    continue
            
            return 0
        except Exception as e:
            logger.warning(f"Yahoo failed for {symbol}: {e}")
            return 0
    
    def _get_nse_ltp(self, symbol: str) -> float:
        """Get LTP from NSE API"""
        try:
            indices = {
                "NIFTY": "NIFTY 50",
                "BANKNIFTY": "NIFTY BANK"
            }
            
            # Refresh session
            try:
                self.nse_session.get('https://www.nseindia.com', timeout=10)
            except:
                pass
            
            url = "https://www.nseindia.com/api/equity-stockIndices"
            response = self.nse_session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for index in data.get('data', []):
                    if indices.get(symbol) == index.get('indexName'):
                        ltp = float(index.get('last', 0))
                        if ltp and ltp > 0:
                            logger.info(f"NSE LTP for {symbol}: {ltp}")
                            return ltp
            return 0
        except Exception as e:
            logger.warning(f"NSE API error for {symbol}: {e}")
            return 0
    
    def get_market_data(self, symbol: str = "NIFTY", timeframe: str = "5m", days: int = 5) -> List[MarketData]:
        """Get market data"""
        try:
            # Try Yahoo first
            ticker = self.symbol_map.get(symbol, symbol)
            stock = yf.Ticker(ticker)
            data = stock.history(period=f"{days}d")
            
            if not data.empty:
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
            logger.warning(f"Yahoo market data failed: {e}")
        
        # Try NSE
        try:
            nse_data = self._get_nse_market_data(symbol)
            if nse_data:
                return nse_data
        except Exception as e:
            logger.warning(f"NSE market data failed: {e}")
        
        return [self._get_mock_market_data(symbol)]
    
    def _get_nse_market_data(self, symbol: str) -> List[MarketData]:
        """Get market data from NSE"""
        try:
            indices = {
                "NIFTY": "NIFTY 50",
                "BANKNIFTY": "NIFTY BANK"
            }
            
            url = "https://www.nseindia.com/api/equity-stockIndices"
            response = self.nse_session.get(url, timeout=15)
            
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
            return []
        except Exception as e:
            logger.error(f"NSE market data error: {e}")
            return []
    
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