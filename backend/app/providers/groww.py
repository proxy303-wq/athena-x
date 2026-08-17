# backend/app/providers/groww.py
import pyotp
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from functools import wraps
from growwapi import GrowwAPI

from ..core.config import settings
from ..core.models import MarketData, OptionChainData, OptionData, OptionType

logger = logging.getLogger(__name__)

# ============================================================
# SINGLETON PROVIDER
# ============================================================

_groww_instance = None

def get_groww_provider():
    """Get singleton Groww provider instance"""
    global _groww_instance
    if _groww_instance is None:
        _groww_instance = GrowwProvider()
    return _groww_instance

# ============================================================
# RATE LIMITER WITH COOLDOWN
# ============================================================

class RateLimiter:
    _last_call_time = 0
    _min_interval = 3.0
    _call_count = 0
    _reset_time = datetime.now()
    _cooldown_until = None
    
    @classmethod
    def wait_if_needed(cls):
        # Check if in cooldown
        if cls._cooldown_until and time.time() < cls._cooldown_until:
            wait_time = cls._cooldown_until - time.time()
            if wait_time > 0:
                logger.info(f"Rate limit cooldown: {wait_time:.0f}s remaining")
                time.sleep(min(wait_time, 60))
            return
        
        now = datetime.now()
        
        if (now - cls._reset_time).total_seconds() > 60:
            cls._call_count = 0
            cls._reset_time = now
        
        if cls._call_count >= 15:
            cls._cooldown_until = time.time() + 120
            logger.info("Rate limit approaching. Cooling down for 2 minutes")
            time.sleep(30)
            cls._call_count = 0
            cls._reset_time = datetime.now()
            return
        
        elapsed = time.time() - cls._last_call_time
        if elapsed < cls._min_interval:
            time.sleep(cls._min_interval - elapsed)
        
        cls._call_count += 1
        cls._last_call_time = time.time()
    
    @classmethod
    def reset_cooldown(cls):
        cls._cooldown_until = None

def rate_limited(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Skip rate limiting if we're in mock mode
        if hasattr(self, '_use_mock') and self._use_mock:
            raise Exception("Using mock mode")
        RateLimiter.wait_if_needed()
        return func(self, *args, **kwargs)
    return wrapper

# ============================================================
# GROWW PROVIDER
# ============================================================

class GrowwProvider:
    """Groww provider using the official SDK with rate limit handling"""
    
    def __init__(self):
        # Singleton check
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._initialized = True
        self.totp_secret = settings.GROWW_TOTP_SECRET
        self.totp_token = settings.GROWW_TOTP_TOKEN
        self._client = None
        self.authenticated = False
        self._auth_time = None
        self._use_mock = False
        self._cooldown_until = None
        
        # Correct constants from SDK
        self.EXCHANGE_NSE = GrowwAPI.EXCHANGE_NSE
        self.EXCHANGE_BSE = GrowwAPI.EXCHANGE_BSE
        self.EXCHANGE_MCX = GrowwAPI.EXCHANGE_MCX
        
        self.SEGMENT_CASH = GrowwAPI.SEGMENT_CASH
        self.SEGMENT_FNO = GrowwAPI.SEGMENT_FNO
        self.SEGMENT_COMMODITY = GrowwAPI.SEGMENT_COMMODITY
        self.SEGMENT_CURRENCY = GrowwAPI.SEGMENT_CURRENCY
        
        self.PRODUCT_NRML = GrowwAPI.PRODUCT_NRML
        self.PRODUCT_MIS = GrowwAPI.PRODUCT_MIS
        self.PRODUCT_CNC = GrowwAPI.PRODUCT_CNC
        self.PRODUCT_BO = GrowwAPI.PRODUCT_BO
        self.PRODUCT_CO = GrowwAPI.PRODUCT_CO
        self.PRODUCT_MTF = GrowwAPI.PRODUCT_MTF
        self.PRODUCT_ARBITRAGE = GrowwAPI.PRODUCT_ARBITRAGE
        
        self.ORDER_TYPE_MARKET = GrowwAPI.ORDER_TYPE_MARKET
        self.ORDER_TYPE_LIMIT = GrowwAPI.ORDER_TYPE_LIMIT
        self.ORDER_TYPE_STOP_LOSS = GrowwAPI.ORDER_TYPE_STOP_LOSS
        self.ORDER_TYPE_STOP_LOSS_MARKET = GrowwAPI.ORDER_TYPE_STOP_LOSS_MARKET
        
        self.TRANSACTION_TYPE_BUY = GrowwAPI.TRANSACTION_TYPE_BUY
        self.TRANSACTION_TYPE_SELL = GrowwAPI.TRANSACTION_TYPE_SELL
        
        self.VALIDITY_DAY = GrowwAPI.VALIDITY_DAY
        self.VALIDITY_GTC = GrowwAPI.VALIDITY_GTC
        self.VALIDITY_GTD = GrowwAPI.VALIDITY_GTD
        self.VALIDITY_IOC = GrowwAPI.VALIDITY_IOC
        self.VALIDITY_EOS = GrowwAPI.VALIDITY_EOS
        
        # Symbol mapping
        self.SYMBOL_MAP = {
            "NIFTY": {"exchange": self.EXCHANGE_NSE, "segment": self.SEGMENT_CASH},
            "BANKNIFTY": {"exchange": self.EXCHANGE_NSE, "segment": self.SEGMENT_CASH},
            "FINNIFTY": {"exchange": self.EXCHANGE_NSE, "segment": self.SEGMENT_CASH},
            "SENSEX": {"exchange": self.EXCHANGE_BSE, "segment": self.SEGMENT_CASH},
        }
        
        # Aggressive caching
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = {
            'quote': 60,
            'ltp': 30,
            'market_data': 300,
            'option_chain': 600,
            'orders': 30,
            'positions': 30,
            'margin': 300,
            'profile': 600,
        }
        
        self._last_known_price = {}
        self._last_known_time = {}
        
        # Try initial login
        self._login()
    
    def _get_cache(self, key: str, ttl_key: str = 'quote') -> Optional[Any]:
        if key in self._cache and key in self._cache_time:
            age = (datetime.now() - self._cache_time[key]).total_seconds()
            ttl = self._cache_ttl.get(ttl_key, 30)
            if age < ttl:
                return self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        self._cache[key] = value
        self._cache_time[key] = datetime.now()
    
    def _login(self):
        """Authenticate with exponential backoff for rate limits"""
        # Skip if already authenticated and token not expired
        if self.authenticated and self._auth_time:
            elapsed = time.time() - self._auth_time
            if elapsed < 3600:  # 1 hour session
                return True
        
        # Check if in cooldown
        if self._cooldown_until and time.time() < self._cooldown_until:
            wait_time = self._cooldown_until - time.time()
            if wait_time > 0:
                logger.info(f"Rate limit cooldown: {wait_time:.0f}s remaining")
                return False
        
        try:
            logger.info("Authenticating with Groww SDK...")
            totp = pyotp.TOTP(self.totp_secret)
            current_otp = totp.now()
            
            access_token = GrowwAPI.get_access_token(
                api_key=self.totp_token,
                totp=current_otp,
            )
            
            self._client = GrowwAPI(access_token)
            self.authenticated = True
            self._auth_time = time.time()
            self._cooldown_until = None
            self._use_mock = False
            logger.info("Groww authentication successful!")
            return True
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Authentication failed: {error_msg}")
            self.authenticated = False
            self._client = None
            self._use_mock = True
            
            if "rate limit" in error_msg.lower():
                self._cooldown_until = time.time() + 600  # 10 minutes
                logger.info(f"Rate limit detected. Cooling down for 10 minutes")
            else:
                self._cooldown_until = None
            
            return False
    
    @property
    def client(self):
        if self._client is None or not self.authenticated:
            if not self._login():
                self._use_mock = True
                raise Exception("Not authenticated - using mock mode")
        return self._client
    
    # ============================================================
    # MARKET DATA APIS (Now using Yahoo Finance, so these are fallback only)
    # ============================================================
    
    @rate_limited
    def get_quote(self, symbol: str = "NIFTY") -> Dict:
        """Get live quote - fallback only"""
        if self._use_mock:
            return {"last_price": self._get_fallback_price(symbol), "is_mock": True}
        
        cache_key = f"quote_{symbol}"
        cached = self._get_cache(cache_key, 'quote')
        if cached:
            return cached
        
        try:
            if symbol in self.SYMBOL_MAP:
                exchange = self.SYMBOL_MAP[symbol]["exchange"]
                segment = self.SYMBOL_MAP[symbol]["segment"]
            else:
                exchange = self.EXCHANGE_NSE
                segment = self.SEGMENT_CASH
            
            data = self.client.get_quote(
                trading_symbol=symbol,
                exchange=exchange,
                segment=segment,
            )
            
            if data:
                self._set_cache(cache_key, data)
                if "last_price" in data and data["last_price"]:
                    self._last_known_price[symbol] = float(data["last_price"])
                    self._last_known_time[symbol] = datetime.now()
            
            return data
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {"last_price": self._get_fallback_price(symbol), "is_mock": True}
    
    @rate_limited
    def get_ltp(self, symbol: str = "NIFTY") -> float:
        """Get last traded price - fallback only"""
        if self._use_mock:
            return self._get_fallback_price(symbol)
        
        cache_key = f"ltp_{symbol}"
        cached = self._get_cache(cache_key, 'ltp')
        if cached is not None:
            return cached
        
        try:
            data = self.get_quote(symbol)
            if data and "last_price" in data and data["last_price"]:
                ltp = float(data["last_price"])
                self._set_cache(cache_key, ltp)
                return ltp
            
            if symbol in self._last_known_price:
                return self._last_known_price[symbol]
            
            return self._get_fallback_price(symbol)
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {e}")
            if symbol in self._last_known_price:
                return self._last_known_price[symbol]
            return self._get_fallback_price(symbol)
    
    @rate_limited
    def get_market_data(self, symbol: str = "NIFTY", timeframe: str = "5m", days: int = 5) -> List:
        """Get historical market data - fallback only"""
        if self._use_mock:
            return []
        
        cache_key = f"market_{symbol}_{timeframe}_{days}"
        cached = self._get_cache(cache_key, 'market_data')
        if cached:
            return cached
        
        try:
            if days > 180:
                days = 180
            
            end = datetime.now()
            start = end - timedelta(days=days)
            interval_map = {
                "1m": GrowwAPI.CANDLE_INTERVAL_MIN_1,
                "5m": GrowwAPI.CANDLE_INTERVAL_MIN_5,
                "15m": GrowwAPI.CANDLE_INTERVAL_MIN_15,
                "30m": GrowwAPI.CANDLE_INTERVAL_MIN_30,
                "1h": GrowwAPI.CANDLE_INTERVAL_HOUR_1,
                "1d": GrowwAPI.CANDLE_INTERVAL_DAY,
            }
            interval = interval_map.get(timeframe, GrowwAPI.CANDLE_INTERVAL_MIN_5)
            
            exchange = self.EXCHANGE_NSE
            segment = self.SEGMENT_CASH
            if symbol in self.SYMBOL_MAP:
                exchange = self.SYMBOL_MAP[symbol]["exchange"]
                segment = self.SYMBOL_MAP[symbol]["segment"]
            
            groww_symbol = f"{exchange}-{symbol}"
            data = self.client.get_historical_candles(
                exchange=exchange,
                segment=segment,
                groww_symbol=groww_symbol,
                start_time=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end_time=end.strftime("%Y-%m-%dT%H:%M:%S"),
                candle_interval=interval,
            )
            
            if data and "candles" in data and data["candles"]:
                self._set_cache(cache_key, data["candles"])
                return data["candles"]
            
            return []
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return []
    
    def get_option_chain(self, symbol: str = "NIFTY", expiry: datetime = None) -> OptionChainData:
        """Get option chain data - fallback only"""
        if self._use_mock:
            return self._get_mock_option_chain(symbol)
        
        cache_key = f"option_chain_{symbol}_{expiry.strftime('%Y-%m-%d') if expiry else 'default'}"
        cached = self._get_cache(cache_key, 'option_chain')
        if cached:
            return cached
        
        try:
            if not expiry:
                expiry = datetime.now() + timedelta(days=7)
            
            expiry_str = expiry.strftime("%Y-%m-%d")
            
            exchange = self.EXCHANGE_NSE
            if symbol in self.SYMBOL_MAP:
                exchange = self.SYMBOL_MAP[symbol]["exchange"]
            
            data = self.client.get_option_chain(
                exchange=exchange,
                underlying=symbol,
                expiry_date=expiry_str,
            )
            
            if data:
                result = self._parse_option_chain(data, symbol, expiry)
                self._set_cache(cache_key, result)
                return result
            
            return self._get_mock_option_chain(symbol)
        except Exception as e:
            logger.error(f"Error fetching option chain for {symbol}: {e}")
            return self._get_mock_option_chain(symbol)
    
    def _parse_option_chain(self, data: Dict, symbol: str, expiry: datetime) -> OptionChainData:
        """Parse option chain from SDK response"""
        try:
            strikes = []
            call_options = {}
            put_options = {}
            
            if "data" in data:
                data = data["data"]
            
            strikes_data = data.get("strikes", [])
            if not strikes_data:
                strikes_data = data.get("option_chain", [])
            
            for strike_data in strikes_data:
                strike = float(strike_data.get("strike", 0))
                if not strike:
                    continue
                strikes.append(strike)
                
                call = strike_data.get("call", {})
                if call:
                    call_options[strike] = OptionData(
                        symbol=symbol,
                        expiry=expiry,
                        strike=strike,
                        option_type=OptionType.CE,
                        open_interest=int(call.get("open_interest", 0)),
                        change_in_oi=int(call.get("change_in_oi", 0)),
                        volume=int(call.get("volume", 0)),
                        implied_volatility=float(call.get("iv", 0)),
                        delta=float(call.get("delta", 0)) if call.get("delta") else None,
                        gamma=float(call.get("gamma", 0)) if call.get("gamma") else None,
                        theta=float(call.get("theta", 0)) if call.get("theta") else None,
                        vega=float(call.get("vega", 0)) if call.get("vega") else None,
                        rho=float(call.get("rho", 0)) if call.get("rho") else None,
                        last_price=float(call.get("last_price", 0)),
                        bid=float(call.get("bid", 0)),
                        ask=float(call.get("ask", 0))
                    )
                
                put = strike_data.get("put", {})
                if put:
                    put_options[strike] = OptionData(
                        symbol=symbol,
                        expiry=expiry,
                        strike=strike,
                        option_type=OptionType.PE,
                        open_interest=int(put.get("open_interest", 0)),
                        change_in_oi=int(put.get("change_in_oi", 0)),
                        volume=int(put.get("volume", 0)),
                        implied_volatility=float(put.get("iv", 0)),
                        delta=float(put.get("delta", 0)) if put.get("delta") else None,
                        gamma=float(put.get("gamma", 0)) if put.get("gamma") else None,
                        theta=float(put.get("theta", 0)) if put.get("theta") else None,
                        vega=float(put.get("vega", 0)) if put.get("vega") else None,
                        rho=float(put.get("rho", 0)) if put.get("rho") else None,
                        last_price=float(put.get("last_price", 0)),
                        bid=float(put.get("bid", 0)),
                        ask=float(put.get("ask", 0))
                    )
            
            total_call_oi = sum(c.open_interest for c in call_options.values())
            total_put_oi = sum(p.open_interest for p in put_options.values())
            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else None
            
            return OptionChainData(
                symbol=symbol,
                expiry=expiry,
                timestamp=datetime.now(),
                strikes=sorted(strikes),
                call_options=call_options,
                put_options=put_options,
                pcr=pcr,
                max_pain=data.get("max_pain"),
                underlying_price=float(data.get("underlying_price", 0))
            )
        except Exception as e:
            logger.error(f"Error parsing option chain: {e}")
            return self._get_mock_option_chain(symbol)
    
    # ============================================================
    # ORDER & POSITION APIS
    # ============================================================
    
    @rate_limited
    def get_order_list(self) -> List[Dict]:
        """Get all orders"""
        if self._use_mock:
            return []
        
        cache_key = "orders"
        cached = self._get_cache(cache_key, 'orders')
        if cached:
            return cached
        
        try:
            response = self.client.get_order_list()
            data = response.get("data", [])
            self._set_cache(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []
    
    @rate_limited
    def get_positions_for_user(self) -> List[Dict]:
        """Get all live positions"""
        if self._use_mock:
            return []
        
        cache_key = "positions"
        cached = self._get_cache(cache_key, 'positions')
        if cached:
            return cached
        
        try:
            response = self.client.get_positions_for_user()
            data = response.get("data", [])
            self._set_cache(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    @rate_limited
    def get_available_margin_details(self) -> Dict:
        """Get available margin details"""
        if self._use_mock:
            return {}
        
        cache_key = "margin"
        cached = self._get_cache(cache_key, 'margin')
        if cached:
            return cached
        
        try:
            response = self.client.get_available_margin_details()
            self._set_cache(cache_key, response)
            return response
        except Exception as e:
            logger.error(f"Error fetching margin: {e}")
            return {}
    
    @rate_limited
    def get_user_profile(self) -> Dict:
        """Get user profile"""
        if self._use_mock:
            return {}
        
        cache_key = "profile"
        cached = self._get_cache(cache_key, 'profile')
        if cached:
            return cached
        
        try:
            response = self.client.get_user_profile()
            data = response.get("data", {})
            self._set_cache(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            return {}
    
    @rate_limited
    def place_order(self, order_data: Dict) -> Dict:
        """Place an order"""
        if self._use_mock:
            return {"error": "Mock mode - order not placed"}
        
        try:
            if "exchange" not in order_data:
                order_data["exchange"] = self.EXCHANGE_NSE
            if "segment" not in order_data:
                order_data["segment"] = self.SEGMENT_FNO
            if "product" not in order_data:
                order_data["product"] = self.PRODUCT_NRML
            if "order_type" not in order_data:
                order_data["order_type"] = self.ORDER_TYPE_LIMIT
            
            response = self.client.place_order(**order_data)
            self._cache.pop("orders", None)  # Clear cache
            return response
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"error": str(e)}
    
    @rate_limited
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        if self._use_mock:
            return {"error": "Mock mode - order not cancelled"}
        
        try:
            response = self.client.cancel_order(order_id)
            self._cache.pop("orders", None)
            return response
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return {"error": str(e)}
    
    @rate_limited
    def create_smart_order(self, order_data: Dict) -> Dict:
        """Create a smart order (GTT/OCO)"""
        if self._use_mock:
            return {"error": "Mock mode - order not placed"}
        
        try:
            if "exchange" not in order_data:
                order_data["exchange"] = self.EXCHANGE_NSE
            if "segment" not in order_data:
                order_data["segment"] = self.SEGMENT_FNO
            
            response = self.client.create_smart_order(**order_data)
            return response
        except Exception as e:
            logger.error(f"Smart order failed: {e}")
            return {"error": str(e)}
    
    @rate_limited
    def get_smart_order_list(self) -> List[Dict]:
        """Get all smart orders"""
        if self._use_mock:
            return []
        
        cache_key = "smart_orders"
        cached = self._get_cache(cache_key, 'orders')
        if cached:
            return cached
        
        try:
            response = self.client.get_smart_order_list()
            data = response.get("data", [])
            self._set_cache(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Error fetching smart orders: {e}")
            return []
    
    @rate_limited
    def get_smart_order(self, order_id: str) -> Dict:
        """Get a specific smart order"""
        if self._use_mock:
            return {}
        
        try:
            response = self.client.get_smart_order(order_id)
            return response
        except Exception as e:
            logger.error(f"Error fetching smart order: {e}")
            return {}
    
    @rate_limited
    def modify_smart_order(self, order_id: str, **kwargs) -> Dict:
        """Modify a smart order"""
        if self._use_mock:
            return {"error": "Mock mode - order not modified"}
        
        try:
            response = self.client.modify_smart_order(order_id, **kwargs)
            return response
        except Exception as e:
            logger.error(f"Modify smart order failed: {e}")
            return {"error": str(e)}
    
    @rate_limited
    def cancel_smart_order(self, order_id: str) -> Dict:
        """Cancel a smart order"""
        if self._use_mock:
            return {"error": "Mock mode - order not cancelled"}
        
        try:
            response = self.client.cancel_smart_order(order_id)
            return response
        except Exception as e:
            logger.error(f"Cancel smart order failed: {e}")
            return {"error": str(e)}
    
    # ============================================================
    # WEBSOCKET METHODS
    # ============================================================
    
    def get_websocket_url(self) -> str:
        """Get WebSocket URL for real-time streaming"""
        if self._use_mock:
            return ""
        
        try:
            token = self.generate_socket_token()
            if token:
                return f"wss://stream.groww.in/v1?token={token}"
            return ""
        except Exception as e:
            logger.error(f"Error getting WebSocket URL: {e}")
            return ""
    
    def generate_socket_token(self) -> str:
        """Generate WebSocket token"""
        if self._use_mock:
            return ""
        
        try:
            if not self.authenticated:
                self._login()
            
            try:
                response = self.client.generate_socket_token()
            except TypeError:
                try:
                    response = self.client.generate_socket_token(key_pair=self.totp_token)
                except:
                    response = self.client.generate_socket_token({})
            
            if response and response.get("token"):
                return response.get("token")
            return ""
        except Exception as e:
            logger.error(f"Error generating socket token: {e}")
            return ""
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _get_fallback_price(self, symbol: str) -> float:
        """Get fallback price for a symbol"""
        fallback = {
            "NIFTY": 24395.85,
            "BANKNIFTY": 57491.10,
            "FINNIFTY": 26213.65,
            "SENSEX": 81000.00
        }
        return fallback.get(symbol, 24395.85)
    
    def _get_mock_market_data(self, symbol: str) -> MarketData:
        """Generate mock market data"""
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
        """Generate mock option chain"""
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
    
    def get_auth_status(self) -> Dict:
        """Get authentication status"""
        return {
            "authenticated": self.authenticated,
            "use_mock": self._use_mock,
            "cooldown_until": self._cooldown_until,
            "auth_time": self._auth_time,
            "session_token": self._client is not None
        }
    
    def reset_auth(self):
        """Reset authentication"""
        self._client = None
        self.authenticated = False
        self._use_mock = False
        self._cooldown_until = None
        logger.info("Auth reset - will retry on next request")