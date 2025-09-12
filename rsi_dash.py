import ccxt
import time
import numpy as np
from datetime import datetime
import platform
import os
import winsound
import threading
import sys

# Initialize MEXC exchange
exchange = ccxt.mexc({
    'enableRateLimit': True,
})

# Configuration
# symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']  # Add your coins here
symbols = ['XRP/USDT']  # Add your coins here
timeframe = '1m'  # Timeframe: 1m, 5m, 15m, 30m, 1h, 4h, 1d
rsi_period = 14
price_lookback = 200  # Candles to analyze for divergence
min_peak_distance = 5  # Minimum candles between peaks
play_sounds = True  # Set to False to disable alert sounds
price_refresh_seconds = 5  # Live price refresh interval

# Global variables for tracking state
live_prices = {symbol: "Loading..." for symbol in symbols}
last_alerts = {symbol: {"bullish": None, "bearish": None} for symbol in symbols}
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
    print(f"RSI Divergence Monitor RSI Dash ({timeframe}) | {timestamp}")
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
        if last_alerts[symbol]["bullish"]:
            alert_status = " | 🟢 BULLISH ALERT"
        elif last_alerts[symbol]["bearish"]:
            alert_status = " | 🔴 BEARISH ALERT"
        print(f"  {symbol}: {price:.4f}{alert_status}")
    print("-" * 50)

def play_bullish_alert():
    """Play sound for bullish divergence detection"""
    if not play_sounds:
        return
        
    system = platform.system()
    try:
        if system == 'Windows':
            winsound.PlaySound("alert.wav", winsound.SND_FILENAME)  # Higher pitch
            winsound.PlaySound("alert.wav", winsound.SND_FILENAME)
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
            winsound.PlaySound("alert.wav", winsound.SND_FILENAME)  # Lower pitch
            winsound.PlaySound("alert.wav", winsound.SND_FILENAME)
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

def find_peaks(data, min_distance=5):
    peaks = []
    for i in range(min_distance, len(data)-min_distance):
        if data[i] == max(data[i-min_distance:i+min_distance+1]):
            peaks.append(i)
    return peaks

def detect_divergence(prices, rsi_values):
    # Find price peaks
    price_peaks = find_peaks(prices, min_peak_distance)
    rsi_peaks = find_peaks(rsi_values, min_peak_distance)
    
    bearish_divergences = []
    bullish_divergences = []
    
    # Check last two peaks for bearish divergence
    if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
        last_price_peak = price_peaks[-1]
        prev_price_peak = price_peaks[-2]
        last_rsi_peak = rsi_peaks[-1]
        prev_rsi_peak = rsi_peaks[-2]
        
        # Bearish divergence: Higher price highs with lower RSI highs
        if (prices[last_price_peak] > prices[prev_price_peak] and
            rsi_values[last_rsi_peak] < rsi_values[prev_rsi_peak]):
            bearish_divergences.append((prev_price_peak, last_price_peak))
    
    # Find troughs (reverse of peaks)
    price_troughs = find_peaks([-x for x in prices], min_peak_distance)
    rsi_troughs = find_peaks([-x for x in rsi_values], min_peak_distance)
    
    # Check last two troughs for bullish divergence
    if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
        last_price_trough = price_troughs[-1]
        prev_price_trough = price_troughs[-2]
        last_rsi_trough = rsi_troughs[-1]
        prev_rsi_trough = rsi_troughs[-2]
        
        # Bullish divergence: Lower price lows with higher RSI lows
        if (prices[last_price_trough] < prices[prev_price_trough] and
            rsi_values[last_rsi_trough] > rsi_values[prev_rsi_trough]):
            bullish_divergences.append((prev_price_trough, last_price_trough))
    
    return bullish_divergences, bearish_divergences

def check_divergences():
    """Check for divergences in all symbols"""
    while True:
        try:
            for symbol in symbols:
                # Reset alert status
                last_alerts[symbol]["bullish"] = False
                last_alerts[symbol]["bearish"] = False
                
                # Fetch OHLCV data
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=price_lookback + rsi_period)
                if len(ohlcv) < price_lookback + rsi_period:
                    continue
                
                # Extract closing prices
                closes = np.array([x[4] for x in ohlcv])
                
                # Calculate RSI
                rsi = calculate_rsi(closes, rsi_period)
                valid_rsi = rsi[-price_lookback:]
                valid_prices = closes[-price_lookback:]
                
                # Detect divergences
                bullish, bearish = detect_divergence(valid_prices, valid_rsi)
                
                # Process bullish divergence
                if bullish:
                    last_alerts[symbol]["bullish"] = True
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    threading.Thread(target=play_bullish_alert).start()
                
                # Process bearish divergence
                if bearish:
                    last_alerts[symbol]["bearish"] = True
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    threading.Thread(target=play_bearish_alert).start()
            
            # Wait before next check (based on timeframe)
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
            
            # Print alerts section
            print("RSI DIVERGENCE ALERTS:")
            print("-" * 50)
            alert_found = False
            
            for symbol in symbols:
                if last_alerts[symbol]["bullish"]:
                    print(f"  🚀 BULLISH DIVERGENCE DETECTED ({symbol})")
                    alert_found = True
                if last_alerts[symbol]["bearish"]:
                    print(f"  ⚠️ BEARISH DIVERGENCE DETECTED ({symbol})")
                    alert_found = True
            
            if not alert_found:
                print("  No active alerts")
            
            # Print footer
            print("=" * 50)
            print("Monitoring... Press Ctrl+C to exit")
            
            # Update line count
            screen_lines = len(symbols) + 10  # Header + prices + alerts + footer
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            os._exit(0)
        except Exception as e:
            print(f"Display error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Start live price updater thread
    price_thread = threading.Thread(target=update_live_prices, daemon=True)
    price_thread.start()
    
    # Start divergence checker thread
    divergence_thread = threading.Thread(target=check_divergences, daemon=True)
    divergence_thread.start()
    
    # Start display loop in main thread
    display_loop()