# backend/app/analytics/greeks_engine.py
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

class GreeksEngine(BaseAnalyticsEngine):
    """Greeks Engine - analyzes Delta, Gamma, Theta, Vega"""
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        if not option_chain.call_options or not option_chain.put_options:
            return Score(
                engine_name="GreeksEngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No Greeks data available"
            )
        
        # Find ATM strike
        atm_strike = self._find_atm_strike(option_chain, market_data.close)
        
        if atm_strike not in option_chain.call_options:
            return Score(
                engine_name="GreeksEngine",
                score=0,
                confidence=0,
                signal="NEUTRAL",
                reasoning="No ATM option data"
            )
        
        call = option_chain.call_options[atm_strike]
        put = option_chain.put_options.get(atm_strike)
        
        # Delta Analysis: High call delta + low put delta = Bullish
        delta_score = 0
        if call.delta and put and put.delta:
            delta_score = (call.delta - abs(put.delta)) / 1.0
        
        # Gamma Analysis: High gamma = high volatility expected
        gamma_score = 0
        if call.gamma:
            gamma_score = self.normalize_score(call.gamma, 0, 0.1)
        
        # Combined score
        score = (delta_score * 0.6 + gamma_score * 0.4)
        score = max(-1.0, min(1.0, score))
        
        if score > 0.3:
            signal = "BULLISH"
            reasoning = f"Delta and Gamma indicate bullish momentum (Delta: {call.delta:.3f})"
        elif score < -0.3:
            signal = "BEARISH"
            reasoning = "Delta and Gamma indicate bearish momentum"
        else:
            signal = "NEUTRAL"
            reasoning = "Greeks indicate neutral momentum"
        
        return Score(
            engine_name="GreeksEngine",
            score=score,
            weight=self.weight,
            confidence=abs(score) * 75,
            signal=signal,
            reasoning=reasoning
        )
    
    def _find_atm_strike(self, option_chain: OptionChainData, underlying_price: float) -> float:
        if not option_chain.strikes:
            return 0
        return min(option_chain.strikes, key=lambda x: abs(x - underlying_price))