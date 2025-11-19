# Backtester OOP

## Instalasi
1. Buat virtualenv, kemudian:
   pip install -r requirements.txt

2. Jika ingin pakai MT5 (Windows):
   - Install MetaTrader 5 app dan Python package MetaTrader5.
   - Set `MT5_PATH` di `config.py` ke path terminal64.exe.

## Struktur
backtester_oop/
├─ README.md
├─ requirements.txt
├─ config.py
├─ run.py
├─ backtester/
│  ├─ __init__.py
│  ├─ data/
│  │  ├─ __init__.py
│  │  ├─ fetcher.py
│  ├─ strategies/
│  │  ├─ __init__.py
│  │  ├─ base.py
│  │  ├─ ma_atr.py
│  ├─ engine/
│  │  ├─ __init__.py
│  │  ├─ backtest.py
│  ├─ optimizer/
│  │  ├─ __init__.py
│  │  ├─ metrics.py
│  ├─ utils.py

## Contoh menjalankan dengan CSV
Pastikan CSV Anda punya kolom: time, open, high, low, close
Contoh:
time,open,high,low,close
2025-01-01 00:00,1800.0,1802.0,1799.0,1801.5
...

Jalankan:
python run.py --source csv --csv path/to/data.csv

## Contoh menjalankan dengan MT5 (Windows)
python run.py --source mt5 --symbol XAUUSD --bars 5000

## Pengembangan
- `backtester/strategies/` : tambahkan strategi lain (inherit Strategy)
- `backtester/engine/backtest.py` : bisa diperluas event-driven, multi-symbol, komisi, slippage
- `backtester/optimizer/` : tambahkan GA, walk-forward, atau bayesian optimizer
