# backend/app/services/websocket_manager.py
import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Dict, Set, Any, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
from ..providers.groww import get_groww_provider

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscribers: Dict[str, Set[WebSocket]] = {}
        self.provider = get_groww_provider()
        self.running = False
        self.groww_ws = None
        self.last_prices = {}
        self.symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"]
        self._mock_mode = False
    
    async def connect_groww_websocket(self):
        """Connect to Groww WebSocket"""
        try:
            # Try to get WebSocket URL
            ws_url = self.provider.get_websocket_url()
            
            # If no URL or mock mode, use mock data
            if not ws_url:
                logger.info("No WebSocket URL - using mock data")
                self._mock_mode = True
                self.running = True
                asyncio.create_task(self._mock_stream())
                return False
            
            # Try to connect to real WebSocket
            try:
                import websockets
                self.groww_ws = await websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=60
                )
                self.running = True
                self._mock_mode = False
                logger.info("Connected to Groww WebSocket")
                
                await self._subscribe_symbols()
                asyncio.create_task(self._listen_loop())
                return True
                
            except ImportError:
                logger.warning("websockets library not installed - using mock data")
                self._mock_mode = True
                self.running = True
                asyncio.create_task(self._mock_stream())
                return False
            except Exception as e:
                logger.error(f"WebSocket connection failed: {e}")
                logger.info("Falling back to mock data")
                self._mock_mode = True
                self.running = True
                asyncio.create_task(self._mock_stream())
                return False
                
        except Exception as e:
            logger.error(f"WebSocket setup error: {e}")
            self._mock_mode = True
            self.running = True
            asyncio.create_task(self._mock_stream())
            return False
    
    async def _mock_stream(self):
        """Mock WebSocket stream for testing"""
        base_prices = {
            "NIFTY": 24395.85,
            "BANKNIFTY": 57491.10,
            "FINNIFTY": 26213.65,
            "SENSEX": 81000.00
        }
        
        logger.info("Starting mock WebSocket stream")
        
        while self.running:
            try:
                for symbol in self.symbols:
                    current = self.last_prices.get(symbol, {}).get("price", base_prices.get(symbol, 20000))
                    change = random.uniform(-3, 3)
                    new_price = max(1000, current + change)
                    
                    self.last_prices[symbol] = {
                        "price": new_price,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    if symbol in self.subscribers:
                        message = {
                            "type": "price_update",
                            "symbol": symbol,
                            "price": new_price,
                            "timestamp": datetime.now().isoformat()
                        }
                        for ws in self.subscribers.get(symbol, set()):
                            try:
                                await ws.send_json(message)
                            except:
                                pass
                
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Mock stream error: {e}")
                await asyncio.sleep(5)
    
    async def _subscribe_symbols(self):
        """Subscribe to symbols on real WebSocket"""
        if not self.groww_ws:
            return
        
        for symbol in self.symbols:
            try:
                await self.groww_ws.send(json.dumps({
                    "action": "subscribe",
                    "symbol": symbol,
                    "exchange": "NSE"
                }))
                logger.info(f"Subscribed to: {symbol}")
            except Exception as e:
                logger.error(f"Subscription error for {symbol}: {e}")
    
    async def _listen_loop(self):
        """Listen for real WebSocket messages"""
        while self.running and self.groww_ws:
            try:
                data = json.loads(await self.groww_ws.recv())
                symbol = data.get("symbol")
                price = data.get("ltp")
                
                if symbol and price:
                    self.last_prices[symbol] = {
                        "price": price,
                        "timestamp": data.get("timestamp", datetime.now().isoformat())
                    }
                    
                    if symbol in self.subscribers:
                        message = {
                            "type": "price_update",
                            "symbol": symbol,
                            "price": price,
                            "timestamp": datetime.now().isoformat()
                        }
                        for ws in self.subscribers.get(symbol, set()):
                            try:
                                await ws.send_json(message)
                            except:
                                pass
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                await asyncio.sleep(5)
    
    # ============================================================
    # CLIENT CONNECTION MANAGEMENT
    # ============================================================
    
    async def connect_client(self, websocket: WebSocket):
        """Accept new WebSocket client"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Client connected: {len(self.active_connections)} total")
    
    def disconnect_client(self, websocket: WebSocket):
        """Remove WebSocket client"""
        self.active_connections.remove(websocket)
        for symbol in list(self.subscribers.keys()):
            if websocket in self.subscribers.get(symbol, set()):
                self.subscribers[symbol].remove(websocket)
        logger.info(f"Client disconnected: {len(self.active_connections)} remaining")
    
    async def subscribe_client(self, websocket: WebSocket, symbol: str):
        """Subscribe client to symbol"""
        if symbol not in self.subscribers:
            self.subscribers[symbol] = set()
        self.subscribers[symbol].add(websocket)
        
        if symbol in self.last_prices:
            await websocket.send_json({
                "type": "initial_price",
                "symbol": symbol,
                "price": self.last_prices[symbol]["price"],
                "timestamp": self.last_prices[symbol]["timestamp"]
            })
        
        logger.info(f"Client subscribed to {symbol}")
    
    async def unsubscribe_client(self, websocket: WebSocket, symbol: str):
        """Unsubscribe client from symbol"""
        if symbol in self.subscribers and websocket in self.subscribers[symbol]:
            self.subscribers[symbol].remove(websocket)
            logger.info(f"Client unsubscribed from {symbol}")
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price from cache"""
        if symbol in self.last_prices:
            return self.last_prices[symbol]["price"]
        return None
    
    def get_status(self) -> Dict:
        """Get WebSocket status"""
        return {
            "running": self.running,
            "connected": self.groww_ws is not None,
            "mock_mode": self._mock_mode,
            "subscribed_symbols": list(self.subscribers.keys()),
            "connected_clients": len(self.active_connections),
            "last_prices": self.last_prices,
            "timestamp": datetime.now().isoformat()
        }