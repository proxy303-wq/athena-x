import numpy as np
from typing import Dict, Any, List
from .base import BaseAnalytics
from ..core.models import MarketData

class SupportResistanceAnalytics(BaseAnalytics):
    def analyze(self, data: MarketData, historical: List[MarketData]) -> Dict[str, Any]:
        if len(historical) < 30:
            return {"support": data.close * 0.99, "resistance": data.close * 1.01, "predicted": "NEUTRAL", "confidence": 0}
        
        highs = [h.high for h in historical[-30:]]
        lows = [h.low for h in historical[-30:]]
        
        resistance = np.percentile(highs, 90)
        support = np.percentile(lows, 10)
        
        current = data.close
        dist_to_support = (current - support) / current
        dist_to_resistance = (resistance - current) / current
        
        if dist_to_support < 0.005:
            predicted = "UP"
            confidence = min(70, (0.01 - dist_to_support) * 100)
        elif dist_to_resistance < 0.005:
            predicted = "DOWN"
            confidence = min(70, (0.01 - dist_to_resistance) * 100)
        else:
            predicted = "NEUTRAL"
            confidence = 30
        
        return {
            "support": support,
            "resistance": resistance,
            "predicted": predicted,
            "confidence": confidence
        }