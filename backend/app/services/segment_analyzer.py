# backend/app/services/segment_analyzer.py
import logging
from datetime import datetime
from typing import Dict, Any, List
from ..core.models import MarketData, OptionChainData
from ..analytics import (
    PCREngine, OIEngine, MaxPainEngine, 
    GreeksEngine, TrendEngine, VWAPEngine, PredictorEngine
)
from ..providers.groww import GrowwProvider
from ..core.config import settings

logger = logging.getLogger(__name__)

class SegmentAnalyzer:
    """Analyze multiple segments and display trade reasons"""
    
    def __init__(self):
        self.provider = GrowwProvider()
        self.engines = [
            PCREngine(),
            OIEngine(),
            MaxPainEngine(),
            GreeksEngine(),
            TrendEngine(),
            VWAPEngine(),
            PredictorEngine()
        ]
        self.segments = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]
    
    def analyze_all_segments(self) -> List[Dict[str, Any]]:
        """Analyze all segments and return detailed results"""
        results = []
        
        for symbol in self.segments:
            try:
                market_data = self._get_market_data(symbol)
                option_chain = self._get_option_chain(symbol)
                
                segment_result = {
                    "symbol": symbol,
                    "price": market_data.close if market_data else 0,
                    "timestamp": datetime.now().isoformat(),
                    "engines": [],
                    "overall_score": 0,
                    "recommendation": "WAIT",
                    "trade_reason": []
                }
                
                total_score = 0
                total_weight = 0
                trade_reasons = []
                
                for engine in self.engines:
                    try:
                        score = engine.calculate(market_data, option_chain)
                        score.weight = settings.ENGINE_WEIGHTS.get(engine.__class__.__name__, 1.0)
                        
                        segment_result["engines"].append({
                            "name": score.engine_name,
                            "score": score.score,
                            "signal": score.signal,
                            "confidence": score.confidence,
                            "reasoning": score.reasoning
                        })
                        
                        total_score += score.score * score.weight
                        total_weight += score.weight
                        
                        # Collect trade reasons if score is significant
                        if abs(score.score) > 0.3:
                            trade_reasons.append({
                                "engine": score.engine_name,
                                "signal": score.signal,
                                "reason": score.reasoning,
                                "score": score.score
                            })
                    except Exception as e:
                        logger.error(f"Engine error for {symbol}: {e}")
                
                overall_score = total_score / total_weight if total_weight > 0 else 0
                segment_result["overall_score"] = overall_score
                
                # Determine recommendation
                if overall_score > 0.3:
                    segment_result["recommendation"] = "BUY"
                elif overall_score < -0.3:
                    segment_result["recommendation"] = "SELL"
                else:
                    segment_result["recommendation"] = "WAIT"
                
                segment_result["trade_reason"] = trade_reasons
                results.append(segment_result)
                
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                results.append({
                    "symbol": symbol,
                    "error": str(e),
                    "recommendation": "ERROR"
                })
        
        return results