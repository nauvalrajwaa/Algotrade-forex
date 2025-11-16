class BacktestConfig:
    def __init__(self,
                 initial_balance=10000.0,
                 risk_per_trade=0.01,
                 max_trades=1):
        self.initial_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.max_trades = max_trades
