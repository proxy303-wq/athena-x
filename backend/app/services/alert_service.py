# backend/app/services/alert_service.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from ..core.config import settings

logger = logging.getLogger(__name__)

class AlertService:
    """
    Alert Service - Handles notifications and alerts
    
    Features:
    - Console alerts (always enabled)
    - File logging
    - Future: WhatsApp, Telegram, Email
    """
    
    def __init__(self):
        self.alerts_enabled = True
        self.logger = logger
    
    def _log(self, level: str, message: str, data: Optional[Dict] = None):
        """Log an alert"""
        if data:
            full_message = f"{message} | Data: {data}"
        else:
            full_message = message
        
        if level == "info":
            self.logger.info(f"ALERT: {full_message}")
        elif level == "warning":
            self.logger.warning(f"ALERT: {full_message}")
        elif level == "error":
            self.logger.error(f"ALERT: {full_message}")
        else:
            self.logger.info(f"ALERT: {full_message}")
        
        # Also print to console
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {full_message}")
    
    # ============================================================
    # TRADE ALERTS
    # ============================================================
    
    def send_trade_execution(self, trade_plan: Dict[str, Any]) -> bool:
        """
        Send trade execution alert
        """
        if not trade_plan:
            return False
        
        symbol = trade_plan.get("option_symbol", "UNKNOWN")
        entry = trade_plan.get("entry_price", 0)
        target = trade_plan.get("target1", 0)
        sl = trade_plan.get("stop_loss", 0)
        quantity = trade_plan.get("quantity", 0)
        position_type = trade_plan.get("position_type", "BUY")
        reason = trade_plan.get("reason", "")
        
        message = f"""
TRADE EXECUTED
- Symbol: {symbol}
- Type: {position_type}
- Entry: Rs.{entry:.2f}
- Target: Rs.{target:.2f}
- Stop-Loss: Rs.{sl:.2f}
- Quantity: {quantity}
- Reason: {reason}
- Time: {datetime.now().strftime('%I:%M %p')}
"""
        
        return self._log("info", message)
    
    def send_trade_exit(self, trade_plan: Dict[str, Any], exit_price: float, profit: float, reason: str = "Target Hit") -> bool:
        """
        Send trade exit alert
        """
        if not trade_plan:
            return False
        
        symbol = trade_plan.get("option_symbol", "UNKNOWN")
        entry = trade_plan.get("entry_price", 0)
        position_type = trade_plan.get("position_type", "BUY")
        quantity = trade_plan.get("quantity", 0)
        
        status = "PROFIT" if profit >= 0 else "LOSS"
        profit_str = f"+Rs.{profit:.2f}" if profit >= 0 else f"-Rs.{abs(profit):.2f}"
        
        message = f"""
TRADE EXITED - {status}
- Symbol: {symbol}
- Type: {position_type}
- Entry: Rs.{entry:.2f}
- Exit: Rs.{exit_price:.2f}
- P&L: {profit_str}
- Quantity: {quantity}
- Reason: {reason}
- Time: {datetime.now().strftime('%I:%M %p')}
"""
        
        return self._log("info", message)
    
    # ============================================================
    # SIGNAL ALERTS
    # ============================================================
    
    def send_signal(self, symbol: str, action: str, confidence: float, reason: str, score: float = 0) -> bool:
        """
        Send signal alert
        """
        message = f"""
SIGNAL GENERATED
- Symbol: {symbol}
- Action: {action}
- Confidence: {confidence:.1f}%
- Score: {score:.3f}
- Reason: {reason}
- Time: {datetime.now().strftime('%I:%M %p')}
"""
        
        return self._log("info", message)
    
    # ============================================================
    # DAILY REPORT ALERTS
    # ============================================================
    
    def send_daily_report(self, performance: Dict[str, Any]) -> bool:
        """
        Send daily performance report
        """
        total_pnl = performance.get("total_pnl", 0)
        total_trades = performance.get("total_trades", 0)
        winning_trades = performance.get("winning_trades", 0)
        losing_trades = performance.get("losing_trades", 0)
        win_rate = performance.get("win_rate", 0)
        
        pnl_str = f"+Rs.{total_pnl:.2f}" if total_pnl >= 0 else f"-Rs.{abs(total_pnl):.2f}"
        
        message = f"""
DAILY REPORT
- Total Trades: {total_trades}
- Wins: {winning_trades}
- Losses: {losing_trades}
- Win Rate: {win_rate:.1f}%
- P&L: {pnl_str}
- Date: {datetime.now().strftime('%Y-%m-%d')}
"""
        
        return self._log("info", message)
    
    # ============================================================
    # ERROR ALERTS
    # ============================================================
    
    def send_error(self, error: str, context: Optional[str] = None) -> bool:
        """
        Send error alert
        """
        message = f"""
SYSTEM ERROR
- Error: {error}
- Context: {context or 'N/A'}
- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return self._log("error", message)
    
    # ============================================================
    # STATUS ALERTS
    # ============================================================
    
    def send_status(self, status: str, details: Optional[str] = None) -> bool:
        """
        Send system status alert
        """
        message = f"""
SYSTEM STATUS
- Status: {status}
- Details: {details or 'N/A'}
- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return self._log("info", message)
    
    # ============================================================
    # TRADE PLAN ALERTS
    # ============================================================
    
    def send_trade_plan(self, trade_plan: Dict[str, Any]) -> bool:
        """
        Send trade plan alert before execution
        """
        if not trade_plan:
            return False
        
        symbol = trade_plan.get("option_symbol", "UNKNOWN")
        entry = trade_plan.get("entry_price", 0)
        target = trade_plan.get("target1", 0)
        sl = trade_plan.get("stop_loss", 0)
        quantity = trade_plan.get("quantity", 0)
        position_type = trade_plan.get("position_type", "BUY")
        risk_reward = trade_plan.get("risk_reward_ratio", 0)
        
        message = f"""
TRADE PLAN READY
- Symbol: {symbol}
- Type: {position_type}
- Entry: Rs.{entry:.2f}
- Target: Rs.{target:.2f}
- Stop-Loss: Rs.{sl:.2f}
- Quantity: {quantity}
- Risk/Reward: 1:{risk_reward:.1f}
- Time: {datetime.now().strftime('%I:%M %p')}
"""
        
        return self._log("info", message)
    
    # ============================================================
    # CUSTOM ALERTS
    # ============================================================
    
    def send_custom(self, title: str, message_body: str, level: str = "info") -> bool:
        """
        Send custom alert
        """
        message = f"""
{title}
{message_body}
- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return self._log(level, message)