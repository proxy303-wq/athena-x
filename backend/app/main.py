# backend/app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import logging
import asyncio
from datetime import datetime

from backend.app.api.routes import router
from backend.app.services.health_service import HealthService
from backend.app.services.error_recovery import ErrorRecovery
from backend.app.services.websocket_manager import WebSocketManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
health_service = HealthService()
error_recovery = ErrorRecovery()
ws_manager = WebSocketManager()

app = FastAPI(
    title="Athena-X Trading Engine",
    description="Complete trading system with all features",
    version="5.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)

# ============================================================
# STARTUP EVENT - Start WebSocket
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Start WebSocket connection on boot"""
    try:
        await ws_manager.connect_groww_websocket()
        logger.info("WebSocket streaming started")
    except Exception as e:
        logger.warning(f"WebSocket startup error: {e}")

# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data"""
    await ws_manager.connect_client(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            symbol = data.get("symbol")
            
            if action == "subscribe" and symbol:
                await ws_manager.subscribe_client(websocket, symbol)
            elif action == "unsubscribe" and symbol:
                await ws_manager.unsubscribe_client(websocket, symbol)
            elif action == "get_price" and symbol:
                price = ws_manager.get_latest_price(symbol)
                if price:
                    await websocket.send_json({
                        "type": "price",
                        "symbol": symbol,
                        "price": price,
                        "timestamp": datetime.now().isoformat()
                    })
    except WebSocketDisconnect:
        ws_manager.disconnect_client(websocket)

# ============================================================
# HEALTH ENDPOINTS
# ============================================================

@app.get("/health")
async def health():
    return health_service.get_status()

@app.get("/health/live")
async def health_live():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}

@app.get("/health/ready")
async def health_ready():
    status = health_service.get_status()
    is_ready = status.get("status") not in ["critical"]
    return {"ready": is_ready, "status": status.get("status")}

@app.get("/health/ws")
async def health_ws():
    """Get WebSocket health status"""
    return ws_manager.get_status()

# ============================================================
# DASHBOARD
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("frontend/dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return """
        <html>
            <head><title>Athena-X</title></head>
            <body>
                <h1>Athena-X Dashboard</h1>
                <p>Dashboard file not found. Please create frontend/dashboard.html</p>
                <p>System is running with all features!</p>
                <ul>
                    <li>Live Market Data</li>
                    <li>ML Predictions</li>
                    <li>Backtesting</li>
                    <li>WebSocket Streaming</li>
                    <li>Health Monitoring</li>
                    <li>Auto-Trade</li>
                </ul>
                <p><a href="/docs">API Documentation</a></p>
            </body>
        </html>
        """

@app.get("/")
async def root():
    return {
        "message": "Athena-X Trading Engine v5.0",
        "status": "running",
        "features": {
            "market_data": "4 Indices",
            "analytics": "6 Engines + Advanced Technical Analysis",
            "trading": "Auto-execution with OCO/SL",
            "ml": "LSTM Price Prediction",
            "backtesting": "Historical Strategy Testing",
            "websocket": "Real-time Price Streaming",
            "health": "System Health Monitoring"
        },
        "endpoints": {
            "dashboard": "/dashboard",
            "health": "/health",
            "analyze": "/analyze/{symbol}",
            "ws": "ws://localhost:8000/ws"
        }
    }