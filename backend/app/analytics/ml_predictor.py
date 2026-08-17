# backend/app/analytics/ml_predictor.py
import numpy as np
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from ..core.models import Score, MarketData, OptionChainData
from .base_engine import BaseAnalyticsEngine

logger = logging.getLogger(__name__)

class MLPredictorEngine(BaseAnalyticsEngine):
    """Machine Learning based prediction engine"""
    
    def __init__(self, weight: float = 1.0):
        super().__init__(weight)
        self.prediction_cache = {}
        self.last_update = None
    
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        """Calculate ML-based prediction score"""
        try:
            if not market_data or not market_data.close:
                return self._neutral_score("No market data")
            
            # Get features from market data
            features = self._extract_features(market_data)
            
            # Make prediction using simple ML model (LSTM would be better)
            prediction = self._predict_movement(features, market_data)
            
            score = prediction["score"]
            confidence = prediction["confidence"]
            signal = prediction["signal"]
            reasoning = prediction["reasoning"]
            
            return Score(
                engine_name="MLPredictor",
                score=score,
                weight=self.weight,
                confidence=confidence,
                signal=signal,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"ML Predictor error: {e}")
            return self._neutral_score(f"Error: {str(e)}")
    
    def _extract_features(self, data: MarketData) -> Dict:
        """Extract features for ML model"""
        features = {
            "price": data.close,
            "vwap": data.vwap or data.close,
            "prev_close": data.prev_close or data.close,
            "range": (data.high - data.low) / data.close if data.high and data.low else 0,
            "volume": data.volume or 0,
        }
        
        # Calculate additional features
        if data.vwap and data.vwap > 0:
            features["vwap_diff"] = (data.close - data.vwap) / data.vwap
        else:
            features["vwap_diff"] = 0
        
        if data.prev_close and data.prev_close > 0:
            features["daily_change"] = (data.close - data.prev_close) / data.prev_close
        else:
            features["daily_change"] = 0
        
        return features
    
    def _predict_movement(self, features: Dict, data: MarketData) -> Dict:
        """Simple ML prediction (replace with actual LSTM model)"""
        score = 0
        confidence = 0
        reasons = []
        
        # 1. VWAP analysis
        vwap_diff = features.get("vwap_diff", 0)
        score += vwap_diff * 0.3
        if abs(vwap_diff) > 0.005:
            reasons.append(f"VWAP: {vwap_diff:.4f}")
        
        # 2. Daily change
        daily_change = features.get("daily_change", 0)
        score += daily_change * 0.3
        if abs(daily_change) > 0.005:
            reasons.append(f"Daily: {daily_change:.4f}")
        
        # 3. Range (volatility)
        range_val = features.get("range", 0)
        if range_val > 0.02:
            score -= 0.1  # High volatility = uncertain
            reasons.append(f"High volatility: {range_val:.4f}")
        elif range_val < 0.005:
            score += 0.1  # Low volatility = stable
            reasons.append(f"Low volatility: {range_val:.4f}")
        
        # 4. Momentum (price relative to recent)
        momentum = (data.close - 24300) / 24300 * 0.3
        score += momentum
        
        # Calculate confidence
        confidence = min(abs(score) * 80 + 10, 85)
        
        # Determine signal
        if score > 0.15:
            signal = "BULLISH"
            reasoning = f"ML predicts UP ({score:.3f}): {', '.join(reasons[:2])}"
        elif score < -0.15:
            signal = "BEARISH"
            reasoning = f"ML predicts DOWN ({score:.3f}): {', '.join(reasons[:2])}"
        else:
            signal = "NEUTRAL"
            reasoning = f"ML predicts SIDEWAYS ({score:.3f})"
        
        return {
            "score": max(-1.0, min(1.0, score)),
            "confidence": confidence,
            "signal": signal,
            "reasoning": reasoning
        }
    
    def _neutral_score(self, reason: str) -> Score:
        return Score(
            engine_name="MLPredictor",
            score=0,
            weight=self.weight,
            confidence=0,
            signal="NEUTRAL",
            reasoning=reason
        )