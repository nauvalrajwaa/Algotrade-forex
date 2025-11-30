# backtester_oop/config.py
import os
from dotenv import load_dotenv

# Load file .env
load_dotenv()

"""
Global configuration for Backtester + LiveEngine Framework.
"""

# ============================================================
# MetaTrader 5 Settings
# ============================================================
MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
SYMBOLS = ["XAUUSD"]
TIMEFRAME = None
BARS = 5000


# ============================================================
# Backtest Defaults
# ============================================================
INITIAL_BALANCE = 10000.0
MAX_TRADES = 1

# none / ga / mc / ga_mc
OPTIMIZER = "none"

# ------------------------------------------------------------
# DEFAULT SEARCH SPACE (fallback jika strategi tidak punya)
# ------------------------------------------------------------
SEARCH_SPACE_DEFAULT = {
    "ma_fast": (5, 20),
    "ma_slow": (21, 100),
    "atr_mul": (1.0, 3.0),
}

# ------------------------------------------------------------
# SEARCH SPACE PER STRATEGI
# (Akan dipanggil di run_backtest.py sesuai strategy_name)
# ------------------------------------------------------------
SEARCH_SPACE_BY_STRATEGY = {
    "ma_atr": {
        # --- Moving Average Crossover ---
        # Fast MA untuk deteksi perubahan tren cepat
        "ma_fast": (5, 30),
        # Slow MA untuk tren mayor / filter noise
        "ma_slow": (20, 200),

        # --- ATR Volatility Filter ---
        # ATR untuk mengukur volatilitas dinamis
        "atr_period": (5, 30),
        # Threshold volatilitas → entry hanya ketika ATR cukup besar
        "atr_mult": (0.5, 3.0),

        # --- Anti-Flip / Anti-Whipsaw ---
        # Cooldown antar sinyal supaya tidak flip-flop
        "cooldown": (1, 15)
    },
    
    "swing_engulf_base": {
        # Swing length (jumlah bar kiri-kanan untuk pivot)
        "length": (5, 10),

       # Tolerance jarak swing-index → rentang valid engulfing
        "tolerance": (10, 30)
    }, 

    "swing_engulf": {
        # Swing length (jumlah bar kiri-kanan untuk pivot)
        "length": (5, 10),

       # Tolerance jarak swing-index → rentang valid engulfing
        "tolerance": (10, 30)
    },

    "swing_engulf_ema": {
        # Sama seperti DEFAULT_PARAMETERS
        "length": (2, 15),          # Swing Length
        "tolerance": (5, 60),       # Bar tolerance
        "ema_period": (10, 50)      # EMA filter
    }
}


# ============================================================
# Optimization – Genetic Algorithm
# ============================================================
GA_CONFIG_DEFAULT = {
    "population_size": 20,
    "generations": 3,
    "mutation_rate": 0.12,
    "crossover_rate": 0.7,
    "elitism": 2,
}

# GA CONFIG PER STRATEGI
GA_CONFIG_BY_STRATEGY = {
    "ma_atr": {
        "population_size": 25,
        "generations": 6,
        "mutation_rate": 0.10,
        "crossover_rate": 0.7,
        "elitism": 2,
    },

    "swing_engulf": {
        "population_size": 35,
        "generations": 3,
        "mutation_rate": 0.18,
        "crossover_rate": 0.55,
        "elitism": 4,
    },
    
    "swing_engulf": {
        "population_size": 35,
        "generations": 3,
        "mutation_rate": 0.18,
        "crossover_rate": 0.55,
        "elitism": 4,
    },
    
    "swing_engulf_base": {
        "population_size": 35,
        "generations": 3,
        "mutation_rate": 0.18,
        "crossover_rate": 0.55,
        "elitism": 4,
    },
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

SLTP_RATIO = "1:1"
BASE_PIPS = 60
TRAILING_STOP_PIP = 20

FIXED_LOT_BACKTEST = 0.5

FIXED_LOT_LIVE = 0.5

FIXED_LOT_XAUUSD = 0.5
FIXED_LOT_EURUSD = 1 
FIXED_LOT_GBPUSD = 1
FIXED_LOT_GBPJPY = 1

MAX_LOT_CAP = 100.0
MIN_LOT_FALLBACK = 0.01

MAX_OPEN_TRADES = 2


# ============================================================
# Logging / Trade Recording
# ============================================================
LOG_FILE = "logs/live/live_default.log"
LOG_FILE_SCREENING = "logs/screening/screening.log"
TRADE_CSV = "logs/live/trades.csv"
TRADE_CSV_SCREENING = "logs/screening/trades_screening.csv"

# ============================================================
# GOOGLE SHEETS CONFIG
# ============================================================
USE_GSHEET = True
# Ambil nama file dari env, defaultnya 'credentials.json'
GSHEET_CREDENTIAL_FILE = os.getenv("GSHEET_CREDENTIAL_FILE", "credentials.json")
GSHEET_ID = os.getenv("GSHEET_ID")

# ============================================================
# TELEGRAM CONFIG
# ============================================================
# Jika tidak ada di .env, return string kosong atau error
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Chat ID biasanya tidak terlalu rahasia, tapi boleh dimasukkan ke env juga