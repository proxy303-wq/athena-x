import numpy as np
from typing import Dict, Any, List
from .base import BaseAnalytics
from ..core.models import MarketData

class MomentumAnalytics(BaseAnalytics):
    def analyze(self, data: MarketData, historical: List[MarketData]) -> Dict[str, Any]:
        if len(historical) < 14:
            return {"momentum": 0, "rsi": 50, "confidence": 0}
        
        closes = [h.close for h in historical]
        gains, losses = [], []
        
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        avg_gain = np.mean(gains[-14:]) if gains else 0
        avg_loss = np.mean(losses[-14:]) if losses else 0
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        if rsi > 70:
            momentum = "OVERSOLD"
            confidence = self.normalize(rsi - 70, 0, 30) * 100
        elif rsi < 30:
            momentum = "OVERBOUGHT"
            confidence = self.normalize(30 - rsi, 0, 30) * 100
        else:
            momentum = "NEUTRAL"
            confidence = 30
        
        return {"momentum": momentum, "rsi": rsi, "confidence": min(confidence, 90)}