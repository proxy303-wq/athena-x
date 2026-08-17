# backend/app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import logging
import os
import asyncio
from datetime import datetime

# Import services
from backend.app.api.routes import router
from backend.app.services.health_service import HealthService
from backend.app.services.error_recovery import ErrorRecovery
from backend.app.services.websocket_manager import WebSocketManager
from backend.app.services.data_validator import DataValidator
from backend.app.services.ml_predictor import MLPredictor
from backend.app.services.backtest import BacktestEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
health_service = HealthService()
error_recovery = ErrorRecovery()
websocket_manager = WebSocketManager()
data_validator = DataValidator()
ml_predictor = MLPredictor()
backtest_engine = BacktestEngine()

# Create FastAPI app
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
    logger.info("Athena-X starting up...")
    
    # Start error recovery
    error_recovery.start()
    logger.info("Error recovery started")
    
    # Start WebSocket
    try:
        await websocket_manager.connect_groww_websocket()
        logger.info("WebSocket streaming started")
    except Exception as e:
        logger.warning(f"WebSocket startup error: {e}")
    
    # Train ML model in background
    try:
        logger.info("Training ML model...")
        asyncio.create_task(train_ml_model())
    except Exception as e:
        logger.warning(f"ML training startup error: {e}")

async def train_ml_model():
    """Train ML model in background"""
    try:
        ml_predictor.train("NIFTY")
        logger.info("ML model trained successfully")
    except Exception as e:
        logger.warning(f"ML training failed: {e}")

# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data"""
    await websocket_manager.connect_client(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            symbol = data.get("symbol")
            
            if action == "subscribe" and symbol:
                await websocket_manager.subscribe_client(websocket, symbol)
            elif action == "unsubscribe" and symbol:
                await websocket_manager.unsubscribe_client(websocket, symbol)
            elif action == "get_price" and symbol:
                price = websocket_manager.get_latest_price(symbol)
                if price:
                    await websocket.send_json({
                        "type": "price",
                        "symbol": symbol,
                        "price": price,
                        "timestamp": datetime.now().isoformat()
                    })
    except WebSocketDisconnect:
        websocket_manager.disconnect_client(websocket)

# ============================================================
# HEALTH ENDPOINTS
# ============================================================

@app.get("/health")
async def health():
    """Get system health status"""
    return health_service.get_status()

@app.get("/health/detailed")
async def health_detailed():
    """Get detailed health status"""
    return health_service.get_status()

@app.get("/health/validate")
async def health_validate():
    """Get validation status"""
    return {
        "errors": data_validator.get_errors(),
        "warnings": data_validator.get_warnings()
    }

@app.get("/health/live")
async def health_live():
    """Liveness probe"""
    return {"status": "alive", "timestamp": datetime.now().isoformat()}

@app.get("/health/ready")
async def health_ready():
    """Readiness probe"""
    status = health_service.get_status()
    is_ready = status.get("status") not in ["critical"]
    return {"ready": is_ready, "status": status.get("status")}

@app.get("/health/ws")
async def health_ws():
    """Get WebSocket health status"""
    return websocket_manager.get_status()

# ============================================================
# DASHBOARD
# ============================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML"""
    try:
        with open("frontend/dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return """
        <html>
            <head><title>Athena-X</title></head>
            <body style="font-family: Arial; background: #0f0f1a; color: #fff; padding: 40px;">
                <h1>Athena-X Dashboard</h1>
                <p>System is running!</p>
                <p>Environment: <strong>Railway</strong></p>
                <p><a href="/docs" style="color: #00ff88;">API Documentation</a></p>
                <p><a href="/health" style="color: #ffaa00;">Health Check</a></p>
                <hr style="border-color: #2a2a4e;">
                <p style="color: #666;">Athena-X v5.0 | Fully Automated Trading Engine</p>
            </body>
        </html>
        """

# ============================================================
# BACKTESTING ENDPOINTS
# ============================================================

@app.get("/backtest/{symbol}")
async def run_backtest(symbol: str, days: int = 30):
    """Run backtest for a symbol"""
    try:
        from datetime import datetime, timedelta
        start_date = datetime.now() - timedelta(days=days)
        result = backtest_engine.run(symbol, start_date, datetime.now())
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/backtest/multiple")
async def run_backtest_multiple(days: int = 30):
    """Run backtest on multiple symbols"""
    try:
        result = backtest_engine.run_multiple(days=days)
        return result
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# ML PREDICTION ENDPOINTS
# ============================================================

@app.get("/ml/predict/{symbol}")
async def ml_predict(symbol: str = "NIFTY"):
    """Get ML prediction for a symbol"""
    try:
        if not ml_predictor.is_trained:
            ml_predictor.train(symbol)
        result = ml_predictor.get_signal(symbol)
        return result
    except Exception as e:
        return {"error": str(e)}

@app.post("/ml/train/{symbol}")
async def ml_train(symbol: str = "NIFTY"):
    """Train ML model for a symbol"""
    try:
        success = ml_predictor.train(symbol)
        return {"success": success, "symbol": symbol}
    except Exception as e:
        return {"error": str(e)}

@app.get("/ml/status")
async def ml_status():
    """Get ML model status"""
    return {
        "is_trained": ml_predictor.is_trained,
        "model_available": ml_predictor.model is not None,
        "tensorflow_available": ml_predictor.TENSORFLOW_AVAILABLE
    }

# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():
    """Root endpoint"""
    is_railway = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    
    return {
        "message": "Athena-X Trading Engine v5.0",
        "status": "running",
        "environment": "railway" if is_railway else "local",
        "features": {
            "market_data": "4 Indices (NIFTY, BANKNIFTY, FINNIFTY, SENSEX)",
            "analytics": "6 Engines + Advanced Technical Analysis",
            "trading": "Auto-execution with OCO/SL",
            "ml": "LSTM Price Prediction",
            "backtesting": "Historical Strategy Testing",
            "websocket": "Real-time Price Streaming",
            "health": "System Health Monitoring",
            "margin": "Real-time Margin Calculation"
        },
        "endpoints": {
            "dashboard": "/dashboard",
            "health": "/health",
            "docs": "/docs",
            "analyze": "/analyze/{symbol}",
            "backtest": "/backtest/{symbol}",
            "ml_predict": "/ml/predict/{symbol}",
            "ws": "ws://localhost:8000/ws"
        },
        "timestamp": datetime.now().isoformat()
    }