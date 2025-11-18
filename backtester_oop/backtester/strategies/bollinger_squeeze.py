# backtester/strategies/bollinger_squeeze.py
import pandas as pd
from .base import Strategy

class BollingerSqueeze(Strategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.period = int(self.params.get("period", 20))
        self.mult = float(self.params.get("mult", 2.0))
        self.squeeze_threshold = float(self.params.get("squeeze_threshold", 0.05))

    def generate_signals(self, df):
        df = df.copy()

        df["ma"] = df["close"].rolling(self.period).mean()
        df["std"] = df["close"].rolling(self.period).std()

        df["upper"] = df["ma"] + self.mult * df["std"]
        df["lower"] = df["ma"] - self.mult * df["std"]

        # BandWidth (volatility indicator)
        df["bandwidth"] = (df["upper"] - df["lower"]) / df["ma"]

        df["signal"] = 0

        # BUY breakout
        df.loc[(df["bandwidth"] < self.squeeze_threshold) &
               (df["close"] > df["upper"]), "signal"] = 1

        # SELL breakout
        df.loc[(df["bandwidth"] < self.squeeze_threshold) &
               (df["close"] < df["lower"]), "signal"] = -1

        return df.dropna()
