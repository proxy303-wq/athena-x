# backend/app/services/websocket_service.py
import asyncio
import json
import logging
import threading
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)

class WebSocketService:
    """
    WebSocket service for real-time market data streaming
    """
    
    def __init__(self):
        self.websocket = None
        self.running = False
        self.subscribed_symbols = set()
        self.callbacks = []
        self.last_price = {}
        self._ohlc = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
    
    def connect(self):
        """Establish WebSocket connection"""
        try:
            logger.info("🔌 Connecting to WebSocket...")
            self.running = True
            threading.Thread(target=self._run, daemon=True).start()
            logger.info("✅ WebSocket service started")
            return True
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect WebSocket"""
        self.running = False
        logger.info("🔌 WebSocket disconnected")
    
    def subscribe(self, symbol: str):
        """Subscribe to a symbol for real-time updates"""
        self.subscribed_symbols.add(symbol)
        logger.info(f"📡 Subscribed to: {symbol}")
    
    def unsubscribe(self, symbol: str):
        """Unsubscribe from a symbol"""
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols.remove(symbol)
            logger.info(f"📡 Unsubscribed from: {symbol}")
    
    def register_callback(self, callback: Callable):
        """Register a callback for price updates"""
        self.callbacks.append(callback)
    
    def _run(self):
        """Main WebSocket loop"""
        while self.running:
            try:
                self._simulate_stream()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.reconnect_attempts += 1
                if self.reconnect_attempts > self.max_reconnect_attempts:
                    logger.error("❌ Max reconnect attempts reached")
                    self.running = False
                    break
                time.sleep(5 * self.reconnect_attempts)
    
    def _simulate_stream(self):
        """Simulate real-time price updates"""
        base_prices = {
            "NIFTY": 24395.85,
            "BANKNIFTY": 44000.0,
            "FINNIFTY": 24000.0,
            "SENSEX": 65000.0
        }
        
        while self.running:
            try:
                for symbol in self.subscribed_symbols:
                    base_price = self.last_price.get(symbol, base_prices.get(symbol, 24395.85))
                    change = random.uniform(-2, 2)
                    new_price = max(10000, base_price + change)
                    self.last_price[symbol] = new_price
                    
                    # Update OHLC
                    if symbol not in self._ohlc:
                        self._ohlc[symbol] = {
                            "open": new_price,
                            "high": new_price,
                            "low": new_price,
                            "close": new_price
                        }
                    else:
                        ohlc = self._ohlc[symbol]
                        ohlc["high"] = max(ohlc["high"], new_price)
                        ohlc["low"] = min(ohlc["low"], new_price)
                        ohlc["close"] = new_price
                    
                    # Notify callbacks
                    data = {
                        "symbol": symbol,
                        "ltp": new_price,
                        "ohlc": self._ohlc.get(symbol, {}),
                        "timestamp": datetime.now().isoformat()
                    }
                    for callback in self.callbacks:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
            except Exception as e:
                logger.error(f"Simulation error: {e}")
            
            time.sleep(1)  # Update every second
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price from cache"""
        return self.last_price.get(symbol)
    
    def get_ohlc(self, symbol: str) -> Optional[Dict]:
        """Get latest OHLC for a symbol"""
        return self._ohlc.get(symbol)
    
    def get_status(self) -> Dict:
        """Get WebSocket service status"""
        return {
            "running": self.running,
            "connected": self.websocket is not None,
            "subscribed_symbols": list(self.subscribed_symbols),
            "last_update": datetime.now().isoformat(),
            "reconnect_attempts": self.reconnect_attempts
        }