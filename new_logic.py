import ccxt
import time
import numpy as np
from datetime import datetime
import platform
import os
import winsound
import threading
import sys
import json
from collections import defaultdict

# Initialize MEXC exchange
exchange = ccxt.mexc({
    'enableRateLimit': True,
})

# Configuration
symbols = ['XRP/USDT']  # Add your coins here
timeframe = '5m'  # Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d
rsi_period = 14
price_refresh_seconds = 5  # Live price refresh interval
play_sounds = True  # Set to False to disable alert sounds
log_file = "divergence_log.txt"  # File to save divergence history
max_occurrences = 3  # Maximum times to show the same alert

# Divergence detection parameters (from PineScript)
lbL = 5  # Pivot lookback left
lbR = 5  # Pivot lookback right
rangeUpper = 60  # Max of lookback range
rangeLower = 5   # Min of lookback range
plotBull = True      # Detect Regular Bullish
plotHiddenBull = False  # Detect Hidden Bullish
plotBear = True      # Detect Regular Bearish
plotHiddenBear = False  # Detect Hidden Bearish

# Global variables for tracking state
live_prices = {symbol: "Loading..." for symbol in symbols}
current_alerts = {symbol: {
    "regular_bullish": False,
    "hidden_bullish": False,
    "regular_bearish": False,
    "hidden_bearish": False
} for symbol in symbols}

# Divergence history storage
divergence_history = []
divergence_counts = defaultdict(lambda: defaultdict(int))  # symbol -> type -> count
screen_lines = 0

def clear_console():
    """Clear console based on OS"""
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        os.system('clear')

def print_header():
    """Print the header with current time and timeframe"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Advanced RSI Divergence Monitor ({timeframe}) | {timestamp}")
    print("=" * 50)

def update_live_prices():
    """Fetch and update live prices for all symbols"""
    while True:
        try:
            for symbol in symbols:
                ticker = exchange.fetch_ticker(symbol)
                live_prices[symbol] = float(ticker['last'])
            time.sleep(price_refresh_seconds)
        except Exception as e:
            print(f"Price update error: {e}")
            time.sleep(5)

def print_live_prices():
    """Print live prices in a fixed position"""
    print("LIVE PRICES:")
    for symbol in symbols:
        price = live_prices[symbol]
        alert_status = ""
        if current_alerts[symbol]["regular_bullish"] or current_alerts[symbol]["hidden_bullish"]:
            alert_status = " | 🟢 BULLISH"
        elif current_alerts[symbol]["regular_bearish"] or current_alerts[symbol]["hidden_bearish"]:
            alert_status = " | 🔴 BEARISH"
        print(f"  {symbol}: {price:.4f}{alert_status}")
    print("-" * 50)

def play_bullish_alert():
    """Play sound for bullish divergence detection"""
    if not play_sounds:
        return
        
    system = platform.system()
    try:
        if system == 'Windows':
            if timeframe == '1m':
                winsound.PlaySound("XRP-1m-bullish.wav", winsound.SND_FILENAME)  # Higher pitch                
                winsound.PlaySound("XRP-1m-bullish.wav", winsound.SND_FILENAME)  # Higher pitch                
            else:
                winsound.PlaySound("XRP-5m-Bullish.wav", winsound.SND_FILENAME)  # Higher pitch
                winsound.PlaySound("XRP-5m-Bullish.wav", winsound.SND_FILENAME)  # Higher pitch
                
        elif system == 'Darwin':  # macOS
            os.system('afplay /System/Library/Sounds/Ping.aiff')
            time.sleep(0.5)
            os.system('afplay /System/Library/Sounds/Ping.aiff')
        elif system == 'Linux':
            os.system('spd-say "bullish divergence"')
        else:
            print('\a')  # System beep as fallback
            time.sleep(0.3)
            print('\a')
    except:
        print("Couldn't play sound")

def play_bearish_alert():
    """Play sound for bearish divergence detection"""
    if not play_sounds:
        return
        
    system = platform.system()
    try:
        if system == 'Windows':
           if timeframe == '1m':
                winsound.PlaySound("XRP-1m-bearish.wav", winsound.SND_FILENAME)  # Higher pitch                
                winsound.PlaySound("XRP-1m-bearish.wav", winsound.SND_FILENAME)  # Higher pitch                
           else:
                winsound.PlaySound("XRP-5m-Bearish.wav", winsound.SND_FILENAME)  # Higher pitch
                winsound.PlaySound("XRP-5m-Bearish.wav", winsound.SND_FILENAME)  # Higher pitch

        elif system == 'Darwin':  # macOS
            os.system('afplay /System/Library/Sounds/Basso.aiff')
        elif system == 'Linux':
            os.system('spd-say "bearish divergence"')
        else:
            print('\a')  # System beep
    except:
        print("Couldn't play sound")

def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    
    rsi = np.zeros_like(prices)
    rsi[:period] = 100.0 - 100.0 / (1 + avg_gain / (avg_loss + 1e-10))
    
    for i in range(period, len(prices)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i-1]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i-1]) / period
        
        if avg_loss < 1e-10:
            rs = 100  # Prevent division by zero
        else:
            rs = avg_gain / avg_loss
            
        rsi[i] = 100.0 - 100.0 / (1 + rs)
    
    return rsi

def find_pivot_lows(data, lbL, lbR):
    """Find pivot lows in data series"""
    pivot_lows = []
    n = len(data)
    for i in range(lbL, n - lbR):
        window = data[i-lbL : i+lbR+1]
        if data[i] == min(window):
            pivot_lows.append(i)
    return pivot_lows

def find_pivot_highs(data, lbL, lbR):
    """Find pivot highs in data series"""
    pivot_highs = []
    n = len(data)
    for i in range(lbL, n - lbR):
        window = data[i-lbL : i+lbR+1]
        if data[i] == max(window):
            pivot_highs.append(i)
    return pivot_highs

def in_range(cond, current_index, rangeLower, rangeUpper):
    """Check if condition is within bar range"""
    bars = current_index - cond
    return rangeLower <= bars <= rangeUpper

def detect_divergences(osc, lows, highs, lbL, lbR, rangeLower, rangeUpper):
    """Detect all types of divergences based on PineScript logic"""
    # Find pivots in RSI
    rsi_pl = find_pivot_lows(osc, lbL, lbR)
    rsi_ph = find_pivot_highs(osc, lbL, lbR)
    
    # Find pivots in price
    price_pl = find_pivot_lows(lows, lbL, lbR)
    price_ph = find_pivot_highs(highs, lbL, lbR)
    
    results = {
        "regular_bullish": False,
        "hidden_bullish": False,
        "regular_bearish": False,
        "hidden_bearish": False
    }
    
    # Regular Bullish: Price Lower Low, RSI Higher Low
    if len(rsi_pl) >= 2 and len(price_pl) >= 2:
        current_rsi_pl = rsi_pl[-1]
        prev_rsi_pl = rsi_pl[-2]
        
        if in_range(prev_rsi_pl, current_rsi_pl, rangeLower, rangeUpper):
            # Get corresponding price pivot indices
            current_price_pl = price_pl[-1]
            prev_price_pl = price_pl[-2]
            
            # Conditions
            osc_hl = osc[current_rsi_pl] > osc[prev_rsi_pl]  # RSI Higher Low
            price_ll = lows[current_price_pl] < lows[prev_price_pl]  # Price Lower Low
            
            if plotBull and osc_hl and price_ll:
                results["regular_bullish"] = True
    
    # Hidden Bullish: Price Higher Low, RSI Lower Low
    if len(rsi_pl) >= 2 and len(price_pl) >= 2:
        current_rsi_pl = rsi_pl[-1]
        prev_rsi_pl = rsi_pl[-2]
        
        if in_range(prev_rsi_pl, current_rsi_pl, rangeLower, rangeUpper):
            current_price_pl = price_pl[-1]
            prev_price_pl = price_pl[-2]
            
            osc_ll = osc[current_rsi_pl] < osc[prev_rsi_pl]  # RSI Lower Low
            price_hl = lows[current_price_pl] > lows[prev_price_pl]  # Price Higher Low
            
            if plotHiddenBull and osc_ll and price_hl:
                results["hidden_bullish"] = True
    
    # Regular Bearish: Price Higher High, RSI Lower High
    if len(rsi_ph) >= 2 and len(price_ph) >= 2:
        current_rsi_ph = rsi_ph[-1]
        prev_rsi_ph = rsi_ph[-2]
        
        if in_range(prev_rsi_ph, current_rsi_ph, rangeLower, rangeUpper):
            current_price_ph = price_ph[-1]
            prev_price_ph = price_ph[-2]
            
            osc_lh = osc[current_rsi_ph] < osc[prev_rsi_ph]  # RSI Lower High
            price_hh = highs[current_price_ph] > highs[prev_price_ph]  # Price Higher High
            
            if plotBear and osc_lh and price_hh:
                results["regular_bearish"] = True
    
    # Hidden Bearish: Price Lower High, RSI Higher High
    if len(rsi_ph) >= 2 and len(price_ph) >= 2:
        current_rsi_ph = rsi_ph[-1]
        prev_rsi_ph = rsi_ph[-2]
        
        if in_range(prev_rsi_ph, current_rsi_ph, rangeLower, rangeUpper):
            current_price_ph = price_ph[-1]
            prev_price_ph = price_ph[-2]
            
            osc_hh = osc[current_rsi_ph] > osc[prev_rsi_ph]  # RSI Higher High
            price_lh = highs[current_price_ph] < highs[prev_price_ph]  # Price Lower High
            
            if plotHiddenBear and osc_hh and price_lh:
                results["hidden_bearish"] = True
    
    return results

def log_divergence(symbol, divergence_type, price, timestamp):
    """Log divergence to file and history if not exceeded max occurrences"""
    # Get current count for this divergence
    key = f"{symbol}_{divergence_type}"
    current_count = divergence_counts[symbol][divergence_type]
    
    if current_count >= max_occurrences:
        return  # Skip logging if max occurrences reached
    
    entry = {
        "timestamp": timestamp,
        "symbol": symbol,
        "type": divergence_type,
        "price": price
    }
    
    # Add to history
    divergence_history.append(entry)
    
    # Write to log file
    try:
        with open(log_file, "a") as f:
            f.write(f"{timestamp} | {symbol} | {divergence_type} | {price:.4f}\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")
    
    # Update count
    divergence_counts[symbol][divergence_type] += 1

def check_divergences():
    """Check for divergences in all symbols"""
    min_bars = max(rangeUpper + lbL + lbR, 100)  # Ensure enough bars for analysis
    
    while True:
        try:
            for symbol in symbols:
                # Reset current alerts
                for key in current_alerts[symbol]:
                    current_alerts[symbol][key] = False
                
                # Fetch OHLCV data
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=min_bars)
                if len(ohlcv) < min_bars:
                    continue
                
                # Extract data
                closes = np.array([x[4] for x in ohlcv])
                lows = np.array([x[3] for x in ohlcv])
                highs = np.array([x[2] for x in ohlcv])
                
                # Calculate RSI
                rsi = calculate_rsi(closes, rsi_period)
                
                # Detect divergences
                divergences = detect_divergences(
                    rsi, lows, highs, 
                    lbL, lbR, rangeLower, rangeUpper
                )
                
                # Update current alerts
                current_alerts[symbol] = divergences
                
                # Log new divergences
                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for div_type, detected in divergences.items():
                    if detected:
                        # Reset count if divergence is not currently active
                        if not detected:
                            divergence_counts[symbol][div_type] = 0
                            
                        # Use current price for logging
                        log_divergence(symbol, div_type, live_prices[symbol], timestamp_str)
                
                # Play alerts
                if (divergences["regular_bullish"] or divergences["hidden_bullish"]) and \
                   divergence_counts[symbol].get("regular_bullish", 0) < max_occurrences and \
                   divergence_counts[symbol].get("hidden_bullish", 0) < max_occurrences:
                    threading.Thread(target=play_bullish_alert).start()
                    
                if (divergences["regular_bearish"] or divergences["hidden_bearish"]) and \
                   divergence_counts[symbol].get("regular_bearish", 0) < max_occurrences and \
                   divergence_counts[symbol].get("hidden_bearish", 0) < max_occurrences:
                    threading.Thread(target=play_bearish_alert).start()
            
            # Wait before next check
            sleep_time = {
                '1m': 60,
                '5m': 300,
                '15m': 900,
                '30m': 1800,
                '1h': 3600,
                '4h': 14400,
                '1d': 86400
            }.get(timeframe, 300)
            
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"Divergence check error: {e}")
            time.sleep(60)

def display_loop():
    """Main display loop that updates the console"""
    global screen_lines
    
    while True:
        try:
            # Save current line count
            current_lines = screen_lines
            
            # Clear only the lines we've written
            for _ in range(current_lines):
                sys.stdout.write("\033[F")  # Move cursor up one line
                sys.stdout.write("\033[K")  # Clear line
            
            # Print updated content
            print_header()
            print_live_prices()
            
            # Print current alerts section
            print("CURRENT DIVERGENCE ALERTS:")
            print("-" * 50)
            current_alert_found = False
            
            for symbol in symbols:
                alerts = []
                if current_alerts[symbol]["regular_bullish"]:
                    count = divergence_counts[symbol].get("regular_bullish", 0)
                    if count < max_occurrences:
                        alerts.append(f"REGULAR BULLISH ({count+1}/{max_occurrences})")
                if current_alerts[symbol]["hidden_bullish"]:
                    count = divergence_counts[symbol].get("hidden_bullish", 0)
                    if count < max_occurrences:
                        alerts.append(f"HIDDEN BULLISH ({count+1}/{max_occurrences})")
                if current_alerts[symbol]["regular_bearish"]:
                    count = divergence_counts[symbol].get("regular_bearish", 0)
                    if count < max_occurrences:
                        alerts.append(f"REGULAR BEARISH ({count+1}/{max_occurrences})")
                if current_alerts[symbol]["hidden_bearish"]:
                    count = divergence_counts[symbol].get("hidden_bearish", 0)
                    if count < max_occurrences:
                        alerts.append(f"HIDDEN BEARISH ({count+1}/{max_occurrences})")
                
                if alerts:
                    current_alert_found = True
                    print(f"  {symbol}:")
                    for alert in alerts:
                        print(f"    • {alert}")
            
            if not current_alert_found:
                print("  No current alerts")
            
            # Print divergence history
            print("\nDIVERGENCE HISTORY (newest first, max 3 per type):")
            print("-" * 50)
            if divergence_history:
                # Show last 10 entries (newest first)
                for entry in reversed(divergence_history[-10:]):
                    count = divergence_counts[entry['symbol']].get(entry['type'], 0)
                    if count <= max_occurrences:
                        print(f"  {entry['timestamp']} - {entry['symbol']}:")
                        print(f"    • {entry['type']} at {entry['price']:.4f} ({count}/{max_occurrences})")
            else:
                print("  No divergences recorded yet")
            
            # Print footer
            print("=" * 50)
            print(f"Monitoring... Press Ctrl+C to exit | Log: {log_file}")
            
            # Update line count
            screen_lines = len(symbols) + 15 + len(divergence_history[-10:]) * 3
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            os._exit(0)
        except Exception as e:
            print(f"Display error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Create log file header if new file
    if not os.path.exists(log_file):
        try:
            with open(log_file, "w") as f:
                f.write("TIMESTAMP | SYMBOL | DIVERGENCE TYPE | PRICE\n")
                f.write("="*50 + "\n")
        except:
            pass
    
    # Start live price updater thread
    price_thread = threading.Thread(target=update_live_prices, daemon=True)
    price_thread.start()
    
    # Start divergence checker thread
    divergence_thread = threading.Thread(target=check_divergences, daemon=True)
    divergence_thread.start()
    
    # Start display loop in main thread
    display_loop()