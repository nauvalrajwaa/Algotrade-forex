## 📁 Datasets

### 1. Source
The dataset is obtained from MT5 (MetaTrader 5) using fetch request bars, then saved in CSV format for use in backtesting and analysis pipelines.

---

### 2. How to Download MT5 Bars

```python
import MetaTrader5 as mt5
import pandas as pd

symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M5
bars = 200000

mt5.initialize()

rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
df = pd.DataFrame(rates)

df['time'] = pd.to_datetime(df['time'], unit='s')
df.set_index('time', inplace=True)

df.to_csv("datasets/XAUUSD_M5.csv")
print("Saved:", len(df), "rows")
````

---

### 3. Dataset Structure

| Column      | Description                |
| ----------- | -------------------------- |
| time        | Timestamp (UTC)            |
| open        | Open price                 |
| high        | High price                 |
| low         | Low price                  |
| close       | Close price                |
| tick_volume | Tick volume                |
| spread      | Spread at that bar         |
| real_volume | Real volume (if available) |

---

### 4. Location

```
/datasets/
    ├── SYMBOL_TIMEFRAME.csv
    ├── XAUUSD_M5.csv
    ├── EURUSD_H1.csv
    └── ...
```

---

### 5. Notes

* If MT5 limits the number of bars (`limited by chart settings`), increase **Max bars in chart** and **Max bars in history** via MT5 → Tools → Options → Charts.