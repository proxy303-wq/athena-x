# backend/app/services/price_monitor.py
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any
from .websocket_service import WebSocketService

logger = logging.getLogger(__name__)

class PriceMonitor:
    """
    Real-time price monitor using WebSocket
    """
    
    def __init__(self):
        self.ws_service = WebSocketService()
        self.price_history = {}
        self.last_ohlc = {}
        self.callbacks = []
        
        # Register WebSocket callbacks
        self.ws_service.register_callback(self._on_price_update)
    
    def start(self):
        """Start the price monitor"""
        self.ws_service.connect()
        logger.info("📊 Price monitor started")
    
    def stop(self):
        """Stop the price monitor"""
        self.ws_service.disconnect()
        logger.info("📊 Price monitor stopped")
    
    def subscribe(self, symbol: str):
        """Subscribe to a symbol"""
        self.ws_service.subscribe(symbol)
    
    def unsubscribe(self, symbol: str):
        """Unsubscribe from a symbol"""
        self.ws_service.unsubscribe(symbol)
    
    def _on_price_update(self, data: Dict):
        """Handle incoming price updates"""
        symbol = data.get("symbol")
        price = data.get("ltp")
        timestamp = data.get("timestamp")
        
        if not symbol or not price:
            return
        
        # Update price history
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append({
            "price": price,
            "timestamp": timestamp or datetime.now().isoformat()
        })
        
        # Keep last 100 prices
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol] = self.price_history[symbol][-100:]
        
        # Update OHLC
        if symbol not in self.last_ohlc:
            self.last_ohlc[symbol] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "timestamp": datetime.now().isoformat()
            }
        else:
            ohlc = self.last_ohlc[symbol]
            ohlc["high"] = max(ohlc["high"], price)
            ohlc["low"] = min(ohlc["low"], price)
            ohlc["close"] = price
            ohlc["timestamp"] = datetime.now().isoformat()
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback({
                    "symbol": symbol,
                    "price": price,
                    "ohlc": self.last_ohlc[symbol],
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def register_callback(self, callback):
        """Register a callback for price updates"""
        self.callbacks.append(callback)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        if symbol in self.last_ohlc:
            return self.last_ohlc[symbol]["close"]
        return None
    
    def get_ohlc(self, symbol: str) -> Optional[Dict]:
        """Get current OHLC for a symbol"""
        return self.last_ohlc.get(symbol)
    
    def get_price_history(self, symbol: str, count: int = 10) -> List[Dict]:
        """Get recent price history for a symbol"""
        if symbol in self.price_history:
            return self.price_history[symbol][-count:]
        return []
    
    def get_status(self) -> Dict:
        """Get monitor status"""
        return {
            "active_symbols": list(self.last_ohlc.keys()),
            "ws_status": self.ws_service.get_status(),
            "timestamp": datetime.now().isoformat()
        }