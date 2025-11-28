import pandas as pd
import numpy as np
import pandas_ta as ta  # Pastikan library ini terinstall, atau gunakan talib
from .base import Strategy

class Swing_Engulf_EMA_Strategy(Strategy):

    # === DEFAULT PARAMS ===
    DEFAULT_PARAMETERS = {
        "length": 5,            # Swing Length
        "tolerance": 40,        # Engulfing Tolerance (bars)
        "ema_period": 14        # Periode EMA (Asumsi dari variable ema21)
    }

    """
    Swing + Engulfing + EMA Breakout Filter.
    Converted from Pine Script.
    """

    def __init__(self, params=None):
        super().__init__(params)

        merged = Swing_Engulf_EMA_Strategy.DEFAULT_PARAMETERS.copy()
        if params is not None:
            merged.update(params)

        self.length = int(merged["length"])
        self.tolerance = int(merged["tolerance"])
        self.ema_period = int(merged["ema_period"])

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # === 1. PRE-CALCULATION (Vectorized) ===
        # Menghitung EMA 21
        # Menggunakan pandas_ta, jika tidak ada bisa pakai: df['close'].ewm(span=self.ema_period, adjust=False).mean()
        try:
            df["ema21"] = ta.ema(df["close"], length=self.ema_period)
        except AttributeError:
             # Fallback jika pandas_ta tidak terload dengan benar atau user pakai pure pandas
            df["ema21"] = df["close"].ewm(span=self.ema_period, adjust=False).mean()

        # Menghitung Breakout EMA (Crossover/Crossunder)
        # Crossover: Close skrg > EMA skrg AND Close sblm <= EMA sblm
        prev_close = df["close"].shift(1)
        prev_ema = df["ema21"].shift(1)
        
        # Bullish Breakout (ta.crossover)
        bull_breakout = (df["close"] > df["ema21"]) & (prev_close <= prev_ema)
        
        # Bearish Breakout (ta.crossunder)
        bear_breakout = (df["close"] < df["ema21"]) & (prev_close >= prev_ema)

        # Siapkan container untuk loop
        opens = df["open"].values
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        
        # Signal array
        signals = np.zeros(len(df))
        
        # === 2. STATEFUL CALCULATION (Looping) ===
        # Kita butuh loop karena status 'engulfed' pada swing bersifat persisten
        
        swings = [] # List untuk menyimpan dict swing: {'idx', 'open', 'close', 'type', 'engulfed'}
        
        length = self.length
        tolerance = self.tolerance
        n = len(df)
        
        # Mulai loop setelah cukup data
        start_idx = max(length * 2, self.ema_period)
        
        for i in range(start_idx, n):
            
            # --- A. SWING DETECTION ---
            # Pivot dikonfirmasi pada bar ke-'i', tapi kejadiannya di 'i - length'
            pivot_idx = i - length
            
            # Cek Pivot High (Max di range i-2*length s.d i)
            # Window check pivot logic:
            window_start = i - (length * 2)
            window_end = i + 1
            
            local_highs = highs[window_start:window_end]
            local_lows = lows[window_start:window_end]
            
            # Apakah pivot_idx adalah yang tertinggi/terendah di window tersebut?
            is_pivot_high = (highs[pivot_idx] == np.max(local_highs))
            is_pivot_low = (lows[pivot_idx] == np.min(local_lows))
            
            if is_pivot_high:
                swings.append({
                    'idx': pivot_idx,
                    'open': opens[pivot_idx],
                    'close': closes[pivot_idx],
                    'type': 'HH', # Label tidak krusial untuk logic signal
                    'engulfed': False
                })
            
            if is_pivot_low:
                swings.append({
                    'idx': pivot_idx,
                    'open': opens[pivot_idx],
                    'close': closes[pivot_idx],
                    'type': 'LL',
                    'engulfed': False
                })
                
            # --- B. ENGULFING LOGIC ---
            bullEngulfPlot = False
            bearEngulfPlot = False
            
            # Iterasi swings untuk cek engulfing
            # Pine: for i = 0 to array.size - 1
            for s in swings:
                dist = i - s['idx']
                
                # Filter Tolerance & Status Engulfed
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
                            s['engulfed'] = True # Mark as used
                            
                        if isBearish:
                            bearEngulfPlot = True
                            s['engulfed'] = True # Mark as used

            # --- C. FINAL ENTRY TRIGGER ---
            # Menggabungkan Engulfing Flag dengan EMA Breakout yang sudah dihitung di awal
            
            # if bullEngulfPlot and bullBreakout
            if bullEngulfPlot and bull_breakout.iloc[i]:
                signals[i] = 1
                
            # if bearEngulfPlot and bearBreakout
            elif bearEngulfPlot and bear_breakout.iloc[i]:
                signals[i] = -1

        # Masukkan hasil ke DataFrame
        df["signal"] = signals
        
        return df.dropna()