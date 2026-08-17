# backend/app/services/order_service.py
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from ..providers.groww import get_groww_provider
from ..core.models import TradePlan

logger = logging.getLogger(__name__)

class OrderService:
    """
    Complete Order Service with all Groww APIs
    - Order Placement (Market, Limit, SL, SL-M)
    - Order Modification & Cancellation
    - Smart Orders (GTT, OCO)
    - Position Tracking (Live P&L)
    - Holdings & Margin Management
    - OCO Modification (NEW)
    - Margin Calculation (NEW)
    """
    
    def __init__(self):
        self.provider = get_groww_provider()
        self.active_orders = []
        self.completed_orders = []
        self._orders_cache = None
        self._orders_cache_time = None
        self._positions_cache = None
        self._positions_cache_time = None
    
    # ============================================================
    # ORDER PLACEMENT
    # ============================================================
    
    def place_order(self, trade_plan: TradePlan) -> Dict[str, Any]:
        try:
            order_data = {
                "trading_symbol": trade_plan.option_symbol,
                "exchange": "NSE",
                "segment": "FNO",
                "product": "NRML",
                "order_type": "LIMIT",
                "transaction_type": trade_plan.position_type,
                "quantity": trade_plan.quantity,
                "price": trade_plan.entry_price,
                "trigger_price": trade_plan.stop_loss,
                "validity": "DAY"
            }
            
            response = self.provider.place_order(order_data)
            
            if response and not response.get("error"):
                order = {
                    "order_id": response.get("order_id"),
                    "trade_plan": trade_plan.dict() if hasattr(trade_plan, 'dict') else trade_plan,
                    "status": "OPEN",
                    "entry_time": datetime.now(),
                    "response": response
                }
                self.active_orders.append(order)
                logger.info(f"Order placed: {trade_plan.option_symbol} @ {trade_plan.entry_price}")
                return {"status": "success", "order": order}
            else:
                logger.error(f"Order failed: {response}")
                return {"status": "error", "message": response.get("error", "Order failed")}
                
        except Exception as e:
            logger.error(f"Order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def place_market_order(self, trading_symbol: str, transaction_type: str, quantity: int, **kwargs) -> Dict:
        order_data = {
            "trading_symbol": trading_symbol,
            "exchange": kwargs.get("exchange", "NSE"),
            "segment": kwargs.get("segment", "FNO"),
            "product": kwargs.get("product", "NRML"),
            "order_type": "MARKET",
            "transaction_type": transaction_type,
            "quantity": quantity,
            "validity": "DAY"
        }
        return self.provider.place_order(order_data)
    
    def place_limit_order(self, trading_symbol: str, transaction_type: str, quantity: int, price: float, **kwargs) -> Dict:
        order_data = {
            "trading_symbol": trading_symbol,
            "exchange": kwargs.get("exchange", "NSE"),
            "segment": kwargs.get("segment", "FNO"),
            "product": kwargs.get("product", "NRML"),
            "order_type": "LIMIT",
            "transaction_type": transaction_type,
            "quantity": quantity,
            "price": price,
            "validity": "DAY"
        }
        return self.provider.place_order(order_data)
    
    def place_sl_order(self, trading_symbol: str, transaction_type: str, quantity: int, trigger_price: float, price: float = None, **kwargs) -> Dict:
        order_data = {
            "trading_symbol": trading_symbol,
            "exchange": kwargs.get("exchange", "NSE"),
            "segment": kwargs.get("segment", "FNO"),
            "product": kwargs.get("product", "NRML"),
            "order_type": "STOP_LOSS",
            "transaction_type": transaction_type,
            "quantity": quantity,
            "trigger_price": trigger_price,
            "price": price or trigger_price,
            "validity": "DAY"
        }
        return self.provider.place_order(order_data)
    
    # ============================================================
    # ORDER MANAGEMENT
    # ============================================================
    
    def modify_order(self, order_id: str, **kwargs) -> Dict[str, Any]:
        try:
            response = self.provider.modify_order(order_id, **kwargs)
            if response and not response.get("error"):
                logger.info(f"Order modified: {order_id}")
                return {"status": "success", "message": "Order modified"}
            return {"status": "error", "message": response.get("error", "Modification failed")}
        except Exception as e:
            logger.error(f"Modify order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        try:
            response = self.provider.cancel_order(order_id)
            if response and not response.get("error"):
                for order in self.active_orders:
                    if order["order_id"] == order_id:
                        order["status"] = "CANCELLED"
                        self.completed_orders.append(order)
                        self.active_orders.remove(order)
                        break
                logger.info(f"Order cancelled: {order_id}")
                return {"status": "success", "message": "Order cancelled"}
            return {"status": "error", "message": response.get("error", "Cancellation failed")}
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        try:
            return self.provider.get_order_detail(order_id)
        except Exception as e:
            logger.error(f"Order status error: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_order_list(self) -> List[Dict]:
        try:
            return self.provider.get_order_list()
        except Exception as e:
            logger.error(f"Order list error: {e}")
            return []
    
    def get_live_orders(self) -> List[Dict]:
        if self._orders_cache and self._orders_cache_time:
            age = (datetime.now() - self._orders_cache_time).total_seconds()
            if age < 30:
                return self._orders_cache
        
        orders = self.provider.get_order_list()
        self._orders_cache = orders
        self._orders_cache_time = datetime.now()
        return orders
    
    def get_active_orders(self) -> list:
        return self.active_orders
    
    def get_completed_orders(self) -> list:
        return self.completed_orders
    
    # ============================================================
    # POSITIONS & HOLDINGS
    # ============================================================
    
    def get_positions(self) -> List[Dict]:
        try:
            return self.provider.get_positions_for_user()
        except Exception as e:
            logger.error(f"Positions error: {e}")
            return []
    
    def get_position(self, trading_symbol: str) -> Dict:
        try:
            return self.provider.get_position_for_trading_symbol(trading_symbol)
        except Exception as e:
            logger.error(f"Position error: {e}")
            return {}
    
    def get_holdings(self) -> List[Dict]:
        try:
            return self.provider.get_holdings_for_user()
        except Exception as e:
            logger.error(f"Holdings error: {e}")
            return []
    
    def get_live_positions(self) -> List[Dict]:
        if self._positions_cache and self._positions_cache_time:
            age = (datetime.now() - self._positions_cache_time).total_seconds()
            if age < 30:
                return self._positions_cache
        
        positions = self.provider.get_positions_for_user()
        for pos in positions:
            pos["unrealized_pnl"] = pos.get("unrealized_pnl", 0)
            pos["realized_pnl"] = pos.get("realized_pnl", 0)
            pos["total_pnl"] = pos.get("unrealized_pnl", 0) + pos.get("realized_pnl", 0)
        self._positions_cache = positions
        self._positions_cache_time = datetime.now()
        return positions
    
    # ============================================================
    # SMART ORDERS (GTT & OCO)
    # ============================================================
    
    def create_gtt_order(
        self,
        trading_symbol: str,
        transaction_type: str,
        quantity: int,
        trigger_price: float,
        limit_price: float = None,
        exchange: str = "NSE",
        segment: str = "FNO",
        product: str = "NRML",
        validity: str = "GTC"
    ) -> Dict:
        """Create a GTT (Good Till Triggered) order"""
        try:
            if limit_price is None:
                limit_price = trigger_price
            
            order_data = {
                "order_type": "GTT",
                "trading_symbol": trading_symbol,
                "exchange": exchange,
                "segment": segment,
                "product": product,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "trigger_price": trigger_price,
                "price": limit_price,
                "validity": validity
            }
            
            response = self.provider.create_smart_order(order_data)
            
            if response and not response.get("error"):
                logger.info(f"GTT order created: {trading_symbol} @ {trigger_price}")
                return {"status": "success", "order": response}
            
            return {"status": "error", "message": response.get("error", "GTT creation failed")}
            
        except Exception as e:
            logger.error(f"GTT order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def create_oco_order(
        self,
        trading_symbol: str,
        transaction_type: str,
        quantity: int,
        trigger_price: float,
        target_price: float,
        stop_loss: float,
        exchange: str = "NSE",
        segment: str = "FNO",
        product: str = "NRML"
    ) -> Dict:
        """Create an OCO (One Cancels Other) order"""
        try:
            order_data = {
                "order_type": "OCO",
                "trading_symbol": trading_symbol,
                "exchange": exchange,
                "segment": segment,
                "product": product,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "trigger_price": trigger_price,
                "price": trigger_price,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "validity": "GTC"
            }
            
            response = self.provider.create_smart_order(order_data)
            
            if response and not response.get("error"):
                logger.info(f"OCO order created: {trading_symbol}")
                logger.info(f"   Entry: {trigger_price}, Target: {target_price}, SL: {stop_loss}")
                return {"status": "success", "order": response}
            
            return {"status": "error", "message": response.get("error", "OCO creation failed")}
            
        except Exception as e:
            logger.error(f"OCO order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def create_oco_from_trade_plan(self, trade_plan) -> Dict:
        try:
            if trade_plan.position_type == "BUY":
                trigger_price = trade_plan.entry_price
                target_price = trade_plan.target1
                stop_loss = trade_plan.stop_loss
            else:
                trigger_price = trade_plan.entry_price
                target_price = trade_plan.target1
                stop_loss = trade_plan.stop_loss
            
            return self.create_oco_order(
                trading_symbol=trade_plan.option_symbol,
                transaction_type=trade_plan.position_type,
                quantity=trade_plan.quantity,
                trigger_price=trigger_price,
                target_price=target_price,
                stop_loss=stop_loss
            )
            
        except Exception as e:
            logger.error(f"OCO from trade plan error: {e}")
            return {"status": "error", "message": str(e)}
    
    # ============================================================
    # OCO ORDER MODIFICATION (NEW)
    # ============================================================
    
    def modify_oco_order(
        self,
        order_id: str,
        new_target: float = None,
        new_stop_loss: float = None,
        new_trigger_price: float = None,
        new_quantity: int = None
    ) -> Dict:
        """
        Modify an existing OCO order dynamically
        
        Args:
            order_id: Existing OCO order ID
            new_target: New target price
            new_stop_loss: New stop-loss price
            new_trigger_price: New trigger price
            new_quantity: New quantity
        """
        try:
            current_order = self.get_smart_order(order_id)
            
            if not current_order:
                return {"status": "error", "message": "Order not found"}
            
            update_data = {}
            
            if new_target:
                update_data["target_price"] = new_target
            if new_stop_loss:
                update_data["stop_loss"] = new_stop_loss
            if new_trigger_price:
                update_data["trigger_price"] = new_trigger_price
            if new_quantity:
                update_data["quantity"] = new_quantity
            
            if not update_data:
                return {"status": "error", "message": "No updates provided"}
            
            response = self.provider.modify_smart_order(order_id, **update_data)
            
            if response and not response.get("error"):
                logger.info(f"OCO order modified: {order_id}")
                return {"status": "success", "order": response}
            
            return {"status": "error", "message": response.get("error", "Modification failed")}
            
        except Exception as e:
            logger.error(f"Modify OCO order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_active_oco_orders(self) -> List[Dict]:
        """Get all active OCO orders"""
        try:
            orders = self.get_smart_orders()
            return [o for o in orders if o.get("order_type") == "OCO" and o.get("status") == "ACTIVE"]
        except Exception as e:
            logger.error(f"Error fetching OCO orders: {e}")
            return []
    
    def get_gtt_orders(self) -> List[Dict]:
        """Get all GTT orders"""
        try:
            orders = self.get_smart_orders()
            return [o for o in orders if o.get("order_type") == "GTT"]
        except Exception as e:
            logger.error(f"Error fetching GTT orders: {e}")
            return []
    
    # ============================================================
    # MARGIN MANAGEMENT (NEW)
    # ============================================================
    
    def calculate_margin_required(
        self,
        trading_symbol: str,
        transaction_type: str,
        quantity: int,
        price: float,
        exchange: str = "NSE",
        segment: str = "FNO",
        product: str = "NRML"
    ) -> Dict:
        """
        Calculate margin required for an order before placing it
        This prevents order rejection due to insufficient margin.
        """
        try:
            order_data = {
                "trading_symbol": trading_symbol,
                "exchange": exchange,
                "segment": segment,
                "product": product,
                "transaction_type": transaction_type,
                "quantity": quantity,
                "price": price
            }
            
            response = self.provider.get_order_margin_details(order_data)
            
            if response and not response.get("error"):
                margin_required = response.get("total_margin", 0)
                available_margin = self.provider.get_available_margin_details().get("clear_cash", 0)
                
                return {
                    "status": "success",
                    "margin_required": margin_required,
                    "available_margin": available_margin,
                    "can_trade": available_margin >= margin_required,
                    "remaining_margin": available_margin - margin_required
                }
            
            return {"status": "error", "message": response.get("error", "Margin calculation failed")}
            
        except Exception as e:
            logger.error(f"Margin calculation error: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_margin_utilization(self) -> Dict:
        """Get current margin utilization across all positions"""
        try:
            margin = self.provider.get_available_margin_details()
            
            clear_cash = margin.get("clear_cash", 0)
            net_margin_used = margin.get("net_margin_used", 0)
            
            return {
                "total_cash": clear_cash,
                "margin_used": net_margin_used,
                "margin_available": clear_cash - net_margin_used,
                "utilization_percent": (net_margin_used / clear_cash * 100) if clear_cash > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error fetching margin utilization: {e}")
            return {}
    
    # ============================================================
    # SMART ORDER MANAGEMENT
    # ============================================================
    
    def get_smart_orders(self) -> List[Dict]:
        try:
            return self.provider.get_smart_order_list()
        except Exception as e:
            logger.error(f"Error fetching smart orders: {e}")
            return []
    
    def get_smart_order(self, order_id: str) -> Dict:
        try:
            return self.provider.get_smart_order(order_id)
        except Exception as e:
            logger.error(f"Error fetching smart order: {e}")
            return {}
    
    def modify_smart_order(self, order_id: str, **kwargs) -> Dict:
        try:
            response = self.provider.modify_smart_order(order_id, **kwargs)
            if response and not response.get("error"):
                return {"status": "success", "message": "Smart order modified"}
            return {"status": "error", "message": response.get("error", "Modification failed")}
        except Exception as e:
            logger.error(f"Modify smart order error: {e}")
            return {"status": "error", "message": str(e)}
    
    def cancel_smart_order(self, order_id: str) -> Dict:
        try:
            response = self.provider.cancel_smart_order(order_id)
            if response and not response.get("error"):
                return {"status": "success", "message": "Smart order cancelled"}
            return {"status": "error", "message": response.get("error", "Cancellation failed")}
        except Exception as e:
            logger.error(f"Cancel smart order error: {e}")
            return {"status": "error", "message": str(e)}
    
    # ============================================================
    # PERFORMANCE TRACKING
    # ============================================================
    
    def get_trade_performance(self) -> Dict:
        try:
            positions = self.get_live_positions()
            orders = self.get_live_orders()
            
            total_pnl = 0
            winning_trades = 0
            losing_trades = 0
            
            for position in positions:
                pnl = position.get("unrealized_pnl", 0)
                total_pnl += pnl
                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
            
            win_rate = (winning_trades / len(positions) * 100) if positions else 0
            
            return {
                "total_pnl": total_pnl,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "total_trades": len(positions),
                "win_rate": win_rate,
                "positions": positions,
                "orders": orders,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Performance error: {e}")
            return {"error": str(e)}
    
    # ============================================================
    # ACCOUNT & USER
    # ============================================================
    
    def get_user_profile(self) -> Dict:
        return self.provider.get_user_profile()
    
    def get_trade_list(self, order_id: str) -> List[Dict]:
        try:
            return self.provider.get_trade_list_for_order(order_id)
        except Exception as e:
            logger.error(f"Trade list error: {e}")
            return []
    
    def get_contracts(self, exchange: str = None, segment: str = None) -> List[Dict]:
        try:
            return self.provider.get_contracts(exchange, segment)
        except Exception as e:
            logger.error(f"Contracts error: {e}")
            return []
    
    def get_expiries(self, symbol: str) -> List[str]:
        try:
            return self.provider.get_expiries(symbol)
        except Exception as e:
            logger.error(f"Expiries error: {e}")
            return []
    
    def get_greeks(self, symbol: str, strike: float, expiry: str, option_type: str) -> Dict:
        try:
            return self.provider.get_greeks(symbol, strike, expiry, option_type)
        except Exception as e:
            logger.error(f"Greeks error: {e}")
            return {}
    
    def get_full_summary(self) -> Dict:
        try:
            profile = self.get_user_profile()
            positions = self.get_live_positions()
            holdings = self.get_holdings()
            margin = self.get_margin_utilization()
            performance = self.get_trade_performance()
            
            return {
                "profile": profile,
                "positions": positions,
                "holdings": holdings,
                "margin": margin,
                "performance": performance,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Summary error: {e}")
            return {"error": str(e)}