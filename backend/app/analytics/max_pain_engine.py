# backend/app/analytics/max_pain_engine.py
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

class MaxPainEngine(BaseAnalyticsEngine):
    """Max Pain Engine - calculates maximum pain for option writers"""
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        if not option_chain.max_pain or not option_chain.underlying_price:
            return Score(
                engine_name="MaxPainEngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No Max Pain data available"
            )
        
        max_pain = option_chain.max_pain
        underlying = option_chain.underlying_price
        
        # If price is above max pain, market might move down (negative)
        # If price is below max pain, market might move up (positive)
        diff_pct = (underlying - max_pain) / max_pain
        
        # Normalize: 5% difference = full score
        score = -self.normalize_score(diff_pct, -0.05, 0.05)
        
        if score > 0.3:
            signal = "BULLISH"
            reasoning = f"Price below Max Pain ({max_pain:.2f}), likely to move up"
        elif score < -0.3:
            signal = "BEARISH"
            reasoning = f"Price above Max Pain ({max_pain:.2f}), likely to move down"
        else:
            signal = "NEUTRAL"
            reasoning = f"Price near Max Pain ({max_pain:.2f}), range-bound expected"
        
        return Score(
            engine_name="MaxPainEngine",
            score=score,
            weight=self.weight,
            confidence=abs(score) * 70,
            signal=signal,
            reasoning=reasoning
        )