# strategies/m1_scalper.py
import pandas as pd
import numpy as np
from .base import Strategy

class M1ScalperStrategy(Strategy):
    """
    Scalping M1:
    - Cepat MA crossover
    - ATR rendah untuk sinyal sering
    - Momentum filter untuk entry cepat
    """

    def __init__(self, params=None):
        super().__init__(params)
        # MA crossover cepat
        self.ma_fast = int(self.params.get("ma_fast", 3))
        self.ma_slow = int(self.params.get("ma_slow", 8))

        # ATR cepat, threshold rendah supaya sering entry
        self.atr_period = int(self.params.get("atr_period", 5))
        self.atr_mult = float(self.params.get("atr_mult", 0.3))

        # Filter momentum: perubahan harga candle
        self.mom_period = int(self.params.get("mom_period", 2))
        self.mom_threshold = float(self.params.get("mom_threshold", 0.0))  # bisa disesuaikan

        self.cooldown = int(self.params.get("cooldown", 1))  # scalping, minimal delay

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # --- Moving Averages ---
        df["ma_fast"] = df["close"].rolling(self.ma_fast).mean()
        df["ma_slow"] = df["close"].rolling(self.ma_slow).mean()

        # --- ATR ---
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift()).abs()
        lc = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.atr_period).mean().bfill()

        # --- Momentum ---
        df["mom"] = df["close"].diff(self.mom_period)

        # --- Crossover detection ---
        cross_up = (df["ma_fast"] > df["ma_slow"]) & (df["ma_fast"].shift() <= df["ma_slow"].shift())
        cross_down = (df["ma_fast"] < df["ma_slow"]) & (df["ma_fast"].shift() >= df["ma_slow"].shift())

        # --- ATR & Momentum filter ---
        min_atr = df["atr"].mean() * self.atr_mult
        valid_vol = df["atr"] > min_atr
        valid_mom_up = df["mom"] > self.mom_threshold
        valid_mom_down = df["mom"] < -self.mom_threshold

        df["signal"] = 0
        last_entry = None

        for i in range(len(df)):
            if last_entry is not None and i - last_entry < self.cooldown:
                continue

            # BUY
            if cross_up.iloc[i] and valid_vol.iloc[i] and valid_mom_up.iloc[i]:
                df.at[df.index[i], "signal"] = 1
                last_entry = i

            # SELL
            elif cross_down.iloc[i] and valid_vol.iloc[i] and valid_mom_down.iloc[i]:
                df.at[df.index[i], "signal"] = -1
                last_entry = i

        return df.dropna()
