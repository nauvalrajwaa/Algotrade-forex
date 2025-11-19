# config.py
"""
Global configuration for Backtester OOP Framework.
"""

# -----------------------------
# MetaTrader 5 Settings
# -----------------------------
mt5 = None   # Hint only. MT5 import dilakukan di fetcher jika diperlukan.

MT5_PATH = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
SYMBOLS = ["XAUUSD"]

# Contoh: gunakan mt5.TIMEFRAME_M15 di run.py saat fetch MT5
TIMEFRAME = None  
BARS = 5000


# -----------------------------
# Backtest Defaults
# -----------------------------
INITIAL_BALANCE = 10000.0
RISK_PER_TRADE = 0.01
MAX_TRADES = 1


# -----------------------------
# Optimization Settings
# -----------------------------
# Pilih optimizer yang digunakan:
#   "none" -> hanya backtest biasa
#   "ga"   -> Genetic Algorithm
#   "mc"   -> Monte Carlo / Simulated Annealing
#   "ga_mc"   -> Genetic Algorith + Monte Carlo / Simulated Annealing

OPTIMIZER = "ga_mc"


# Search space untuk parameter strategi MA + ATR
SEARCH_SPACE = {
    "ma_fast": (5, 20),
    "ma_slow": (21, 100),
    "atr_mul": (1.0, 3.0),
    "risk_per_trade": (0.005, 0.03),
}


# -----------------------------
# GA (Genetic Algorithm) Settings
# -----------------------------
GA_CONFIG = {
    "population_size": 20,
    "generations": 3,
    "mutation_rate": 0.12,
    "crossover_rate": 0.7,
    "elitism": 2,
}


# -----------------------------
# Monte Carlo (Simulated Annealing)
# -----------------------------
MC_CONFIG = {
    "iterations": 100,
    "temperature": 1.0,
    "cooling_rate": 0.999,
}
