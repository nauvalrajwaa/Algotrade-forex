from .trade import Trade

class Backtester:
    def __init__(self, config, strategy):
        self.config = config
        self.strategy = strategy

    def run(self, df):
        df = self.strategy.generate_signals(df)
        equity = self.config.initial_balance
        equity_curve = []
        open_trades = []
        trades = []

        for idx, row in df.iterrows():
            # --- manage existing trades ---
            # logic sama seperti script asli Anda

            # --- open new trade ---
            sig = row["signal"]
            if sig != 0 and len(open_trades) < self.config.max_trades:
                atr = row["atr"]
                risk_amount = equity * self.config.risk_per_trade

                pip = 0.0001
                sl_dist = atr * self.strategy.atr_mul
                lot = max(0.01, risk_amount / ((sl_dist / pip) * 10))

                if sig == 1:
                    sl = row["close"] - sl_dist
                    tps = [row["close"] + sl_dist * i for i in [1,2,3]]
                else:
                    sl = row["close"] + sl_dist
                    tps = [row["close"] - sl_dist * i for i in [1,2,3]]

                trade = Trade(sig, row["close"], sl, tps, lot, idx)
                open_trades.append(trade)

            equity_curve.append(equity)

        return equity_curve, trades
