# backend/app/services/ml_predictor.py
import os
import sys
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

# ============================================================
# SUPPRESS TENSORFLOW WARNINGS AT THE EARLIEST POINT
# ============================================================
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_VLOG_LEVEL'] = '3'

# Suppress absl logging
try:
    import absl.logging
    absl.logging.set_verbosity('error')
    absl.logging.set_stderrthreshold('error')
except:
    pass

logger = logging.getLogger(__name__)

# ============================================================
# TENSORFLOW IMPORT
# ============================================================
TENSORFLOW_AVAILABLE = False
try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    TENSORFLOW_AVAILABLE = True
    logger.info("TensorFlow loaded successfully")
except ImportError as e:
    logger.warning(f"TensorFlow not available: {e}")
except Exception as e:
    logger.warning(f"TensorFlow import error: {e}")

# ============================================================
# SCIKIT-LEARN IMPORT
# ============================================================
SKLEARN_AVAILABLE = False
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
    logger.info("Scikit-learn loaded successfully")
except ImportError as e:
    logger.warning(f"Scikit-learn not available: {e}")

# ============================================================
# GROWW PROVIDER
# ============================================================
from ..providers.groww import GrowwProvider
from ..core.models import MarketData


class MLPredictor:
    """ML-based price prediction with fallback options"""
    
    def __init__(self):
        self.provider = GrowwProvider()
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.training_symbol = None
        self.last_prediction = None
        
        logger.info(f"ML Predictor initialized - TF: {TENSORFLOW_AVAILABLE}, Sklearn: {SKLEARN_AVAILABLE}")
    
    def train(self, symbol: str = "NIFTY", days: int = 180) -> bool:
        """Train the ML model"""
        try:
            if days > 180:
                days = 180
                logger.info(f"Capped days to 180 due to API limits")
            
            logger.info(f"Training ML model for {symbol} using {days} days of data")
            
            data = self.prepare_data(symbol, days)
            if data is None:
                logger.warning("No data available for training - using fallback")
                self.is_trained = True
                self.training_symbol = symbol
                return True
            
            X, y = data
            
            if TENSORFLOW_AVAILABLE:
                success = self._train_tensorflow(X, y)
                if success:
                    self.is_trained = True
                    self.training_symbol = symbol
                    logger.info(f"TensorFlow model trained successfully for {symbol}")
                    return True
            
            if SKLEARN_AVAILABLE:
                success = self._train_sklearn(X, y)
                if success:
                    self.is_trained = True
                    self.training_symbol = symbol
                    logger.info(f"Scikit-learn model trained successfully for {symbol}")
                    return True
            
            self.is_trained = True
            self.training_symbol = symbol
            logger.info(f"Using simple moving average fallback for {symbol}")
            return True
                
        except Exception as e:
            logger.error(f"Training error: {e}")
            self.is_trained = True
            self.training_symbol = symbol
            return True
    
    def _train_tensorflow(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train with TensorFlow LSTM"""
        try:
            X = X.reshape((X.shape[0], X.shape[1], 1))
            
            self.model = Sequential([
                LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)),
                Dropout(0.2),
                LSTM(50, return_sequences=False),
                Dropout(0.2),
                Dense(1)
            ])
            
            self.model.compile(optimizer='adam', loss='mse')
            self.model.fit(X, y, epochs=10, batch_size=32, verbose=0)
            return True
        except Exception as e:
            logger.error(f"TensorFlow training error: {e}")
            return False
    
    def _train_sklearn(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Train with Scikit-learn"""
        try:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            self.model = LinearRegression()
            self.model.fit(X_scaled, y)
            return True
        except Exception as e:
            logger.error(f"Scikit-learn training error: {e}")
            return False
    
    def prepare_data(self, symbol: str = "NIFTY", days: int = 180) -> Optional[Tuple]:
        """Prepare data for training"""
        try:
            # Fetch market data
            data = self.provider.get_market_data(symbol, "1d", days)
            
            if not data or len(data) < 30:
                logger.warning(f"Insufficient data for {symbol}: {len(data) if data else 0} candles")
                return None
            
            # Extract prices - handle both list of lists and list of objects
            prices = []
            
            if isinstance(data[0], (list, tuple)):
                # Data is list of lists: [timestamp, open, high, low, close, volume]
                for candle in data:
                    if len(candle) >= 5:
                        prices.append(float(candle[4]))  # close at index 4
            else:
                # Data is list of MarketData objects
                for item in data:
                    if hasattr(item, 'close'):
                        prices.append(float(item.close))
            
            if not prices or len(prices) < 30:
                logger.warning(f"Could not extract prices from data for {symbol}")
                return None
            
            prices = np.array(prices)
            
            if TENSORFLOW_AVAILABLE:
                return self._prepare_lstm_data(prices)
            else:
                return self._prepare_sklearn_data(prices)
                
        except Exception as e:
            logger.error(f"Data preparation error: {e}")
            return None
    
    def _prepare_lstm_data(self, prices: np.ndarray) -> Tuple:
        """Prepare data for LSTM"""
        sequence_length = 30
        X, y = [], []
        for i in range(sequence_length, len(prices)):
            X.append(prices[i-sequence_length:i])
            y.append(prices[i])
        return np.array(X), np.array(y)
    
    def _prepare_sklearn_data(self, prices: np.ndarray) -> Tuple:
        """Prepare data for scikit-learn"""
        features, targets = [], []
        for i in range(30, len(prices) - 5):
            window = prices[i-30:i]
            features.append([
                np.mean(window),
                np.std(window),
                window[-1],
                np.percentile(window, 75),
                np.percentile(window, 25),
                (window[-1] - window[-2]) / window[-2] if window[-2] > 0 else 0,
                (window[-1] - window[-5]) / window[-5] if window[-5] > 0 else 0,
            ])
            target = (prices[i+5] - prices[i]) / prices[i] if prices[i] > 0 else 0
            targets.append(target)
        return np.array(features), np.array(targets)
    
    def predict(self, symbol: str = "NIFTY", days: int = 5) -> Dict[str, Any]:
        """Predict future prices"""
        try:
            if days < 1 or days > 30:
                days = 5
                logger.warning(f"Capped days to 5 (valid range: 1-30)")
            
            if not self.is_trained or self.training_symbol != symbol:
                self.train(symbol)
            
            data = self.provider.get_market_data(symbol, "1d", 60)
            if not data or len(data) < 30:
                return {"error": "Insufficient data for prediction", "symbol": symbol}
            
            # Extract prices
            prices = []
            if isinstance(data[0], (list, tuple)):
                for candle in data:
                    if len(candle) >= 5:
                        prices.append(float(candle[4]))
            else:
                for item in data:
                    if hasattr(item, 'close'):
                        prices.append(float(item.close))
            
            if not prices or len(prices) < 30:
                return {"error": "Could not extract price data", "symbol": symbol}
            
            prices = np.array(prices)
            current_price = prices[-1]
            
            if TENSORFLOW_AVAILABLE and self.model:
                result = self._predict_tensorflow(prices, current_price, days)
            elif SKLEARN_AVAILABLE and self.model:
                result = self._predict_sklearn(prices, current_price, days)
            else:
                result = self._predict_simple(prices, current_price, days)
            
            result["symbol"] = symbol
            result["current_price"] = float(current_price)
            result["timestamp"] = datetime.now().isoformat()
            result["method"] = self._get_method_name()
            
            self.last_prediction = result
            return result
                
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"error": str(e), "symbol": symbol, "timestamp": datetime.now().isoformat()}
    
    def _predict_tensorflow(self, prices: np.ndarray, current_price: float, days: int) -> Dict:
        """Predict with TensorFlow"""
        try:
            sequence = prices[-30:].reshape(1, 30, 1)
            predictions = []
            current_seq = sequence.copy()
            
            for _ in range(days):
                pred = self.model.predict(current_seq, verbose=0)
                predictions.append(float(pred[0][0]))
                current_seq = np.roll(current_seq, -1, axis=1)
                current_seq[0, -1, 0] = pred[0][0]
            
            return {
                "predictions": predictions,
                "predicted_price": float(predictions[-1]),
                "change_percent": ((predictions[-1] - current_price) / current_price) * 100,
                "method": "tensorflow_lstm"
            }
        except Exception as e:
            logger.error(f"TensorFlow prediction error: {e}")
            return self._predict_simple(prices, current_price, days)
    
    def _predict_sklearn(self, prices: np.ndarray, current_price: float, days: int) -> Dict:
        """Predict with Scikit-learn"""
        try:
            features = np.array([
                np.mean(prices[-30:]),
                np.std(prices[-30:]),
                prices[-1],
                np.percentile(prices[-30:], 75),
                np.percentile(prices[-30:], 25),
                (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0,
                (prices[-1] - prices[-5]) / prices[-5] if prices[-5] > 0 else 0,
            ]).reshape(1, -1)
            
            X_scaled = self.scaler.transform(features)
            predicted_return = self.model.predict(X_scaled)[0]
            predicted_price = current_price * (1 + predicted_return)
            
            predictions = [current_price + i * (predicted_price - current_price) / days for i in range(1, days + 1)]
            
            return {
                "predictions": predictions,
                "predicted_price": float(predicted_price),
                "change_percent": predicted_return * 100,
                "method": "sklearn_linear"
            }
        except Exception as e:
            logger.error(f"Sklearn prediction error: {e}")
            return self._predict_simple(prices, current_price, days)
    
    def _predict_simple(self, prices: np.ndarray, current_price: float, days: int) -> Dict:
        """Simple moving average fallback"""
        try:
            sma_5 = np.mean(prices[-5:])
            sma_10 = np.mean(prices[-10:])
            sma_20 = np.mean(prices[-20:])
            
            trend = (sma_5 - sma_20) / sma_20 if sma_20 > 0 else 0
            
            predictions = []
            for i in range(1, days + 1):
                decay = 1.0 - (i / days) * 0.5
                price = current_price * (1 + trend * 0.5 * decay)
                predictions.append(float(price))
            
            return {
                "predictions": predictions,
                "predicted_price": float(predictions[-1]),
                "change_percent": ((predictions[-1] - current_price) / current_price) * 100,
                "method": "moving_average"
            }
        except Exception as e:
            logger.error(f"Simple prediction error: {e}")
            return {
                "predictions": [current_price] * days,
                "predicted_price": float(current_price),
                "change_percent": 0,
                "method": "fallback"
            }
    
    def _get_method_name(self) -> str:
        """Get prediction method name"""
        if TENSORFLOW_AVAILABLE and self.model:
            return "tensorflow_lstm"
        elif SKLEARN_AVAILABLE and self.model:
            return "sklearn_linear"
        else:
            return "moving_average"
    
    def get_signal(self, symbol: str = "NIFTY") -> Dict[str, Any]:
        """Get trading signal"""
        try:
            prediction = self.predict(symbol)
            
            if "error" in prediction:
                return {
                    "signal": "NEUTRAL",
                    "confidence": 0,
                    "reason": prediction["error"],
                    "timestamp": datetime.now().isoformat()
                }
            
            change = prediction.get("change_percent", 0)
            confidence = min(abs(change) * 50, 90)
            
            if change > 0.7:
                signal = "STRONG_BUY"
                reason = f"Strong upward movement predicted: {change:.2f}%"
            elif change > 0.3:
                signal = "BUY"
                reason = f"Upward movement predicted: {change:.2f}%"
            elif change < -0.7:
                signal = "STRONG_SELL"
                reason = f"Strong downward movement predicted: {abs(change):.2f}%"
            elif change < -0.3:
                signal = "SELL"
                reason = f"Downward movement predicted: {abs(change):.2f}%"
            else:
                signal = "WAIT"
                reason = f"Sideways movement predicted: {change:.2f}%"
            
            return {
                "signal": signal,
                "confidence": confidence,
                "reason": reason,
                "method": prediction.get("method", "unknown"),
                "prediction": prediction,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            return {
                "signal": "NEUTRAL",
                "confidence": 0,
                "reason": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get ML predictor status"""
        return {
            "is_trained": self.is_trained,
            "training_symbol": self.training_symbol,
            "tensorflow_available": TENSORFLOW_AVAILABLE,
            "sklearn_available": SKLEARN_AVAILABLE,
            "last_prediction": self.last_prediction,
            "timestamp": datetime.now().isoformat()
        }