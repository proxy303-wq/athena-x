import numpy as np
from typing import Dict, Any, List
from .base import BaseAnalytics
from ..core.models import MarketData

class TrendAnalytics(BaseAnalytics):
    def analyze(self, data: MarketData, historical: List[MarketData]) -> Dict[str, Any]:
        if len(historical) < 20:
            return {"direction": "NEUTRAL", "strength": 0, "confidence": 0}
        
        closes = [h.close for h in historical]
        sma_5 = np.mean(closes[-5:])
        sma_10 = np.mean(closes[-10:])
        sma_20 = np.mean(closes[-20:])
        current = data.close
        
        if current > sma_5 > sma_10 > sma_20:
            direction = "BULLISH"
            strength = self.normalize((current - sma_20) / sma_20, 0, 0.03)
        elif current < sma_5 < sma_10 < sma_20:
            direction = "BEARISH"
            strength = self.normalize((sma_20 - current) / sma_20, 0, 0.03)
        else:
            direction = "SIDEWAYS"
            strength = 0.3
        
        return {
            "direction": direction,
            "strength": strength,
            "confidence": min(strength * 100, 95),
            "sma_5": sma_5,
            "sma_10": sma_10,
            "sma_20": sma_20
        }