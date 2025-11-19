# config.py
"""
Global configuration for Backtester + LiveEngine Framework.
"""

# ============================================================
# MetaTrader 5 Settings
# ============================================================

# Path menuju terminal MT5
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"

# Default symbol list (untuk scanner/backtest)
SYMBOLS = ["XAUUSD"]

# Timeframe (untuk backtest dan default live)
# Untuk live, user biasanya override via CLI
TIMEFRAME = None  
BARS = 5000


# ============================================================
# Backtest Defaults
# ============================================================
INITIAL_BALANCE = 10000.0
MAX_TRADES = 1
OPTIMIZER = "ga_mc"  # none / ga / mc / ga_mc

SEARCH_SPACE = {
    "ma_fast": (5, 20),
    "ma_slow": (21, 100),
    "atr_mul": (1.0, 3.0),
    "risk_per_trade": (0.005, 0.03),
}


# ============================================================
# Optimization – Genetic Algorithm
# ============================================================
GA_CONFIG = {
    "population_size": 20,
    "generations": 3,
    "mutation_rate": 0.12,
    "crossover_rate": 0.7,
    "elitism": 2,
}


# ============================================================
# Optimization – Monte Carlo / Simulated Annealing
# ============================================================
MC_CONFIG = {
    "iterations": 100,
    "temperature": 1.0,
    "cooling_rate": 0.999,
}


# ============================================================
# LIVE-BACKTEST ENGINE CONFIG
# ============================================================

# --- SL/TP Ratio -------------------------------------------------
# Pilihan: "1:1", "1:2", "1:3"
SLTP_RATIO = "1:2"

# "1" dalam SL/TP = 30 pips (sesuai permintaan user)
BASE_PIPS = 30  


# --- Lot Sizing ---------------------------------------------------
# FIXED lot (jika ingin lot tetap)
# contoh: 0.01 === 0.01 lot setiap trade
# set ke None untuk dynamic risk-based lot sizing
FIXED_LOT = 0.5  

# fallback broker caps
MAX_LOT_CAP = 100.0  
MIN_LOT_FALLBACK = 0.01


# --- Max Open Trades ----------------------------------------------
MAX_OPEN_TRADES = 1  # untuk live trading per symbol


# ============================================================
# Logging / Trade Recording
# ============================================================
LOG_FILE = "logs/live_default.log"

# CSV log per trade (open/close/pnl/sl/tp dll)
TRADE_CSV = "logs/trades.csv"

