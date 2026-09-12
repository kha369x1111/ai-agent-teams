"""
═══════════════════════════════════════════════════════════════════
💾 Database Manager (PostgreSQL + Redis)
═══════════════════════════════════════════════════════════════════
إدارة قواعد البيانات:
- PostgreSQL: بيانات دائمة (trades, signals, ML data)
- Redis: cache سريع + real-time data
- SQLAlchemy ORM
═══════════════════════════════════════════════════════════════════
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB
from loguru import logger

import redis
import json


Base = declarative_base()


# ══════════════ نماذج قاعدة البيانات ══════════════

class TradeRecord(Base):
    """سجل الصفقات"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    trade_id = Column(String, unique=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    amount = Column(Float)
    entry_time = Column(DateTime, index=True)
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, default=0)
    pnl_pct = Column(Float, default=0)
    status = Column(String)  # open, closed
    reason = Column(String)
    features = Column(JSONB)  # ML features

    __table_args__ = (
        Index('idx_symbol_status', 'symbol', 'status'),
        Index('idx_entry_time', 'entry_time'),
    )


class SignalRecord(Base):
    """سجل الإشارات"""
    __tablename__ = 'signals'

    id = Column(Integer, primary_key=True)
    signal_id = Column(String, unique=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    confluence_score = Column(Integer)
    ml_score = Column(Integer, nullable=True)
    risk_reward = Column(Float)
    was_executed = Column(Boolean, default=False)
    was_winner = Column(Boolean, nullable=True)
    timestamp = Column(DateTime, index=True)
    features = Column(JSONB)
    reasoning = Column(JSONB)


class ModelPerformanceRecord(Base):
    """سجل أداء ML"""
    __tablename__ = 'model_performance'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, index=True)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    total_samples = Column(Integer)
    metrics_json = Column(JSONB)


class NewsRecord(Base):
    """سجل الأخبار"""
    __tablename__ = 'news'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(Text)
    source = Column(String)
    url = Column(String)
    timestamp = Column(DateTime, index=True)
    impact_level = Column(String)
    sentiment = Column(Float)
    affected_symbols = Column(JSONB)
    category = Column(String)


class AgentHealthRecord(Base):
    """سجل صحة الوكلاء"""
    __tablename__ = 'agent_health'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, index=True)
    agent_name = Column(String, index=True)
    status = Column(String)
    messages_processed = Column(Integer)
    errors = Column(Integer)
    uptime_seconds = Column(Float)


# ══════════════ مدير قاعدة البيانات ══════════════

class DatabaseManager:
    """مدير قاعدة البيانات الرئيسي"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL',
            'sqlite:///./trading_bot.db'  # fallback to SQLite
        )

        # PostgreSQL engine
        self.engine = create_engine(
            self.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )

        # إنشاء الجداول
        Base.metadata.create_all(self.engine)

        # Session factory
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Redis (اختياري)
        self.redis_client = None
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.success("✅ Redis connected")
        except Exception as e:
            logger.warning(f"⚠️ Redis not available: {e}")

        logger.success(f"✅ Database connected: {self._safe_url()}")

    def _safe_url(self) -> str:
        """URL آمن للعرض"""
        if '@' in self.database_url:
            parts = self.database_url.split('@')
            return f"{parts[0].split('://')[0]}://****@{parts[1]}"
        return self.database_url

    # ==================== Trade Operations ====================

    def save_trade(self, trade_data: Dict) -> int:
        """حفظ صفقة"""
        with self.SessionLocal() as session:
            trade = TradeRecord(**trade_data)
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade.id

    def update_trade(self, trade_id: str, updates: Dict):
        """تحديث صفقة"""
        with self.SessionLocal() as session:
            trade = session.query(TradeRecord).filter_by(trade_id=trade_id).first()
            if trade:
                for key, value in updates.items():
                    setattr(trade, key, value)
                session.commit()

    def get_open_trades(self) -> List[Dict]:
        """جلب الصفقات المفتوحة"""
        with self.SessionLocal() as session:
            trades = session.query(TradeRecord).filter_by(status='open').all()
            return [self._trade_to_dict(t) for t in trades]

    def get_closed_trades(self, limit: int = 100) -> List[Dict]:
        """جلب الصفقات المغلقة"""
        with self.SessionLocal() as session:
            trades = session.query(TradeRecord).filter_by(
                status='closed'
            ).order_by(TradeRecord.exit_time.desc()).limit(limit).all()
            return [self._trade_to_dict(t) for t in trades]

    def get_trades_for_ml(self) -> List[Dict]:
        """جلب الصفقات للتدريب ML"""
        with self.SessionLocal() as session:
            trades = session.query(TradeRecord).filter(
                TradeRecord.status == 'closed',
                TradeRecord.features.isnot(None)
            ).all()
            return [self._trade_to_dict(t) for t in trades]

    # ==================== Signal Operations ====================

    def save_signal(self, signal_data: Dict) -> int:
        """حفظ إشارة"""
        with self.SessionLocal() as session:
            signal = SignalRecord(**signal_data)
            session.add(signal)
            session.commit()
            session.refresh(signal)
            return signal.id

    # ==================== ML Performance ====================

    def save_ml_metrics(self, metrics: Dict):
        """حفظ مقاييس ML"""
        with self.SessionLocal() as session:
            record = ModelPerformanceRecord(**metrics)
            session.add(record)
            session.commit()

    def get_latest_ml_metrics(self) -> Optional[Dict]:
        """أحدث مقاييس ML"""
        with self.SessionLocal() as session:
            record = session.query(ModelPerformanceRecord).order_by(
                ModelPerformanceRecord.timestamp.desc()
            ).first()
            return self._to_dict(record) if record else None

    # ==================== News Operations ====================

    def save_news(self, news_data: Dict):
        """حفظ خبر"""
        with self.SessionLocal() as session:
            news = NewsRecord(**news_data)
            session.add(news)
            session.commit()

    def get_recent_news(self, hours: int = 24) -> List[Dict]:
        """أخبار آخر 24 ساعة"""
        cutoff = datetime.now() - __import__('datetime').timedelta(hours=hours)
        with self.SessionLocal() as session:
            news = session.query(NewsRecord).filter(
                NewsRecord.timestamp >= cutoff
            ).order_by(NewsRecord.timestamp.desc()).all()
            return [self._to_dict(n) for n in news]

    # ==================== Agent Health ====================

    def save_agent_health(self, agent_name: str, health: Dict):
        """حفظ صحة وكيل"""
        with self.SessionLocal() as session:
            record = AgentHealthRecord(
                timestamp=datetime.now(),
                agent_name=agent_name,
                status=health.get('status'),
                messages_processed=health.get('messages_processed', 0),
                errors=health.get('errors', 0),
                uptime_seconds=health.get('uptime_seconds', 0),
            )
            session.add(record)
            session.commit()

    # ==================== Statistics ====================

    def get_performance_stats(self) -> Dict:
        """إحصائيات الأداء"""
        with self.SessionLocal() as session:
            total_trades = session.query(TradeRecord).filter_by(status='closed').count()
            winners = session.query(TradeRecord).filter(
                TradeRecord.status == 'closed',
                TradeRecord.pnl > 0
            ).count()

            total_pnl = session.query(TradeRecord).filter_by(
                status='closed'
            ).with_entities(
                __import__('sqlalchemy').func.sum(TradeRecord.pnl)
            ).scalar() or 0

            return {
                'total_trades': total_trades,
                'winners': winners,
                'win_rate': (winners / total_trades * 100) if total_trades > 0 else 0,
                'total_pnl': total_pnl,
            }

    # ==================== Redis Cache ====================

    def cache_set(self, key: str, value, ttl: int = 300):
        """حفظ في Redis"""
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, json.dumps(value, default=str))
            except Exception as e:
                logger.warning(f"Redis cache set failed: {e}")

    def cache_get(self, key: str):
        """جلب من Redis"""
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            except Exception as e:
                logger.warning(f"Redis cache get failed: {e}")
        return None

    # ==================== Helpers ====================

    def _trade_to_dict(self, trade) -> Dict:
        """تحويل TradeRecord إلى Dict"""
        return {
            'id': trade.id,
            'trade_id': trade.trade_id,
            'symbol': trade.symbol,
            'side': trade.side,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'stop_loss': trade.stop_loss,
            'take_profit': trade.take_profit,
            'amount': trade.amount,
            'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
            'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
            'pnl': trade.pnl,
            'pnl_pct': trade.pnl_pct,
            'status': trade.status,
            'reason': trade.reason,
            'features': trade.features,
        }

    def _to_dict(self, obj) -> Dict:
        """تحويل عام إلى Dict"""
        return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}

    def close(self):
        """إغلاق الاتصال"""
        self.engine.dispose()
        if self.redis_client:
            self.redis_client.close()
        logger.info("Database connections closed")
