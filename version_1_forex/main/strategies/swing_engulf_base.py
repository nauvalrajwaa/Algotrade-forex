import pandas as pd
import numpy as np
from .base import Strategy

class Swing_Engulf_Strategy_Base(Strategy):

    # === DEFAULT PARAMS ===
    DEFAULT_PARAMETERS = {
        "length": 5,          # Swing Length (Pivot lookback/forward)
        "tolerance": 40,      # Engulfing Tolerance (bars duration)
        # Parameter SL/TP diabaikan di sini karena dihandle oleh backtest_engine
    }

    """
    Swing + Engulfing Detector Strategy (Pure Price Action).
    Converted from Pine Script.
    Note: Title in Pine says EMA21, but the provided code had NO EMA logic.
    This conversion follows the provided code strictly.
    """

    def __init__(self, params=None):
        super().__init__(params)

        # Merge defaults
        merged = Swing_Engulf_Strategy_Base.DEFAULT_PARAMETERS.copy()
        if params is not None:
            merged.update(params)

        self.length = int(merged["length"])
        self.tolerance = int(merged["tolerance"])

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Copy df untuk keamanan data
        df = df.copy()
        
        # Inisialisasi kolom signal
        df["signal"] = 0
        
        # === PREPARASI DATA (Vector to Numpy) ===
        # Menggunakan numpy array jauh lebih cepat daripada looping pandas df.iloc
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        
        n = len(df)
        length = self.length
        tolerance = self.tolerance
        
        # Array untuk menyimpan hasil sinyal sementara
        signals = np.zeros(n)
        
        # === STORAGE (Memori Swing) ===
        # List of dictionaries untuk meniru 'var array' di Pine Script
        swings = [] 
        
        # Mulai loop
        # Kita butuh minimal (length * 2) data untuk konfirmasi pivot pertama
        start_idx = length * 2
        
        for i in range(start_idx, n):
            
            # ---------------------------------------
            # 1. SWING DETECTION (PIVOT LOGIC)
            # ---------------------------------------
            # Pivot terjadi di masa lalu (i - length), tapi baru dikonfirmasi sekarang (i)
            check_idx = i - length
            
            # Define window range: [check_idx - length] s/d [check_idx + length]
            # Di python slicing, batas kanan eksklusif, jadi +1
            # Tapi karena kita di index 'i', dan i = check_idx + length,
            # maka window kita adalah dari (i - 2*length) sampai (i + 1)
            
            w_start = i - (length * 2)
            w_end = i + 1 
            
            current_highs = highs[w_start : w_end]
            current_lows = lows[w_start : w_end]
            
            # Cek Pivot High
            is_ph = (highs[check_idx] == np.max(current_highs))
            # Cek Pivot Low
            is_pl = (lows[check_idx] == np.min(current_lows))
            
            if is_ph:
                swings.append({
                    'idx': check_idx,
                    'open': opens[check_idx],
                    'close': closes[check_idx],
                    'type': 'HH', # Tipe HH/LH tidak mempengaruhi logic entry di script ini
                    'engulfed': False
                })
                
            if is_pl:
                swings.append({
                    'idx': check_idx,
                    'open': opens[check_idx],
                    'close': closes[check_idx],
                    'type': 'LL', 
                    'engulfed': False
                })

            # ---------------------------------------
            # 2. ENGULFING DETECTION
            # ---------------------------------------
            bullEngulfPlot = False
            bearEngulfPlot = False
            
            # Iterasi swings yang tersimpan (seperti loop array di Pine)
            for s in swings:
                
                # Hitung jarak candle sekarang ke candle swing
                dist = i - s['idx']
                
                # Logic: if bar_index - idx >= 1 and bar_index - idx <= tolerance
                if 1 <= dist <= tolerance:
                    
                    # Cek apakah swing ini sudah pernah dimakan?
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
                            s['engulfed'] = True # Update status (array.set)
                            
                        if isBearish:
                            bearEngulfPlot = True
                            s['engulfed'] = True # Update status (array.set)

            # ---------------------------------------
            # 3. SET SIGNAL
            # ---------------------------------------
            if bullEngulfPlot:
                signals[i] = 1
            elif bearEngulfPlot:
                signals[i] = -1

        # Masukkan array signals kembali ke DataFrame
        df["signal"] = signals
        
        return df.dropna()