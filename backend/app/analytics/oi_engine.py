# backend/app/analytics/oi_engine.py
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

class OIEngine(BaseAnalyticsEngine):
    """Open Interest Engine - analyzes OI changes"""
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        if not option_chain.call_options or not option_chain.put_options:
            return Score(
                engine_name="OIEngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No OI data available"
            )
        
        # Calculate total OI for ATM strikes
        atm_strike = self._find_atm_strike(option_chain, market_data.close)
        
        if atm_strike not in option_chain.call_options or atm_strike not in option_chain.put_options:
            return Score(
                engine_name="OIEngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No ATM strike data available"
            )
        
        call = option_chain.call_options[atm_strike]
        put = option_chain.put_options[atm_strike]
        call_oi = call.open_interest
        put_oi = put.open_interest
        call_change = call.change_in_oi
        put_change = put.change_in_oi
        
        # OI Ratio and changes
        oi_ratio = put_oi / call_oi if call_oi > 0 else 0
        
        # Strong put OI increase = Bearish (negative)
        # Strong call OI increase = Bullish (positive)
        net_oi_change = put_change - call_change
        normalized_change = self.normalize_score(net_oi_change, -100000, 100000)
        
        # Combine ratio and change for final score
        ratio_score = self.normalize_score(oi_ratio, 0.5, 2.0)
        score = (ratio_score * 0.5 + normalized_change * 0.5)
        score = max(-1.0, min(1.0, score))
        
        if score > 0.3:
            signal = "BULLISH"
            reasoning = "OI changes indicate bullish sentiment (Call OI building)"
        elif score < -0.3:
            signal = "BEARISH"
            reasoning = "OI changes indicate bearish sentiment (Put OI building)"
        else:
            signal = "NEUTRAL"
            reasoning = "OI changes are neutral"
        
        return Score(
            engine_name="OIEngine",
            score=score,
            weight=self.weight,
            confidence=abs(score) * 80,
            signal=signal,
            reasoning=reasoning
        )
    
    def _find_atm_strike(self, option_chain: OptionChainData, underlying_price: float) -> float:
        """Find the closest strike to underlying price"""
        if not option_chain.strikes:
            return 0
        return min(option_chain.strikes, key=lambda x: abs(x - underlying_price))