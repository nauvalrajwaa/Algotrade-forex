# strategies/ict_time.py

import pandas as pd
import numpy as np
from .base import Strategy


class ICTAdvancedStrategy(Strategy):
    """
    ICT advanced model:
    - Equal High/Low liquidity pools
    - Killzones (ASD, London, NY)
    - VWAP directional bias
    - FVG + Sweep + BOS confirmation
    """

    def __init__(self, params=None):
        super().__init__(params)

        # Hyperparameters
        self.fvg_shift = int(self.params.get("fvg_shift", 3))
        self.equal_threshold_pct = float(self.params.get("equal_threshold_pct", 0.0003))
        self.use_killzones = bool(self.params.get("use_killzones", True))

    # ================= VWAP ======================
    def compute_vwap(self, df):
        typical = (df["high"] + df["low"] + df["close"]) / 3
        df["cum_vol_price"] = typical * df["volume"]
        df["cum_volume"] = df["volume"].cumsum()
        df["vwap"] = df["cum_vol_price"].cumsum() / df["cum_volume"]
        return df

    # ================= Killzone Detection ======================
    def assign_killzones(self, df):
        df["hour"] = df.index.hour

        df["killzone"] = False
        # Asia session: 0–3 UTC
        df.loc[(df["hour"] >= 0) & (df["hour"] < 3), "killzone"] = True

        # London session: 7–10 UTC
        df.loc[(df["hour"] >= 7) & (df["hour"] < 10), "killzone"] = True

        # New York session: 12–16 UTC
        df.loc[(df["hour"] >= 12) & (df["hour"] < 16), "killzone"] = True

        return df

    # ================= Equal High / Low ======================
    def detect_equal_levels(self, df):
        df["equal_high"] = (
            (df["high"].diff().abs() / df["close"]) < self.equal_threshold_pct
        )
        df["equal_low"] = (
            (df["low"].diff().abs() / df["close"]) < self.equal_threshold_pct
        )
        return df

    # ================= Liquidity Sweeps ======================
    def detect_sweeps(self, df):
        df["sweep_high"] = df["high"] > df["high"].shift(1)
        df["sweep_low"] = df["low"] < df["low"].shift(1)
        return df

    # ================= BOS ======================
    def detect_bos(self, df):
        df["bos_up"] = df["close"] > df["high"].shift(1)
        df["bos_down"] = df["close"] < df["low"].shift(1)
        return df

    # ================= FVG ======================
    def detect_fvg(self, df):
        # Bullish FVG: low[n-1] > high[n-3]
        df["bull_fvg"] = df["low"].shift(1) > df["high"].shift(self.fvg_shift)
        # Bearish FVG: high[n-1] < low[n-3]
        df["bear_fvg"] = df["high"].shift(1) < df["low"].shift(self.fvg_shift)
        return df

    # ================= Signals ======================
    def generate_signals(self, df):
        df = df.copy()

        df = self.compute_vwap(df)
        df = self.assign_killzones(df)
        df = self.detect_equal_levels(df)
        df = self.detect_sweeps(df)
        df = self.detect_bos(df)
        df = self.detect_fvg(df)

        df["signal"] = 0

        # BUY:
        df.loc[
            (
                df["equal_low"] |
                df["sweep_low"]
            ) &                              # liquidity sweep (EQH/EQL atau swing break)
            df["bos_up"] &                    # BOS upwards
            df["bull_fvg"] &                  # FVG bullish
            (df["close"] > df["vwap"]) &      # VWAP bias
            (df["killzone"] | ~self.use_killzones),  # killzone filter optional
            "signal"
        ] = 1

        # SELL:
        df.loc[
            (
                df["equal_high"] |
                df["sweep_high"]
            ) &                              
            df["bos_down"] &                  # BOS downwards
            df["bear_fvg"] &                  # FVG bearish
            (df["close"] < df["vwap"]) &      # VWAP bias
            (df["killzone"] | ~self.use_killzones),
            "signal"
        ] = -1

        return df.dropna()
