# backend/app/services/paper_trade.py
import logging
from datetime import datetime
from typing import Dict, Any
from ..core.models import TradePlan
from ..core.config import settings

logger = logging.getLogger(__name__)

class PaperTradeService:
    """Paper trading service - virtual trading without real money"""
    
    def __init__(self):
        self.virtual_balance = settings.INITIAL_CAPITAL
        self.initial_balance = settings.INITIAL_CAPITAL
        self.positions = []
        self.trade_history = []
        self.daily_pnl = 0
    
    def execute_paper_trade(self, trade_plan: TradePlan) -> Dict[str, Any]:
        """Execute a paper trade"""
        # Check if enough virtual balance
        if trade_plan.entry_price * trade_plan.quantity > self.virtual_balance:
            return {
                "status": "failed",
                "reason": "Insufficient virtual balance",
                "required": trade_plan.entry_price * trade_plan.quantity,
                "available": self.virtual_balance
            }
        
        position = {
            "symbol": trade_plan.option_symbol,
            "entry_price": trade_plan.entry_price,
            "quantity": trade_plan.quantity,
            "target": trade_plan.target1,
            "stop_loss": trade_plan.stop_loss,
            "entry_time": datetime.now(),
            "status": "OPEN",
            "initial_value": trade_plan.entry_price * trade_plan.quantity
        }
        
        self.positions.append(position)
        self.virtual_balance -= position["initial_value"]
        
        return {
            "status": "success",
            "position": position,
            "remaining_balance": self.virtual_balance,
            "message": f"Paper trade executed: {trade_plan.option_symbol} @ {trade_plan.entry_price}"
        }