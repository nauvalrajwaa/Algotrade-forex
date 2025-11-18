# backtester/strategies/rsi_ma_reversal.py
import pandas as pd
import numpy as np
from .base import Strategy

class RSI_MA_Reversal(Strategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.ma_fast = int(self.params.get('ma_fast', 20))
        self.ma_slow = int(self.params.get('ma_slow', 50))
        self.rsi_period = int(self.params.get('rsi_period', 14))
        self.rsi_overbought = float(self.params.get('rsi_overbought', 70))
        self.rsi_oversold = float(self.params.get('rsi_oversold', 30))

    def compute_rsi(self, close, period):
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signals(self, df):
        df = df.copy()

        df["ma_fast"] = df["close"].rolling(self.ma_fast).mean()
        df["ma_slow"] = df["close"].rolling(self.ma_slow).mean()
        df["rsi"] = self.compute_rsi(df["close"], self.rsi_period)

        df["signal"] = 0

        # BUY reversal in uptrend
        df.loc[(df["ma_fast"] > df["ma_slow"]) &
               (df["rsi"] < self.rsi_oversold), "signal"] = 1

        # SELL reversal in downtrend
        df.loc[(df["ma_fast"] < df["ma_slow"]) &
               (df["rsi"] > self.rsi_overbought), "signal"] = -1

        return df.dropna()
