# engine/backtest_engine.py

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from backtester.strategies.base import Strategy
import config

class BacktestEngine:
    def __init__(self,
                 strategy: Strategy,
                 initial_balance: float = None,
                 pip_point: float = 0.0001):
        self.strategy = strategy
        self.initial_balance = initial_balance or config.INITIAL_BALANCE
        self.pip_point = pip_point
        self.max_trades = config.MAX_OPEN_TRADES

    # =====================================================
    # PIP SIZE PER SYMBOL
    # =====================================================
    def _pip_size(self, symbol: str):
        symbol = symbol.upper()
        if symbol == "XAUUSD":
            return 0.10
        if symbol in ("EURUSD", "GBPUSD"):
            return 0.0001
        if symbol == "GBPJPY":
            return 0.01
        # fallback generic
        return self.pip_point

    # =====================================================
    # RUN BACKTEST
    # =====================================================
    def run(self, df: pd.DataFrame, symbol: str = None) -> (pd.Series, List[Dict[str, Any]]):
        df = self.strategy.generate_signals(df)

        equity = self.initial_balance
        equity_curve = []

        trades = []
        open_trades = []

        # Parse SL/TP ratio from config
        parts = config.SLTP_RATIO.split(":")
        try:
            tp_multiplier = float(parts[1]) / float(parts[0])
        except Exception:
            tp_multiplier = 1.0

        base_pips = config.BASE_PIPS
        # gunakan pip spesifik per symbol jika diberikan
        pip_size = self._pip_size(symbol) if symbol else self.pip_point
        sl_distance_base = base_pips * pip_size

        # =================================================
        # MAIN LOOP OVER CANDLES
        # =================================================
        for idx, row in df.iterrows():

            # --------------------------
            # 1) Manage OPEN TRADES (SL/TP)
            # --------------------------
            remaining_trades = []

            for t in open_trades:
                alive = True

                if t["dir"] == "buy":
                    if row["low"] <= t["sl"]:
                        pnl = (t["sl"] - t["entry"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({"exit": t["sl"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False
                    elif row["high"] >= t["tp"]:
                        pnl = (t["tp"] - t["entry"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({"exit": t["tp"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False

                else:  # sell
                    if row["high"] >= t["sl"]:
                        pnl = (t["entry"] - t["sl"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({"exit": t["sl"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False
                    elif row["low"] <= t["tp"]:
                        pnl = (t["entry"] - t["tp"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({"exit": t["tp"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False

                if alive:
                    remaining_trades.append(t)

            open_trades = remaining_trades

            # --------------------------
            # 2) Open NEW TRADES based on strategy signals
            # --------------------------
            if len(open_trades) < self.max_trades:
                sig = int(row.get("signal", 0))
                if sig != 0:

                    entry = row["close"]

                    # LOT SIZING
                    if config.FIXED_LOT_BACKTEST is not None:
                        size = config.FIXED_LOT_BACKTEST
                    else:
                        # fallback risk-based sizing: equity / SL distance
                        risk_amount = equity * getattr(self.strategy.params, "risk_per_trade", 0.01)
                        sl_dist = sl_distance_base
                        pip_dist = sl_dist / pip_size
                        size = max(config.MIN_LOT_FALLBACK, risk_amount / pip_dist)
                        size = min(size, config.MAX_LOT_CAP)

                    # SL/TP
                    sl_dist = sl_distance_base
                    tp_dist = sl_dist * tp_multiplier

                    if sig == 1:
                        sl = entry - sl_dist
                        tp = entry + tp_dist
                        direction = "buy"
                    else:
                        sl = entry + sl_dist
                        tp = entry - tp_dist
                        direction = "sell"

                    trade = {
                        "entry_time": idx,
                        "dir": direction,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "size": size,
                        "closed": False
                    }
                    open_trades.append(trade)

            equity_curve.append(equity)

        # =================================================
        # Close remaining trades at last price
        # =================================================
        if open_trades:
            last_price = df["close"].iloc[-1]
            last_time = df.index[-1]

            for t in open_trades:
                if not t["closed"]:
                    if t["dir"] == "buy":
                        pnl = (last_price - t["entry"]) * t["size"] / pip_size
                    else:
                        pnl = (t["entry"] - last_price) * t["size"] / pip_size
                    t.update({"exit": last_price, "exit_time": last_time, "pnl": pnl})
                    trades.append(t)
                    equity += pnl

        eq_series = pd.Series(equity_curve, index=df.index[:len(equity_curve)])
        return eq_series, trades
