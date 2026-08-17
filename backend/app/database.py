# backend/app/database.py
import sqlite3
import logging
from datetime import datetime, timedelta  # Added timedelta
from typing import Dict, List, Any, Optional
from .core.config import settings

logger = logging.getLogger(__name__)

class Database:
    """Database handler for Athena-X"""
    
    def __init__(self):
        self.db_path = "athena.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                option_symbol TEXT,
                position_type TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity INTEGER,
                profit REAL,
                status TEXT,
                entry_time TEXT,
                exit_time TEXT,
                reason TEXT
            )
        ''')
        
        # Performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_profit REAL,
                total_loss REAL,
                net_profit REAL,
                capital REAL
            )
        ''')
        
        # Signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                action TEXT,
                confidence REAL,
                score REAL,
                reason TEXT,
                timestamp TEXT
            )
        ''')
        
        # ML Predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                predicted_price REAL,
                actual_price REAL,
                accuracy REAL,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def save_trade(self, trade_data: Dict) -> int:
        """Save a trade to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (
                symbol, option_symbol, position_type, entry_price, 
                exit_price, quantity, profit, status, entry_time, exit_time, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data.get('symbol'),
            trade_data.get('option_symbol'),
            trade_data.get('position_type'),
            trade_data.get('entry_price'),
            trade_data.get('exit_price'),
            trade_data.get('quantity'),
            trade_data.get('profit'),
            trade_data.get('status'),
            trade_data.get('entry_time'),
            trade_data.get('exit_time'),
            trade_data.get('reason')
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trade_id
    
    def update_trade_status(self, trade_id: int, status: str, exit_price: float = None, profit: float = None):
        """Update trade status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if exit_price is not None and profit is not None:
            cursor.execute('''
                UPDATE trades 
                SET status=?, exit_price=?, profit=?, exit_time=?
                WHERE id=?
            ''', (status, exit_price, profit, datetime.now().isoformat(), trade_id))
        else:
            cursor.execute('''
                UPDATE trades SET status=?, exit_time=?
                WHERE id=?
            ''', (status, datetime.now().isoformat(), trade_id))
        
        conn.commit()
        conn.close()
    
    def save_signal(self, signal_data: Dict) -> int:
        """Save a signal to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals (
                symbol, action, confidence, score, reason, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            signal_data.get('symbol'),
            signal_data.get('action'),
            signal_data.get('confidence'),
            signal_data.get('score'),
            signal_data.get('reason'),
            signal_data.get('timestamp')
        ))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return signal_id
    
    def save_prediction(self, pred_data: Dict) -> int:
        """Save ML prediction to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO predictions (
                symbol, predicted_price, actual_price, accuracy, timestamp
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            pred_data.get('symbol'),
            pred_data.get('predicted_price'),
            pred_data.get('actual_price'),
            pred_data.get('accuracy'),
            pred_data.get('timestamp')
        ))
        
        pred_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return pred_id
    
    def save_performance(self, perf_data: Dict) -> int:
        """Save daily performance to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO performance (
                date, total_trades, winning_trades, losing_trades,
                win_rate, total_profit, total_loss, net_profit, capital
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            perf_data.get('date'),
            perf_data.get('total_trades'),
            perf_data.get('winning_trades'),
            perf_data.get('losing_trades'),
            perf_data.get('win_rate'),
            perf_data.get('total_profit'),
            perf_data.get('total_loss'),
            perf_data.get('net_profit'),
            perf_data.get('capital')
        ))
        
        perf_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return perf_id
    
    def get_trades(self, limit: int = 100) -> List[Dict]:
        """Get recent trades"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades ORDER BY id DESC LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_predictions(self, limit: int = 50) -> List[Dict]:
        """Get recent predictions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM predictions ORDER BY id DESC LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_performance_history(self, days: int = 30) -> List[Dict]:
        """Get performance history"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM performance 
            ORDER BY date DESC LIMIT ?
        ''', (days,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict:
        """Get overall statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN profit > 0 THEN 1 END) as wins,
                COUNT(CASE WHEN profit < 0 THEN 1 END) as losses
            FROM trades WHERE profit IS NOT NULL
        ''')
        row = cursor.fetchone()
        wins = row[0] or 0
        losses = row[1] or 0
        
        cursor.execute('SELECT SUM(profit) FROM trades')
        total_profit = cursor.fetchone()[0] or 0
        
        # Get win rate for last 30 days
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN profit > 0 THEN 1 END) as recent_wins,
                COUNT(CASE WHEN profit < 0 THEN 1 END) as recent_losses
            FROM trades 
            WHERE profit IS NOT NULL 
            AND entry_time > datetime('now', '-30 days')
        ''')
        recent = cursor.fetchone()
        recent_wins = recent[0] or 0
        recent_losses = recent[1] or 0
        
        conn.close()
        
        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / (wins + losses) * 100 if (wins + losses) > 0 else 0,
            "total_profit": total_profit,
            "recent_win_rate": recent_wins / (recent_wins + recent_losses) * 100 if (recent_wins + recent_losses) > 0 else 0
        }
    
    def clear_old_data(self, days: int = 365):
        """Clear data older than specified days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        cursor.execute('DELETE FROM trades WHERE entry_time < ?', (cutoff_str,))
        cursor.execute('DELETE FROM signals WHERE timestamp < ?', (cutoff_str,))
        cursor.execute('DELETE FROM predictions WHERE timestamp < ?', (cutoff_str,))
        
        conn.commit()
        conn.close()
        logger.info(f"Cleared data older than {days} days")
    
    def vacuum(self):
        """Optimize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('VACUUM')
        conn.close()
        logger.info("Database vacuumed")