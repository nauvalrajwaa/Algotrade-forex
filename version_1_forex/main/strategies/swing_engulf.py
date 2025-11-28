import pandas as pd
import numpy as np
from .base import Strategy

class Swing_Engulf_Strategy(Strategy):

    # === DEFAULT PARAMS ===
    DEFAULT_PARAMETERS = {
        "length": 5,          # Swing Length
        "tolerance": 40,      # Engulfing Tolerance (bars)
        # SL/TP parameters diabaikan di sini karena dihandle engine
        # "sl_pips": 6000, 
        # "tp_pips": 20000,
        # "pip_value": 0.0001
    }

    """
    Swing + Engulfing Detector Strategy.
    Logic converted from Pine Script.
    Menghasilkan SIGNAL (1 = Buy, -1 = Sell, 0 = No Signal)
    """

    def __init__(self, params=None):
        super().__init__(params)

        # Merge defaults
        merged = Swing_Engulf_Strategy.DEFAULT_PARAMETERS.copy()
        if params is not None:
            merged.update(params)

        self.length = int(merged["length"])
        self.tolerance = int(merged["tolerance"])

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Copy df to avoid SettingWithCopy warnings
        df = df.copy()
        
        # Inisialisasi kolom signal
        df["signal"] = 0
        
        # Konversi ke numpy array untuk performa (looping di pandas lambat)
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        # Kita asumsikan index adalah DatetimeIndex
        times = df.index
        
        n = len(df)
        length = self.length
        tolerance = self.tolerance
        
        # === STORAGE UNTUK SWINGS (Sama seperti array di Pine Script) ===
        # List of dicts: {'idx': int, 'open': float, 'close': float, 'type': 'HH/LL', 'engulfed': bool}
        swings = []
        
        # Loop utama (bar-by-bar simulation)
        # Kita mulai loop dari index yang cukup untuk melihat ke belakang (2 * length)
        start_idx = length * 2
        
        for i in range(start_idx, n):
            
            # 1. === SWING DETECTION LOGIC ===
            # Pivot High/Low dikonfirmasi 'length' bars setelah kejadiannya.
            # Jadi pada bar 'i', kita mengecek apakah bar di 'i - length' adalah pivot.
            
            check_idx = i - length
            
            # Tentukan window range untuk cek pivot: [i - 2*length, i]
            # Pivot High Logic: high[check_idx] harus max di range local
            window_start = i - (length * 2)
            window_end = i + 1 # +1 karena slicing python exclusive
            
            current_window_highs = highs[window_start : window_end]
            current_window_lows = lows[window_start : window_end]
            
            # Cek Pivot High
            # (Note: Logic Pine ta.pivothigh(5,5) means it's the highest in 5 left and 5 right)
            is_pivot_high = highs[check_idx] == np.max(current_window_highs)
            
            # Cek Pivot Low
            is_pivot_low = lows[check_idx] == np.min(current_window_lows)
            
            # Simpan Swing (Sama seperti array.push di Pine)
            if is_pivot_high:
                # Type HH/LH logic disederhanakan (disimpan tapi logic engulfing utama hanya butuh open/close)
                swings.append({
                    'idx': check_idx,
                    'open': opens[check_idx],
                    'close': closes[check_idx],
                    'type': 'High',
                    'engulfed': False
                })
                
            if is_pivot_low:
                swings.append({
                    'idx': check_idx,
                    'open': opens[check_idx],
                    'close': closes[check_idx],
                    'type': 'Low',
                    'engulfed': False
                })
            
            # 2. === ENGULFING DETECTION LOGIC ===
            
            bullEngulfPlot = False
            bearEngulfPlot = False
            
            # Iterasi swings yang tersimpan (seperti loop array di Pine)
            # Kita loop terbalik (reverse) atau biasa, Pine loop 0 to size-1.
            # Agar efisien, kita bisa filter swings yang sudah kadaluarsa (di luar tolerance), 
            # tapi untuk persis logic Pine, kita loop semua dan cek kondisi if.
            
            for s in swings:
                # Condition: Tolerance
                # if bar_index - idx >= 1 and bar_index - idx <= tolerance
                dist = i - s['idx']
                
                if 1 <= dist <= tolerance:
                    if not s['engulfed']:
                        swOpen = s['open']
                        swClose = s['close']
                        
                        currOpen = opens[i]
                        currClose = closes[i]
                        
                        # Logic Bullish Engulfing
                        # close > open and swClose < swOpen and close > swOpen and open < swClose
                        isBullish = (currClose > currOpen) and \
                                    (swClose < swOpen) and \
                                    (currClose > swOpen) and \
                                    (currOpen < swClose)
                                    
                        # Logic Bearish Engulfing
                        # close < open and swClose > swOpen and close < swOpen and open > swClose
                        isBearish = (currClose < currOpen) and \
                                    (swClose > swOpen) and \
                                    (currClose < swOpen) and \
                                    (currOpen > swClose)
                        
                        if isBullish:
                            bullEngulfPlot = True
                            s['engulfed'] = True # Mark as engulfed (array.set)
                            
                        if isBearish:
                            bearEngulfPlot = True
                            s['engulfed'] = True # Mark as engulfed
            
            # 3. === TIME FILTER ===
            # allowedMinutes >= 50 or allowedMinutes <= 10
            # Pastikan index adalah datetime objects
            current_minute = times[i].minute
            time_ok = (current_minute >= 50) or (current_minute <= 10)
            
            # 4. === STRATEGY ENTRY ===
            if bullEngulfPlot and time_ok:
                df.at[df.index[i], "signal"] = 1 # Buy Signal
            
            elif bearEngulfPlot and time_ok:
                df.at[df.index[i], "signal"] = -1 # Sell Signal
                
        # Return dataframe dengan sinyal, hapus NaN awal akibat lookback
        return df.dropna()