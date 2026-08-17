# backend/app/analytics/advanced_analytics.py
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
from ..core.models import MarketData

class AdvancedAnalytics:
    """
    Advanced technical analysis indicators
    
    Includes:
    - Moving Averages (SMA, EMA, WMA)
    - RSI, MACD, Bollinger Bands
    - Support/Resistance levels
    - Candlestick patterns
    - Volume analysis
    - Market breadth indicators
    """
    
    def __init__(self):
        self.window_sma = [5, 10, 20, 50, 100]
        self.window_ema = [5, 10, 20, 50]
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.bb_period = 20
        self.bb_std = 2
    
    def analyze(self, historical: List[MarketData]) -> Dict[str, Any]:
        """
        Run all advanced analysis on historical data
        """
        if len(historical) < 100:
            return self._empty_result()
        
        # Convert to DataFrame for easier calculation
        df = self._to_dataframe(historical)
        
        results = {
            "moving_averages": self._moving_averages(df),
            "rsi": self._rsi(df),
            "macd": self._macd(df),
            "bollinger_bands": self._bollinger_bands(df),
            "support_resistance": self._support_resistance(df),
            "volume_analysis": self._volume_analysis(df),
            "candlestick_patterns": self._candlestick_patterns(df),
            "trend_strength": self._trend_strength(df),
            "volatility": self._volatility(df),
            "timestamp": datetime.now().isoformat()
        }
        
        return results
    
    def _to_dataframe(self, historical: List[MarketData]) -> pd.DataFrame:
        """Convert MarketData list to DataFrame"""
        data = {
            'timestamp': [h.timestamp for h in historical],
            'open': [h.open for h in historical],
            'high': [h.high for h in historical],
            'low': [h.low for h in historical],
            'close': [h.close for h in historical],
            'volume': [h.volume for h in historical],
            'vwap': [h.vwap or h.close for h in historical]
        }
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df
    
    def _moving_averages(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Calculate SMA and EMA"""
        result = {}
        
        # Simple Moving Averages
        for window in self.window_sma:
            sma = df['close'].rolling(window=window).mean()
            if not sma.empty:
                result[f'SMA_{window}'] = {
                    'value': float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None,
                    'slope': self._calculate_slope(sma)
                }
        
        # Exponential Moving Averages
        for window in self.window_ema:
            ema = df['close'].ewm(span=window, adjust=False).mean()
            if not ema.empty:
                result[f'EMA_{window}'] = {
                    'value': float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else None,
                    'slope': self._calculate_slope(ema)
                }
        
        return result
    
    def _rsi(self, df: pd.DataFrame) -> Dict:
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        
        return {
            'value': current_rsi,
            'signal': self._rsi_signal(current_rsi),
            'overbought': current_rsi > 70,
            'oversold': current_rsi < 30
        }
    
    def _rsi_signal(self, rsi: float) -> str:
        """Interpret RSI"""
        if rsi > 70:
            return "OVERBOUGHT"
        elif rsi < 30:
            return "OVERSOLD"
        elif rsi > 50:
            return "BULLISH"
        elif rsi < 50:
            return "BEARISH"
        return "NEUTRAL"
    
    def _macd(self, df: pd.DataFrame) -> Dict:
        """Calculate MACD"""
        exp1 = df['close'].ewm(span=self.macd_fast, adjust=False).mean()
        exp2 = df['close'].ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        current_macd = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0
        current_signal = float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0
        current_hist = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0
        
        return {
            'macd_line': current_macd,
            'signal_line': current_signal,
            'histogram': current_hist,
            'crossover': current_macd > current_signal,
            'crossunder': current_macd < current_signal,
            'signal': "BULLISH" if current_macd > current_signal else "BEARISH" if current_macd < current_signal else "NEUTRAL"
        }
    
    def _bollinger_bands(self, df: pd.DataFrame) -> Dict:
        """Calculate Bollinger Bands"""
        sma = df['close'].rolling(window=self.bb_period).mean()
        std = df['close'].rolling(window=self.bb_period).std()
        
        upper_band = sma + (std * self.bb_std)
        lower_band = sma - (std * self.bb_std)
        
        current_close = df['close'].iloc[-1]
        current_sma = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else current_close
        current_upper = float(upper_band.iloc[-1]) if not pd.isna(upper_band.iloc[-1]) else current_close
        current_lower = float(lower_band.iloc[-1]) if not pd.isna(lower_band.iloc[-1]) else current_close
        
        # Position within bands (0 = lower, 1 = upper)
        if current_upper != current_lower:
            position = (current_close - current_lower) / (current_upper - current_lower)
        else:
            position = 0.5
        
        return {
            'upper': current_upper,
            'middle': current_sma,
            'lower': current_lower,
            'position': position,
            'signal': self._bb_signal(position)
        }
    
    def _bb_signal(self, position: float) -> str:
        """Interpret Bollinger Band position"""
        if position > 0.9:
            return "OVERBOUGHT"
        elif position < 0.1:
            return "OVERSOLD"
        elif position > 0.6:
            return "BULLISH"
        elif position < 0.4:
            return "BEARISH"
        return "NEUTRAL"
    
    def _support_resistance(self, df: pd.DataFrame) -> Dict:
        """Find support and resistance levels"""
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        # Use last 50 candles
        recent_highs = highs[-50:]
        recent_lows = lows[-50:]
        
        # Find pivot points (local maxima/minima)
        pivots_high = self._find_pivots(recent_highs, lookback=5)
        pivots_low = self._find_pivots(recent_lows, lookback=5)
        
        # Calculate support and resistance
        resistance_levels = sorted(pivots_high, reverse=True)[:3]
        support_levels = sorted(pivots_low)[:3]
        
        current_price = closes[-1]
        
        nearest_resistance = min([r for r in resistance_levels if r > current_price], default=None)
        nearest_support = max([s for s in support_levels if s < current_price], default=None)
        
        return {
            'support_levels': support_levels,
            'resistance_levels': resistance_levels,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'signal': self._sr_signal(current_price, nearest_support, nearest_resistance)
        }
    
    def _find_pivots(self, data: np.ndarray, lookback: int = 5) -> List[float]:
        """Find local maxima/minima"""
        pivots = []
        for i in range(lookback, len(data) - lookback):
            is_high = all(data[i] >= data[i-j] for j in range(1, lookback+1)) and \
                     all(data[i] >= data[i+j] for j in range(1, lookback+1))
            is_low = all(data[i] <= data[i-j] for j in range(1, lookback+1)) and \
                    all(data[i] <= data[i+j] for j in range(1, lookback+1))
            if is_high or is_low:
                pivots.append(data[i])
        return pivots
    
    def _sr_signal(self, price: float, support: float, resistance: float) -> str:
        """Interpret support/resistance"""
        if support and resistance:
            support_dist = (price - support) / support
            resistance_dist = (resistance - price) / price
            
            if support_dist < 0.005:
                return "NEAR_SUPPORT"
            elif resistance_dist < 0.005:
                return "NEAR_RESISTANCE"
            elif support_dist < 0.02:
                return "ABOVE_SUPPORT"
            elif resistance_dist < 0.02:
                return "BELOW_RESISTANCE"
        return "BETWEEN_LEVELS"
    
    def _volume_analysis(self, df: pd.DataFrame) -> Dict:
        """Analyze volume patterns"""
        volumes = df['volume'].values
        closes = df['close'].values
        
        avg_volume = np.mean(volumes[-20:])
        current_volume = volumes[-1]
        
        # Price change
        price_change = (closes[-1] - closes[-2]) / closes[-2] if len(closes) > 1 else 0
        
        # Volume/Price relationship
        is_up_volume = current_volume > avg_volume and price_change > 0
        is_down_volume = current_volume > avg_volume and price_change < 0
        
        return {
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 1,
            'is_high_volume': current_volume > avg_volume * 1.2,
            'price_change': price_change,
            'signal': self._volume_signal(is_up_volume, is_down_volume, price_change)
        }
    
    def _volume_signal(self, is_up: bool, is_down: bool, price_change: float) -> str:
        """Interpret volume"""
        if is_up:
            return "BULLISH_CONFIRMATION"
        elif is_down:
            return "BEARISH_CONFIRMATION"
        elif price_change > 0:
            return "BULLISH"
        elif price_change < 0:
            return "BEARISH"
        return "NEUTRAL"
    
    def _candlestick_patterns(self, df: pd.DataFrame) -> Dict:
        """Identify candlestick patterns"""
        if len(df) < 3:
            return {}
        
        patterns = {}
        
        # Get last 3 candles
        closes = df['close'].values[-3:]
        opens = df['open'].values[-3:]
        highs = df['high'].values[-3:]
        lows = df['low'].values[-3:]
        
        # Doji
        if abs(closes[-1] - opens[-1]) <= (highs[-1] - lows[-1]) * 0.1:
            patterns['doji'] = True
        
        # Hammer
        body = abs(closes[-1] - opens[-1])
        lower_shadow = min(opens[-1], closes[-1]) - lows[-1]
        upper_shadow = highs[-1] - max(opens[-1], closes[-1])
        
        if lower_shadow > body * 2 and upper_shadow < body * 0.3:
            patterns['hammer'] = True
        
        # Shooting Star
        if upper_shadow > body * 2 and lower_shadow < body * 0.3:
            patterns['shooting_star'] = True
        
        # Bullish Engulfing
        if closes[-1] > opens[-1] and opens[-2] > closes[-2]:
            if closes[-1] > opens[-2] and opens[-1] < closes[-2]:
                patterns['bullish_engulfing'] = True
        
        # Bearish Engulfing
        if closes[-1] < opens[-1] and opens[-2] < closes[-2]:
            if opens[-1] > closes[-2] and closes[-1] < opens[-2]:
                patterns['bearish_engulfing'] = True
        
        return patterns
    
    def _trend_strength(self, df: pd.DataFrame) -> Dict:
        """Calculate trend strength"""
        closes = df['close'].values
        
        # ADX-like calculation
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift()))
        )
        
        # Simplified trend strength
        sma_5 = np.mean(closes[-5:]) if len(closes) >= 5 else closes[-1]
        sma_20 = np.mean(closes[-20:]) if len(closes) >= 20 else closes[-1]
        sma_50 = np.mean(closes[-50:]) if len(closes) >= 50 else closes[-1]
        
        current = closes[-1]
        
        # Trend direction
        if current > sma_5 > sma_20 > sma_50:
            direction = "STRONG_UPTREND"
            strength = 1.0
        elif current > sma_5 > sma_20:
            direction = "UPTREND"
            strength = 0.7
        elif current < sma_5 < sma_20 < sma_50:
            direction = "STRONG_DOWNTREND"
            strength = 1.0
        elif current < sma_5 < sma_20:
            direction = "DOWNTREND"
            strength = 0.7
        else:
            direction = "SIDEWAYS"
            strength = 0.3
        
        return {
            'direction': direction,
            'strength': strength,
            'sma_5': sma_5,
            'sma_20': sma_20,
            'sma_50': sma_50
        }
    
    def _volatility(self, df: pd.DataFrame) -> Dict:
        """Calculate volatility metrics"""
        returns = df['close'].pct_change()
        std = returns.std()
        
        # ATR
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift()))
        )
        atr = tr.rolling(window=14).mean()
        
        current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0
        
        return {
            'std': std,
            'atr': current_atr,
            'volatility_percent': std * 100,
            'signal': "HIGH_VOLATILITY" if std > 0.02 else "LOW_VOLATILITY"
        }
    
    def _calculate_slope(self, series: pd.Series) -> float:
        """Calculate slope of a series"""
        if len(series) < 3:
            return 0
        x = np.arange(len(series))
        y = series.values[-10:] if len(series) >= 10 else series.values
        x = x[-len(y):]
        slope = np.polyfit(x, y, 1)[0] if len(y) > 1 else 0
        return float(slope)
    
    def _empty_result(self) -> Dict:
        """Return empty result when insufficient data"""
        return {
            "moving_averages": {},
            "rsi": {"value": 50, "signal": "NEUTRAL"},
            "macd": {"macd_line": 0, "signal_line": 0, "histogram": 0},
            "bollinger_bands": {},
            "support_resistance": {},
            "volume_analysis": {},
            "candlestick_patterns": {},
            "trend_strength": {},
            "volatility": {},
            "timestamp": datetime.now().isoformat()
        }