# backend/app/services/account_service.py
import logging
from datetime import datetime
from typing import Dict, Any
from ..providers.groww import get_groww_provider
from ..core.config import settings

logger = logging.getLogger(__name__)

class AccountService:
    def __init__(self):
        self.provider = get_groww_provider()  # Singleton
        self._cached_balance = None
        self._cache_time = None
        self._cache_duration = 300
    
    def get_balance(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh and self._cached_balance and self._cache_time:
            age = (datetime.now() - self._cache_time).total_seconds()
            if age < self._cache_duration:
                return self._cached_balance
        
        try:
            logger.info("Fetching balance from Groww...")
            margin_data = self.provider.get_available_margin_details()
            
            if margin_data and not margin_data.get("error"):
                clear_cash = margin_data.get("clear_cash", 0)
                net_margin_used = margin_data.get("net_margin_used", 0)
                
                fno_margin = margin_data.get("fno_margin_details", {})
                equity_margin = margin_data.get("equity_margin_details", {})
                commodity_margin = margin_data.get("commodity_margin_details", {})
                
                balance = {
                    "total": clear_cash,
                    "clear_cash": clear_cash,
                    "fno_balance": fno_margin.get("option_buy_balance_available", 0),
                    "fno_sell_balance": fno_margin.get("option_sell_balance_available", 0),
                    "fno_future_balance": fno_margin.get("future_balance_available", 0),
                    "equity_balance": equity_margin.get("cnc_balance_available", 0),
                    "equity_mis_balance": equity_margin.get("mis_balance_available", 0),
                    "commodity_balance": commodity_margin.get("commodity_available", 0),
                    "margin_used": net_margin_used,
                    "available": clear_cash - net_margin_used,
                    "brokerage_charges": margin_data.get("brokerage_and_charges", 0),
                    "collateral_used": margin_data.get("collateral_used", 0),
                    "collateral_available": margin_data.get("collateral_available", 0),
                    "adhoc_margin": margin_data.get("adhoc_margin", 0),
                    "raw": margin_data,
                    "timestamp": datetime.now().isoformat(),
                    "is_fallback": False
                }
                
                self._cached_balance = balance
                self._cache_time = datetime.now()
                return balance
            else:
                return self._get_fallback_balance()
            
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return self._get_fallback_balance()
    
    def _get_fallback_balance(self) -> Dict[str, Any]:
        return {
            "total": settings.INITIAL_CAPITAL,
            "clear_cash": settings.INITIAL_CAPITAL,
            "fno_balance": settings.INITIAL_CAPITAL,
            "fno_sell_balance": settings.INITIAL_CAPITAL,
            "fno_future_balance": settings.INITIAL_CAPITAL,
            "equity_balance": settings.INITIAL_CAPITAL,
            "equity_mis_balance": settings.INITIAL_CAPITAL,
            "commodity_balance": 0,
            "margin_used": 0,
            "available": settings.INITIAL_CAPITAL,
            "brokerage_charges": 0,
            "collateral_used": 0,
            "collateral_available": 0,
            "adhoc_margin": 0,
            "raw": {},
            "timestamp": datetime.now().isoformat(),
            "is_fallback": True
        }
    
    def get_user_profile(self) -> Dict[str, Any]:
        return self.provider.get_user_profile()
    
    def get_margin_details(self) -> Dict[str, Any]:
        return self.provider.get_available_margin_details()
    
    def can_trade(self, required_margin: float = 0) -> bool:
        balance = self.get_balance()
        available = balance.get("available", 0)
        can_trade = available >= required_margin
        
        if not can_trade:
            logger.warning(f"Insufficient balance: Available Rs.{available:.2f}, Required Rs.{required_margin:.2f}")
        
        return can_trade
    
    def get_available_capital(self) -> float:
        balance = self.get_balance()
        return balance.get("available", 0)
    
    def get_account_summary(self) -> Dict[str, Any]:
        try:
            profile = self.get_user_profile()
            balance = self.get_balance(force_refresh=True)
            margin = self.get_margin_details()
            return {
                "profile": profile,
                "balance": balance,
                "margin": margin,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {"error": str(e)}
    
    def clear_cache(self):
        self._cached_balance = None
        self._cache_time = None
        logger.info("Balance cache cleared")