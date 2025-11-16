from trading_framework.config import BacktestConfig
from trading_framework.data.data_loader import DataLoader
from trading_framework.strategy.ma_crossover import MovingAverageStrategy
from trading_framework.backtester.backtester import Backtester
from trading_framework.optimizer.ga_optimizer import GAOptimizer

MT5_PATH = r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"

def main():
    loader = DataLoader(MT5_PATH)
    df = loader.fetch("XAUUSD", timeframe=5, bars=5000)

    config = BacktestConfig(initial_balance=10000, risk_per_trade=0.01)
    strategy = MovingAverageStrategy(ma_fast=10, ma_slow=40, atr_mul=1.5)
    bt = Backtester(config, strategy)

    eq, trades = bt.run(df)
    print("Baseline:", len(trades))

    ga = GAOptimizer(
        space={"ma_fast":(5,20),"ma_slow":(20,100),"atr_mul":(1.0,3.0)},
        backtester=bt,
        population=20,
        generations=10
    )

    best_params = ga.run(df)
    print("Best:", best_params)

if __name__ == "__main__":
    main()
