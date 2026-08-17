# backend/app/scheduler.py
import time
import logging
from datetime import datetime, time as dt_time
from threading import Thread
from .services.decision_service import DecisionService
from .core.config import settings

logger = logging.getLogger(__name__)

class AthenaScheduler:
    def __init__(self):
        self.decision_service = DecisionService()
        self.running = False
        self.trade_count = 0
        self.max_trades = settings.MAX_TRADES_PER_DAY
        self.scan_interval = 300  # 5 minutes between scans
    
    def start(self):
        self.running = True
        Thread(target=self._run, daemon=True).start()
        logger.info("Auto-trade scheduler started")
    
    def stop(self):
        self.running = False
        logger.info("Scheduler stopped")
    
    def _run(self):
        while self.running:
            try:
                if self._is_market_open():
                    if self.trade_count < self.max_trades:
                        self._execute_trade()
                    else:
                        logger.info(f"Daily trade limit reached ({self.trade_count}/{self.max_trades})")
                else:
                    if self.trade_count > 0:
                        logger.info(f"Market closed. Today's trades: {self.trade_count}")
                        self.trade_count = 0
                
                time.sleep(self.scan_interval)
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def _is_market_open(self):
        now = datetime.now()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 15)
        return market_open <= now.time() <= market_close
    
    def _execute_trade(self):
        try:
            result = self.decision_service.execute_trade(settings.DEFAULT_SYMBOL)
            
            if result.get("status") == "success":
                self.trade_count += 1
                logger.info(f"Trade executed: {self.trade_count}/{self.max_trades}")
            elif result.get("status") == "waiting":
                logger.info("No trade signal detected")
            else:
                logger.info(f"Trade execution skipped: {result.get('message', 'Unknown reason')}")
                
        except Exception as e:
            logger.error(f"Trade execution error: {e}")