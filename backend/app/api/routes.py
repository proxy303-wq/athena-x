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
from ..providers.yfinance_provider import YahooFinanceProvider
from ..providers.groww import get_groww_provider
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
decision_service = DecisionService()
order_service = OrderService()
account_service = AccountService()
groww_provider = get_groww_provider()
yahoo_provider = YahooFinanceProvider()
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
            "market_data": "Yahoo Finance (no rate limits)",
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
            "yahoo-data": "/yahoo-data/{symbol}",
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
# SECTION 2: MARKET DATA (YAHOO FINANCE - NO RATE LIMITS)
# ============================================================

@router.get("/all-indices")
async def get_all_indices():
    """Get live data for all indices from Yahoo Finance (no rate limits)"""
    try:
        results = {}
        for key, info in INDICES.items():
            try:
                # Get LTP from Yahoo
                ltp = yahoo_provider.get_ltp(info["symbol"])
                
                # Get market data for OHLC
                market_data = yahoo_provider.get_market_data(info["symbol"], "1d", 1)
                
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
                        "source": "Yahoo Finance"
                    }
                else:
                    results[key] = {
                        "symbol": info["symbol"],
                        "name": info["name"],
                        "price": ltp,
                        "timestamp": datetime.now().isoformat(),
                        "source": "Yahoo Finance"
                    }
            except Exception as e:
                logger.error(f"Error fetching {key} from Yahoo: {e}")
                # Fallback to mock data
                results[key] = {
                    "symbol": info["symbol"],
                    "name": info["name"],
                    "price": yahoo_provider._get_fallback_price(info["symbol"]),
                    "timestamp": datetime.now().isoformat(),
                    "source": "Fallback",
                    "error": str(e)
                }
        return results
    except Exception as e:
        logger.error(f"Error in /all-indices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/yahoo-data/{symbol}")
async def get_yahoo_data(symbol: str = "NIFTY"):
    """Get live data from Yahoo Finance (no rate limits)"""
    try:
        ltp = yahoo_provider.get_ltp(symbol)
        market_data = yahoo_provider.get_market_data(symbol, "1d", 1)
        
        result = {
            "symbol": symbol,
            "ltp": ltp,
            "timestamp": datetime.now().isoformat(),
            "source": "Yahoo Finance"
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
        logger.error(f"Error fetching Yahoo data for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol, "timestamp": datetime.now().isoformat()}

@router.get("/ltp/{symbol}")
async def get_ltp(symbol: str):
    """Get live LTP from Yahoo Finance"""
    try:
        ltp = yahoo_provider.get_ltp(symbol)
        if ltp and ltp > 0:
            return {
                "symbol": symbol,
                "ltp": ltp,
                "timestamp": datetime.now().isoformat(),
                "source": "Yahoo Finance"
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
    """Get full quote from Yahoo Finance"""
    try:
        ltp = yahoo_provider.get_ltp(symbol)
        market_data = yahoo_provider.get_market_data(symbol, "1d", 1)
        
        result = {
            "symbol": symbol,
            "ltp": ltp,
            "timestamp": datetime.now().isoformat(),
            "source": "Yahoo Finance"
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
        
        # Add Yahoo price to result
        try:
            ltp = yahoo_provider.get_ltp(symbol)
            if ltp and ltp > 0:
                if "market_data" in result and result["market_data"]:
                    result["market_data"]["price"] = ltp
                    result["market_data"]["source"] = "Yahoo Finance"
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
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f0f1a; color: #fff; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .header h1 { font-size: 28px; }
        .status { padding: 8px 20px; border-radius: 20px; background: #00ff8844; color: #00ff88; font-size: 14px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: #1a1a2e; padding: 20px; border-radius: 12px; border: 1px solid #2a2a4e; }
        .card h3 { color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .card .value { font-size: 28px; font-weight: bold; }
        .positive { color: #00ff88; }
        .negative { color: #ff4466; }
        .neutral { color: #ffaa00; }
        .signal-section { background: #1a1a2e; padding: 20px; border-radius: 12px; margin-bottom: 30px; border: 1px solid #2a2a4e; }
        .signal { font-size: 32px; font-weight: bold; margin: 10px 0; }
        .refresh-btn { background: #2a2a4e; border: none; color: #fff; padding: 10px 25px; border-radius: 8px; cursor: pointer; }
        .refresh-btn:hover { background: #3a3a6e; }
        .footer { margin-top: 30px; text-align: center; color: #666; font-size: 12px; }
        .indices-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-top: 20px; }
        .index-card { background: #1a1a2e; padding: 15px; border-radius: 12px; border: 1px solid #2a2a4e; }
        .index-card h4 { color: #888; font-size: 14px; margin-bottom: 5px; }
        .index-card .price { font-size: 22px; font-weight: bold; }
        .index-card .change { font-size: 14px; }
        .live-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #00ff88; margin-right: 5px; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .bullish { color: #00ff88; }
        .bearish { color: #ff4466; }
        .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 800px) { .two-col { grid-template-columns: 1fr; } }
        .table-container { max-height: 300px; overflow-y: auto; }
        .order-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .order-table th { background: #2a2a4e; padding: 10px; text-align: left; color: #888; font-size: 12px; text-transform: uppercase; font-weight: normal; }
        .order-table td { padding: 10px; border-bottom: 1px solid #2a2a4e; }
        .order-table tr:hover { background: #1a1a2e; }
        .status-badge { padding: 3px 10px; border-radius: 12px; font-size: 12px; }
        .status-open { background: #ffaa0044; color: #ffaa00; }
        .status-completed { background: #00ff8844; color: #00ff88; }
        .status-cancelled { background: #ff446644; color: #ff4466; }
        .status-pending { background: #4a90d944; color: #4a90d9; }
        .oco-badge { background: #00ff8844; color: #00ff88; padding: 2px 8px; border-radius: 10px; font-size: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 Athena-X Portfolio Manager</h1>
            <span class="status" id="status">🟢 Live</span>
        </div>
        
        <div class="grid" id="stats">
            <div class="card"><h3>Capital</h3><div class="value" id="capital">₹5,00,000</div></div>
            <div class="card"><h3>Today's P&L</h3><div class="value neutral" id="today_pnl">₹0</div></div>
            <div class="card"><h3>Win Rate</h3><div class="value" id="win_rate">75%</div></div>
            <div class="card"><h3>Status</h3><div class="value positive" id="status_text">Active</div></div>
        </div>
        
        <div class="signal-section">
            <h2>📊 Signal</h2>
            <div class="signal neutral" id="signal">WAIT</div>
            <div id="signal_reason">Market consolidating - awaiting clear direction</div>
            <br>
            <button class="refresh-btn" onclick="refreshAll()">🔄 Refresh</button>
        </div>
        
        <div class="indices-grid" id="indices">
            <div class="index-card"><h4><span class="live-dot"></span>🇮🇳 NIFTY</h4><div class="price" id="nifty_price">---</div><div class="change" id="nifty_change">---</div></div>
            <div class="index-card"><h4><span class="live-dot"></span>🏦 BANK NIFTY</h4><div class="price" id="banknifty_price">---</div><div class="change" id="banknifty_change">---</div></div>
            <div class="index-card"><h4><span class="live-dot"></span>💰 FINNIFTY</h4><div class="price" id="finnifty_price">---</div><div class="change" id="finnifty_change">---</div></div>
            <div class="index-card"><h4><span class="live-dot"></span>📈 SENSEX</h4><div class="price" id="sensex_price">---</div><div class="change" id="sensex_change">---</div></div>
        </div>
        
        <div class="two-col">
            <div class="card">
                <h3>📋 Live Orders <span class="oco-badge">OCO Ready</span></h3>
                <div class="table-container">
                    <table class="order-table" id="orders_table">
                        <thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead>
                        <tbody id="orders_body"><tr><td colspan="5" style="text-align:center;color:#666;padding:20px;">No orders</td></tr></tbody>
                    </table>
                </div>
            </div>
            <div class="card">
                <h3>💼 Live Positions</h3>
                <div class="table-container">
                    <table class="order-table" id="positions_table">
                        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg Price</th><th>LTP</th><th>P&L</th></tr></thead>
                        <tbody id="positions_body"><tr><td colspan="5" style="text-align:center;color:#666;padding:20px;">No positions</td></tr></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Athena-X v5.0 | Data: Yahoo Finance | Trades: Groww API
        </div>
    </div>
    
    <script>
        const idMap = {
            'NIFTY': { price: 'nifty_price', change: 'nifty_change' },
            'BANKNIFTY': { price: 'banknifty_price', change: 'banknifty_change' },
            'FINNIFTY': { price: 'finnifty_price', change: 'finnifty_change' },
            'SENSEX': { price: 'sensex_price', change: 'sensex_change' }
        };
        let previousPrices = {};
        
        async function refreshAll() {
            const status = document.getElementById('status');
            status.textContent = '⏳ Loading...';
            
            try {
                // Get indices data from Yahoo Finance
                const indicesResp = await fetch('/all-indices');
                const indicesData = await indicesResp.json();
                
                for (const [key, indexData] of Object.entries(indicesData)) {
                    const priceEl = document.getElementById(idMap[key].price);
                    const changeEl = document.getElementById(idMap[key].change);
                    
                    if (indexData.price) {
                        priceEl.textContent = '₹' + indexData.price.toFixed(2);
                        const prev = previousPrices[key] || indexData.price;
                        const change = ((indexData.price - prev) / prev * 100);
                        previousPrices[key] = indexData.price;
                        changeEl.textContent = (change > 0 ? '+' : '') + change.toFixed(2) + '%';
                        changeEl.className = 'change ' + (change > 0 ? 'bullish' : (change < 0 ? 'bearish' : 'neutral'));
                    } else {
                        priceEl.textContent = '⚠️';
                        changeEl.textContent = indexData.error || 'No data';
                        changeEl.className = 'change error';
                    }
                }
                
                // Get signal
                const signalResp = await fetch('/analyze/NIFTY');
                const signalData = await signalResp.json();
                if (signalData && signalData.signal) {
                    const signal = signalData.signal;
                    document.getElementById('signal').textContent = signal.action || 'WAIT';
                    document.getElementById('signal_reason').textContent = signal.reason || 'Market analysis complete';
                    const signalEl = document.getElementById('signal');
                    signalEl.className = 'signal ' + (signal.action === 'STRONG_BUY' || signal.action === 'BUY' ? 'bullish' :
                                                       (signal.action === 'STRONG_SELL' || signal.action === 'SELL' ? 'bearish' : 'neutral'));
                }
                
                // Get performance
                const perfResp = await fetch('/performance');
                const perfData = await perfResp.json();
                if (perfData && perfData.performance) {
                    const pnl = perfData.performance.total_pnl || 0;
                    document.getElementById('today_pnl').textContent = (pnl >= 0 ? '+' : '') + '₹' + pnl.toFixed(2);
                    document.getElementById('today_pnl').className = 'value ' + (pnl >= 0 ? 'positive' : 'negative');
                    document.getElementById('win_rate').textContent = (perfData.performance.win_rate || 0).toFixed(1) + '%';
                }
                
                status.textContent = '🟢 Live';
                
            } catch(e) {
                console.error('Error fetching data:', e);
                document.getElementById('signal').textContent = '⚠️ ERROR';
                document.getElementById('signal_reason').textContent = 'Failed to fetch data. Check server.';
                status.textContent = '🔴 Error';
            }
        }
        
        // Refresh every 30 seconds
        refreshAll();
        setInterval(refreshAll, 30000);
        
        console.log('🧠 Athena-X Dashboard loaded');
        console.log('📊 Data source: Yahoo Finance');
        console.log('🔄 Auto-refresh every 30 seconds');
    </script>
</body>
</html>"""