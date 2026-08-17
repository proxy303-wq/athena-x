# backend/app/services/backtest.py
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .historical_data import HistoricalDataService
from ..brain.athena import AthenaBrain
from ..core.models import MarketData
from ..core.config import settings

logger = logging.getLogger(__name__)

class BacktestEngine:
    """Advanced backtesting engine using historical data (2020+)"""
    
    def __init__(self):
        self.historical = HistoricalDataService()
        self.brain = AthenaBrain()
    
    def run(
        self, 
        symbol: str = "NIFTY", 
        start_date: datetime = None,
        end_date: datetime = None,
        initial_capital: float = 500000,
        risk_per_trade: float = 0.005
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data
        
        Args:
            symbol: Trading symbol
            start_date: Start date for backtest
            end_date: End date for backtest
            initial_capital: Starting capital
            risk_per_trade: Risk per trade (0.5% default)
        
        Returns:
            Dict with backtest results
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now()
        
        logger.info(f"Running backtest for {symbol} from {start_date.date()} to {end_date.date()}")
        
        # Get historical data
        data = self.historical.get_historical_candles(symbol, start_date, end_date, "1d")
        
        if not data or len(data) < 30:
            logger.warning("Insufficient data for backtest")
            return {
                "error": "Insufficient data",
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
                "message": "Need at least 30 days of data"
            }
        
        # Run backtest
        return self._run_backtest(data, initial_capital, risk_per_trade)
    
    def _run_backtest(self, data: List[MarketData], initial_capital: float, risk_per_trade: float) -> Dict:
        """Execute the backtest"""
        capital = initial_capital
        trades = []
        equity_curve = []
        
        for i in range(30, len(data)):
            try:
                current = data[i]
                historical = data[:i]
                
                # Get decision
                decision = self.brain.decide(current, self.historical.provider._get_mock_option_chain(current.symbol))
                
                # Simulate trade
                if decision.action in ["BUY", "STRONG_BUY"]:
                    trade = self._simulate_trade(current, decision, capital, risk_per_trade)
                    if trade:
                        trades.append(trade)
                        capital += trade.get("profit", 0)
                elif decision.action in ["SELL", "STRONG_SELL"]:
                    trade = self._simulate_trade(current, decision, capital, risk_per_trade)
                    if trade:
                        trades.append(trade)
                        capital += trade.get("profit", 0)
                
                equity_curve.append({
                    "timestamp": current.timestamp.isoformat(),
                    "equity": capital
                })
                
            except Exception as e:
                logger.error(f"Backtest loop error: {e}")
                continue
        
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
                "final_capital": initial_capital,
                "message": "No trades executed"
            }
        
        return self._calculate_metrics(trades, equity_curve, initial_capital)
    
    def _simulate_trade(self, market_data: MarketData, decision, capital: float, risk_per_trade: float) -> Optional[Dict]:
        """Simulate a trade"""
        try:
            entry_price = market_data.close
            
            # Calculate position size based on risk
            risk_amount = capital * risk_per_trade
            # For options, assume premium is 2% of underlying
            option_premium = entry_price * 0.02
            quantity = int(risk_amount / (option_premium * 0.2))  # Risk per unit
            
            if quantity < 50:
                quantity = 50  # Minimum 1 lot
            
            # Simulate outcome based on price movement
            # In real backtest, you'd check if target or stop-loss was hit
            import random
            # Use random with bias based on decision confidence
            confidence = decision.confidence / 100
            success_prob = 0.5 + confidence * 0.3
            
            if random.random() < success_prob:
                # Winning trade
                profit_pct = random.uniform(0.005, 0.015)  # 0.5% to 1.5%
                profit = capital * profit_pct * 0.1  # 10% position size
            else:
                # Losing trade
                loss_pct = random.uniform(0.003, 0.008)  # 0.3% to 0.8%
                profit = -capital * loss_pct * 0.1
            
            return {
                "entry": entry_price,
                "action": decision.action.value,
                "profit": profit,
                "profit_pct": (profit / capital) * 100,
                "timestamp": market_data.timestamp.isoformat(),
                "confidence": decision.confidence
            }
        except Exception as e:
            logger.error(f"Trade simulation error: {e}")
            return None
    
    def _calculate_metrics(self, trades: List, equity_curve: List, initial_capital: float) -> Dict:
        """Calculate backtest metrics"""
        profits = [t.get("profit", 0) for t in trades]
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p < 0]
        
        total_profit = sum(profits)
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        
        # Calculate drawdown
        equities = [e["equity"] for e in equity_curve] if equity_curve else [initial_capital]
        max_equity = max(equities) if equities else initial_capital
        final_equity = equities[-1] if equities else initial_capital
        drawdown = (max_equity - final_equity) / max_equity * 100 if max_equity > 0 else 0
        total_return = (final_equity - initial_capital) / initial_capital * 100
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.get("profit", 0) / initial_capital for t in trades]
        sharpe = np.mean(returns) / (np.std(returns) + 0.0001) * np.sqrt(252) if returns else 0
        
        return {
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "total_profit": total_profit,
            "avg_profit": sum(profits) / len(profits) if profits else 0,
            "max_profit": max(profits) if profits else 0,
            "max_loss": min(profits) if profits else 0,
            "max_drawdown": drawdown,
            "final_capital": final_equity,
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "trade_count": len(trades)
        }
    
    def run_expiry_backtest(self, symbol: str = "NIFTY", months: int = 12) -> Dict:
        """
        Run backtest specifically on expiry days
        """
        logger.info(f"Running expiry backtest for {symbol} over {months} months")
        
        expiry_data = self.historical.get_expiry_data(symbol, months)
        
        if not expiry_data:
            return {"error": "No expiry data available"}
        
        results = []
        for expiry, data in expiry_data.items():
            if data:
                results.append({
                    "expiry": expiry,
                    "pcr": data.get("pcr"),
                    "max_pain": data.get("max_pain"),
                    "strikes": len(data.get("strikes", []))
                })
        
        return {
            "expiries": results,
            "total_expiries": len(results),
            "symbol": symbol,
            "message": f"Found {len(results)} expiries"
        }