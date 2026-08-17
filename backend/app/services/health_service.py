# backend/app/services/health_service.py
import logging
import psutil
from datetime import datetime
from typing import Dict, Any
from ..core.config import settings

logger = logging.getLogger(__name__)

class HealthService:
    """Health check service with detailed monitoring"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.last_check = None
        self.checks = {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        self.last_check = datetime.now()
        
        return {
            "status": self._get_overall_status(),
            "timestamp": self.last_check.isoformat(),
            "uptime": (self.last_check - self.start_time).total_seconds(),
            "system": self._get_system_health(),
            "api": self._get_api_health(),
            "database": self._get_database_health(),
            "groww": self._get_groww_health(),
            "trading": self._get_trading_health()
        }
    
    def _get_overall_status(self) -> str:
        """Get overall status"""
        if any(self.checks.get(k, {}).get("status") == "critical" for k in ["api", "groww"]):
            return "critical"
        if any(self.checks.get(k, {}).get("status") == "warning" for k in ["system", "database"]):
            return "warning"
        return "healthy"
    
    def _get_system_health(self) -> Dict:
        """Get system health metrics"""
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            status = "healthy"
            if cpu > 80 or memory.percent > 80 or disk.percent > 85:
                status = "warning"
            if cpu > 95 or memory.percent > 95 or disk.percent > 95:
                status = "critical"
            
            return {
                "status": status,
                "cpu": cpu,
                "memory": memory.percent,
                "disk": disk.percent,
                "processes": len(psutil.pids())
            }
        except:
            return {"status": "unknown", "error": "Unable to fetch system metrics"}
    
    def _get_api_health(self) -> Dict:
        """Get API health"""
        try:
            # Check if API is responding
            import requests
            response = requests.get("http://localhost:8000/health", timeout=5)
            
            return {
                "status": "healthy" if response.status_code == 200 else "warning",
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            }
        except:
            return {"status": "critical", "error": "API not responding"}
    
    def _get_database_health(self) -> Dict:
        """Get database health"""
        try:
            from ..database import Database
            db = Database()
            stats = db.get_stats()
            
            return {
                "status": "healthy",
                "trades": stats.get("total_trades", 0),
                "win_rate": stats.get("win_rate", 0),
                "last_check": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "warning", "error": str(e)}
    
    def _get_groww_health(self) -> Dict:
        """Get Groww API health"""
        try:
            from ..providers.groww import GrowwProvider
            provider = GrowwProvider()
            
            # Test authentication
            if provider.authenticated:
                return {
                    "status": "healthy",
                    "authenticated": True,
                    "last_price": provider.get_ltp("NIFTY")
                }
            else:
                return {
                    "status": "warning",
                    "authenticated": False,
                    "message": "Not authenticated"
                }
        except Exception as e:
            return {"status": "critical", "error": str(e)}
    
    def _get_trading_health(self) -> Dict:
        """Get trading health"""
        try:
            from ..services.account_service import AccountService
            account = AccountService()
            balance = account.get_balance()
            
            return {
                "status": "healthy",
                "capital": balance.get("available", 0),
                "margin_used": balance.get("margin_used", 0),
                "can_trade": account.can_trade()
            }
        except Exception as e:
            return {"status": "warning", "error": str(e)}