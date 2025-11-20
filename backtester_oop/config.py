# backtester_oop/config.py

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
OPTIMIZER = "ga"

# ------------------------------------------------------------
# DEFAULT SEARCH SPACE (fallback jika strategi tidak punya)
# ------------------------------------------------------------
SEARCH_SPACE_DEFAULT = {
    "ma_fast": (5, 20),
    "ma_slow": (21, 100),
    "atr_mul": (1.0, 3.0),
    "risk_per_trade": (0.005, 0.03),
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

    "rsi_ma": {
        # --- Moving Average Trend Filter ---
        "ma_fast": (5, 30),
        "ma_slow": (20, 200),

        # --- RSI Reversal ---
        "rsi_period": (5, 30),
        "rsi_overbought": (60, 90),
        "rsi_oversold": (10, 40),

        # --- ATR Volatility Filter ---
        "atr_period": (5, 30),
        "atr_mult": (0.5, 1.5),   # 0.8 default → paling stabil

        # --- Anti-Whipsaw ---
        "cooldown": (1, 20),
    },
    
    "ict_hybrid": {
    # --- Liquidity Sweep Sensitivity ---
        "swing_lookback": (3, 15), # Swing lookback kecil = lebih agresif deteksi sweep

    # --- Displacement / Momentum Filter ---
        "body_pct": (0.40, 0.80), # Semakin tinggi → hanya ambil candle dengan body besar

    # --- Optional Time Filter ---
        "time_filter": (0, 1),  # True → hanya ambil sinyal pada menit tertentu (ICT killzone style), False → sinyal aktif sepanjang hari

    # --- Optional Time Window Evolution ---
        "time_window_choice": (1, 5),  # jumlah item dari daftar minute preset, GA memilih "berapa banyak" menit entry yang efektif (opsional), ex: 10,15,30,45,50 → default
    },

    "ict_time": {
        # --- FVG Shift ---
        "fvg_shift": (2, 5),                   # candle lag untuk Fair Value Gap, default stabil 3
        
        # --- Equal High/Low Threshold ---
        "equal_threshold_pct": (0.0001, 0.001), # % harga untuk deteksi level EQH/EQL, default 0.0003
        
        # --- Killzone Usage ---
        "use_killzones": (0, 1),               # 0=False, 1=True → aktifkan/disable sesi trading
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

    "rsi_ma": {
        "population_size": 30,
        "generations": 8,
        "mutation_rate": 0.15,
        "crossover_rate": 0.6,
        "elitism": 3,
    },

    "ict_hybrid": {
        "population_size": 40,
        "generations": 7,
        "mutation_rate": 0.20,
        "crossover_rate": 0.5,
        "elitism": 4,
    },

    "ict_time": {
        "population_size": 35,
        "generations": 6,
        "mutation_rate": 0.18,
        "crossover_rate": 0.55,
        "elitism": 4,
    }
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

SLTP_RATIO = "1:2"   # 1 unit = 30 pips
BASE_PIPS = 30

# Fixed lot (set None untuk dynamic risk)
FIXED_LOT = 0.5
MAX_LOT_CAP = 100.0
MIN_LOT_FALLBACK = 0.01

MAX_OPEN_TRADES = 1


# ============================================================
# Logging / Trade Recording
# ============================================================
LOG_FILE = "logs/live_default.log"
TRADE_CSV = "logs/trades.csv"
