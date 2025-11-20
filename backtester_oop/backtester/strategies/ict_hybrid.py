# strategies/ict_hybrid.py

import pandas as pd
import numpy as np
from .base import Strategy


class ICTHybridStrategy(Strategy):
    def __init__(self, params=None):
        super().__init__(params)

        # Hyperparameters
        self.swing_lookback = int(self.params.get("swing_lookback", 5))
        self.body_threshold = float(self.params.get("body_pct", 0.55))
        self.use_time_filter = bool(self.params.get("time_filter", True))

        # Time windows
        self.trade_minutes = [10, 15, 30, 45, 50]

    def detect_fvg(self, df):
        """
        Fair Value Gap candle index:
        bull FVG: low[n-1] > high[n-3]
        bear FVG: high[n-1] < low[n-3]
        """
        df["bullish_fvg"] = df["low"].shift(1) > df["high"].shift(3)
        df["bearish_fvg"] = df["high"].shift(1) < df["low"].shift(3)
        return df

    def detect_liquidity_sweep(self, df):
        df["swing_high"] = df["high"].rolling(self.swing_lookback).max()
        df["swing_low"] = df["low"].rolling(self.swing_lookback).min()

        # price sweeping previous swing points
        df["sweep_high"] = df["high"] > df["swing_high"].shift()
        df["sweep_low"] = df["low"] < df["swing_low"].shift()
        return df

    def detect_bos(self, df):
        """
        BOS after sweep:
        - Buy BOS: close > high of prev candle
        - Sell BOS: close < low of prev candle
        """
        df["bos_up"] = df["close"] > df["high"].shift(1)
        df["bos_down"] = df["close"] < df["low"].shift(1)
        return df

    def displacement_filter(self, df):
        """
        Displacement candle = body > 55% of range
        """
        body = (df["close"] - df["open"]).abs()
        range_ = (df["high"] - df["low"]).replace(0, np.nan)
        df["momentum"] = body / range_
        df["displacement"] = df["momentum"] > self.body_threshold
        return df

    def time_filter(self, df):
        df["minute"] = df.index.minute
        df["valid_time"] = df["minute"].isin(self.trade_minutes)
        return df

    def generate_signals(self, df):
        df = df.copy()

        df = self.detect_fvg(df)
        df = self.detect_liquidity_sweep(df)
        df = self.detect_bos(df)
        df = self.displacement_filter(df)

        if self.use_time_filter:
            df = self.time_filter(df)
        else:
            df["valid_time"] = True

        df["signal"] = 0

        # === BUY CONDITIONS ===
        df.loc[
            (df["sweep_low"]) &            # liquidity taken
            (df["bos_up"]) &               # BOS up confirms direction
            (df["bullish_fvg"]) &          # bullish FVG setup
            (df["displacement"]) &         # displacement candle
            (df["valid_time"]),            # in session
            "signal"
        ] = 1

        # === SELL CONDITIONS ===
        df.loc[
            (df["sweep_high"]) &           # liquidity taken
            (df["bos_down"]) &             # BOS down confirms direction
            (df["bearish_fvg"]) &          # bearish FVG
            (df["displacement"]) &         # displacement candle
            (df["valid_time"]),
            "signal"
        ] = -1

        return df.dropna()
