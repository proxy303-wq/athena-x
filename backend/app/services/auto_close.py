# backend/app/services/auto_close.py
import logging
from datetime import datetime
from ..providers.groww import GrowwProvider
from ..core.config import settings

logger = logging.getLogger(__name__)

class AutoCloseService:
    """Auto-close positions at end of day"""
    
    def __init__(self):
        self.groww = GrowwProvider()
    
    def close_all_positions(self):
        """Close all open positions"""
        if not settings.AUTO_CLOSE_POSITIONS:
            return {"status": "disabled"}
        
        try:
            positions = self.groww.get_positions()
            if not positions:
                return {"status": "no_positions"}
            
            closed = []
            for position in positions:
                try:
                    order = self.groww.place_order({
                        "trading_symbol": position.get("trading_symbol"),
                        "transaction_type": "SELL" if position.get("buy") else "BUY",
                        "quantity": position.get("quantity"),
                        "price": self.groww.get_ltp(position.get("trading_symbol")),
                    })
                    closed.append(order)
                except Exception as e:
                    logger.error(f"Error closing position: {e}")
            
            return {"status": "success", "closed": closed}
            
        except Exception as e:
            logger.error(f"Auto-close error: {e}")
            return {"status": "error", "message": str(e)}