# backtester/data/fetcher.py

import pandas as pd
import os
from typing import Optional

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except Exception:
    mt5 = None
    MT5_AVAILABLE = False


class DataFetcher:
    """
    DataFetcher mendukung:
      - source='mt5' → fetch dari MetaTrader5
      - source='csv' → membaca CSV model MT5:
           DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICKVOL,VOL,SPREAD
    """

    def __init__(self, mt5_path: Optional[str] = None):
        self.mt5_path = mt5_path

    # ======================================================
    #  FETCH MT5
    # ======================================================
    def fetch_mt5(self, symbol: str, timeframe, bars: int = 5000) -> pd.DataFrame:
        if not MT5_AVAILABLE:
            raise RuntimeError("MetaTrader5 python package not available.")

        # Initialize MT5
        ok = mt5.initialize(self.mt5_path) if self.mt5_path else mt5.initialize()
        if not ok:
            raise RuntimeError("MT5 initialize() failed.")

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        mt5.shutdown()

        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No MT5 data for {symbol}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time")
        return df

    # ======================================================
    #  FETCH CSV (UPDATED FINAL)
    # ======================================================
    def fetch_csv(self, path: str) -> pd.DataFrame:
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        df = pd.read_csv(path)

        # Normalisasi kolom → lowercase
        df.columns = [c.lower() for c in df.columns]

        # =============================
        # CASE 1 — MT5 format (date + time)
        # =============================
        if "date" in df.columns and "time" in df.columns:
            try:
                df["datetime"] = pd.to_datetime(
                    df["date"] + " " + df["time"],
                    format="%Y.%m.%d %H:%M:%S",
                    errors="raise"
                )
            except Exception as e:
                raise ValueError(f"Failed parsing MT5 DATE+TIME: {e}")

        # =============================
        # CASE 2 — Hanya satu kolom datetime (time)
        # =============================
        elif "time" in df.columns:
            try:
                df["datetime"] = pd.to_datetime(df["time"], errors="raise")
            except Exception as e:
                raise ValueError(f"Failed parsing TIME as datetime: {e}")

        else:
            raise ValueError(
                "CSV must contain either:\n"
                "  - 'date' + 'time' columns (MT5 format)\n"
                "  - OR a 'time' column with full datetime"
            )

        # Set datetime sebagai index
        df = df.set_index("datetime")

        # Validasi kolom OHLC wajib
        required = ["open", "high", "low", "close"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"CSV missing required column '{col}'")

        return df
