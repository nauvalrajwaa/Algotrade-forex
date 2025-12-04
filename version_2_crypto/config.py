# backtester_oop/config.py

import os
from dotenv import load_dotenv

# Load environment variables (.env file)
load_dotenv()

"""
Global configuration for Crypto Engine (Binance Futures).
"""

# ============================================================
# BINANCE CONNECTIVITY
# ============================================================
API_KEY_BINANCE = os.getenv("API_KEY_BINANCE", "")
SECRET_KEY_BINANCE = os.getenv("SECRET_KEY_BINANCE", "")


# ============================================================
# CRYPTO TRADING LOGIC (POSITION SIZING & RISK)
# ============================================================

# 1. ENTRY SIZING
# Persentase dari Total Balance yang digunakan sebagai MARGIN per trade.
# Contoh: 0.05 = 5%. Jika Saldo $1000, margin trade = $50.
ENTRY_EQUITY_PERCENT = 0.05 

# 2. LEVERAGE
# Target leverage yang akan diset ke Binance Futures.
TARGET_LEVERAGE = 30

# 3. STOP LOSS SETTINGS (PERCENTAGE BASED)
# Jarak SL dalam persentase harga.
# 0.02 = SL ditaruh sejauh 2% dari harga entry.
SL_PERCENTAGE = 0.02

# 4. TAKE PROFIT RATIO
# Format "SL:TP". "1:2" berarti TP jaraknya 2x lipat dari jarak SL.
SLTP_RATIO = "1:2"

# 5. TRAILING STOP (PERCENTAGE BASED)
# Menggeser SL jika harga bergerak profit sebesar sekian persen.
# 0.01 = 1%. Set 0 untuk menonaktifkan.
TRAILING_STOP_PERCENT = 0.01

# 6. SAFETY
MAX_OPEN_TRADES = 3  # Maksimal posisi terbuka bersamaan

# 7. BEP
# Berapa persen perjalanan ke TP untuk menggeser SL ke BEP?
# 0.5 = 50%. Jika TP 100 poin, maka saat profit 50 poin, SL geser ke Entry.
BEP_TRIGGER_PCT = 0.5

# 8. REFRESH HOURS
# Waktu refresh scanner otomatis (dalam jam)
REFRESH_HOURS = 4

# ============================================================
# MARKET SCANNER CONFIGURATION
# ============================================================

# 1. MINIMUM VOLUME (USDT)
# Koin dengan volume 24 jam di bawah angka ini akan dibuang.
# Scalping butuh likuiditas tinggi (min 5-10 Juta). Swing bisa lebih rendah.
SCANNER_MIN_VOLUME = 5000000.0  # 5 Juta USDT

# 2. SORTING MODE
# 'activity'   : Fokus Scalping (M1-M5). Cari yang ramai transaksi.
# 'volatility' : Fokus Swing (H1). Cari yang % naik/turun tinggi.
# 'hybrid'     : TERBAIK. Kombinasi Ramai + Volatil. Cari koin "Sweet Spot".
SCANNER_SORT_MODE = 'hybrid'

# 3. BLACKLIST SYMBOLS
# Daftar koin yang HARAM untuk ditradingkan (misal Stablecoin atau koin bermasalah).
# Format list string uppercase tanpa slash.
SCANNER_BLACKLIST = ["USDCUSDT", "TUSDUSDT", "FDUSDUSDT", "USDPUSDT"]

# 4. MINIMUM PRICE CHANGE (%) - Optional
# Hanya ambil koin yang minimal bergerak sekian persen (agar tidak dapat koin mati).
# 1.0 berarti minimal naik/turun 1% dalam 24 jam.
SCANNER_MIN_CHANGE = 1.5

# ============================================================
# BACKTEST DEFAULTS (Simulation)
# ============================================================
INITIAL_BALANCE = 1000.0  # Default saldo simulasi paper trading
MAX_TRADES = 1            # Limit trade simultaneous untuk backtester sederhana

# Optimizer Mode: none / ga / mc
OPTIMIZER = "none"

# ============================================================
# STRATEGY SEARCH SPACES (Untuk Optimization / Backtest)
# ============================================================

# Default fallback
SEARCH_SPACE_DEFAULT = {
    "ma_fast": (5, 20),
    "ma_slow": (21, 100),
    "atr_mult": (1.0, 3.0),
}

# Per Strategy Parameters
SEARCH_SPACE_BY_STRATEGY = {
    "ma_atr": {
        "ma_fast": (5, 30),
        "ma_slow": (20, 200),
        "atr_period": (5, 30),
        "atr_mult": (0.5, 3.0),
        "cooldown": (1, 15)
    },
    
    "swing_engulf_base": {
        "length": (3, 10),      # Swing length
        "tolerance": (10, 50)   # Tolerance dalam satuan tick/poin relatif
    }, 

    "swing_engulf": {
        "length": (3, 10),
        "tolerance": (10, 50)
    },

    "swing_engulf_ema": {
        "length": (2, 15),
        "tolerance": (5, 60),
        "ema_period": (10, 50)
    }
}


# ============================================================
# GENETIC ALGORITHM (GA) CONFIG
# ============================================================
GA_CONFIG_DEFAULT = {
    "population_size": 20,
    "generations": 3,
    "mutation_rate": 0.12,
    "crossover_rate": 0.7,
    "elitism": 2,
}

GA_CONFIG_BY_STRATEGY = {
    "ma_atr": {
        "population_size": 25,
        "generations": 6,
        "mutation_rate": 0.10,
        "crossover_rate": 0.7,
        "elitism": 2,
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
# MONTE CARLO CONFIG
# ============================================================
MC_CONFIG = {
    "iterations": 100,
    "temperature": 1.0,
    "cooling_rate": 0.999,
}


# ============================================================
# INTEGRATIONS (TELEGRAM & GOOGLE SHEETS)
# ============================================================

# --- TELEGRAM ---
USE_TELEGRAM = True
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- GOOGLE SHEETS ---
USE_GSHEET = True
GSHEET_CREDENTIAL_FILE = os.getenv("GSHEET_CREDENTIAL_FILE", "credentials.json")
GSHEET_ID = os.getenv("GSHEET_ID", "")


# ============================================================
# LOGGING PATHS
# ============================================================
LOG_FILE = "logs/live/live_crypto.log"
LOG_FILE_SCREENING = "logs/screening/screening_crypto.log"
TRADE_CSV = "logs/live/trades_crypto.csv"
TRADE_CSV_SCREENING = "logs/screening/trades_screening_crypto.csv"