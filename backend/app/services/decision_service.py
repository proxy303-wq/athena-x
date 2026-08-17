# backend/app/services/decision_service.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from ..core.models import MarketData, OptionChainData
from ..analytics import (
    PCREngine, OIEngine, MaxPainEngine,
    GreeksEngine, TrendEngine, VWAPEngine
)
from ..brain import AthenaBrain, TradePlanner
from ..providers.yfinance_provider import YahooFinanceProvider
from ..providers.groww import get_groww_provider
from ..core.config import settings
from .account_service import AccountService
from .alert_service import AlertService
from ..database import Database

logger = logging.getLogger(__name__)

class DecisionService:
    """Decision Service - Yahoo Finance for data, Groww for orders only"""
    
    def __init__(self):
        # Yahoo Finance for ALL market data (NO rate limits)
        self.data_provider = YahooFinanceProvider()
        
        # Groww for orders and balance only
        self.groww_provider = get_groww_provider()
        
        self.account_service = AccountService()
        self.alert_service = AlertService()
        self.db = Database()
        
        self.brain = AthenaBrain([
            PCREngine(),
            OIEngine(),
            MaxPainEngine(),
            GreeksEngine(),
            TrendEngine(),
            VWAPEngine()
        ])
        self.planner = TradePlanner()
    
    def get_decision(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        symbol = symbol or settings.DEFAULT_SYMBOL
        logger.info(f"Getting decision for {symbol}")
        
        try:
            # Get market data from Yahoo Finance (NO rate limits)
            market_data = self._get_market_data(symbol)
            option_chain = self._get_option_chain(symbol)
            
            decision = self.brain.decide(market_data, option_chain)
            logger.info(f"Decision: {decision.action.value}, Confidence: {decision.confidence:.1f}%")
            
            # Get capital from Groww (fallback to config if rate limited)
            real_capital = self._get_capital()
            logger.info(f"Real capital: Rs.{real_capital:,.2f}")
            
            trade_plan = self.planner.plan(
                decision=decision,
                market_data=market_data,
                option_chain=option_chain,
                capital=real_capital
            )
            
            if trade_plan:
                required_margin = trade_plan.risk_amount
                can_trade = self._can_trade(required_margin)
                if not can_trade:
                    logger.warning(f"Insufficient balance for trade: Rs.{required_margin:,.2f} required")
                    trade_plan = None
            
            return {
                "decision": decision.dict(),
                "trade_plan": trade_plan.dict() if trade_plan else None,
                "market_data": {
                    "symbol": market_data.symbol,
                    "price": market_data.close,
                    "vwap": market_data.vwap,
                    "timestamp": market_data.timestamp.isoformat(),
                    "source": "Yahoo Finance"
                },
                "account": {
                    "capital": real_capital,
                    "can_trade": trade_plan is not None,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error in decision pipeline: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _get_market_data(self, symbol: str) -> MarketData:
        """Get market data from Yahoo Finance (NO rate limits)"""
        try:
            logger.info(f"Fetching market data from Yahoo for {symbol}")
            data = self.data_provider.get_market_data(symbol, settings.DEFAULT_TIMEFRAME, 1)
            if data:
                logger.info(f"Yahoo data successful for {symbol}")
                return data[-1]
        except Exception as e:
            logger.warning(f"Yahoo data failed for {symbol}: {e}")
        
        # Fallback to mock
        logger.warning(f"Using mock market data for {symbol}")
        return self.data_provider._get_mock_market_data(symbol)
    
    def _get_option_chain(self, symbol: str) -> OptionChainData:
        """Get option chain - using mock since Yahoo doesn't provide it"""
        try:
            return self.data_provider.get_option_chain(symbol, datetime.now())
        except Exception as e:
            logger.warning(f"Option chain failed: {e}")
            return self.data_provider._get_mock_option_chain(symbol)
    
    def _get_capital(self) -> float:
        """Get capital from Groww if available, else use config"""
        try:
            balance = self.account_service.get_balance()
            if balance and balance.get("available"):
                return balance.get("available", 0)
        except Exception as e:
            logger.warning(f"Could not fetch balance from Groww: {e}")
        
        # Fallback to config
        return settings.INITIAL_CAPITAL
    
    def _can_trade(self, required_margin: float) -> bool:
        """Check if enough capital to trade"""
        try:
            return self.account_service.can_trade(required_margin)
        except Exception as e:
            logger.warning(f"Balance check failed: {e}")
            # Assume we can trade if we have capital in config
            return required_margin <= settings.INITIAL_CAPITAL
    
    def get_ltp(self, symbol: str) -> float:
        """Get LTP from Yahoo Finance"""
        try:
            return self.data_provider.get_ltp(symbol)
        except Exception as e:
            logger.warning(f"Yahoo LTP failed: {e}")
            return self.data_provider._get_fallback_price(symbol)
    
    def execute_trade(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Execute trade using Groww (orders only)"""
        try:
            result = self.get_decision(symbol)
            
            if result and "trade_plan" in result and result["trade_plan"]:
                trade_plan = result["trade_plan"]
                
                # Check if we can trade
                if not result.get("account", {}).get("can_trade", False):
                    return {
                        "status": "error",
                        "message": "Insufficient balance for trade",
                        "required": trade_plan.get("risk_amount", 0),
                        "available": result.get("account", {}).get("capital", 0)
                    }
                
                trade_plan_dict = trade_plan.dict() if hasattr(trade_plan, 'dict') else trade_plan
                self.alert_service.send_trade_plan(trade_plan_dict)
                
                # Execute using Groww (orders only)
                from .order_service import OrderService
                order_service = OrderService()
                exec_result = order_service.place_order(trade_plan)
                
                if exec_result.get("status") == "success":
                    logger.info("Trade executed successfully via Groww")
                    self.alert_service.send_trade_execution(trade_plan_dict)
                else:
                    logger.error(f"Trade execution failed: {exec_result}")
                    self.alert_service.send_error(str(exec_result), "Trade execution")
                
                return exec_result
            
            return {"status": "waiting", "message": "No trade signal available"}
            
        except Exception as e:
            logger.error(f"Error in execute_trade: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}


def get_decision(symbol: Optional[str] = None) -> Dict[str, Any]:
    service = DecisionService()
    return service.get_decision(symbol)