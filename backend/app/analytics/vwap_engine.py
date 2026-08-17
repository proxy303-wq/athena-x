# backend/app/analytics/vwap_engine.py
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

class VWAPEngine(BaseAnalyticsEngine):
    """VWAP Analysis Engine"""
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        if not market_data.vwap or not market_data.close or market_data.vwap <= 0:
            # Fallback: use close as VWAP
            if market_data.close:
                return Score(
                    engine_name="VWAPEngine",
                    score=0,
                    confidence=0,
                    signal="NEUTRAL",
                    reasoning="No VWAP data available, using neutral stance"
                )
            return Score(
                engine_name="VWAPEngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No data available"
            )
        
        # Price relative to VWAP
        vwap_diff = (market_data.close - market_data.vwap) / market_data.vwap
        score = self.normalize_score(vwap_diff, -0.02, 0.02)
        
        if score > 0.3:
            signal = "BULLISH"
            reasoning = f"Price above VWAP ({market_data.vwap:.2f}), bullish bias"
        elif score < -0.3:
            signal = "BEARISH"
            reasoning = f"Price below VWAP ({market_data.vwap:.2f}), bearish bias"
        else:
            signal = "NEUTRAL"
            reasoning = f"Price near VWAP ({market_data.vwap:.2f}), neutral bias"
        
        return Score(
            engine_name="VWAPEngine",
            score=score,
            weight=self.weight,
            confidence=abs(score) * 65,
            signal=signal,
            reasoning=reasoning
        )