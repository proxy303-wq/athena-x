# backend/app/api/routes.py
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from ..services.decision_service import DecisionService
from ..services.order_service import OrderService
from ..services.account_service import AccountService
from ..services.health_service import HealthService
from ..services.data_validator import DataValidator
from ..services.ml_predictor import MLPredictor
from ..services.backtest import BacktestEngine
from ..providers.nse_provider import NSEProvider  # ✅ Use NSE instead of yfinance
from ..providers.groww import get_groww_provider

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
decision_service = DecisionService()
order_service = OrderService()
account_service = AccountService()
groww_provider = get_groww_provider()
health_service = HealthService()
validator = DataValidator()
ml_predictor = MLPredictor()
backtest_engine = BacktestEngine()
nse_provider = NSEProvider()  # ✅ NSE provider (no rate limits, no IP blocking)

# Define all indices
INDICES = {
    "NIFTY": {"symbol": "NIFTY", "name": "NIFTY 50"},
    "BANKNIFTY": {"symbol": "BANKNIFTY", "name": "NIFTY BANK"},
    "FINNIFTY": {"symbol": "FINNIFTY", "name": "NIFTY FINANCIAL"},
    "SENSEX": {"symbol": "SENSEX", "name": "SENSEX 30"}
}

# ============================================================
# ROOT & HEALTH
# ============================================================

@router.get("/")
async def root():
    return {
        "message": "Athena-X Trading Engine",
        "version": "5.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "market_data": "4 Indices (via NSE API - no rate limits)",
            "trading": "Groww API (orders only)",
            "ml": "LSTM Price Prediction",
            "backtesting": "Historical Strategy Testing",
            "websocket": "Real-time Price Streaming"
        }
    }

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "5.0.0"
    }

@router.get("/health/live")
async def health_live():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}

@router.get("/health/ready")
async def health_ready():
    return {"ready": True, "status": "healthy"}

# ============================================================
# MARKET DATA - NSE API (NO RATE LIMITS)
# ============================================================

@router.get("/all-indices")
async def get_all_indices():
    """Get live data for all indices from NSE API"""
    try:
        results = {}
        for key, info in INDICES.items():
            try:
                # Get LTP from NSE provider
                ltp = nse_provider.get_ltp(info["symbol"])
                
                # If NSE fails, try Groww as fallback
                if ltp is None or ltp <= 0:
                    logger.warning(f"NSE data failed for {key}, using Groww fallback")
                    try:
                        ltp = groww_provider.get_ltp(info["symbol"])
                    except:
                        ltp = None
                
                results[key] = {
                    "symbol": info["symbol"],
                    "name": info["name"],
                    "price": ltp,
                    "change": 0,
                    "change_percent": 0,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error fetching {key}: {e}")
                results[key] = {
                    "symbol": info["symbol"],
                    "name": info["name"],
                    "price": None,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        return results
    except Exception as e:
        logger.error(f"Error in /all-indices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ltp/{symbol}")
async def get_ltp(symbol: str):
    """Get live LTP from NSE API"""
    try:
        # Get from NSE provider
        ltp = nse_provider.get_ltp(symbol)
        
        # Fallback to Groww if NSE fails
        if ltp is None or ltp <= 0:
            try:
                ltp = groww_provider.get_ltp(symbol)
            except:
                ltp = None
        
        if ltp is None or ltp <= 0:
            return {
                "symbol": symbol, 
                "ltp": None, 
                "error": "Invalid price", 
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "symbol": symbol, 
            "ltp": ltp, 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching LTP for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-nse")
async def test_nse():
    """Test NSE API connection"""
    try:
        ltp = nse_provider.get_ltp("NIFTY")
        return {
            "nse_working": ltp is not None,
            "nifty_ltp": ltp,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "nse_working": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ============================================================
# ANALYZE & DECISION
# ============================================================

@router.get("/analyze/{symbol}")
async def analyze(symbol: str):
    """Get trading decision for a symbol"""
    try:
        result = decision_service.get_decision(symbol)
        return result
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return {
            "symbol": symbol, 
            "signal": {"action": "ERROR", "reason": str(e)},
            "timestamp": datetime.now().isoformat()
        }

@router.post("/execute/{symbol}")
async def execute_trade(symbol: str):
    """Execute a trade for a symbol"""
    try:
        result = decision_service.execute_trade(symbol)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# ACCOUNT BALANCE
# ============================================================

@router.get("/account/balance")
async def get_account_balance(force_refresh: bool = False):
    """Get real account balance from Groww"""
    try:
        balance = account_service.get_balance(force_refresh=force_refresh)
        return {
            "status": "success", 
            "data": balance, 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        # Return fallback if API fails
        return {
            "status": "success",
            "data": {
                "available": 500000,
                "clear_cash": 500000,
                "is_fallback": True,
                "error": str(e)
            },
            "timestamp": datetime.now().isoformat()
        }

@router.get("/account/profile")
async def get_account_profile():
    """Get user profile"""
    try:
        profile = account_service.get_user_profile()
        return {"status": "success", "data": profile, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.get("/account/summary")
async def get_account_summary():
    """Get account summary"""
    try:
        summary = account_service.get_account_summary()
        return {"status": "success", "data": summary, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ============================================================
# ORDERS & POSITIONS
# ============================================================

@router.get("/orders")
async def get_orders():
    """Get all orders"""
    try:
        orders = order_service.get_live_orders()
        return {
            "orders": orders, 
            "count": len(orders), 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return {"orders": [], "count": 0, "error": str(e)}

@router.get("/positions")
async def get_positions():
    """Get live positions"""
    try:
        positions = order_service.get_live_positions()
        return {
            "positions": positions, 
            "count": len(positions), 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {"positions": [], "count": 0, "error": str(e)}

@router.get("/performance")
async def get_performance():
    """Get trade performance"""
    try:
        performance = order_service.get_trade_performance()
        return {
            "performance": performance, 
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"performance": {}, "error": str(e)}

# ============================================================
# SMART ORDERS
# ============================================================

@router.post("/smart/gtt")
async def create_gtt_order(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    trigger_price: float,
    limit_price: Optional[float] = None,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    """Create a GTT order"""
    try:
        result = order_service.create_gtt_order(
            trading_symbol, transaction_type, quantity,
            trigger_price, limit_price, exchange, segment, product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/smart/oco")
async def create_oco_order(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    trigger_price: float,
    target_price: float,
    stop_loss: float,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    """Create an OCO order"""
    try:
        result = order_service.create_oco_order(
            trading_symbol, transaction_type, quantity,
            trigger_price, target_price, stop_loss,
            exchange, segment, product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/smart/orders")
async def get_smart_orders():
    """Get all smart orders"""
    try:
        orders = order_service.get_smart_orders()
        return {"orders": orders, "count": len(orders), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"orders": [], "count": 0, "error": str(e)}

# ============================================================
# MARGIN
# ============================================================

@router.post("/margin/calculate")
async def calculate_margin(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    price: float,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    """Calculate margin required for an order"""
    try:
        result = order_service.calculate_margin_required(
            trading_symbol, transaction_type, quantity,
            price, exchange, segment, product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/margin/utilization")
async def get_margin_utilization():
    """Get current margin utilization"""
    try:
        result = order_service.get_margin_utilization()
        return result
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# ML PREDICTIONS
# ============================================================

@router.get("/ml/predict/{symbol}")
async def ml_predict(symbol: str = "NIFTY"):
    """Get ML prediction for a symbol"""
    try:
        if not ml_predictor.is_trained:
            ml_predictor.train(symbol)
        result = ml_predictor.get_signal(symbol)
        return result
    except Exception as e:
        return {"error": str(e)}

@router.post("/ml/train/{symbol}")
async def ml_train(symbol: str = "NIFTY"):
    """Train ML model for a symbol"""
    try:
        success = ml_predictor.train(symbol)
        return {"success": success, "symbol": symbol}
    except Exception as e:
        return {"error": str(e)}

@router.get("/ml/status")
async def ml_status():
    """Get ML model status"""
    return {
        "is_trained": ml_predictor.is_trained,
        "model_available": ml_predictor.model is not None,
        "tensorflow_available": ml_predictor.TENSORFLOW_AVAILABLE
    }

# ============================================================
# BACKTESTING
# ============================================================

@router.get("/backtest/{symbol}")
async def run_backtest(symbol: str = "NIFTY", days: int = 30):
    """Run backtest for a symbol"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        result = backtest_engine.run(symbol, start_date, datetime.now())
        return result
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# DASHBOARD
# ============================================================

@router.get("/dashboard", response_class=HTMLResponse)
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
                <h1>🧠 Athena-X Dashboard</h1>
                <p>✅ System is running on Railway!</p>
                <p>📚 <a href="/docs" style="color: #00ff88;">API Documentation</a></p>
                <p>🔍 <a href="/health" style="color: #ffaa00;">Health Check</a></p>
                <hr style="border-color: #2a2a4e;">
                <p style="color: #666;">Athena-X v5.0 | NSE Data | Groww Execution</p>
            </body>
        </html>
        """