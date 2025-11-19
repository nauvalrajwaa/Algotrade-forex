# backtester/strategies/ma_atr_live.py
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


class MA_ATR_LiveStrategy(Strategy):
    """
    Live variant of MA+ATR strategy.
    Exposes decide(df) returning dict {'signal': 1/-1/0, 'extra': {...}}
    """

    def __init__(self, params=None):
        super().__init__(params)
        self.ma_fast = int(self.params.get('ma_fast', 10))
        self.ma_slow = int(self.params.get('ma_slow', 40))
        self.atr_n = int(self.params.get('atr_n', 14))
        self.atr_mul = float(self.params.get('atr_mul', 1.5))

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['ma_fast'] = df['close'].rolling(self.ma_fast).mean()
        df['ma_slow'] = df['close'].rolling(self.ma_slow).mean()
        df['atr'] = atr_series(df, self.atr_n)
        return df

    def decide(self, df: pd.DataFrame) -> dict:
        """
        Decide based on last row of df.
        """
        df2 = self.compute_indicators(df)
        last = df2.iloc[-1]
        if last['ma_fast'] > last['ma_slow']:
            sig = 1
        elif last['ma_fast'] < last['ma_slow']:
            sig = -1
        else:
            sig = 0

        return {"signal": int(sig),
                "extra": {"atr": float(last.get("atr", np.nan)),
                          "ma_fast": float(last.get("ma_fast", np.nan)),
                          "ma_slow": float(last.get("ma_slow", np.nan))}}
