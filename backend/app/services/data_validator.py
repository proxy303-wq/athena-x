# backend/app/services/data_validator.py
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from ..core.models import MarketData, OptionChainData

logger = logging.getLogger(__name__)

class DataValidator:
    """Validate incoming data before processing"""
    
    def __init__(self):
        self.validation_errors = []
        self.validation_warnings = []
    
    def validate_market_data(self, data: Optional[MarketData]) -> bool:
        """Validate market data"""
        if data is None:
            self._add_error("Market data is None")
            return False
        
        errors = []
        warnings = []
        
        # Check required fields
        if not data.symbol:
            errors.append("Symbol is required")
        if not data.timestamp:
            errors.append("Timestamp is required")
        
        # Check price values
        if data.open <= 0:
            warnings.append(f"Open price is {data.open}")
        if data.high <= 0:
            warnings.append(f"High price is {data.high}")
        if data.low <= 0:
            warnings.append(f"Low price is {data.low}")
        if data.close <= 0:
            warnings.append(f"Close price is {data.close}")
        
        # Check OHLC logic
        if data.high < data.low:
            errors.append(f"High ({data.high}) is less than Low ({data.low})")
        if data.open > data.high or data.open < data.low:
            warnings.append(f"Open ({data.open}) outside High/Low range")
        if data.close > data.high or data.close < data.low:
            warnings.append(f"Close ({data.close}) outside High/Low range")
        
        # Log results
        if errors:
            self._add_error(f"Market data validation failed: {errors}")
            return False
        
        if warnings:
            self._add_warning(f"Market data warnings: {warnings}")
        
        return True
    
    def validate_option_chain(self, data: Optional[OptionChainData]) -> bool:
        """Validate option chain data"""
        if data is None:
            self._add_error("Option chain data is None")
            return False
        
        errors = []
        warnings = []
        
        # Check required fields
        if not data.symbol:
            errors.append("Symbol is required")
        if not data.strikes:
            warnings.append("No strikes available")
        
        # Check option data
        if data.call_options:
            for strike, option in data.call_options.items():
                if option.open_interest < 0:
                    warnings.append(f"Negative OI for call {strike}")
                if option.last_price < 0:
                    warnings.append(f"Negative last price for call {strike}")
        
        if data.put_options:
            for strike, option in data.put_options.items():
                if option.open_interest < 0:
                    warnings.append(f"Negative OI for put {strike}")
                if option.last_price < 0:
                    warnings.append(f"Negative last price for put {strike}")
        
        # PCR validation
        if data.pcr is not None and (data.pcr < 0 or data.pcr > 5):
            warnings.append(f"PCR is {data.pcr} - unusual value")
        
        if errors:
            self._add_error(f"Option chain validation failed: {errors}")
            return False
        
        if warnings:
            self._add_warning(f"Option chain warnings: {warnings}")
        
        return True
    
    def validate_trade(self, trade_data: Dict) -> bool:
        """Validate trade data"""
        if not trade_data:
            self._add_error("Trade data is empty")
            return False
        
        errors = []
        
        required_fields = ["symbol", "entry_price", "quantity", "position_type"]
        for field in required_fields:
            if field not in trade_data:
                errors.append(f"Missing field: {field}")
        
        if trade_data.get("entry_price", 0) <= 0:
            errors.append("Entry price must be positive")
        
        if trade_data.get("quantity", 0) <= 0:
            errors.append("Quantity must be positive")
        
        if trade_data.get("position_type") not in ["BUY", "SELL"]:
            errors.append("Position type must be BUY or SELL")
        
        if errors:
            self._add_error(f"Trade validation failed: {errors}")
            return False
        
        return True
    
    def _add_error(self, message: str):
        """Add validation error"""
        error = {
            "timestamp": datetime.now().isoformat(),
            "message": message
        }
        self.validation_errors.append(error)
        logger.error(f"Validation error: {message}")
    
    def _add_warning(self, message: str):
        """Add validation warning"""
        warning = {
            "timestamp": datetime.now().isoformat(),
            "message": message
        }
        self.validation_warnings.append(warning)
        logger.warning(f"Validation warning: {message}")
    
    def get_errors(self) -> list:
        """Get all validation errors"""
        return self.validation_errors[-100:]  # Last 100 errors
    
    def get_warnings(self) -> list:
        """Get all validation warnings"""
        return self.validation_warnings[-100:]  # Last 100 warnings
    
    def clear(self):
        """Clear validation logs"""
        self.validation_errors.clear()
        self.validation_warnings.clear()