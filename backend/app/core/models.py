# backend/app/core/models.py
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum
from pydantic import BaseModel, Field

class MarketType(str, Enum):
    NIFTY = "NIFTY"
    BANK_NIFTY = "BANK_NIFTY"
    SENSEX = "SENSEX"
    COMMODITY = "COMMODITY"

class TradeAction(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WAIT = "WAIT"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"

class ExpiryType(str, Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"

# --- Data Models ---
class MarketData(BaseModel):
    symbol: str
    market_type: str = "NIFTY"
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    trend: Optional[str] = None
    prev_close: Optional[float] = None

class OptionData(BaseModel):
    symbol: str
    expiry: datetime
    strike: float
    option_type: OptionType
    open_interest: int
    change_in_oi: int
    volume: int
    implied_volatility: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    last_price: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None

class OptionChainData(BaseModel):
    symbol: str
    expiry: datetime
    timestamp: datetime
    strikes: List[float]
    call_options: Dict[float, OptionData]
    put_options: Dict[float, OptionData]
    pcr: Optional[float] = None
    max_pain: Optional[float] = None
    underlying_price: Optional[float] = None

# --- Scoring Models ---
class Score(BaseModel):
    engine_name: str
    score: float  # -1 to +1
    weight: float = 1.0
    confidence: float = 0.0
    signal: str = "NEUTRAL"
    reasoning: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)

class AthenaDecision(BaseModel):
    action: TradeAction
    overall_score: float
    confidence: float
    scores: List[Score]
    recommendation: str
    risk_level: str
    timestamp: datetime = Field(default_factory=datetime.now)
    next_expiry: Optional[datetime] = None

class TradePlan(BaseModel):
    decision: AthenaDecision
    entry_price: float
    stop_loss: float
    target1: float
    target2: float
    target3: float
    risk_reward_ratio: float
    option_symbol: str
    quantity: int
    position_type: str
    reason: str
    timestamp: datetime = Field(default_factory=datetime.now)

class Signal(BaseModel):
    action: TradeAction
    confidence: float
    reason: str
    timestamp: datetime = Field(default_factory=datetime.now)

class Performance(BaseModel):
    capital: float
    today_pnl: float = 0
    monthly_pnl: float = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    current_position: Optional[TradePlan] = None