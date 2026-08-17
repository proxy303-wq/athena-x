# backend/app/core/config.py
import os
from typing import Dict, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Groww API - TOTP credentials
    GROWW_TOTP_TOKEN: str = ""
    GROWW_TOTP_SECRET: str = ""
    
    # Capital & Risk
    INITIAL_CAPITAL: float = 500000
    RISK_PER_TRADE: float = 0.005
    PROFIT_TARGET: float = 0.01
    MAX_DAILY_LOSS: float = 0.01
    MAX_MONTHLY_LOSS: float = 0.05
    MAX_POSITIONS: int = 2
    MAX_TRADES_PER_DAY: int = 2
    MAX_POSITION_SIZE: int = 100
    
    # Trading
    DEFAULT_SYMBOL: str = "NIFTY"
    DEFAULT_TIMEFRAME: str = "5m"
    SCAN_FREQUENCY: int = 30
    AUTO_EXECUTE: bool = False
    
    # Index Config
    NIFTY_LOT_SIZE: int = 65
    BANKNIFTY_LOT_SIZE: int = 30
    FINNIFTY_LOT_SIZE: int = 25
    SENSEX_LOT_SIZE: int = 20
    
    # Engine Weights
    ENGINE_WEIGHTS: Dict[str, float] = {
        "PCREngine": 0.15,
        "OIEngine": 0.10,
        "MaxPainEngine": 0.10,
        "GreeksEngine": 0.10,
        "TrendEngine": 0.15,
        "VWAPEngine": 0.10,
        "PredictorEngine": 0.10,
        "MLPredictor": 0.10,
        "AdvancedML": 0.10,
    }
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = "ignore"

settings = Settings()