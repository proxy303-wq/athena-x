# backend/app/services/auto_trader.py
import logging
import time
from datetime import datetime, time as dt_time
from typing import Dict, Any
from ..core.config import settings
from ..brain.athena import AthenaBrain
from ..brain.trade_planner import TradePlanner
from ..providers.groww import GrowwProvider
from .order_service import OrderService
from ..core.models import MarketData, OptionChainData

logger = logging.getLogger(__name__)

class AutoTrader:
    """Automated trading execution"""
    
    def __init__(self):
        self.groww = GrowwProvider()
        self.brain = AthenaBrain()
        self.planner = TradePlanner()
        self.order_service = OrderService()
        self.is_running = False
        self.last_trade_time = None
        self.trades_today = 0
        self.max_trades = settings.MAX_TRADES_PER_DAY
    
    def start(self):
        """Start auto trading"""
        self.is_running = True
        logger.info("🤖 AutoTrader started")
        self._run_loop()
    
    def stop(self):
        self.is_running = False
        logger.info("⏹️ AutoTrader stopped")
    
    def _run_loop(self):
        """Main auto trading loop"""
        while self.is_running:
            try:
                # Check market hours
                if self._is_market_open():
                    # Check daily limit
                    if self.trades_today < self.max_trades:
                        self._execute_trade()
                    else:
                        logger.info("📊 Daily trade limit reached")
                else:
                    # Reset trade count for new day
                    self.trades_today = 0
                
                # Wait 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"AutoTrader error: {e}")
                time.sleep(60)
    
    def _is_market_open(self):
        """Check if market is open"""
        now = datetime.now()
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 15)
        return market_open <= now.time() <= market_close
    
    def _execute_trade(self):
        """Execute a single trade"""
        try:
            # Get market data
            symbol = settings.DEFAULT_SYMBOL
            market_data = self._get_market_data(symbol)
            option_chain = self._get_option_chain(symbol)
            
            # Generate decision
            decision = self.brain.decide(market_data, option_chain)
            
            # Check if we should trade
            if decision.action in ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL"]:
                # Create trade plan
                trade_plan = self.planner.plan(decision, market_data, option_chain)
                
                if trade_plan:
                    # Check if we should auto-execute
                    if settings.AUTO_EXECUTE:
                        # Place order
                        result = self.order_service.place_order(trade_plan)
                        
                        if result.get("status") == "success":
                            self.trades_today += 1
                            self.last_trade_time = datetime.now()
                            logger.info(f"✅ Auto trade executed: {trade_plan.option_symbol}")
                        else:
                            logger.warning(f"❌ Auto trade failed: {result.get('message')}")
                    else:
                        logger.info(f"🔔 Trade signal: {trade_plan.option_symbol} @ {trade_plan.entry_price}")
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
    
    def _get_market_data(self, symbol: str) -> MarketData:
        """Get market data"""
        try:
            data = self.groww.get_market_data(symbol, "5m", 1)
            if data:
                return data[0]
        except:
            pass
        return self.groww._get_mock_market_data(symbol)
    
    def _get_option_chain(self, symbol: str) -> OptionChainData:
        """Get option chain"""
        try:
            return self.groww.get_option_chain(symbol)
        except:
            return self.groww._get_mock_option_chain(symbol)