# engine/backtest_engine.py

import pandas as pd
import numpy as np
import os
import datetime
from typing import List, Dict, Any
from main.strategies.base import Strategy
import config

class BacktestEngine:
    def __init__(self,
                 strategy: Strategy,
                 initial_balance: float = None,
                 pip_point: float = 0.0001,
                 symbol: str = None):

        self.strategy = strategy
        self.initial_balance = initial_balance or config.INITIAL_BALANCE
        self.pip_point = pip_point

        # NEW
        self.symbol = symbol.upper() if symbol else None

        self.max_trades = config.MAX_OPEN_TRADES


        # ===============================
        # Setup logging file
        # ===============================
        os.makedirs("logs/backtest/", exist_ok=True)

        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        strat_name = self.strategy.__class__.__name__

        self.log_path = f"logs//backtest/{strat_name}_{stamp}.csv"

        with open(self.log_path, "w") as f:
            f.write("trade_id,time,type,entry_price,exit_price,sl,tp,lot,pnl,reason\n")

        self.trade_counter = 0

    # -------------------------------------------------------------------
    def _log(self, t: dict):
        """Append 1 row to CSV log."""
        with open(self.log_path, "a") as f:
            f.write(",".join([
                str(t.get("id", "")),
                str(t.get("time", "")),
                str(t.get("type", "")),
                str(t.get("entry", "")),
                str(t.get("exit", "")),
                str(t.get("sl", "")),
                str(t.get("tp", "")),
                str(t.get("size", "")),
                str(t.get("pnl", "")),
                str(t.get("reason", "")),
            ]) + "\n")

    # =====================================================
    # PIP SIZE PER SYMBOL
    # =====================================================
    def _pip_size(self, symbol: str):
        symbol = symbol.upper()
        if symbol == "XAUUSD":
            return 0.1
        if symbol in ("EURUSD", "GBPUSD"):
            return 0.0001
        if symbol == "GBPJPY":
            return 0.01
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

        parts = config.SLTP_RATIO.split(":")
        try:
            tp_multiplier = float(parts[1]) / float(parts[0])
        except Exception:
            tp_multiplier = 1.0

        base_pips = config.BASE_PIPS
        pip_size = self._pip_size(self.symbol) if self.symbol else self.pip_point
        sl_distance_base = base_pips * pip_size

        # =================================================
        # LOOP CANDLE
        # =================================================
        for idx, row in df.iterrows():

            # -------------------------------------------
            # 1) Check OPEN TRADES for SL/TP
            # -------------------------------------------
            remaining_trades = []

            for t in open_trades:
                alive = True

                if t["dir"] == "buy":
                    # SL
                    if row["low"] <= t["sl"]:
                        pnl = (t["sl"] - t["entry"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({
                            "exit": t["sl"],
                            "exit_time": idx,
                            "pnl": pnl,
                            "closed": True
                        })
                        trades.append(t)

                        # logging
                        self._log({
                            "id": t["id"],
                            "time": idx,
                            "type": "EXIT",
                            "entry": t["entry"],
                            "exit": t["sl"],
                            "sl": t["sl"],
                            "tp": t["tp"],
                            "size": t["size"],
                            "pnl": pnl,
                            "reason": "SL_HIT"
                        })

                        alive = False

                    # TP
                    elif row["high"] >= t["tp"]:
                        pnl = (t["tp"] - t["entry"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({
                            "exit": t["tp"],
                            "exit_time": idx,
                            "pnl": pnl,
                            "closed": True
                        })
                        trades.append(t)

                        # logging
                        self._log({
                            "id": t["id"],
                            "time": idx,
                            "type": "EXIT",
                            "entry": t["entry"],
                            "exit": t["tp"],
                            "sl": t["sl"],
                            "tp": t["tp"],
                            "size": t["size"],
                            "pnl": pnl,
                            "reason": "TP_HIT"
                        })

                        alive = False

                else:  # SELL -------------------------------------

                    # SL
                    if row["high"] >= t["sl"]:
                        pnl = (t["entry"] - t["sl"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({
                            "exit": t["sl"],
                            "exit_time": idx,
                            "pnl": pnl,
                            "closed": True
                        })
                        trades.append(t)

                        self._log({
                            "id": t["id"],
                            "time": idx,
                            "type": "EXIT",
                            "entry": t["entry"],
                            "exit": t["sl"],
                            "sl": t["sl"],
                            "tp": t["tp"],
                            "size": t["size"],
                            "pnl": pnl,
                            "reason": "SL_HIT"
                        })

                        alive = False

                    # TP
                    elif row["low"] <= t["tp"]:
                        pnl = (t["entry"] - t["tp"]) * t["size"] / pip_size
                        equity += pnl
                        t.update({
                            "exit": t["tp"],
                            "exit_time": idx,
                            "pnl": pnl,
                            "closed": True
                        })
                        trades.append(t)

                        self._log({
                            "id": t["id"],
                            "time": idx,
                            "type": "EXIT",
                            "entry": t["entry"],
                            "exit": t["tp"],
                            "sl": t["sl"],
                            "tp": t["tp"],
                            "size": t["size"],
                            "pnl": pnl,
                            "reason": "TP_HIT"
                        })

                        alive = False

                if alive:
                    remaining_trades.append(t)

            open_trades = remaining_trades

            # -------------------------------------------
            # 2) NEW ENTRY
            # -------------------------------------------
            if len(open_trades) < self.max_trades:
                sig = int(row.get("signal", 0))
                if sig != 0:

                    entry = row["close"]

                    if config.FIXED_LOT_BACKTEST is not None:
                        size = config.FIXED_LOT_BACKTEST

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

                    self.trade_counter += 1
                    trade_id = self.trade_counter

                    trade = {
                        "id": trade_id,
                        "entry_time": idx,
                        "dir": direction,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "size": size,
                        "closed": False
                    }
                    open_trades.append(trade)

                    # log entry
                    self._log({
                        "id": trade_id,
                        "time": idx,
                        "type": "ENTRY",
                        "entry": entry,
                        "exit": "",
                        "sl": sl,
                        "tp": tp,
                        "size": size,
                        "pnl": "",
                        "reason": "ENTRY_SIGNAL"
                    })

            equity_curve.append(equity)

        # -------------------------------------------
        # 3) CLOSE REMAINING TRADES AT END
        # -------------------------------------------
        if open_trades:
            last_price = df["close"].iloc[-1]
            last_time = df.index[-1]

            for t in open_trades:
                if not t["closed"]:
                    if t["dir"] == "buy":
                        pnl = (last_price - t["entry"]) * t["size"] / pip_size
                    else:
                        pnl = (t["entry"] - last_price) * t["size"] / pip_size

                    t.update({
                        "exit": last_price,
                        "exit_time": last_time,
                        "pnl": pnl,
                        "closed": True
                    })
                    trades.append(t)

                    self._log({
                        "id": t["id"],
                        "time": last_time,
                        "type": "EXIT",
                        "entry": t["entry"],
                        "exit": last_price,
                        "sl": t["sl"],
                        "tp": t["tp"],
                        "size": t["size"],
                        "pnl": pnl,
                        "reason": "FORCED_CLOSE_END"
                    })

                    equity += pnl

        eq_series = pd.Series(equity_curve, index=df.index[:len(equity_curve)])
        return eq_series, trades
