# backtester/strategies/ma_atr.py
import pandas as pd
import numpy as np
from .base import Strategy

def atr_series(df, n=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    return atr.bfill()

class MA_ATR_Strategy(Strategy):
    """
    Implements MA crossover + ATR-based SL/TP sizing logic.
    It produces 'signal' column where 1=buy, -1=sell, 0=flat.
    """
    def __init__(self, params=None):
        super().__init__(params)
        # defaults
        self.ma_fast = int(self.params.get('ma_fast', 10))
        self.ma_slow = int(self.params.get('ma_slow', 40))
        self.atr_n = int(self.params.get('atr_n', 14))
        self.atr_mul = float(self.params.get('atr_mul', 1.5))

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ma_fast'] = df['close'].rolling(self.ma_fast).mean()
        df['ma_slow'] = df['close'].rolling(self.ma_slow).mean()
        df['atr'] = atr_series(df, self.atr_n)
        df['signal'] = 0
        df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
        df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1
        df = df.dropna()
        return df
