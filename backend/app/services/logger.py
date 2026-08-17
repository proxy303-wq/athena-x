# backend/app/services/logger.py
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Setup logging configuration"""
    
    # Create logs directory
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler with rotation
            RotatingFileHandler(
                f"{log_dir}/athena.log",
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            ),
            # Error file handler
            RotatingFileHandler(
                f"{log_dir}/errors.log",
                maxBytes=5*1024*1024,  # 5MB
                backupCount=3
            ),
            # Console handler
            logging.StreamHandler()
        ]
    )
    
    # Different log levels for different handlers
    error_handler = logging.FileHandler(f"{log_dir}/errors.log")
    error_handler.setLevel(logging.ERROR)
    
    # Get root logger
    logger = logging.getLogger()
    logger.addHandler(error_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)