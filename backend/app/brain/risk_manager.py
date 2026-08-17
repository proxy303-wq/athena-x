# backend/app/brain/risk_manager.py
from datetime import datetime, timedelta
from typing import Dict, List
from ..core.models import TradePlan, Performance
from ..core.config import settings

class RiskManager:
    """Risk Management Engine - protects capital"""
    
    def __init__(self):
        self.initial_capital = settings.INITIAL_CAPITAL
        self.current_balance = settings.INITIAL_CAPITAL
        self.risk_per_trade = settings.RISK_PER_TRADE
        self.max_daily_loss = settings.MAX_DAILY_LOSS
        self.max_positions = settings.MAX_POSITIONS
        
        self.daily_pnl = 0
        self.monthly_pnl = 0
        self.trades = []
        self.performance = Performance(current_balance=settings.INITIAL_CAPITAL)
    
    def can_trade(self) -> bool:
        """Check if we can take a new trade"""
        # Check daily loss limit
        if self.daily_pnl < -self.initial_capital * self.max_daily_loss:
            return False
        
        # Check position limit
        if len(self.trades) >= self.max_positions:
            return False
        
        # Check monthly loss limit (5%)
        if self.monthly_pnl < -self.initial_capital * 0.05:
            return False
        
        return True
    
    def validate_trade(self, trade: TradePlan) -> bool:
        """Validate if trade meets risk criteria"""
        # Check if trade meets risk criteria
        if trade.risk_amount > self.initial_capital * self.risk_per_trade:
            return False
        
        # Check if trade meets reward criteria
        if trade.risk_reward < 1.5:  # Minimum 1.5:1 risk/reward
            return False
        
        return True
    
    def update_trade_result(self, trade: TradePlan, profit: float):
        """Update performance after trade closure"""
        self.current_balance += profit
        self.daily_pnl += profit
        self.monthly_pnl += profit
        
        self.trades.append({
            "trade": trade,
            "profit": profit,
            "timestamp": datetime.now()
        })
        
        # Update performance
        self.performance.total_trades += 1
        if profit > 0:
            self.performance.winning_trades += 1
            self.performance.total_profit += profit
        else:
            self.performance.losing_trades += 1
            self.performance.total_loss += abs(profit)
        
        self.performance.net_profit = self.performance.total_profit - self.performance.total_loss
        self.performance.win_rate = self.performance.winning_trades / self.performance.total_trades * 100
        self.performance.current_balance = self.current_balance
        self.performance.today_pnl = self.daily_pnl
        self.performance.monthly_pnl = self.monthly_pnl
    
    def reset_daily(self):
        self.daily_pnl = 0
    
    def reset_monthly(self):
        self.monthly_pnl = 0
        self.performance.monthly_pnl = 0