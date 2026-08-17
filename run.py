# run.py - Main Entry Point
import uvicorn
import webbrowser
import threading
import time
import os
import sys
import logging
import signal

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging first
from backend.app.services.logger import setup_logging
logger = setup_logging()

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n" + "="*60)
    print("SHUTTING DOWN ATHENA-X")
    print("="*60)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def open_browser():
    """Open browser after server starts"""
    time.sleep(2)
    webbrowser.open("http://localhost:8000/dashboard")

def start_scheduler():
    """Start the auto-trade scheduler"""
    try:
        from backend.app.scheduler import AthenaScheduler
        scheduler = AthenaScheduler()
        scheduler.start()
        logger.info("Auto-trade scheduler started")
        return scheduler
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        return None

def start_services():
    """Start all additional services"""
    services = {}
    
    # Error Recovery
    try:
        from backend.app.services.error_recovery import ErrorRecovery
        recovery = ErrorRecovery()
        recovery.start()
        services["recovery"] = recovery
        logger.info("Error recovery service started")
    except Exception as e:
        logger.warning(f"Error recovery failed: {e}")
    
    # Health Service
    try:
        from backend.app.services.health_service import HealthService
        health = HealthService()
        services["health"] = health
        logger.info("Health service initialized")
    except Exception as e:
        logger.warning(f"Health service failed: {e}")
    
    # Data Validator
    try:
        from backend.app.services.data_validator import DataValidator
        validator = DataValidator()
        services["validator"] = validator
        logger.info("Data validator initialized")
    except Exception as e:
        logger.warning(f"Data validator failed: {e}")
    
    # ML Predictor (train in background)
    try:
        from backend.app.services.ml_predictor import MLPredictor
        ml = MLPredictor()
        def train_ml():
            try:
                logger.info("Training ML model...")
                ml.train("NIFTY")
                logger.info("ML model trained successfully")
            except Exception as e:
                logger.warning(f"ML training failed: {e}")
        threading.Thread(target=train_ml, daemon=True).start()
        services["ml"] = ml
        logger.info("ML predictor initialized")
    except Exception as e:
        logger.warning(f"ML predictor failed: {e}")
    
    # Backtest Engine
    try:
        from backend.app.services.backtest import BacktestEngine
        backtest = BacktestEngine()
        services["backtest"] = backtest
        logger.info("Backtest engine initialized")
    except Exception as e:
        logger.warning(f"Backtest engine failed: {e}")
    
    # WebSocket Manager
    try:
        from backend.app.services.websocket_manager import WebSocketManager
        ws_manager = WebSocketManager()
        services["ws_manager"] = ws_manager
        logger.info("WebSocket manager initialized")
    except Exception as e:
        logger.warning(f"WebSocket manager failed: {e}")
    
    return services

def show_account_info():
    """Display real account info on startup"""
    try:
        from backend.app.services.account_service import AccountService
        account_service = AccountService()
        balance = account_service.get_balance()
        profile = account_service.get_user_profile()
        
        print("\n" + "="*60)
        print("ACCOUNT SUMMARY (LIVE FROM GROWW)")
        print("="*60)
        print(f"User: {profile.get('ucc', 'N/A')}")
        print(f"Available Capital: Rs.{balance.get('available', 0):,.2f}")
        print(f"Clear Cash: Rs.{balance.get('clear_cash', 0):,.2f}")
        print(f"Margin Used: Rs.{balance.get('margin_used', 0):,.2f}")
        print(f"Active Segments: {profile.get('active_segments', [])}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"Could not fetch account info: {e}")

def start_auto_close_service():
    """Start auto-close service to exit positions at 3:15 PM"""
    try:
        from backend.app.services.auto_close_service import AutoCloseService
        auto_close = AutoCloseService()
        auto_close.start()
        logger.info("Auto-close service started")
        return auto_close
    except Exception as e:
        logger.warning(f"Auto-close service failed: {e}")
        return None

def start_monitor():
    """Start system health monitor"""
    try:
        from backend.app.services.monitor import SystemMonitor
        monitor = SystemMonitor()
        monitor.start()
        logger.info("System monitor started")
        return monitor
    except Exception as e:
        logger.warning(f"System monitor failed: {e}")
        return None

def start_alert_service():
    """Initialize alert service"""
    try:
        from backend.app.services.alert_service import AlertService
        alert = AlertService()
        alert.send_status("running", "Athena-X started successfully")
        logger.info("Alert service initialized")
        return alert
    except Exception as e:
        logger.warning(f"Alert service failed: {e}")
        return None

def show_features():
    """Display all enabled features"""
    features = [
        ("Live Market Data", "4 Indices (NIFTY, BANKNIFTY, FINNIFTY, SENSEX)"),
        ("ML Predictions", "LSTM Neural Network"),
        ("Backtesting", "Historical Strategy Testing"),
        ("WebSocket", "Real-time Price Streaming"),
        ("Health Monitoring", "System Health Checks"),
        ("Error Recovery", "Auto-restart on Crash"),
        ("Data Validation", "Input Data Validation"),
        ("Auto-Trade", "Fully Automated Trading"),
        ("Alerts", "Real-time Notifications")
    ]
    
    print("="*60)
    print("ATHENA-X - COMPLETE FEATURES")
    print("="*60)
    for name, desc in features:
        print(f"  {name}: {desc}")
    print("="*60 + "\n")

if __name__ == "__main__":
    print("="*60)
    print("ATHENA-X PORTFOLIO MANAGER")
    print("="*60)
    print(f"Server: http://localhost:8000")
    print(f"Dashboard: http://localhost:8000/dashboard")
    print(f"API Docs: http://localhost:8000/docs")
    print("="*60)
    
    show_features()
    
    print("Press Ctrl+C to stop\n")
    
    show_account_info()
    
    services = start_services()
    monitor = start_monitor()
    alert = start_alert_service()
    scheduler = start_scheduler()
    auto_close = start_auto_close_service()
    
    print("\n" + "="*60)
    print("SYSTEM STATUS")
    print("="*60)
    print(f" Auto-Trade Scheduler: {'[OK] Running' if scheduler else '[ERROR] Disabled'}")
    print(f" Auto-Close Service: {'[OK] Running' if auto_close else '[ERROR] Disabled'}")
    print(f" System Monitor: {'[OK] Running' if monitor else '[ERROR] Disabled'}")
    print(f" Alert Service: {'[OK] Active' if alert else '[ERROR] Disabled'}")
    print(f" Error Recovery: {'[OK] Active' if services.get('recovery') else '[ERROR] Disabled'}")
    print(f" ML Predictor: {'[OK] Active' if services.get('ml') else '[ERROR] Disabled'}")
    print(f" Backtest Engine: {'[OK] Active' if services.get('backtest') else '[ERROR] Disabled'}")
    print(f" WebSocket: {'[OK] Active' if services.get('ws_manager') else '[ERROR] Disabled'}")
    print("="*60 + "\n")
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        uvicorn.run(
            "backend.app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("SHUTTING DOWN ATHENA-X")
        print("="*60)
        if scheduler:
            scheduler.stop()
        if auto_close:
            auto_close.stop()
        if monitor:
            monitor.stop()
        if services.get("recovery"):
            services["recovery"].stop()
        print("Athena-X stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)