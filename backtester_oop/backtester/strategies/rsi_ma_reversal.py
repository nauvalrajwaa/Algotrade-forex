# strategies/rsi_ma_reversal.py

import pandas as pd
import numpy as np
from .base import Strategy


class RSI_MA_Reversal(Strategy):
    """
    Reversal berbasis MA + RSI, versi stabil dan GA-ready.
    Menghasilkan sinyal reversal terkonfirmasi tanpa SL/TP.
    """

    def __init__(self, params=None):
        super().__init__(params)
        self.ma_fast = int(self.params.get("ma_fast", 10))
        self.ma_slow = int(self.params.get("ma_slow", 50))

        self.rsi_period = int(self.params.get("rsi_period", 14))
        self.rsi_overbought = float(self.params.get("rsi_overbought", 70))
        self.rsi_oversold = float(self.params.get("rsi_oversold", 30))

        self.atr_period = int(self.params.get("atr_period", 14))
        self.atr_mult = float(self.params.get("atr_mult", 0.8))

        self.cooldown = int(self.params.get("cooldown", 5))

    # ==========================
    # RSI Function
    # ==========================
    def compute_rsi(self, close, period):
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    # ==========================
    # ATR compute
    # ==========================
    def compute_atr(self, df, period):
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift()).abs()
        lc = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        return tr.rolling(period).mean().bfill()

    # ==========================
    # SIGNAL GENERATION
    # ==========================
    def generate_signals(self, df):
        df = df.copy()

        # MA
        df["ma_fast"] = df["close"].rolling(self.ma_fast).mean()
        df["ma_slow"] = df["close"].rolling(self.ma_slow).mean()

        # RSI
        df["rsi"] = self.compute_rsi(df["close"], self.rsi_period)

        # ATR filter
        df["atr"] = self.compute_atr(df, self.atr_period)
        atr_threshold = df["atr"].mean() * self.atr_mult
        df["vol_ok"] = df["atr"] > atr_threshold

        df["signal"] = 0

        # ===== Trend Cross =====
        df["up_cross"] = (df["ma_fast"] > df["ma_slow"]) & (df["ma_fast"].shift() <= df["ma_slow"].shift())
        df["down_cross"] = (df["ma_fast"] < df["ma_slow"]) & (df["ma_fast"].shift() >= df["ma_slow"].shift())

        # ===== RSI Reversal =====
        df["rsi_rebound_up"] = (df["rsi"] > self.rsi_oversold) & (df["rsi"].shift() <= self.rsi_oversold)
        df["rsi_rebound_down"] = (df["rsi"] < self.rsi_overbought) & (df["rsi"].shift() >= self.rsi_overbought)

        # ===== Final Logic =====
        last_signal_index = None

        for i in range(len(df)):

            # cooldown
            if last_signal_index is not None and i - last_signal_index < self.cooldown:
                continue

            if df["up_cross"].iloc[i] and df["rsi_rebound_up"].iloc[i] and df["vol_ok"].iloc[i]:
                df.at[df.index[i], "signal"] = 1
                last_signal_index = i

            elif df["down_cross"].iloc[i] and df["rsi_rebound_down"].iloc[i] and df["vol_ok"].iloc[i]:
                df.at[df.index[i], "signal"] = -1
                last_signal_index = i

        return df.dropna()
