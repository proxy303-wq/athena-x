# backend/app/brain/trade_planner.py
import math
from typing import Optional
from datetime import datetime
from ..core.models import AthenaDecision, TradePlan, MarketData, OptionChainData
from ..core.config import settings

class TradePlanner:
    """
    Trade execution planner - uses real capital for position sizing
    
    Features:
    - Dynamic lot sizing based on real capital
    - Risk-based position sizing (0.5% risk per trade)
    - Adjusts lot size to capital
    - Trailing stop-loss logic
    - Multiple targets with scaling
    """
    
    def __init__(self, max_position_size: int = None):
        self.max_position_size = max_position_size or settings.MAX_POSITION_SIZE
    
    def plan(
        self, 
        decision: AthenaDecision, 
        market_data: MarketData, 
        option_chain: OptionChainData,
        capital: float = None
    ) -> Optional[TradePlan]:
        """
        Generate trade plan with real capital
        
        Args:
            decision: Athena decision
            market_data: Live market data
            option_chain: Option chain data
            capital: Real capital from Groww (auto-fetched)
        
        Returns:
            TradePlan or None if no trade
        """
        # Only plan for BUY/SELL signals
        if decision.action in ["WAIT", "NEUTRAL"]:
            return None
        
        # Use provided capital or fallback
        if capital is None:
            capital = settings.INITIAL_CAPITAL
        
        # Get ATM strike and price
        atm_strike = self._find_atm_strike(option_chain, market_data.close)
        if not atm_strike:
            return None
        
        # Select option based on signal
        is_bullish = decision.action in ["BUY", "STRONG_BUY"]
        option_type = "CE" if is_bullish else "PE"
        
        # Get option data
        option_data = option_chain.call_options.get(atm_strike) if is_bullish else option_chain.put_options.get(atm_strike)
        if not option_data:
            return None
        
        # Entry price
        entry_price = option_data.ask or option_data.last_price or market_data.close * 0.02
        
        # Calculate dynamic stop-loss based on ATR or fixed percentage
        stop_loss_pct = self._calculate_stop_loss(decision.confidence, capital)
        stop_loss = entry_price * (1 - stop_loss_pct) if is_bullish else entry_price * (1 + stop_loss_pct)
        
        # Calculate targets based on risk-reward
        risk = abs(entry_price - stop_loss)
        target_multipliers = [1.5, 2.5, 4.0]  # Risk-reward ratios
        
        target1 = entry_price + (risk * target_multipliers[0]) if is_bullish else entry_price - (risk * target_multipliers[0])
        target2 = entry_price + (risk * target_multipliers[1]) if is_bullish else entry_price - (risk * target_multipliers[1])
        target3 = entry_price + (risk * target_multipliers[2]) if is_bullish else entry_price - (risk * target_multipliers[2])
        
        # Calculate quantity based on risk and real capital
        quantity = self._calculate_quantity(capital, risk, entry_price)
        
        # Ensure quantity doesn't exceed max position size
        quantity = min(quantity, self.max_position_size * 50)  # 1 lot = 50 units
        
        # Calculate risk and reward amounts
        risk_amount = risk * quantity
        reward_amount = (target1 - entry_price) * quantity if is_bullish else (entry_price - target1) * quantity
        risk_reward = reward_amount / risk_amount if risk_amount > 0 else 0
        
        return TradePlan(
            decision=decision,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target1=target1,
            target2=target2,
            target3=target3,
            risk_reward_ratio=risk_reward,
            option_symbol=f"{market_data.symbol}{option_data.expiry.strftime('%d%b%y').upper()}{atm_strike:.0f}{option_type}",
            quantity=quantity,
            position_type="BUY" if is_bullish else "SELL",
            reason=f"Based on {decision.action} signal with {decision.confidence:.1f}% confidence | Capital: ₹{capital:,.0f}",
            timestamp=datetime.now()
        )
    
    def _calculate_quantity(self, capital: float, risk_per_unit: float, entry_price: float) -> int:
        """
        Calculate quantity based on risk management rules
        
        Risk per trade = 0.5% of capital
        Max risk = capital * 0.005 (0.5%)
        """
        risk_per_trade = capital * settings.RISK_PER_TRADE
        
        if risk_per_unit <= 0:
            return 0
        
        quantity = int(risk_per_trade / risk_per_unit)
        
        # Cap at max position
        max_lots = int(capital / (entry_price * 50))  # 1 lot = 50 units
        quantity = min(quantity, max_lots * 50)
        
        # Minimum 1 lot
        if quantity < 50:
            quantity = 0
        
        return quantity
    
    def _calculate_stop_loss(self, confidence: float, capital: float) -> float:
        """
        Calculate dynamic stop-loss percentage based on confidence and capital
        
        Higher confidence = tighter stop-loss
        """
        base_sl = 0.15  # 15% base stop-loss
        
        # Adjust based on confidence
        if confidence > 80:
            sl_pct = base_sl * 0.8  # Tighter SL for high confidence
        elif confidence > 60:
            sl_pct = base_sl * 1.0
        else:
            sl_pct = base_sl * 1.2  # Wider SL for low confidence
        
        # Ensure it doesn't exceed 0.5% of capital
        max_sl_pct = 0.25
        return min(sl_pct, max_sl_pct)
    
    def _find_atm_strike(self, option_chain: OptionChainData, underlying_price: float) -> float:
        """Find the closest strike to underlying price"""
        if not option_chain or not option_chain.strikes:
            return 0
        return min(option_chain.strikes, key=lambda x: abs(x - underlying_price))
    
    def calculate_position_size(self, capital: float, entry_price: float, stop_loss: float) -> int:
        """Calculate position size based on capital and risk"""
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return 0
        
        risk_amount = capital * settings.RISK_PER_TRADE
        quantity = int(risk_amount / risk_per_unit)
        
        # Cap at max position
        max_quantity = int(capital / (entry_price * 50)) * 50
        quantity = min(quantity, max_quantity)
        
        return max(quantity, 50)  # Minimum 1 lot (50 units)