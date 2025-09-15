import ccxt
import pandas as pd
import numpy as np  # Using numpy for manual calculations instead of pandas_ta
import time
import os
from typing import Optional, Tuple
from datetime import datetime

# Conditional import for Windows-specific sound library
try:
    import winsound
except ImportError:
    winsound = None

# --- Configuration ---
SYMBOL = 'XRP/USDT'
TIMEFRAME = '5m'
RSI_PERIOD = 14
MA_LENGTH = 14
MA_TYPE = 'SMA'
ATR_LENGTH = 14
TP_MULTIPLIER = 2.0
SL_MULTIPLIER = 1.0
CHECK_INTERVAL_SECONDS = 5  # Increased to 5 seconds to avoid rate limits
ALERT_COOLDOWN_SECONDS = 300

# --- Alert Sound Configuration ---
BUY_SOUND_FILE = 'buy_signal.wav'
SELL_SOUND_FILE = 'sell_signal.wav'

# --- Initialize Exchange ---
exchange = ccxt.mexc({
    'options': {
        'defaultType': 'swap',
    },
    'rateLimit': 1000,  # Add rate limiting
})


def play_alert_sound(sound_file: str):
    """Play alert sound on Windows"""
    try:
        if os.name == 'nt' and winsound:
            if os.path.exists(sound_file):
                winsound.PlaySound(sound_file, winsound.SND_FILENAME)
            else:
                print(f"\nWarning: Sound file not found at '{sound_file}'")
                winsound.Beep(1000, 500)
        else:
            print("\a", end='', flush=True)
    except Exception as e:
        print(f"\nCould not play alert sound: {e}")


def calculate_rsi_manual(prices: pd.Series, period: int) -> pd.Series:
    """Manual RSI calculation without pandas_ta"""
    deltas = np.diff(prices)
    seed = deltas[:period+1]
    
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    
    rs = up / down
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100. / (1. + rs)
    
    for i in range(period, len(prices)):
        delta = deltas[i-1]
        
        if delta > 0:
            up_val = delta
            down_val = 0.
        else:
            up_val = 0.
            down_val = -delta
        
        up = (up * (period - 1) + up_val) / period
        down = (down * (period - 1) + down_val) / period
        
        rs = up / down
        rsi[i] = 100. - 100. / (1. + rs)
    
    return pd.Series(rsi, index=prices.index)


def calculate_ema_manual(series: pd.Series, period: int) -> pd.Series:
    """Manual EMA calculation"""
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma_manual(series: pd.Series, period: int) -> pd.Series:
    """Manual SMA calculation"""
    return series.rolling(window=period).mean()


def calculate_atr_manual(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Manual ATR calculation"""
    tr = pd.DataFrame()
    tr['h-l'] = high - low
    tr['h-pc'] = abs(high - close.shift(1))
    tr['l-pc'] = abs(low - close.shift(1))
    tr['tr'] = tr[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    
    return tr['tr'].rolling(window=period).mean()


def calculate_indicators(df: pd.DataFrame) -> Tuple[Optional[float], Optional[float], Optional[float], bool, bool]:
    """Calculate all indicators manually"""
    min_data_needed = max(RSI_PERIOD, MA_LENGTH, ATR_LENGTH) + 2
    
    if len(df) < min_data_needed:
        return None, None, None, False, False

    try:
        # Calculate RSI manually
        rsi_series = calculate_rsi_manual(df['close'], RSI_PERIOD)
        
        # Calculate smoothed MA of RSI
        if MA_TYPE == 'SMA':
            smoothed_ma = calculate_sma_manual(rsi_series, MA_LENGTH)
        elif MA_TYPE == 'EMA':
            smoothed_ma = calculate_ema_manual(rsi_series, MA_LENGTH)
        else:  # WMA or default to EMA
            smoothed_ma = calculate_ema_manual(rsi_series, MA_LENGTH)
        
        # Calculate ATR manually
        atr_series = calculate_atr_manual(df['high'], df['low'], df['close'], ATR_LENGTH)
        
        # Get current values
        current_rsi = rsi_series.iloc[-1]
        current_ma = smoothed_ma.iloc[-1]
        current_atr = atr_series.iloc[-1]
        
        # Get previous values for crossover detection
        rsi_prev = rsi_series.iloc[-2]
        ma_prev = smoothed_ma.iloc[-2]
        
        # Check for crossovers
        buy_signal = (rsi_prev <= ma_prev) and (current_rsi > current_ma)
        sell_signal = (rsi_prev >= ma_prev) and (current_rsi < current_ma)
        
        return current_rsi, current_ma, current_atr, buy_signal, sell_signal
        
    except Exception as e:
        print(f"Error calculating indicators: {e}")
        return None, None, None, False, False


def calculate_tp_sl(current_price: float, atr_value: float, signal_type: str) -> Tuple[float, float]:
    """Calculate Take Profit and Stop Loss levels"""
    if signal_type == 'buy':
        tp = current_price + (atr_value * TP_MULTIPLIER)
        sl = current_price - (atr_value * SL_MULTIPLIER)
    elif signal_type == 'sell':
        tp = current_price - (atr_value * TP_MULTIPLIER)
        sl = current_price + (atr_value * SL_MULTIPLIER)
    else:
        tp = sl = current_price
    
    return tp, sl


def get_current_price(symbol: str) -> Optional[float]:
    """Fetch current price"""
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None


def main():
    """Main trading bot function"""
    last_alert_type = None
    last_alert_time = 0
    
    print(f"--- RSI vs MA Crossover Bot for {SYMBOL} ---")
    print(f"Timeframe: {TIMEFRAME}, RSI: {RSI_PERIOD}, MA: {MA_LENGTH} ({MA_TYPE})")
    print(f"ATR: {ATR_LENGTH}, TP: {TP_MULTIPLIER}x, SL: {SL_MULTIPLIER}x")
    print("-" * 50)

    while True:
        try:
            # Fetch OHLCV data
            limit = max(RSI_PERIOD, MA_LENGTH, ATR_LENGTH) * 2 + 10
            ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=limit)
            
            if len(ohlcv) < 30:  # Minimum data check
                print(f"Waiting for more data... ({len(ohlcv)} candles)")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            # Create DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calculate indicators
            current_rsi, current_ma, current_atr, buy_signal, sell_signal = calculate_indicators(df)
            
            if current_rsi is None:
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            current_price = get_current_price(SYMBOL)
            price_str = f"{current_price:.4f}" if current_price else "N/A"

            # Signal detection
            alert_to_fire = False
            current_alert_type = None
            status_message = ""
            tp_level = sl_level = None

            if buy_signal:
                status_message = f"BUY! RSI({current_rsi:.1f})↑MA({current_ma:.1f})"
                current_alert_type = 'buy'
                if current_price:
                    tp_level, sl_level = calculate_tp_sl(current_price, current_atr, 'buy')
                    status_message += f" | TP: {tp_level:.4f} SL: {sl_level:.4f}"
                alert_to_fire = True

            elif sell_signal:
                status_message = f"SELL! RSI({current_rsi:.1f})↓MA({current_ma:.1f})"
                current_alert_type = 'sell'
                if current_price:
                    tp_level, sl_level = calculate_tp_sl(current_price, current_atr, 'sell')
                    status_message += f" | TP: {tp_level:.4f} SL: {sl_level:.4f}"
                alert_to_fire = True

            else:
                status_message = f"RSI: {current_rsi:.1f}, MA: {current_ma:.1f}, ATR: {current_atr:.4f}"

            # Display results
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            if alert_to_fire and (time.time() - last_alert_time) > ALERT_COOLDOWN_SECONDS:
                print(f"\n*** SIGNAL [{timestamp}] {SYMBOL} {price_str} - {status_message} ***")
                
                if current_alert_type == 'buy':
                    play_alert_sound(BUY_SOUND_FILE)
                elif current_alert_type == 'sell':
                    play_alert_sound(SELL_SOUND_FILE)
                
                last_alert_time = time.time()
                last_alert_type = current_alert_type
            else:
                print(f"[{timestamp}] {SYMBOL} {price_str} - {status_message:<60}", end='\r', flush=True)

            time.sleep(CHECK_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n\nBot stopped by user")
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()