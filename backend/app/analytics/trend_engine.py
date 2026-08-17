# backend/app/analytics/trend_engine.py
import numpy as np
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

class TrendEngine(BaseAnalyticsEngine):
    """Trend Analysis Engine"""
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        if not market_data or not market_data.close:
            return Score(
                engine_name="TrendEngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No trend data available"
            )
        
        score = 0
        reasons = []
        
        # 1. VWAP analysis
        if market_data.vwap and market_data.vwap > 0:
            vwap_diff = (market_data.close - market_data.vwap) / market_data.vwap
            vwap_score = self.normalize_score(vwap_diff, -0.02, 0.02)
            score += vwap_score * 0.5
            reasons.append(f"VWAP diff: {vwap_diff:.4f}")
        
        # 2. Previous close analysis
        if market_data.prev_close and market_data.prev_close > 0:
            daily_change = (market_data.close - market_data.prev_close) / market_data.prev_close
            daily_score = self.normalize_score(daily_change, -0.03, 0.03)
            score += daily_score * 0.5
            reasons.append(f"Daily change: {daily_change:.4f}")
        
        # 3. Range analysis (High-Low)
        if market_data.high and market_data.low and market_data.high > market_data.low:
            range_pct = (market_data.high - market_data.low) / market_data.close
            range_score = self.normalize_score(range_pct, 0, 0.03)
            if range_score > 0.5:
                score += 0.1
                reasons.append(f"Range: {range_pct:.4f}")
        
        # If no data, use mock
        if score == 0:
            score = self.normalize_score(market_data.close - 24300, -200, 200) * 0.3
            reasons.append("Using price relative to 24300")
        
        # Determine signal
        if score > 0.3:
            signal = "BULLISH"
            reasoning = f"Trend Up: {reasons[0] if reasons else 'Positive momentum'}"
        elif score < -0.3:
            signal = "BEARISH"
            reasoning = f"Trend Down: {reasons[0] if reasons else 'Negative momentum'}"
        else:
            signal = "NEUTRAL"
            reasoning = f"Sideways: {reasons[0] if reasons else 'No clear direction'}"
        
        return Score(
            engine_name="TrendEngine",
            score=score,
            weight=self.weight,
            confidence=abs(score) * 70,
            signal=signal,
            reasoning=reasoning
        )