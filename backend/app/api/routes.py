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
from ..providers.nse_provider import NSEProvider
from ..providers.groww import get_groww_provider
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
decision_service = DecisionService()
order_service = OrderService()
account_service = AccountService()
groww_provider = get_groww_provider()
nse_provider = NSEProvider()
health_service = HealthService()
validator = DataValidator()
ml_predictor = MLPredictor()
backtest_engine = BacktestEngine()

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
            "market_data": "NSE API (no rate limits)",
            "analytics": "6 Engines + Advanced Technical Analysis",
            "trading": "Auto-execution with OCO/SL",
            "ml": "LSTM Price Prediction",
            "backtesting": "Historical Strategy Testing",
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
            "nse-data": "/nse-data/{symbol}",
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
# SECTION 2: MARKET DATA (NSE API - NO RATE LIMITS)
# ============================================================

@router.get("/all-indices")
async def get_all_indices():
    """Get live data for all indices from NSE (no rate limits)"""
    try:
        results = {}
        for key, info in INDICES.items():
            try:
                # Get LTP from NSE
                ltp = nse_provider.get_ltp(info["symbol"])
                
                # Get market data for OHLC
                market_data = nse_provider.get_market_data(info["symbol"], "1d", 1)
                
                if market_data and len(market_data) > 0:
                    data = market_data[0]
                    results[key] = {
                        "symbol": info["symbol"],
                        "name": info["name"],
                        "price": ltp,
                        "open": data.open,
                        "high": data.high,
                        "low": data.low,
                        "close": data.close,
                        "volume": data.volume,
                        "vwap": data.vwap,
                        "change": ltp - data.open if data.open else 0,
                        "change_percent": ((ltp - data.open) / data.open * 100) if data.open and data.open > 0 else 0,
                        "timestamp": datetime.now().isoformat(),
                        "source": "NSE"
                    }
                else:
                    results[key] = {
                        "symbol": info["symbol"],
                        "name": info["name"],
                        "price": ltp,
                        "timestamp": datetime.now().isoformat(),
                        "source": "NSE"
                    }
            except Exception as e:
                logger.error(f"Error fetching {key} from NSE: {e}")
                # Fallback to Groww
                try:
                    ltp = groww_provider.get_ltp(info["symbol"])
                    results[key] = {
                        "symbol": info["symbol"],
                        "name": info["name"],
                        "price": ltp,
                        "timestamp": datetime.now().isoformat(),
                        "source": "Groww (fallback)",
                        "error": str(e)
                    }
                except:
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

@router.get("/nse-data/{symbol}")
async def get_nse_data(symbol: str = "NIFTY"):
    """Get live data from NSE (no rate limits)"""
    try:
        ltp = nse_provider.get_ltp(symbol)
        market_data = nse_provider.get_market_data(symbol, "1d", 1)
        
        result = {
            "symbol": symbol,
            "ltp": ltp,
            "timestamp": datetime.now().isoformat(),
            "source": "NSE"
        }
        
        if market_data and len(market_data) > 0:
            data = market_data[0]
            result.update({
                "open": data.open,
                "high": data.high,
                "low": data.low,
                "close": data.close,
                "volume": data.volume,
                "vwap": data.vwap,
                "change": ltp - data.open if data.open else 0,
                "change_percent": ((ltp - data.open) / data.open * 100) if data.open and data.open > 0 else 0
            })
        
        return result
    except Exception as e:
        logger.error(f"Error fetching NSE data for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol, "timestamp": datetime.now().isoformat()}

@router.get("/ltp/{symbol}")
async def get_ltp(symbol: str):
    """Get live LTP from NSE first, fallback to Groww"""
    try:
        # Try NSE first (no rate limits)
        ltp = nse_provider.get_ltp(symbol)
        if ltp and ltp > 0:
            return {
                "symbol": symbol,
                "ltp": ltp,
                "timestamp": datetime.now().isoformat(),
                "source": "NSE"
            }
        
        # Fallback to Groww
        ltp = groww_provider.get_ltp(symbol)
        if ltp and ltp > 0:
            return {
                "symbol": symbol,
                "ltp": ltp,
                "timestamp": datetime.now().isoformat(),
                "source": "Groww (fallback)"
            }
        
        return {
            "symbol": symbol,
            "ltp": None,
            "error": "Invalid price",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching LTP for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """Get full quote from NSE"""
    try:
        ltp = nse_provider.get_ltp(symbol)
        market_data = nse_provider.get_market_data(symbol, "1d", 1)
        
        result = {
            "symbol": symbol,
            "ltp": ltp,
            "timestamp": datetime.now().isoformat(),
            "source": "NSE"
        }
        
        if market_data and len(market_data) > 0:
            data = market_data[0]
            result.update({
                "open": data.open,
                "high": data.high,
                "low": data.low,
                "close": data.close,
                "volume": data.volume,
                "vwap": data.vwap
            })
        
        return result
    except Exception as e:
        logger.error(f"Error fetching quote for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}

# ============================================================
# SECTION 3: ANALYZE & DECISION
# ============================================================

@router.get("/analyze/{symbol}")
async def analyze(symbol: str):
    """Get trading decision for a symbol"""
    try:
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol required")
        
        result = decision_service.get_decision(symbol)
        
        # Add NSE price to result
        try:
            ltp = nse_provider.get_ltp(symbol)
            if ltp and ltp > 0:
                if "market_data" in result and result["market_data"]:
                    result["market_data"]["price"] = ltp
                    result["market_data"]["source"] = "NSE"
        except:
            pass
        
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

@router.post("/execute/{symbol}")
async def execute_trade(symbol: str):
    """Execute a trade for a symbol"""
    try:
        result = decision_service.execute_trade(symbol)
        return result
    except Exception as e:
        logger.error(f"Error executing trade for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 4: ORDER MANAGEMENT
# ============================================================

@router.post("/order/market")
async def place_market_order(
    trading_symbol: str,
    transaction_type: str,
    quantity: int,
    exchange: str = "NSE",
    segment: str = "FNO",
    product: str = "NRML"
):
    """Place a market order via Groww"""
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
        logger.error(f"Error placing market order: {e}")
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
    """Place a limit order via Groww"""
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
        logger.error(f"Error placing limit order: {e}")
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
    """Place a stop-loss order via Groww"""
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
        logger.error(f"Error placing SL order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders")
async def get_orders():
    """Get all orders from Groww"""
    try:
        orders = order_service.get_live_orders()
        return {"orders": orders, "count": len(orders), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return {"orders": [], "count": 0, "error": str(e)}

@router.get("/order/{order_id}")
async def get_order_detail(order_id: str):
    """Get specific order detail"""
    try:
        order = order_service.get_order_status(order_id)
        return order
    except Exception as e:
        logger.error(f"Error fetching order detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/order/{order_id}")
async def modify_order(order_id: str, order_data: Dict):
    """Modify an order"""
    try:
        result = order_service.modify_order(order_id, **order_data)
        return result
    except Exception as e:
        logger.error(f"Error modifying order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/order/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order"""
    try:
        result = order_service.cancel_order(order_id)
        return result
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 5: POSITIONS & HOLDINGS
# ============================================================

@router.get("/positions")
async def get_positions():
    """Get live positions from Groww"""
    try:
        positions = order_service.get_live_positions()
        return {"positions": positions, "count": len(positions), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {"positions": [], "count": 0, "error": str(e)}

@router.get("/position/{trading_symbol}")
async def get_position(trading_symbol: str):
    """Get position for a specific symbol"""
    try:
        position = order_service.get_position(trading_symbol)
        return position
    except Exception as e:
        logger.error(f"Error fetching position: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/holdings")
async def get_holdings():
    """Get all holdings"""
    try:
        holdings = order_service.get_holdings()
        return {"holdings": holdings, "count": len(holdings), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching holdings: {e}")
        return {"holdings": [], "count": 0, "error": str(e)}

# ============================================================
# SECTION 6: PERFORMANCE
# ============================================================

@router.get("/performance")
async def get_performance():
    """Get trade performance"""
    try:
        performance = order_service.get_trade_performance()
        return {"performance": performance, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching performance: {e}")
        return {"performance": {}, "error": str(e)}

@router.get("/performance/summary")
async def get_performance_summary():
    """Get performance summary"""
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
        logger.error(f"Error fetching performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 7: SMART ORDERS (GTT/OCO)
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
    """Create a GTT (Good Till Triggered) order"""
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
        logger.error(f"Error creating GTT order: {e}")
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
    """Create an OCO (One Cancels Other) order"""
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
        logger.error(f"Error creating OCO order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/smart/orders")
async def get_smart_orders():
    """Get all smart orders"""
    try:
        orders = order_service.get_smart_orders()
        return {"orders": orders, "count": len(orders), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching smart orders: {e}")
        return {"orders": [], "count": 0, "error": str(e)}

@router.get("/smart/order/{order_id}")
async def get_smart_order(order_id: str):
    """Get a specific smart order"""
    try:
        order = order_service.get_smart_order(order_id)
        return order
    except Exception as e:
        logger.error(f"Error fetching smart order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/smart/order/{order_id}")
async def modify_smart_order(order_id: str, order_data: Dict):
    """Modify a smart order"""
    try:
        result = order_service.modify_smart_order(order_id, **order_data)
        return result
    except Exception as e:
        logger.error(f"Error modifying smart order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/smart/order/{order_id}")
async def cancel_smart_order(order_id: str):
    """Cancel a smart order"""
    try:
        result = order_service.cancel_smart_order(order_id)
        return result
    except Exception as e:
        logger.error(f"Error cancelling smart order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 8: MARGIN MANAGEMENT
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
        logger.error(f"Error calculating margin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/margin/utilization")
async def get_margin_utilization():
    """Get current margin utilization"""
    try:
        result = order_service.get_margin_utilization()
        return result
    except Exception as e:
        logger.error(f"Error fetching margin utilization: {e}")
        return {"error": str(e)}

# ============================================================
# SECTION 9: ACCOUNT
# ============================================================

@router.get("/account/balance")
async def get_account_balance(force_refresh: bool = False):
    """Get real account balance from Groww"""
    try:
        balance = account_service.get_balance(force_refresh=force_refresh)
        return {"status": "success", "data": balance, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/profile")
async def get_account_profile():
    """Get user profile"""
    try:
        profile = account_service.get_user_profile()
        return {"status": "success", "data": profile, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/margin")
async def get_account_margin():
    """Get margin details"""
    try:
        margin = account_service.get_margin_details()
        return {"status": "success", "data": margin, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching margin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/summary")
async def get_account_summary():
    """Get account summary"""
    try:
        summary = account_service.get_account_summary()
        return {"status": "success", "data": summary, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching account summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/account/pnl")
async def get_account_pnl():
    """Get P&L"""
    try:
        realized = account_service.get_realized_pnl()
        unrealized = account_service.get_unrealized_pnl()
        total = account_service.get_total_pnl()
        return {
            "status": "success",
            "data": {
                "realized_pnl": realized,
                "unrealized_pnl": unrealized,
                "total_pnl": total
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching P&L: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/account/refresh")
async def refresh_account():
    """Refresh account data"""
    try:
        account_service.clear_cache()
        balance = account_service.get_balance(force_refresh=True)
        return {"status": "success", "message": "Account data refreshed", "data": balance, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error refreshing account: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 10: ML PREDICTIONS
# ============================================================

@router.get("/ml/status")
async def ml_status():
    """Get ML model status"""
    try:
        return {
            "is_trained": ml_predictor.is_trained,
            "model_available": ml_predictor.model is not None
        }
    except Exception as e:
        logger.error(f"Error fetching ML status: {e}")
        return {"error": str(e)}

@router.get("/ml/predict/{symbol}")
async def get_ml_prediction(symbol: str = "NIFTY"):
    """Get ML prediction for a symbol"""
    try:
        if not ml_predictor.is_trained:
            ml_predictor.train(symbol)
        result = ml_predictor.get_signal(symbol)
        return result
    except Exception as e:
        logger.error(f"Error getting ML prediction: {e}")
        return {"error": str(e)}

@router.post("/ml/train/{symbol}")
async def train_ml_model(symbol: str = "NIFTY"):
    """Train ML model for a symbol"""
    try:
        success = ml_predictor.train(symbol)
        return {"success": success, "symbol": symbol}
    except Exception as e:
        logger.error(f"Error training ML model: {e}")
        return {"error": str(e)}

@router.get("/ml/signal/{symbol}")
async def ml_signal(symbol: str = "NIFTY"):
    """Get ML trading signal"""
    try:
        result = ml_predictor.get_signal(symbol)
        return result
    except Exception as e:
        logger.error(f"Error getting ML signal: {e}")
        return {"error": str(e)}

# ============================================================
# SECTION 11: BACKTESTING
# ============================================================

@router.get("/backtest/historical/{symbol}")
async def backtest_historical(
    symbol: str = "NIFTY",
    days: int = 30,
    capital: float = 500000
):
    """Run backtest on historical data"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        result = backtest_engine.run(symbol, start_date, datetime.now(), capital)
        return result
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        return {"error": str(e)}

@router.get("/backtest/expiry/{symbol}")
async def backtest_expiry(symbol: str = "NIFTY", months: int = 12):
    """Run expiry backtest"""
    try:
        result = backtest_engine.run_expiry_backtest(symbol, months)
        return result
    except Exception as e:
        logger.error(f"Error running expiry backtest: {e}")
        return {"error": str(e)}

# ============================================================
# SECTION 12: INSTRUMENTS & TRADES
# ============================================================

@router.get("/contracts")
async def get_contracts(exchange: Optional[str] = None, segment: Optional[str] = None):
    """Get all tradable contracts"""
    try:
        contracts = order_service.get_contracts(exchange, segment)
        return {"contracts": contracts, "count": len(contracts), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching contracts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/expiries/{symbol}")
async def get_expiries(symbol: str):
    """Get expiry dates for a symbol"""
    try:
        expiries = order_service.get_expiries(symbol)
        return {"symbol": symbol, "expiries": expiries, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching expiries: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trades/{order_id}")
async def get_trades(order_id: str):
    """Get trades for a specific order"""
    try:
        trades = order_service.get_trade_list(order_id)
        return {"order_id": order_id, "trades": trades, "count": len(trades), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 13: WEBSOCKET TOKEN
# ============================================================

@router.get("/ws/token")
async def get_ws_token():
    """Get WebSocket token"""
    try:
        token = groww_provider.generate_socket_token()
        return {"socket_token": token, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error generating WebSocket token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SECTION 14: DASHBOARD
# ============================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML"""
    try:
        with open("frontend/dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Dashboard file not found: {e}")
        return """<!DOCTYPE html>
<html>
<head>
    <title>Athena-X Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f0f1a; color: #fff; padding: 40px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; }
        .status { color: #00ff88; }
        .card { background: #1a1a2e; padding: 20px; border-radius: 12px; border: 1px solid #2a2a4e; margin: 10px 0; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .value { font-size: 24px; font-weight: bold; }
        .positive { color: #00ff88; }
        .negative { color: #ff4466; }
        .neutral { color: #ffaa00; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Athena-X Portfolio Manager</h1>
            <span class="status">🟢 Live</span>
        </div>
        <div class="card">
            <h2>📊 Signal</h2>
            <div class="value neutral">WAIT</div>
            <p>Market consolidating - awaiting clear direction</p>
        </div>
        <div class="grid">
            <div class="card"><h3>💰 Capital</h3><div class="value">₹5,00,000</div></div>
            <div class="card"><h3>📈 Today's P&L</h3><div class="value neutral">₹0</div></div>
            <div class="card"><h3>📊 Win Rate</h3><div class="value">75%</div></div>
            <div class="card"><h3>🟢 Status</h3><div class="value positive">Active</div></div>
        </div>
        <p style="color: #666; margin-top: 20px; text-align: center;">
            Athena-X v5.0 | Data: NSE API | Trades: Groww API
        </p>
    </div>
</body>
</html>"""