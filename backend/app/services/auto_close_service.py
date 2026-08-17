# backend/app/services/auto_close_service.py
import logging
import time
from datetime import datetime, time as dt_time
from threading import Thread
from ..providers.groww import get_groww_provider

logger = logging.getLogger(__name__)

class AutoCloseService:
    def __init__(self):
        self.provider = get_groww_provider()  # Singleton
        self.running = False
        self.last_close_time = None
    
    def start(self):
        self.running = True
        Thread(target=self._run, daemon=True).start()
        logger.info("Auto-close service started")
    
    def stop(self):
        self.running = False
        logger.info("Auto-close service stopped")
    
    def _run(self):
        while self.running:
            try:
                now = datetime.now()
                current_time = now.time()
                close_time = dt_time(15, 15)
                
                if current_time >= close_time and self.last_close_time != now.date():
                    logger.info("Time to close all positions (3:15 PM)")
                    self._close_all_positions()
                    self.last_close_time = now.date()
                
                time.sleep(60)
            except Exception as e:
                logger.error(f"Auto-close error: {e}")
                time.sleep(60)
    
    def _close_all_positions(self):
        try:
            orders = self.provider.get_order_list()
            pending_orders = [o for o in orders if o.get('status') in ['OPEN', 'PENDING']]
            
            for order in pending_orders:
                order_id = order.get('order_id')
                if order_id:
                    self.provider.cancel_order(order_id)
                    logger.info(f"Cancelled order: {order_id}")
            
            positions = self.provider.get_positions_for_user()
            open_positions = [p for p in positions if p.get('quantity', 0) != 0]
            
            for position in open_positions:
                symbol = position.get('trading_symbol')
                quantity = abs(position.get('quantity', 0))
                transaction_type = "SELL" if position.get('quantity', 0) > 0 else "BUY"
                
                if symbol and quantity > 0:
                    order_data = {
                        "trading_symbol": symbol,
                        "exchange": "NSE",
                        "segment": "FNO",
                        "product": "NRML",
                        "order_type": "MARKET",
                        "transaction_type": transaction_type,
                        "quantity": quantity,
                    }
                    self.provider.place_order(order_data)
                    logger.info(f"Closed position: {symbol} ({transaction_type} {quantity})")
            
            logger.info("All positions closed and orders cancelled")
        except Exception as e:
            logger.error(f"Error closing positions: {e}")
    
    def force_close_now(self):
        logger.info("Manual force close triggered")
        self._close_all_positions()
        self.last_close_time = datetime.now().date()
        return {"status": "success", "message": "All positions closed"}