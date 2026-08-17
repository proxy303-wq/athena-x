# backend/app/analytics/pcr_engine.py
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

class PCREngine(BaseAnalyticsEngine):
    """Put-Call Ratio Engine"""
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        if not option_chain.pcr:
            return Score(
                engine_name="PCREngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No PCR data available"
            )
        
        pcr = option_chain.pcr
        
        # PCR interpretation:
        # > 1.2: Oversold (Bullish) -> positive score
        # < 0.8: Overbought (Bearish) -> negative score
        # 0.8 - 1.2: Neutral
        
        if pcr > 1.2:
            score = min((pcr - 1.2) / 0.8, 1.0)
            signal = "BULLISH"
            reasoning = f"PCR at {pcr:.2f} indicates oversold conditions (Bullish)"
        elif pcr < 0.8:
            score = -min((0.8 - pcr) / 0.8, 1.0)
            signal = "BEARISH"
            reasoning = f"PCR at {pcr:.2f} indicates overbought conditions (Bearish)"
        else:
            score = 0
            signal = "NEUTRAL"
            reasoning = f"PCR at {pcr:.2f} is in neutral range"
        
        confidence = min(abs(score) * 100, 90)
        
        return Score(
            engine_name="PCREngine",
            score=score,
            weight=self.weight,
            confidence=confidence,
            signal=signal,
            reasoning=reasoning
        )