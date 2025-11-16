import pandas as pd
from ...data.indicators import Indicators

class MovingAverageStrategy(BaseStrategy):
    def __init__(self, ma_fast, ma_slow, atr_mul):
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.atr_mul = atr_mul

    def generate_signals(self, df):
        df = df.copy()
        df["ma_fast"] = df["close"].rolling(self.ma_fast).mean()
        df["ma_slow"] = df["close"].rolling(self.ma_slow).mean()
        df["atr"] = Indicators.atr(df, 14)

        df["signal"] = 0
        df.loc[df["ma_fast"] > df["ma_slow"], "signal"] = 1
        df.loc[df["ma_fast"] < df["ma_slow"], "signal"] = -1
        return df.dropna()
