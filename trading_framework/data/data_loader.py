import MetaTrader5 as mt5
import pandas as pd

class DataLoader:
    def __init__(self, mt5_path):
        self.mt5_path = mt5_path

    def fetch(self, symbol, timeframe, bars):
        if not mt5.initialize(self.mt5_path):
            raise RuntimeError("MT5 initialize failed")
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        mt5.shutdown()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df
