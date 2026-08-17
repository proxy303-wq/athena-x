# backend/app/services/decision_service.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from ..core.models import MarketData, OptionChainData, AthenaDecision, TradePlan
from ..analytics import (
    PCREngine, OIEngine, MaxPainEngine, 
    GreeksEngine, TrendEngine, VWAPEngine
)
from ..brain import AthenaBrain, TradePlanner
from ..providers.groww import get_groww_provider
from ..providers.nse_provider import NSEProvider
from ..core.config import settings
from .account_service import AccountService
from .alert_service import AlertService
from ..database import Database

logger = logging.getLogger(__name__)

class DecisionService:
    """
    Decision Service - Hybrid approach:
    - Free data (yfinance) for market data (NO rate limits)
    - Groww API only for orders and positions
    """
    
    def __init__(self):
        # Groww provider - for orders only
        self.groww_provider = get_groww_provider()
        
        # Free data provider - for market data (no rate limits)
        self.free_provider = NSEProvider()
        
        # Other services
        self.account_service = AccountService()
        self.alert_service = AlertService()
        self.db = Database()
        
        # Brain and Planner
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
        """
        Main pipeline: Free Data -> Analytics -> Brain -> Decision -> Plan
        """
        symbol = symbol or settings.DEFAULT_SYMBOL
        logger.info(f"Getting decision for {symbol}")
        
        try:
            # Step 1: Get market data from FREE provider (no rate limit)
            market_data = self._get_market_data(symbol)
            
            # Step 2: Get option chain (from Groww - only if needed)
            option_chain = self._get_option_chain(symbol)
            
            # Step 3: Run Athena Brain
            decision = self.brain.decide(market_data, option_chain)
            logger.info(f"Decision: {decision.action.value}, Confidence: {decision.confidence:.1f}%")
            
            # Step 4: Get real capital from Groww
            real_capital = self.account_service.get_available_capital()
            logger.info(f"Real capital: Rs.{real_capital:,.2f}")
            
            # Step 5: Create Trade Plan
            trade_plan = self.planner.plan(
                decision=decision,
                market_data=market_data,
                option_chain=option_chain,
                capital=real_capital
            )
            
            # Step 6: Check if enough balance to trade
            if trade_plan:
                required_margin = trade_plan.risk_amount
                can_trade = self.account_service.can_trade(required_margin)
                if not can_trade:
                    logger.warning(f"Insufficient balance for trade: Rs.{required_margin:,.2f} required")
                    trade_plan = None
            
            # Step 7: Return result
            return {
                "decision": decision.dict(),
                "trade_plan": trade_plan.dict() if trade_plan else None,
                "market_data": {
                    "symbol": market_data.symbol,
                    "price": market_data.close,
                    "vwap": market_data.vwap,
                    "timestamp": market_data.timestamp.isoformat()
                },
                "account": {
                    "capital": real_capital,
                    "can_trade": trade_plan is not None,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error in decision pipeline: {e}", exc_info=True)
            self.alert_service.send_error(str(e), "Decision pipeline")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def execute_trade(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute trade using Groww API only (no rate limit on orders)
        """
        try:
            result = self.get_decision(symbol)
            
            if result and "trade_plan" in result and result["trade_plan"]:
                trade_plan = result["trade_plan"]
                
                # Check if enough balance
                if not result.get("account", {}).get("can_trade", False):
                    error_msg = "Insufficient balance for trade"
                    logger.warning(error_msg)
                    self.alert_service.send_error(error_msg, "Trade execution")
                    return {
                        "status": "error", 
                        "message": error_msg,
                        "required": trade_plan.get("risk_amount", 0),
                        "available": result.get("account", {}).get("capital", 0)
                    }
                
                # Send trade plan alert
                trade_plan_dict = trade_plan.dict() if hasattr(trade_plan, 'dict') else trade_plan
                self.alert_service.send_trade_plan(trade_plan_dict)
                
                # Save trade to database
                trade_data = {
                    "symbol": symbol or settings.DEFAULT_SYMBOL,
                    "option_symbol": trade_plan.option_symbol,
                    "position_type": trade_plan.position_type,
                    "entry_price": trade_plan.entry_price,
                    "quantity": trade_plan.quantity,
                    "status": "PENDING",
                    "entry_time": datetime.now().isoformat(),
                    "reason": trade_plan.reason
                }
                trade_id = self.db.save_trade(trade_data)
                logger.info(f"Trade saved to database (ID: {trade_id})")
                
                # Execute using Groww API (only for orders)
                from .order_service import OrderService
                order_service = OrderService()
                exec_result = order_service.place_order(trade_plan)
                
                if exec_result.get("status") == "success":
                    logger.info("Trade executed successfully via Groww")
                    self.db.update_trade_status(trade_id, "EXECUTED")
                    self.alert_service.send_trade_execution(trade_plan_dict)
                else:
                    logger.error(f"Trade execution failed: {exec_result}")
                    self.db.update_trade_status(trade_id, "FAILED")
                    self.alert_service.send_error(str(exec_result), "Trade execution")
                
                return exec_result
            
            return {"status": "waiting", "message": "No trade signal available"}
            
        except Exception as e:
            logger.error(f"Error in execute_trade: {e}", exc_info=True)
            self.alert_service.send_error(str(e), "Execute trade")
            return {"status": "error", "message": str(e)}
    
    def _get_market_data(self, symbol: str) -> MarketData:
        """
        Get market data using FREE provider first, fallback to Groww
        
        Priority:
        1. Free data (yfinance) - NO rate limit
        2. Groww API - if free data fails
        3. Mock data - if all else fails
        """
        try:
            # Try free data first (yfinance)
            logger.info(f"Fetching market data from FREE provider for {symbol}")
            data = self.free_provider.get_market_data(symbol, days=1)
            if data:
                logger.info(f"Free data successful for {symbol}")
                return data[-1]
        except Exception as e:
            logger.warning(f"Free data failed for {symbol}: {e}")
        
        # Fallback to Groww API (only if needed)
        try:
            logger.info(f"Falling back to Groww API for {symbol}")
            data = self.groww_provider.get_market_data(symbol, settings.DEFAULT_TIMEFRAME, 1)
            if data:
                logger.info(f"Groww data successful for {symbol}")
                return data[-1]
        except Exception as e:
            logger.warning(f"Groww data failed for {symbol}: {e}")
        
        # Final fallback - mock data
        logger.warning(f"Using mock market data for {symbol}")
        return self.groww_provider._get_mock_market_data(symbol)
    
    def _get_option_chain(self, symbol: str) -> OptionChainData:
        """
        Get option chain from Groww API (only when needed)
        """
        try:
            # Only fetch from Groww when needed
            data = self.groww_provider.get_option_chain(symbol, datetime.now())
            if data:
                logger.info(f"Option chain fetched from Groww for {symbol}")
                return data
        except Exception as e:
            logger.warning(f"Error fetching option chain from Groww: {e}")
        
        # Return mock data if Groww fails
        logger.warning(f"Using mock option chain for {symbol}")
        return self.groww_provider._get_mock_option_chain(symbol)
    
    def get_ltp(self, symbol: str) -> float:
        """
        Get LTP using FREE provider first
        """
        try:
            # Try free data first
            ltp = self.free_provider.get_ltp(symbol)
            if ltp:
                return ltp
        except Exception as e:
            logger.warning(f"Free LTP failed for {symbol}: {e}")
        
        # Fallback to Groww
        try:
            return self.groww_provider.get_ltp(symbol)
        except Exception as e:
            logger.warning(f"Groww LTP failed for {symbol}: {e}")
        
        # Final fallback
        return self.groww_provider._get_fallback_price(symbol)

    def get_decision_with_live_data(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Same as get_decision but forces fresh data from free provider
        """
        # Clear cache for this symbol
        self.free_provider.clear_cache()
        return self.get_decision(symbol)


def get_decision(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to get a trading decision"""
    service = DecisionService()
    return service.get_decision(symbol)