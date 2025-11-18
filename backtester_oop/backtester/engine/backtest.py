import pandas as pd
import numpy as np
from typing import List, Dict, Any
from backtester.strategies.base import Strategy


class BacktestEngine:
    def __init__(self,
                 strategy: Strategy,
                 initial_balance: float = 10000.0,
                 max_trades: int = 1,
                 pip_point: float = 0.0001):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.max_trades = max_trades
        self.pip_point = pip_point     # typically 0.0001 for forex

    # =====================================================
    # RUN BACKTEST
    # =====================================================
    def run(self, df: pd.DataFrame) -> (pd.Series, List[Dict[str, Any]]):
        df = self.strategy.generate_signals(df)

        equity = self.initial_balance
        equity_curve = []

        trades = []
        open_trades = []

        # =================================================
        # MAIN LOOP OVER CANDLES
        # =================================================
        for idx, row in df.iterrows():

            # -------------------------------------------------
            # 1) Manage OPEN TRADES (SL/TP)
            # -------------------------------------------------
            remaining_trades = []

            for t in open_trades:
                alive = True

                if t["dir"] == "buy":

                    # Stop Loss hit
                    if row["low"] <= t["sl"]:
                        pnl = (t["sl"] - t["entry"]) * t["size"] / self.pip_point
                        equity += pnl
                        t.update({"exit": t["sl"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False

                    # Take Profit hit
                    elif row["high"] >= t["tp"]:
                        pnl = (t["tp"] - t["entry"]) * t["size"] / self.pip_point
                        equity += pnl
                        t.update({"exit": t["tp"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False

                else:  # SELL

                    if row["high"] >= t["sl"]:
                        pnl = (t["entry"] - t["sl"]) * t["size"] / self.pip_point
                        equity += pnl
                        t.update({"exit": t["sl"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False

                    elif row["low"] <= t["tp"]:
                        pnl = (t["entry"] - t["tp"]) * t["size"] / self.pip_point
                        equity += pnl
                        t.update({"exit": t["tp"], "exit_time": idx, "pnl": pnl, "closed": True})
                        trades.append(t)
                        alive = False

                if alive:
                    remaining_trades.append(t)

            open_trades = remaining_trades

            # -------------------------------------------------
            # 2) Open NEW TRADES based on strategy signals
            # -------------------------------------------------
            if len(open_trades) < self.max_trades:
                sig = int(row.get("signal", 0))

                if sig != 0:

                    # ATR for SL distance
                    atr = row.get("atr", df["atr"].median() if "atr" in df.columns else 0.001)
                    atr_mul = self.strategy.params.get("atr_mul", 1.5)
                    sl_dist = atr * atr_mul

                    entry = row["close"]
                    risk_amount = equity * self.strategy.params.get("risk_per_trade", 0.01)

                    # ============= REALISTIC RISK-BASED POSITION SIZE =============
                    # Risk = SL distance in price / pip; risk per pip = size
                    pip_dist = sl_dist / self.pip_point
                    size = max(0.01, risk_amount / pip_dist)

                    if sig == 1:
                        sl = entry - sl_dist
                        tp = entry + sl_dist * 2
                        direction = "buy"
                    else:
                        sl = entry + sl_dist
                        tp = entry - sl_dist * 2
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
                        pnl = (last_price - t["entry"]) * t["size"] / self.pip_point
                    else:
                        pnl = (t["entry"] - last_price) * t["size"] / self.pip_point

                    t.update({"exit": last_price, "exit_time": last_time, "pnl": pnl})
                    trades.append(t)
                    equity += pnl

        eq_series = pd.Series(equity_curve, index=df.index[:len(equity_curve)])
        return eq_series, trades
