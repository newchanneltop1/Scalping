import os
import logging
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError
from models import Base, Signal, SignalResult, MarketSnapshot

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    logging.warning("DATABASE_URL not found in environment variables, using in-memory SQLite")
    DATABASE_URL = "sqlite:///:memory:"
else:
    # Parse and reconstruct the URL to handle SSL properly
    # Don't add parameters to the URL directly - they'll be added in the connect_args
    logging.info(f"Using database URL: {DATABASE_URL}")

# Create engine and session with retry logic
def create_db_engine(url, max_retries=3, retry_interval=2):
    """Create DB engine with retry logic for handling connection issues"""
    retry_count = 0
    while retry_count < max_retries:
        try:
            # Different connect_args for PostgreSQL vs SQLite
            connect_args = {}
            if url.startswith("postgresql"):
                connect_args = {
                    "connect_timeout": 10,
                    "application_name": "eur_usd_dashboard",
                    "sslmode": "require"
                }
            
            engine = create_engine(
                url,
                pool_pre_ping=True,        # Check connection before use
                pool_recycle=1800,         # Recycle connections after 30 minutes
                pool_size=5,               # Small pool size for Replit
                max_overflow=10,           # Allow some overflow connections
                connect_args=connect_args
            )
            
            # Try a simple query to verify connection
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
                
            logging.info("Database engine created successfully")
            return engine
        except Exception as e:
            retry_count += 1
            logging.warning(f"Database connection attempt {retry_count} failed: {e}")
            if retry_count < max_retries:
                logging.info(f"Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
            else:
                logging.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                # Fallback to SQLite for development
                logging.warning("Falling back to in-memory SQLite database")
                return create_engine("sqlite:///:memory:")

# Create engine and session
engine = create_db_engine(DATABASE_URL)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# Helper function for database operations with retry mechanism
def db_operation(operation_func, max_retries=3, retry_interval=1):
    """Execute a database operation with retry logic"""
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            return operation_func()
        except OperationalError as e:
            last_error = e
            retry_count += 1
            logging.warning(f"Database operation failed (attempt {retry_count}): {e}")
            if retry_count < max_retries:
                logging.info(f"Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
    
    logging.error(f"Database operation failed after {max_retries} attempts: {last_error}")
    return None

# Initialize database
def init_db():
    """Initialize the database, create tables if they don't exist"""
    def _init():
        Base.metadata.create_all(engine)
        return True
    
    result = db_operation(_init)
    if result:
        logging.info("Database initialized")
    else:
        logging.error("Failed to initialize database")

# Signal operations
def save_signal(signal_data):
    """Save a new signal to the database"""
    session = Session()
    try:
        # Convert any non-compatible types to strings for JSON
        strategies = {}
        for key, value in signal_data.get("strategies", {}).items():
            strategies[key] = int(value) if isinstance(value, bool) else value
        
        signal = Signal(
            timestamp=signal_data.get("timestamp"),
            direction=signal_data.get("direction"),
            probability=signal_data.get("probability"),
            entry_price=signal_data.get("entry_price"),
            target_price=signal_data.get("target_price"),
            stop_loss=signal_data.get("stop_loss"),
            pips_target=signal_data.get("pips_target"),
            risk_reward=signal_data.get("risk_reward"),
            duration=signal_data.get("duration"),
            strategies=strategies,
            strength_class=signal_data.get("strength_class"),
            trading_allowed=signal_data.get("trading_allowed", True),
            high_impact_news=signal_data.get("has_high_impact_news", False),
            volume=signal_data.get("volume", 0)
        )
        session.add(signal)
        session.commit()
        logging.info(f"Signal saved with ID: {signal.id}")
        return signal.id
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving signal: {e}")
        return None
    finally:
        session.close()

def get_signals(limit=10):
    """Get the most recent signals from the database"""
    session = Session()
    try:
        signals = session.query(Signal).order_by(Signal.timestamp.desc()).limit(limit).all()
        return [signal.to_dict() for signal in signals]
    except Exception as e:
        logging.error(f"Error getting signals: {e}")
        return []
    finally:
        session.close()

def get_signal_by_id(signal_id):
    """Get a signal by its ID"""
    session = Session()
    try:
        signal = session.query(Signal).filter(Signal.id == signal_id).first()
        if signal:
            return signal.to_dict()
        return None
    except Exception as e:
        logging.error(f"Error getting signal: {e}")
        return None
    finally:
        session.close()

# Signal result operations
def save_signal_result(result_data):
    """Save a signal result to the database"""
    session = Session()
    try:
        result = SignalResult(
            signal_id=result_data.get("signal_id"),
            result=result_data.get("result"),
            pips_gained=result_data.get("pips_gained"),
            exit_price=result_data.get("exit_price"),
            exit_time=result_data.get("exit_time"),
            notes=result_data.get("notes")
        )
        session.add(result)
        session.commit()
        logging.info(f"Signal result saved with ID: {result.id}")
        return result.id
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving signal result: {e}")
        return None
    finally:
        session.close()

# Market data operations
def save_market_snapshot(market_data):
    """Save a market data snapshot to the database"""
    session = Session()
    try:
        snapshot = MarketSnapshot(
            symbol="EURUSD",
            price=market_data.get("current_price"),
            high_24h=market_data.get("high_24h"),
            low_24h=market_data.get("low_24h"),
            volume=market_data.get("volume", 0)
        )
        session.add(snapshot)
        session.commit()
        logging.info(f"Market snapshot saved with ID: {snapshot.id}")
        return snapshot.id
    except Exception as e:
        session.rollback()
        logging.error(f"Error saving market snapshot: {e}")
        return None
    finally:
        session.close()

def get_market_snapshots(limit=100):
    """Get recent market snapshots"""
    session = Session()
    try:
        snapshots = session.query(MarketSnapshot).order_by(MarketSnapshot.timestamp.desc()).limit(limit).all()
        return [snapshot.to_dict() for snapshot in snapshots]
    except Exception as e:
        logging.error(f"Error getting market snapshots: {e}")
        return []
    finally:
        session.close()

# Statistical functions
def get_signal_statistics():
    """Get statistics on signal performance"""
    session = Session()
    try:
        # Count total signals
        total_signals = session.query(Signal).count()
        
        # Count signals with results
        signals_with_results = session.query(SignalResult).count()
        
        # Count wins and losses
        wins = session.query(SignalResult).filter(SignalResult.result == "WIN").count()
        losses = session.query(SignalResult).filter(SignalResult.result == "LOSS").count()
        
        # Calculate win rate
        win_rate = (wins / signals_with_results) * 100 if signals_with_results > 0 else 0
        
        # Calculate average pips gained
        from sqlalchemy import func
        avg_pips = session.query(func.avg(SignalResult.pips_gained)).scalar() or 0
        
        return {
            "total_signals": total_signals,
            "signals_with_results": signals_with_results,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "avg_pips_gained": round(float(avg_pips), 2)
        }
    except Exception as e:
        logging.error(f"Error getting signal statistics: {e}")
        return {
            "total_signals": 0,
            "signals_with_results": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_pips_gained": 0
        }
    finally:
        session.close()