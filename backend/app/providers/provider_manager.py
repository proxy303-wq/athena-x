# backend/app/providers/provider_manager.py
import logging
from typing import Optional
from .nse_provider import NSEProvider
from .free_data_provider import FreeDataProvider
from .groww import get_groww_provider

logger = logging.getLogger(__name__)

class ProviderManager:
    """
    Manages multiple data providers with fallback chain
    """
    
    def __init__(self):
        self.providers = []
        self.fallback_prices = {
            "NIFTY": 24395.85,
            "BANKNIFTY": 57491.10,
            "FINNIFTY": 26213.65,
            "SENSEX": 81000.00
        }
        
        # Initialize providers (order matters - first one to work wins)
        try:
            from .nse_provider import NSEProvider
            self.providers.append(NSEProvider())
            logger.info("NSE Provider added to chain")
        except Exception as e:
            logger.warning(f"NSE Provider init failed: {e}")
        
        try:
            from .free_data_provider import FreeDataProvider
            self.providers.append(FreeDataProvider())
            logger.info("FreeData Provider added to chain")
        except Exception as e:
            logger.warning(f"FreeData Provider init failed: {e}")
        
        # Groww is always available as fallback
        try:
            self.providers.append(get_groww_provider())
            logger.info("Groww Provider added to chain")
        except Exception as e:
            logger.warning(f"Groww Provider init failed: {e}")
        
        logger.info(f"Provider Manager initialized with {len(self.providers)} providers")
    
    def get_ltp(self, symbol: str = "NIFTY") -> Optional[float]:
        """
        Try each provider in order until one returns data
        """
        for provider in self.providers:
            try:
                ltp = provider.get_ltp(symbol)
                if ltp and ltp > 0:
                    provider_name = provider.__class__.__name__
                    logger.info(f"✅ {provider_name} returned LTP for {symbol}: {ltp}")
                    return ltp
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                continue
        
        # If all providers fail, use fallback
        logger.warning(f"All providers failed for {symbol}, using fallback")
        return self.fallback_prices.get(symbol, 0)
    
    def get_all_indices(self) -> dict:
        """
        Get all indices data
        """
        symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]
        results = {}
        
        for symbol in symbols:
            ltp = self.get_ltp(symbol)
            results[symbol] = {
                "symbol": symbol,
                "price": ltp,
                "timestamp": datetime.now().isoformat()
            }
        
        return results