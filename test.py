import MetaTrader5 as mt5

path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

if not mt5.initialize(path):
    print("Initialize failed, error:", mt5.last_error())
else:
    print("MT5 connected!")
    mt5.shutdown()

import MetaTrader5 as mt5
import pandas as pd

path = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

mt5.initialize(path)

symbol = "EURUSD"
timeframe = mt5.TIMEFRAME_H1
bars = 5000  # jumlah candle

rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
mt5.shutdown()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

print(df.head())
print(df.tail())
