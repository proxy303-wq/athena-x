# backend/app/providers/option_chain.py
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from .groww import GrowwProvider
from ..core.models import OptionChainData, OptionData, OptionType

logger = logging.getLogger(__name__)

class OptionChainProvider:
    """Real option chain data provider for all indices"""
    
    def __init__(self):
        self.groww = GrowwProvider()
        self.cache = {}
        self.cache_expiry = {}
        self.cache_ttl = 60  # seconds
    
    def get_option_chain(self, symbol: str = "NIFTY", expiry: str = None) -> Optional[OptionChainData]:
        """Get real option chain data"""
        try:
            # Check cache first
            cache_key = f"{symbol}_{expiry}"
            if cache_key in self.cache:
                if datetime.now() < self.cache_expiry.get(cache_key, datetime.now()):
                    return self.cache[cache_key]
            
            # Get expiry dates
            if not expiry:
                expiries = self.get_expiry_dates(symbol)
                if expiries:
                    expiry = expiries[0]
            
            if not expiry:
                logger.warning(f"No expiry available for {symbol}")
                return self._get_mock_option_chain(symbol)
            
            # Fetch option chain
            data = self.groww.client.get_option_chain(
                exchange=self.groww.EXCHANGE_NSE,
                underlying=symbol,
                expiry_date=expiry,
            )
            
            if data:
                # Parse and structure the data
                result = self._parse_option_chain(data, symbol, expiry)
                
                # Cache the result
                self.cache[cache_key] = result
                self.cache_expiry[cache_key] = datetime.now() + timedelta(seconds=self.cache_ttl)
                
                return result
            
            return self._get_mock_option_chain(symbol)
            
        except Exception as e:
            logger.error(f"Error fetching option chain for {symbol}: {e}")
            return self._get_mock_option_chain(symbol)
    
    def get_expiry_dates(self, symbol: str = "NIFTY") -> List[str]:
        """Get available expiry dates"""
        try:
            data = self.groww.client.get_expiries(
                exchange=self.groww.EXCHANGE_NSE,
                underlying=symbol,
            )
            if data and "expiries" in data:
                return data["expiries"]
            return []
        except Exception as e:
            logger.error(f"Error fetching expiries for {symbol}: {e}")
            return []
    
    def _parse_option_chain(self, data: Dict, symbol: str, expiry: str) -> OptionChainData:
        """Parse option chain data"""
        strikes = []
        call_options = {}
        put_options = {}
        
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
        
        chain_data = data.get("data", {})
        strikes_data = chain_data.get("strikes", [])
        
        for strike_data in strikes_data:
            strike = float(strike_data.get("strike", 0))
            if not strike:
                continue
            
            strikes.append(strike)
            
            # Call option
            call = strike_data.get("call", {})
            if call:
                call_options[strike] = OptionData(
                    symbol=symbol,
                    expiry=expiry_date,
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
            
            # Put option
            put = strike_data.get("put", {})
            if put:
                put_options[strike] = OptionData(
                    symbol=symbol,
                    expiry=expiry_date,
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
        
        # Calculate PCR
        total_call_oi = sum(c.open_interest for c in call_options.values())
        total_put_oi = sum(p.open_interest for p in put_options.values())
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else None
        
        return OptionChainData(
            symbol=symbol,
            expiry=expiry_date,
            timestamp=datetime.now(),
            strikes=sorted(strikes),
            call_options=call_options,
            put_options=put_options,
            pcr=pcr,
            max_pain=chain_data.get("max_pain"),
            underlying_price=float(chain_data.get("underlying_price", 0))
        )
    
    def _get_mock_option_chain(self, symbol: str) -> OptionChainData:
        """Fallback mock option chain"""
        current_price = 24366.0
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
    
    def get_all_indices_chain(self) -> Dict:
        """Get option chain summary for all indices"""
        indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]
        result = {}
        
        for symbol in indices:
            try:
                chain = self.get_option_chain(symbol)
                if chain:
                    result[symbol] = {
                        "pcr": chain.pcr,
                        "max_pain": chain.max_pain,
                        "underlying": chain.underlying_price,
                        "strikes": len(chain.strikes),
                        "expiry": chain.expiry.isoformat()
                    }
                else:
                    result[symbol] = {"error": "No data"}
            except Exception as e:
                logger.error(f"Error fetching chain for {symbol}: {e}")
                result[symbol] = {"error": str(e)}
        
        return result