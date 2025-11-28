import pandas as pd
import numpy as np
from .base import Strategy

class MA_ATR_Strategy(Strategy):

    # === DEFAULT PARAMS UNIVERSAL ===
    DEFAULT_PARAMETERS = {
        "ma_fast": 10,
        "ma_slow": 40,
        "atr_period": 14,
        "atr_mult": 1.0,
        "cooldown": 3
    }

    """
    MA crossover + ATR filter, GA-ready.
    Menghasilkan hanya SIGNAL (1 / -1 / 0)
    SL/TP diatur engine.
    """

    def __init__(self, params=None):
        super().__init__(params)

        # merge between DEFAULT_PARAMETERS and user params
        merged = MA_ATR_Strategy.DEFAULT_PARAMETERS.copy()
        if params is not None:
            merged.update(params)

        # assign final parameters
        self.ma_fast     = int(merged["ma_fast"])
        self.ma_slow     = int(merged["ma_slow"])
        self.atr_period  = int(merged["atr_period"])
        self.atr_mult    = float(merged["atr_mult"])
        self.cooldown    = int(merged["cooldown"])

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

        df["signal"] = 0

        # --- Crossover detection ---
        cross_up = (df["ma_fast"] > df["ma_slow"]) & (df["ma_fast"].shift() <= df["ma_slow"].shift())
        cross_down = (df["ma_fast"] < df["ma_slow"]) & (df["ma_fast"].shift() >= df["ma_slow"].shift())

        # ATR Filter
        min_atr = df["atr"].mean() * self.atr_mult
        valid_vol = df["atr"] > min_atr

        last_entry = None

        for i in range(len(df)):
            if last_entry is not None and i - last_entry < self.cooldown:
                continue

            if cross_up.iloc[i] and valid_vol.iloc[i]:
                df.at[df.index[i], "signal"] = 1
                last_entry = i

            elif cross_down.iloc[i] and valid_vol.iloc[i]:
                df.at[df.index[i], "signal"] = -1
                last_entry = i

        return df.dropna()
