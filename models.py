from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Signal(Base):
    """Model for trading signals"""
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    direction = Column(String(10), nullable=False)  # LONG or SHORT
    probability = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    pips_target = Column(Integer, nullable=False)
    risk_reward = Column(Float, nullable=False)
    duration = Column(Integer, nullable=False)  # in minutes
    strategies = Column(JSON, nullable=False)
    strength_class = Column(String(20), nullable=False)
    trading_allowed = Column(Boolean, default=True)
    high_impact_news = Column(Boolean, default=False)
    volume = Column(Float, nullable=True)
    
    # Relationship to results (one signal can have one result)
    result = relationship("SignalResult", back_populates="signal", uselist=False)

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "direction": self.direction,
            "probability": self.probability,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "pips_target": self.pips_target,
            "risk_reward": self.risk_reward,
            "duration": self.duration,
            "strategies": self.strategies,
            "strength_class": self.strength_class,
            "trading_allowed": self.trading_allowed,
            "high_impact_news": self.high_impact_news,
            "volume": self.volume
        }

class SignalResult(Base):
    """Model for tracking the results of signals"""
    __tablename__ = "signal_results"
    
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey("signals.id"))
    result = Column(String(10))  # WIN, LOSS, or NEUTRAL
    pips_gained = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    notes = Column(String(255), nullable=True)
    
    # Relationship to signal
    signal = relationship("Signal", back_populates="result")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "signal_id": self.signal_id,
            "result": self.result,
            "pips_gained": self.pips_gained,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.strftime("%Y-%m-%d %H:%M:%S") if self.exit_time is not None else None,
            "notes": self.notes
        }

class MarketSnapshot(Base):
    """Model for storing historical market data snapshots"""
    __tablename__ = "market_snapshots"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    symbol = Column(String(20), default="EURUSD", nullable=False)
    price = Column(Float, nullable=False)
    high_24h = Column(Float, nullable=True)
    low_24h = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": self.symbol,
            "price": self.price,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "volume": self.volume
        }