# backend/app/services/monitor.py
import logging
import time
from datetime import datetime
from typing import Dict, Any
from threading import Thread

# Try to import psutil, fallback if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available. System monitor will use fallback metrics.")

logger = logging.getLogger(__name__)

class SystemMonitor:
    """System health monitor"""
    
    def __init__(self):
        self.running = False
        self.metrics = {
            "cpu": 0,
            "memory": 0,
            "disk": 0,
            "uptime": 0,
            "start_time": datetime.now()
        }
        self.check_count = 0
    
    def start(self):
        """Start monitoring"""
        self.running = True
        Thread(target=self._run, daemon=True).start()
        logger.info("System monitor started")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("System monitor stopped")
    
    def _run(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self.check_count += 1
                
                if PSUTIL_AVAILABLE:
                    # CPU usage
                    self.metrics["cpu"] = psutil.cpu_percent(interval=1)
                    
                    # Memory usage
                    memory = psutil.virtual_memory()
                    self.metrics["memory"] = memory.percent
                    
                    # Disk usage
                    disk = psutil.disk_usage('/')
                    self.metrics["disk"] = disk.percent
                else:
                    # Fallback metrics
                    self.metrics["cpu"] = 0
                    self.metrics["memory"] = 0
                    self.metrics["disk"] = 0
                
                # Uptime
                self.metrics["uptime"] = (datetime.now() - self.metrics["start_time"]).total_seconds()
                
                # Log if high usage
                if PSUTIL_AVAILABLE:
                    if self.metrics["cpu"] > 80:
                        logger.warning(f"High CPU usage: {self.metrics['cpu']}%")
                    if self.metrics["memory"] > 80:
                        logger.warning(f"High memory usage: {self.metrics['memory']}%")
                    if self.metrics["disk"] > 85:
                        logger.warning(f"High disk usage: {self.metrics['disk']}%")
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(60)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "status": "healthy",
            "metrics": self.metrics,
            "check_count": self.check_count,
            "psutil_available": PSUTIL_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }