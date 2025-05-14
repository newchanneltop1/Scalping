from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import random
import logging
import os
import yfinance as yf
import requests
import json
from threading import Thread
import time
import database as db
from models import Signal, SignalResult, MarketSnapshot
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Initialize database
try:
    db.init_db()
    logging.info("Database initialized successfully")
except Exception as e:
    logging.error(f"Error initializing database: {e}")
    logging.error(traceback.format_exc())

# Store signal history (will be replaced with DB)
history = []

# Store market data
market_data = {
    "current_price": 0,
    "volume": 0,
    "high_24h": 0,
    "low_24h": 0,
    "last_update": None
}

# News impact tracker
economic_news = {
    "latest": [],
    "high_impact": False,
    "last_update": None
}

# Trading hours filter (Default is 24 hours trading)
trading_hours = {
    "start": 0,  # 00:00 UTC
    "end": 24,   # 24:00 UTC
    "enabled": False
}

# Technical indicators with descriptions
INDICATORS = {
    "EMA Crossover": "Exponential Moving Average crossover between 9 and 21 periods",
    "MACD": "Moving Average Convergence Divergence showing bullish/bearish momentum",
    "RSI Divergence": "Relative Strength Index divergence from price action",
    "Liquidity Sweep": "Price sweeping liquidity levels before reversing",
    "VWAP Bounce": "Price bouncing off the Volume Weighted Average Price",
    "Breakout": "Price breaking through significant resistance/support level",
    "Order Block": "Institutional order block identified on the chart",
    "Volume Confirmation": "Trading volume supports the price direction",
    "Fibonacci Retracement": "Price retracing to key Fibonacci levels",
    "Bollinger Bands": "Price touching or breaking through Bollinger Bands"
}

def fetch_market_data():
    """Fetch real-time market data for EUR/USD"""
    try:
        # Use yfinance to get current EURUSD data
        ticker = yf.Ticker("EURUSD=X")
        data = ticker.history(period="1d")
        
        if not data.empty:
            current_price = round(float(data['Close'].iloc[-1]), 5)
            volume = int(data['Volume'].iloc[-1]) if 'Volume' in data else 0
            high_24h = round(float(data['High'].max()), 5)
            low_24h = round(float(data['Low'].min()), 5)
            
            market_data.update({
                "current_price": current_price,
                "volume": volume,
                "high_24h": high_24h,
                "low_24h": low_24h,
                "last_update": datetime.now()
            })
            logging.debug(f"Updated market data: {market_data}")
        else:
            logging.warning("Empty data received from yfinance")
    except Exception as e:
        logging.error(f"Error fetching market data: {e}")
        # If error, use fallback value but mark as stale
        if market_data["current_price"] == 0:
            market_data["current_price"] = 1.07 + random.random() * 0.01

def fetch_economic_news():
    """Fetch latest economic news that might impact EUR/USD"""
    try:
        # This would ideally use a proper economic calendar API
        # For now we use a simplified approach with public APIs
        url = "https://www.forexfactory.com/news.xml"
        
        # Simulation for now since we need API access
        news_list = [
            {
                "title": "ECB Interest Rate Decision",
                "time": (datetime.now() - timedelta(hours=random.randint(1, 8))).isoformat(),
                "impact": "high" if random.random() > 0.7 else "medium",
                "currency": "EUR"
            },
            {
                "title": "US Non-Farm Payrolls",
                "time": (datetime.now() - timedelta(hours=random.randint(2, 12))).isoformat(),
                "impact": "high" if random.random() > 0.6 else "medium",
                "currency": "USD"
            },
            {
                "title": "EU Manufacturing PMI",
                "time": (datetime.now() - timedelta(hours=random.randint(4, 24))).isoformat(),
                "impact": "medium",
                "currency": "EUR"
            }
        ]
        
        # Check if there's high impact news in the last 2 hours
        high_impact = False
        for news in news_list:
            news_time = datetime.fromisoformat(news["time"])
            if news["impact"] == "high" and (datetime.now() - news_time).total_seconds() < 7200:
                high_impact = True
                break
        
        economic_news.update({
            "latest": news_list,
            "high_impact": high_impact,
            "last_update": datetime.now()
        })
        logging.debug(f"Updated economic news data, high impact: {high_impact}")
    except Exception as e:
        logging.error(f"Error fetching economic news: {e}")

def is_trading_allowed():
    """Check if trading is allowed based on current time and news impact"""
    if not trading_hours["enabled"]:
        return True
    
    now = datetime.utcnow().hour
    if now >= trading_hours["start"] and now < trading_hours["end"]:
        # Check for high impact news
        if economic_news["high_impact"]:
            return False
        return True
    return False

def background_data_updater():
    """Background thread to update market data and news periodically"""
    while True:
        fetch_market_data()
        fetch_economic_news()
        time.sleep(60)  # Update every minute

def calculate_signal_strength(probability):
    """Determine the signal strength class based on probability"""
    if probability >= 75:
        return "strong", "success"
    elif probability >= 50:
        return "moderate", "warning"
    else:
        return "weak", "danger"

def analyze_signal():
    """Generate a trading signal with technical indicators and probability"""
    # Ensure we have market data
    if market_data["current_price"] == 0 or market_data["last_update"] is None:
        fetch_market_data()
    
    # Check if trading is allowed based on time filters and news
    trading_allowed = is_trading_allowed()
    
    # Determine which strategies are active
    strategies = {}
    for name in INDICATORS:
        # Make Volume Confirmation dependent on actual volume data
        if name == "Volume Confirmation" and market_data["volume"] > 0:
            # Higher volume increases chances of confirmation
            strategies[name] = 1 if market_data["volume"] > 1000000 else 0
        else:
            # For other indicators, still use random for demo
            # In a real system, these would be calculated from price data
            strategies[name] = random.choice([0, 1])
    
    # If there's high impact news, reduce certain indicators
    if economic_news["high_impact"]:
        strategies["News Spike"] = 1  # Activate news spike indicator
        # Reduce reliability of pattern-based indicators during news
        strategies["EMA Crossover"] = 0
        strategies["RSI Divergence"] = 0
    
    # Add more weight to certain reliable indicators
    weighted_strategies = list(strategies.values())
    weighted_strategies += [strategies["EMA Crossover"]] * 2  # Give EMA more weight
    weighted_strategies += [strategies["MACD"]] * 2  # Give MACD more weight
    weighted_strategies += [strategies["Volume Confirmation"]] * 2  # Volume is important
    
    # Calculate the weighted probability
    active_signals = sum(weighted_strategies)
    total_signals = len(weighted_strategies)
    probability = int((active_signals / total_signals) * 100)
    
    # If trading not allowed due to time filters or news, reduce probability
    if not trading_allowed:
        probability = max(10, probability // 2)  # Cut probability in half, minimum 10%
    
    # Determine direction based on relative positioning to daily range
    if market_data["current_price"] > 0:
        # Calculate where current price is in today's range
        daily_range = market_data["high_24h"] - market_data["low_24h"]
        if daily_range > 0:
            position_in_range = (market_data["current_price"] - market_data["low_24h"]) / daily_range
            # If price is in lower third of range, more likely to go long
            # If price is in upper third of range, more likely to go short
            if position_in_range < 0.33:
                direction = "LONG" if random.random() > 0.3 else "SHORT"  # 70% chance of LONG
            elif position_in_range > 0.66:
                direction = "SHORT" if random.random() > 0.3 else "LONG"  # 70% chance of SHORT
            else:
                direction = "LONG" if random.random() > 0.5 else "SHORT"  # 50/50
        else:
            direction = "LONG" if random.random() > 0.5 else "SHORT"
    else:
        direction = "LONG" if random.random() > 0.5 else "SHORT"
    
    # Calculate estimated duration based on probability and news impact
    # Higher probability signals tend to last longer
    base_duration = random.randint(5, 15)
    modifier = probability / 50  # Gives a range of 0.5 to 2.0
    
    # News impact reduces expected duration of signals
    if economic_news["high_impact"]:
        modifier *= 0.5  # Halve duration during high impact news
    
    duration = int(base_duration * modifier)
    duration = max(5, min(45, duration))  # Cap between 5-45 minutes
    
    # Generate risk/reward ratio (higher for higher probability)
    risk_reward = round(1 + (probability / 100) * 2, 1)  # 1.0 to 3.0
    
    # Use real price from market data if available
    current_price = market_data["current_price"]
    if current_price == 0:
        current_price = round(1.07 + random.random() * 0.01, 5)
    
    # Calculate pip values for targets
    pip_value = 0.0001
    pips_movement = int(probability / 10) + random.randint(5, 15)  # 5-25 pips
    
    # Calculate entry, target and stop loss based on direction
    if direction == "LONG":
        entry_price = current_price
        target_price = round(current_price + (pip_value * pips_movement), 5)
        stop_loss = round(current_price - (pip_value * (pips_movement / risk_reward)), 5)
    else:
        entry_price = current_price
        target_price = round(current_price - (pip_value * pips_movement), 5)
        stop_loss = round(current_price + (pip_value * (pips_movement / risk_reward)), 5)
    
    # Determine signal strength class and color
    strength_class, strength_color = calculate_signal_strength(probability)
    
    # Create the signal dictionary
    signal = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategies": strategies,
        "probability": probability,
        "direction": direction,
        "duration": duration,
        "risk_reward": risk_reward,
        "current_price": current_price,
        "entry_price": entry_price,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "pips_target": pips_movement,
        "strength_class": strength_class,
        "strength_color": strength_color,
        "trading_allowed": trading_allowed,
        "volume": market_data["volume"],
        "high_24h": market_data["high_24h"],
        "low_24h": market_data["low_24h"],
        "has_high_impact_news": economic_news["high_impact"]
    }
    
    return signal

@app.route('/')
def index():
    """Render the main dashboard page"""
    global background_thread_started
    
    # Start background thread on first request
    if not background_thread_started:
        start_background_thread()
        background_thread_started = True
    
    # Make sure we have market data and news
    if market_data["last_update"] is None:
        fetch_market_data()
    if economic_news["last_update"] is None:
        fetch_economic_news()
        
    signal = analyze_signal()
    
    # Add signal to history
    history.append(signal)
    if len(history) > 10:
        history.pop(0)
    
    # Get statistics from the database
    try:
        stats = db.get_signal_statistics()
    except Exception as e:
        logging.error(f"Error getting signal statistics: {e}")
        stats = {
            "total_signals": 0,
            "signals_with_results": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "avg_pips_gained": 0
        }
    
    return render_template('index.html', 
                          signal=signal, 
                          history=history, 
                          indicators=INDICATORS,
                          market_data=market_data,
                          news=economic_news,
                          trading_hours=trading_hours,
                          stats=stats)

@app.route('/api/new-signal', methods=['GET'])
def new_signal():
    """API endpoint to generate a new signal"""
    # Fetch latest market data
    fetch_market_data()
    fetch_economic_news()
    
    signal = analyze_signal()
    
    # Add signal to history
    history.append(signal)
    if len(history) > 10:
        history.pop(0)
    
    # Save signal to database
    try:
        signal_id = db.save_signal(signal)
        if signal_id is not None:
            logging.info(f"Signal saved to database with ID: {signal_id}")
            signal["id"] = signal_id
    except Exception as e:
        logging.error(f"Error saving signal to database: {e}")
    
    # Save market snapshot
    try:
        db.save_market_snapshot(market_data)
    except Exception as e:
        logging.error(f"Error saving market snapshot: {e}")
    
    return jsonify(signal)

@app.route('/api/market-data', methods=['GET'])
def get_market_data():
    """API endpoint to get latest market data"""
    fetch_market_data()
    return jsonify(market_data)

@app.route('/api/economic-news', methods=['GET'])
def get_economic_news():
    """API endpoint to get latest economic news"""
    fetch_economic_news()
    return jsonify(economic_news)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """API endpoint to update trading settings"""
    try:
        data = request.get_json(force=True)
        
        if isinstance(data, dict) and 'trading_hours' in data:
            hours = data.get('trading_hours', {})
            if isinstance(hours, dict):
                if 'enabled' in hours:
                    trading_hours['enabled'] = bool(hours['enabled'])
                if 'start' in hours:
                    trading_hours['start'] = int(hours['start'])
                if 'end' in hours:
                    trading_hours['end'] = int(hours['end'])
    except Exception as e:
        logging.error(f"Error updating settings: {e}")
        return jsonify({"success": False, "error": str(e)})
    
    return jsonify({"success": True, "settings": {
        "trading_hours": trading_hours
    }})

@app.route('/api/signals', methods=['GET'])
def get_signals_api():
    """API endpoint to get signals from the database"""
    try:
        limit = int(request.args.get('limit', 10))
        signals = db.get_signals(limit)
        return jsonify({"success": True, "signals": signals})
    except Exception as e:
        logging.error(f"Error getting signals: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/signal/<int:signal_id>', methods=['GET'])
def get_signal_api(signal_id):
    """API endpoint to get a specific signal"""
    try:
        signal = db.get_signal_by_id(signal_id)
        if signal:
            return jsonify({"success": True, "signal": signal})
        return jsonify({"success": False, "error": "Signal not found"}), 404
    except Exception as e:
        logging.error(f"Error getting signal: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/signal/<int:signal_id>/result', methods=['POST'])
def add_signal_result(signal_id):
    """API endpoint to add a result for a signal"""
    try:
        data = request.get_json(force=True)
        
        if not isinstance(data, dict):
            return jsonify({"success": False, "error": "Invalid data format"}), 400
            
        # Validate required fields
        required_fields = ["result", "exit_price"]
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400
                
        # Add signal_id to data
        data["signal_id"] = signal_id
        
        # Set exit time if not provided
        if "exit_time" not in data:
            data["exit_time"] = datetime.now()
            
        # Save result
        result_id = db.save_signal_result(data)
        
        if result_id is not None:
            return jsonify({"success": True, "result_id": result_id})
        return jsonify({"success": False, "error": "Failed to save result"}), 500
    except Exception as e:
        logging.error(f"Error saving signal result: {e}")
        return jsonify({"success": False, "error": str(e)})

# Create a background thread starter function
def start_background_thread():
    # Get initial data
    fetch_market_data()
    fetch_economic_news()
    
    # Start updater thread
    thread = Thread(target=background_data_updater)
    thread.daemon = True
    thread.start()
    logging.debug("Started background data updater thread")

# We'll start the thread on first request since before_first_request is deprecated
background_thread_started = False

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
