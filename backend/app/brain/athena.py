# backend/app/brain/athena.py
import logging
from typing import List, Dict, Any
from datetime import datetime

from ..core.models import MarketData, OptionChainData, AthenaDecision, Score, TradeAction
from ..analytics import (
    PCREngine, OIEngine, MaxPainEngine, 
    GreeksEngine, TrendEngine, VWAPEngine
)
from ..analytics.advanced_analytics import AdvancedAnalytics
from ..core.config import settings

logger = logging.getLogger(__name__)

class AthenaBrain:
    """Core decision engine - aggregates all analytics engines"""
    
    def __init__(self, engines: List = None):
        if engines is None:
            self.engines = {
                'PCREngine': PCREngine(),
                'OIEngine': OIEngine(),
                'MaxPainEngine': MaxPainEngine(),
                'GreeksEngine': GreeksEngine(),
                'TrendEngine': TrendEngine(),
                'VWAPEngine': VWAPEngine()
            }
        else:
            self.engines = {e.__class__.__name__: e for e in engines}
        
        self.weights = settings.ENGINE_WEIGHTS
        self.advanced = AdvancedAnalytics()  # Advanced technical analysis
    
    def decide(self, market_data: MarketData, option_chain: OptionChainData) -> AthenaDecision:
        """Generate trading decision based on all analytics"""
        
        # Calculate scores from all engines
        scores: List[Score] = []
        for name, engine in self.engines.items():
            try:
                score = engine.calculate(market_data, option_chain)
                score.weight = self.weights.get(name, 1.0)
                scores.append(score)
                logger.info(f"{name}: {score.score:.3f} ({score.signal})")
            except Exception as e:
                logger.error(f"Error in {name}: {e}")
                scores.append(Score(
                    engine_name=name,
                    score=0,
                    weight=self.weights.get(name, 1.0),
                    confidence=0,
                    signal="NEUTRAL",
                    reasoning=f"Engine error: {str(e)}"
                ))
        
        # Calculate weighted average
        total_score = 0.0
        total_weight = 0.0
        for score in scores:
            total_score += score.score * score.weight
            total_weight += score.weight
        
        overall_score = total_score / total_weight if total_weight > 0 else 0
        overall_score = max(-1.0, min(1.0, overall_score))
        
        # Calculate confidence
        confidence = self._calculate_confidence(scores, overall_score)
        
        # Determine action
        action = self._determine_action(overall_score)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(action, overall_score)
        
        # Risk level
        risk_level = self._determine_risk(action, confidence)
        
        return AthenaDecision(
            action=action,
            overall_score=overall_score,
            confidence=confidence,
            scores=scores,
            recommendation=recommendation,
            risk_level=risk_level,
            next_expiry=option_chain.expiry if option_chain else None
        )
    
    def analyze_advanced(self, market_data: MarketData, historical: List[MarketData]) -> Dict[str, Any]:
        """
        Run advanced technical analysis on historical data
        
        Returns:
            Dict with advanced indicators:
            - moving_averages: SMA, EMA values and slopes
            - rsi: RSI value and signal
            - macd: MACD line, signal line, histogram
            - bollinger_bands: Upper, middle, lower bands
            - support_resistance: Support and resistance levels
            - volume_analysis: Volume patterns
            - candlestick_patterns: Pattern recognition
            - trend_strength: Trend direction and strength
            - volatility: Volatility metrics
        """
        try:
            return self.advanced.analyze(historical)
        except Exception as e:
            logger.error(f"Error in advanced analysis: {e}")
            return self.advanced._empty_result()
    
    def get_signal_score(self, market_data: MarketData, historical: List[MarketData]) -> Dict[str, Any]:
        """
        Get enhanced signal score with advanced indicators
        
        Returns:
            Dict with combined signal and confidence
        """
        # Get advanced analysis
        advanced = self.analyze_advanced(market_data, historical)
        
        # Calculate signal from advanced indicators
        signal_score = 0.0
        confidence = 0.0
        reasons = []
        
        # 1. Trend Strength (25% weight)
        trend = advanced.get("trend_strength", {})
        if trend:
            direction = trend.get("direction", "SIDEWAYS")
            strength = trend.get("strength", 0.3)
            
            if direction == "STRONG_UPTREND":
                signal_score += 0.25 * strength
                confidence += 0.25
                reasons.append("Strong uptrend")
            elif direction == "UPTREND":
                signal_score += 0.15 * strength
                confidence += 0.2
                reasons.append("Uptrend")
            elif direction == "STRONG_DOWNTREND":
                signal_score -= 0.25 * strength
                confidence += 0.25
                reasons.append("Strong downtrend")
            elif direction == "DOWNTREND":
                signal_score -= 0.15 * strength
                confidence += 0.2
                reasons.append("Downtrend")
            else:
                confidence += 0.1
                reasons.append("Sideways")
        
        # 2. RSI (20% weight)
        rsi_data = advanced.get("rsi", {})
        rsi = rsi_data.get("value", 50)
        if rsi > 70:
            signal_score -= 0.2
            confidence += 0.2
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi < 30:
            signal_score += 0.2
            confidence += 0.2
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 55:
            signal_score += 0.1
            confidence += 0.1
            reasons.append(f"RSI bullish ({rsi:.1f})")
        elif rsi < 45:
            signal_score -= 0.1
            confidence += 0.1
            reasons.append(f"RSI bearish ({rsi:.1f})")
        
        # 3. MACD (20% weight)
        macd_data = advanced.get("macd", {})
        macd_signal = macd_data.get("signal", "NEUTRAL")
        if macd_signal == "BULLISH":
            signal_score += 0.2
            confidence += 0.2
            reasons.append("MACD bullish crossover")
        elif macd_signal == "BEARISH":
            signal_score -= 0.2
            confidence += 0.2
            reasons.append("MACD bearish crossover")
        
        # 4. Bollinger Bands (15% weight)
        bb = advanced.get("bollinger_bands", {})
        bb_signal = bb.get("signal", "NEUTRAL")
        if bb_signal == "OVERSOLD":
            signal_score += 0.15
            confidence += 0.15
            reasons.append("Price near lower Bollinger Band")
        elif bb_signal == "OVERBOUGHT":
            signal_score -= 0.15
            confidence += 0.15
            reasons.append("Price near upper Bollinger Band")
        
        # 5. Support/Resistance (10% weight)
        sr = advanced.get("support_resistance", {})
        sr_signal = sr.get("signal", "BETWEEN_LEVELS")
        if sr_signal == "NEAR_SUPPORT":
            signal_score += 0.1
            confidence += 0.1
            reasons.append("Near support level")
        elif sr_signal == "NEAR_RESISTANCE":
            signal_score -= 0.1
            confidence += 0.1
            reasons.append("Near resistance level")
        
        # 6. Volume (10% weight)
        volume = advanced.get("volume_analysis", {})
        vol_signal = volume.get("signal", "NEUTRAL")
        if vol_signal == "BULLISH_CONFIRMATION":
            signal_score += 0.1
            confidence += 0.1
            reasons.append("Bullish volume confirmation")
        elif vol_signal == "BEARISH_CONFIRMATION":
            signal_score -= 0.1
            confidence += 0.1
            reasons.append("Bearish volume confirmation")
        
        # 7. Candlestick Patterns (bonus)
        patterns = advanced.get("candlestick_patterns", {})
        if patterns.get("bullish_engulfing"):
            signal_score += 0.05
            reasons.append("Bullish engulfing pattern")
        elif patterns.get("bearish_engulfing"):
            signal_score -= 0.05
            reasons.append("Bearish engulfing pattern")
        elif patterns.get("hammer"):
            signal_score += 0.03
            reasons.append("Hammer pattern")
        elif patterns.get("shooting_star"):
            signal_score -= 0.03
            reasons.append("Shooting star pattern")
        
        # Normalize signal to -1 to 1
        signal_score = max(-1.0, min(1.0, signal_score))
        confidence = min(100, max(0, confidence * 100))
        
        # Determine action from signal
        if signal_score > 0.5:
            action = TradeAction.STRONG_BUY
        elif signal_score > 0.2:
            action = TradeAction.BUY
        elif signal_score > -0.2:
            action = TradeAction.WAIT
        elif signal_score > -0.5:
            action = TradeAction.SELL
        else:
            action = TradeAction.STRONG_SELL
        
        return {
            "signal": action,
            "score": signal_score,
            "confidence": confidence,
            "reasons": reasons,
            "advanced": advanced
        }
    
    def _calculate_confidence(self, scores: List[Score], overall_score: float) -> float:
        """Calculate confidence based on score extremity and engine agreement"""
        if not scores:
            return 0
        
        base_confidence = abs(overall_score) * 100
        
        if overall_score > 0:
            agreement = sum(1 for s in scores if s.score > 0.2) / len(scores)
        else:
            agreement = sum(1 for s in scores if s.score < -0.2) / len(scores)
        
        confidence = base_confidence * 0.7 + (agreement * 30)
        return min(confidence, 95)
    
    def _determine_action(self, overall_score: float) -> TradeAction:
        if overall_score > 0.7:
            return TradeAction.STRONG_BUY
        elif overall_score > 0.3:
            return TradeAction.BUY
        elif overall_score > -0.3:
            return TradeAction.WAIT
        elif overall_score > -0.7:
            return TradeAction.SELL
        else:
            return TradeAction.STRONG_SELL
    
    def _generate_recommendation(self, action: TradeAction, score: float) -> str:
        if action in [TradeAction.STRONG_BUY, TradeAction.BUY]:
            strength = "Strong" if action == TradeAction.STRONG_BUY else ""
            return f"{strength} Bullish signal detected. Overall score: {score:.3f}. Consider long positions."
        elif action in [TradeAction.STRONG_SELL, TradeAction.SELL]:
            strength = "Strong" if action == TradeAction.STRONG_SELL else ""
            return f"{strength} Bearish signal detected. Overall score: {score:.3f}. Consider short positions."
        else:
            return f"Neutral market conditions. Overall score: {score:.3f}. Wait for clearer signals."
    
    def _determine_risk(self, action: TradeAction, confidence: float) -> str:
        if confidence > 75 and action in [TradeAction.STRONG_BUY, TradeAction.STRONG_SELL]:
            return "LOW"
        elif confidence > 50:
            return "MEDIUM"
        else:
            return "HIGH"