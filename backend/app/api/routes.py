# backend/app/api/routes.py
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from ..services.decision_service import DecisionService
from ..services.order_service import OrderService
from ..services.account_service import AccountService
from ..services.websocket_service import WebSocketService
from ..services.health_service import HealthService
from ..services.data_validator import DataValidator
from ..services.ml_predictor import MLPredictor
from ..services.backtest import BacktestEngine
from ..services.historical_data import HistoricalDataService
from ..providers.groww import get_groww_provider

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
decision_service = DecisionService()
order_service = OrderService()
account_service = AccountService()
groww_provider = get_groww_provider()
ws_service = WebSocketService()
health_service = HealthService()
validator = DataValidator()
ml_predictor = MLPredictor()
backtest_engine = BacktestEngine()
historical_service = HistoricalDataService()

# Define all indices
INDICES = {
    "NIFTY": {"symbol": "NIFTY", "name": "NIFTY 50"},
    "BANKNIFTY": {"symbol": "BANKNIFTY", "name": "NIFTY BANK"},
    "FINNIFTY": {"symbol": "FINNIFTY", "name": "NIFTY FINANCIAL"},
    "SENSEX": {"symbol": "SENSEX", "name": "SENSEX 30"}
}

# ============================================================
# SECTION 1: ROOT & HEALTH
# ============================================================

@router.get("/")
async def root():
    return {
        "message": "Athena-X Trading Engine",
        "version": "5.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "market_data": "4 Indices",
            "analytics": "6 Engines + Advanced Technical Analysis",
            "trading": "Auto-execution with OCO/SL",
            "ml": "LSTM Price Prediction",
            "backtesting": "Historical Strategy Testing (2020+)",
            "websocket": "Real-time Price Streaming",
            "health": "System Health Monitoring",
            "margin": "Real-time Margin Calculation"
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "dashboard": "/dashboard",
            "analyze": "/analyze/{symbol}",
            "all-indices": "/all-indices",
            "ltp": "/ltp/{symbol}",
            "orders": "/orders",
            "positions": "/positions",
            "performance": "/performance",
            "execute": "/execute/{symbol}",
            "smart": {
                "gtt": "/smart/gtt",
                "oco": "/smart/oco",
                "orders": "/smart/orders"
            },
            "ml": {
                "predict": "/ml/predict/{symbol}",
                "train": "/ml/train/{symbol}",
                "signal": "/ml/signal/{symbol}"
            },
            "backtest": {
                "historical": "/backtest/historical/{symbol}",
                "expiry": "/backtest/expiry/{symbol}"
            },
            "order": {
                "oco_modify": "/order/oco/{order_id}",
                "oco_active": "/order/oco/active",
                "gtt_active": "/order/gtt/active",
                "gtt_create": "/order/gtt"
            },
            "margin": {
                "calculate": "/margin/calculate",
                "utilization": "/margin/utilization"
            },
            "ws": "/ws",
            "account": {
                "balance": "/account/balance",
                "profile": "/account/profile",
                "margin": "/account/margin",
                "summary": "/account/summary",
                "pnl": "/account/pnl"
            }
        }
    }

@router.get("/health")
async def health():
    return health_service.get_status()

@router.get("/health/detailed")
async def health_detailed():
    return health_service.get_status()

@router.get("/health/validate")
async def health_validate():
    return {
        "errors": validator.get_errors(),
        "warnings": validator.get_warnings()
    }

@router.get("/health/live")
async def health_live():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}

@router.get("/health/ready")
async def health_ready():
    status = health_service.get_status()
    is_ready = status.get("status") not in ["critical"]
    return {"ready": is_ready, "status": status.get("status")}

# ============================================================
# SECTION 2: MARKET DATA
# ============================================================

@router.get("/analyze/{symbol}")
async def analyze(symbol: str):
    try:
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol required")
        
        result = decision_service.get_decision(symbol)
        ltp = groww_provider.get_ltp(symbol)
        
        if "market_data" in result and result["market_data"]:
            result["market_data"]["price"] = ltp
        
        if "decision" in result:
            decision = result["decision"]
            result["signal"] = {
                "action": decision.get("action", "WAIT"),
                "confidence": decision.get("confidence", 0),
                "reason": decision.get("recommendation", "Market analysis complete"),
                "timestamp": datetime.now().isoformat()
            }
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return {"symbol": symbol, "signal": {"action": "ERROR", "reason": str(e)}}

@router.get("/all-indices")
async def get_all_indices():
    try:
        results = {}
        for key, info in INDICES.items():
            try:
                ws_price = ws_service.get_latest_price(info["symbol"])
                if ws_price:
                    ltp = ws_price
                else:
                    ltp = groww_provider.get_ltp(info["symbol"])
                
                if ltp is None or ltp <= 0:
                    raise ValueError(f"Invalid price for {info['symbol']}")
                
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ltp/{symbol}")
async def get_ltp(symbol: str):
    try:
        ws_price = ws_service.get_latest_price(symbol)
        if ws_price:
            ltp = ws_price
        else:
            ltp = groww_provider.get_ltp(symbol)
        
        if ltp is None or ltp <= 0:
            return {"symbol": symbol, "ltp": None, "error": "Invalid price"}
        
        return {"symbol": symbol, "ltp": ltp, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 3: BACKTESTING (NEW)
# ============================================================

@router.get("/backtest/historical/{symbol}")
async def backtest_historical(
    symbol: str = "NIFTY",
    days: int = 30,
    capital: float = 500000
):
    """Run backtest on historical data (2020+)"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        result = backtest_engine.run(symbol, start_date, datetime.now(), capital)
        return result
    except Exception as e:
        return {"error": str(e)}

@router.get("/backtest/expiry/{symbol}")
async def backtest_expiry(symbol: str = "NIFTY", months: int = 12):
    """Run expiry backtest"""
    try:
        result = backtest_engine.run_expiry_backtest(symbol, months)
        return result
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# SECTION 4: ORDER MANAGEMENT ENHANCEMENTS (NEW)
# ============================================================

@router.put("/order/oco/{order_id}")
async def modify_oco(
    order_id: str,
    target: Optional[float] = None,
    stop_loss: Optional[float] = None,
    trigger: Optional[float] = None,
    quantity: Optional[int] = None
):
    """Modify an existing OCO order"""
    try:
        result = order_service.modify_oco_order(
            order_id, target, stop_loss, trigger, quantity
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/order/oco/active")
async def get_active_oco():
    """Get all active OCO orders"""
    try:
        orders = order_service.get_active_oco_orders()
        return {"orders": orders, "count": len(orders)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order/gtt")
async def create_gtt(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    trigger_price: float,
    limit_price: Optional[float] = None,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    """Create a GTT (Good Till Triggered) order"""
    try:
        result = order_service.create_gtt_order(
            trading_symbol, transaction_type, quantity,
            trigger_price, limit_price, exchange, segment, product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/order/gtt/active")
async def get_gtt_orders():
    """Get all GTT orders"""
    try:
        orders = order_service.get_gtt_orders()
        return {"orders": orders, "count": len(orders)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 5: MARGIN ENDPOINTS (NEW)
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
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 6: ORDER MANAGEMENT
# ============================================================

@router.post("/execute/{symbol}")
async def execute_trade(symbol: str):
    try:
        result = decision_service.execute_trade(symbol)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order/market")
async def place_market_order(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    try:
        result = order_service.place_market_order(
            trading_symbol=trading_symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            exchange=exchange,
            segment=segment,
            product=product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order/limit")
async def place_limit_order(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    price: float,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    try:
        result = order_service.place_limit_order(
            trading_symbol=trading_symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            exchange=exchange,
            segment=segment,
            product=product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order/sl")
async def place_sl_order(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    trigger_price: float,
    price: Optional[float] = None,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    try:
        result = order_service.place_sl_order(
            trading_symbol=trading_symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            trigger_price=trigger_price,
            price=price,
            exchange=exchange,
            segment=segment,
            product=product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders")
async def get_orders():
    try:
        orders = order_service.get_live_orders()
        return {"orders": orders, "count": len(orders), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/order/{order_id}")
async def get_order_detail(order_id: str):
    try:
        order = order_service.get_order_status(order_id)
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/order/{order_id}")
async def modify_order(order_id: str, order_data: Dict):
    try:
        result = order_service.modify_order(order_id, **order_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/order/{order_id}")
async def cancel_order(order_id: str):
    try:
        result = order_service.cancel_order(order_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 7: POSITIONS & HOLDINGS
# ============================================================

@router.get("/positions")
async def get_positions():
    try:
        positions = order_service.get_live_positions()
        return {"positions": positions, "count": len(positions), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/position/{trading_symbol}")
async def get_position(trading_symbol: str):
    try:
        position = order_service.get_position(trading_symbol)
        return position
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/holdings")
async def get_holdings():
    try:
        holdings = order_service.get_holdings()
        return {"holdings": holdings, "count": len(holdings), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 8: PERFORMANCE
# ============================================================

@router.get("/performance")
async def get_performance():
    try:
        performance = order_service.get_trade_performance()
        profile = order_service.get_user_profile()
        return {"performance": performance, "profile": profile, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/summary")
async def get_performance_summary():
    try:
        performance = order_service.get_trade_performance()
        return {
            "total_pnl": performance.get("total_pnl", 0),
            "total_realized_pnl": performance.get("total_realized_pnl", 0),
            "total_unrealized_pnl": performance.get("total_unrealized_pnl", 0),
            "winning_trades": performance.get("winning_trades", 0),
            "losing_trades": performance.get("losing_trades", 0),
            "total_trades": performance.get("total_trades", 0),
            "win_rate": performance.get("win_rate", 0),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 9: SMART ORDERS
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
    try:
        result = order_service.create_gtt_order(
            trading_symbol=trading_symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            trigger_price=trigger_price,
            limit_price=limit_price,
            exchange=exchange,
            segment=segment,
            product=product
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
    try:
        result = order_service.create_oco_order(
            trading_symbol=trading_symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            trigger_price=trigger_price,
            target_price=target_price,
            stop_loss=stop_loss,
            exchange=exchange,
            segment=segment,
            product=product
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/smart/orders")
async def get_smart_orders():
    try:
        orders = order_service.get_smart_orders()
        return {"orders": orders, "count": len(orders), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/smart/order/{order_id}")
async def get_smart_order(order_id: str):
    try:
        order = order_service.get_smart_order(order_id)
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/smart/order/{order_id}")
async def modify_smart_order(order_id: str, order_data: Dict):
    try:
        result = order_service.modify_smart_order(order_id, **order_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/smart/order/{order_id}")
async def cancel_smart_order(order_id: str):
    try:
        result = order_service.cancel_smart_order(order_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 10: ACCOUNT
# ============================================================

@router.get("/account/balance")
async def get_account_balance(force_refresh: bool = False):
    try:
        balance = account_service.get_balance(force_refresh=force_refresh)
        return {"status": "success", "data": balance, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/profile")
async def get_account_profile():
    try:
        profile = account_service.get_user_profile()
        return {"status": "success", "data": profile, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/margin")
async def get_account_margin():
    try:
        margin = account_service.get_margin_details()
        return {"status": "success", "data": margin, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/summary")
async def get_account_summary():
    try:
        summary = account_service.get_account_summary()
        return {"status": "success", "data": summary, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/pnl")
async def get_account_pnl():
    try:
        realized = account_service.get_realized_pnl()
        unrealized = account_service.get_unrealized_pnl()
        total = account_service.get_total_pnl()
        return {
            "status": "success",
            "data": {"realized_pnl": realized, "unrealized_pnl": unrealized, "total_pnl": total},
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/refresh")
async def refresh_account():
    try:
        account_service.clear_cache()
        balance = account_service.get_balance(force_refresh=True)
        return {"status": "success", "message": "Account data refreshed", "data": balance, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 11: ML PREDICTIONS
# ============================================================

@router.get("/ml/status")
async def ml_status():
    try:
        return {
            "is_trained": ml_predictor.is_trained,
            "model_available": ml_predictor.model is not None
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/ml/predict/{symbol}")
async def get_ml_prediction(symbol: str = "NIFTY"):
    try:
        if not ml_predictor.is_trained:
            ml_predictor.train(symbol)
        result = ml_predictor.get_signal(symbol)
        return result
    except Exception as e:
        return {"error": str(e)}

@router.post("/ml/train/{symbol}")
async def train_ml_model(symbol: str = "NIFTY"):
    try:
        success = ml_predictor.train(symbol)
        return {"success": success, "symbol": symbol}
    except Exception as e:
        return {"error": str(e)}

@router.get("/ml/signal/{symbol}")
async def ml_signal(symbol: str = "NIFTY"):
    try:
        result = ml_predictor.get_signal(symbol)
        return result
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# SECTION 12: WEBSOCKET TOKEN
# ============================================================

@router.get("/ws/token")
async def get_ws_token():
    try:
        token = groww_provider.generate_socket_token()
        return {"socket_token": token, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 13: INSTRUMENTS & TRADES
# ============================================================

@router.get("/contracts")
async def get_contracts(exchange: Optional[str] = None, segment: Optional[str] = None):
    try:
        contracts = order_service.get_contracts(exchange, segment)
        return {"contracts": contracts, "count": len(contracts), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/expiries/{symbol}")
async def get_expiries(symbol: str):
    try:
        expiries = order_service.get_expiries(symbol)
        return {"symbol": symbol, "expiries": expiries, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trades/{order_id}")
async def get_trades(order_id: str):
    try:
        trades = order_service.get_trade_list(order_id)
        return {"order_id": order_id, "trades": trades, "count": len(trades), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 14: DASHBOARD
# ============================================================

from fastapi.responses import HTMLResponse

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("frontend/dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return """
        <html>
            <head><title>Athena-X Dashboard</title></head>
            <body>
                <h1>Athena-X Dashboard</h1>
                <p>Dashboard file not found. Please create frontend/dashboard.html</p>
                <p>System is running with all features!</p>
                <ul>
                    <li>Live Market Data</li>
                    <li>ML Predictions</li>
                    <li>Backtesting (2020+)</li>
                    <li>OCO/GTT Orders</li>
                    <li>Margin Management</li>
                    <li>WebSocket Streaming</li>
                    <li>Health Monitoring</li>
                    <li>Auto-Trade</li>
                </ul>
                <p><a href="/docs">API Documentation</a></p>
            </body>
        </html>
        """