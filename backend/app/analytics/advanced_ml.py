# backend/app/analytics/advanced_ml.py
import numpy as np
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

logger = logging.getLogger(__name__)

class AdvancedMLPredictor(BaseAnalyticsEngine):
    """Advanced ML prediction with ensemble models"""
    
    def __init__(self, weight: float = 1.0):
        super().__init__(weight)
        self.is_trained = False
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        """Calculate ML-based prediction"""
        try:
            if not market_data or not market_data.close:
                return self._neutral_score("No market data")
            
            # Extract features
            features = self._extract_features(market_data, option_chain)
            
            # Get ensemble prediction
            predictions = self._ensemble_predict(features, market_data)
            
            return Score(
                engine_name="AdvancedML",
                score=predictions["score"],
                weight=self.weight,
                confidence=predictions["confidence"],
                signal=predictions["signal"],
                reasoning=predictions["reasoning"]
            )
            
        except Exception as e:
            logger.error(f"Advanced ML error: {e}")
            return self._neutral_score(f"Error: {str(e)}")
    
    def _extract_features(self, data: MarketData, option_chain: OptionChainData) -> Dict:
        """Extract advanced features"""
        features = {
            "price": data.close,
            "vwap": data.vwap or data.close,
            "prev_close": data.prev_close or data.close,
            "range_pct": (data.high - data.low) / data.close * 100 if data.high and data.low else 0,
            "vwap_diff": (data.close - data.vwap) / data.vwap if data.vwap and data.vwap > 0 else 0,
            "daily_change": (data.close - data.prev_close) / data.prev_close if data.prev_close and data.prev_close > 0 else 0,
            "pcr": option_chain.pcr if option_chain and option_chain.pcr else 1.0,
            "max_pain": option_chain.max_pain if option_chain and option_chain.max_pain else data.close,
            "underlying": option_chain.underlying_price if option_chain and option_chain.underlying_price else data.close,
            "strikes_count": len(option_chain.strikes) if option_chain else 0,
        }
        
        # Derived features
        features["momentum"] = features["daily_change"]
        features["volatility"] = features["range_pct"] / 100
        features["trend_strength"] = abs(features["vwap_diff"])
        
        # Support/Resistance proximity
        if option_chain and option_chain.strikes:
            nearest_strike = min(option_chain.strikes, key=lambda x: abs(x - data.close))
            features["strike_distance"] = (data.close - nearest_strike) / data.close
        else:
            features["strike_distance"] = 0
        
        return features
    
    def _ensemble_predict(self, features: Dict, data: MarketData) -> Dict:
        """Ensemble prediction from multiple models"""
        # Model 1: Linear momentum model
        score1 = self._model_linear(features)
        
        # Model 2: Volatility model
        score2 = self._model_volatility(features)
        
        # Model 3: Option chain model
        score3 = self._model_option_chain(features)
        
        # Model 4: Trend model
        score4 = self._model_trend(features)
        
        # Weighted ensemble
        scores = [score1, score2, score3, score4]
        weights = [0.30, 0.20, 0.25, 0.25]
        
        final_score = sum(s * w for s, w in zip(scores, weights))
        final_score = max(-1.0, min(1.0, final_score))
        
        # Confidence
        confidence = self._calculate_confidence(scores, final_score)
        
        # Signal
        if final_score > 0.15:
            signal = "BULLISH"
            reasoning = f"ML ensemble predicts UP ({final_score:.3f})"
        elif final_score < -0.15:
            signal = "BEARISH"
            reasoning = f"ML ensemble predicts DOWN ({final_score:.3f})"
        else:
            signal = "NEUTRAL"
            reasoning = f"ML ensemble predicts SIDEWAYS ({final_score:.3f})"
        
        return {
            "score": final_score,
            "confidence": confidence,
            "signal": signal,
            "reasoning": reasoning
        }
    
    def _model_linear(self, features: Dict) -> float:
        """Linear model"""
        score = (features.get("vwap_diff", 0) * 0.4 + 
                 features.get("daily_change", 0) * 0.3 + 
                 features.get("momentum", 0) * 0.3)
        return max(-1.0, min(1.0, score))
    
    def _model_volatility(self, features: Dict) -> float:
        """Volatility model"""
        vol = features.get("volatility", 0)
        if vol < 0.005:
            return 0.1
        elif vol > 0.02:
            return -0.1
        return 0
    
    def _model_option_chain(self, features: Dict) -> float:
        """Option chain model"""
        pcr = features.get("pcr", 1.0)
        if pcr > 1.2:
            return 0.3
        elif pcr < 0.8:
            return -0.3
        return 0
    
    def _model_trend(self, features: Dict) -> float:
        """Trend model"""
        strength = features.get("trend_strength", 0)
        if features.get("vwap_diff", 0) > 0:
            return min(strength, 0.5)
        else:
            return -min(strength, 0.5)
    
    def _calculate_confidence(self, scores: List[float], final_score: float) -> float:
        if not scores:
            return 0
        
        base = abs(final_score) * 100
        
        if final_score > 0:
            agreement = sum(1 for s in scores if s > 0) / len(scores)
        else:
            agreement = sum(1 for s in scores if s < 0) / len(scores)
        
        return min(base * 0.6 + agreement * 40, 95)
    
    def _neutral_score(self, reason: str) -> Score:
        return Score(
            engine_name="AdvancedML",
            score=0,
            weight=self.weight,
            confidence=0,
            signal="NEUTRAL",
            reasoning=reason
        )