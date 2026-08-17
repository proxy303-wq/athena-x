# backend/app/services/error_recovery.py
import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from threading import Thread

logger = logging.getLogger(__name__)

class ErrorRecovery:
    """Auto-restart system on crash"""
    
    def __init__(self):
        self.running = False
        self.restart_count = 0
        self.max_restarts = 10
        self.last_restart_time = None
        self.restart_window = 300  # 5 minutes
    
    def start(self):
        """Start the recovery monitor"""
        self.running = True
        Thread(target=self._monitor, daemon=True).start()
        logger.info("Error recovery monitor started")
    
    def stop(self):
        self.running = False
        logger.info("Error recovery monitor stopped")
    
    def _monitor(self):
        """Monitor for errors and restart"""
        while self.running:
            # Check if we need to restart
            if self._should_restart():
                self._perform_restart()
            
            time.sleep(30)  # Check every 30 seconds
    
    def _should_restart(self) -> bool:
        """Check if restart is needed"""
        # Reset restart count if window expired
        if self.last_restart_time:
            elapsed = (datetime.now() - self.last_restart_time).total_seconds()
            if elapsed > self.restart_window:
                self.restart_count = 0
        
        # Check if we've exceeded max restarts
        if self.restart_count >= self.max_restarts:
            return False
        
        # Check system health
        return self._is_system_unhealthy()
    
    def _is_system_unhealthy(self) -> bool:
        """Check if system is unhealthy"""
        try:
            # Check if main process is running
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if 'python' in proc.info['name'] and 'run.py' in str(proc.info['cmdline']):
                    return False
            return True
        except:
            return False
    
    def _perform_restart(self):
        """Restart the system"""
        self.restart_count += 1
        self.last_restart_time = datetime.now()
        
        logger.warning(f"System restarting... (Attempt {self.restart_count})")
        
        # Restart the script
        python = sys.executable
        script = os.path.join(os.path.dirname(__file__), '../../run.py')
        subprocess.Popen([python, script])
        
        # Exit current process
        sys.exit(0)
    
    def register_error(self, error: str):
        """Register an error for tracking"""
        logger.error(f"Error registered: {error}")
        if self._should_restart():
            self._perform_restart()