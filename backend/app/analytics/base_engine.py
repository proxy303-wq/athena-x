# backend/app/analytics/base_engine.py
from abc import ABC, abstractmethod
from typing import Any
from ..core.models import Score, MarketData, OptionChainData

class BaseAnalyticsEngine(ABC):
    """Base class for all analytical engines"""
    
    def __init__(self, weight: float = 1.0):
        self.weight = weight
    
    @abstractmethod
    def calculate(self, market_data: MarketData, option_chain: OptionChainData) -> Score:
        """Calculate score based on market data"""
        pass
    
    def normalize_score(self, raw_value: float, min_val: float, max_val: float) -> float:
        """Normalize any value to -1 to +1 range"""
        if max_val == min_val:
            return 0
        normalized = 2 * ((raw_value - min_val) / (max_val - min_val)) - 1
        return max(-1.0, min(1.0, normalized))