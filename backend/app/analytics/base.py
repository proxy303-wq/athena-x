from abc import ABC, abstractmethod
from typing import Dict, Any, List
from ..core.models import MarketData

class BaseAnalytics(ABC):
    @abstractmethod
    def analyze(self, data: MarketData, historical: List[MarketData]) -> Dict[str, Any]:
        pass
    
    def normalize(self, value: float, min_val: float, max_val: float) -> float:
        if max_val == min_val:
            return 0.5
        return max(0, min(1, (value - min_val) / (max_val - min_val)))