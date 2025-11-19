# run_backtest.py
import argparse
import matplotlib.pyplot as plt
import pandas as pd
import MetaTrader5 as mt5

from config import (
    MT5_PATH,
    BARS,
    INITIAL_BALANCE,
    OPTIMIZER,
    SEARCH_SPACE,
    GA_CONFIG,
    MC_CONFIG,
    MAX_OPEN_TRADES,
    SLTP_RATIO,
    BASE_PIPS,
    FIXED_LOT
)

from backtester.data.fetcher import DataFetcher
from backtester.strategies.ma_atr import MA_ATR_Strategy
from backtester.strategies.rsi_ma_reversal import RSI_MA_Reversal
from backtester.strategies.bollinger_squeeze import BollingerSqueeze

from backtester.engine.backtest_engine import BacktestEngine
from backtester.optimizer.metrics import metrics_from_trades, ascii_box_table
from backtester.optimizer.ga import GeneticOptimizer
from backtester.optimizer.montecarlo import MonteCarloOptimizer

# ======================================================
# STRATEGY REGISTRY
# ======================================================
STRATEGY_CLASSES = {
    "ma_atr": MA_ATR_Strategy,
    "rsi_ma": RSI_MA_Reversal,
    "squeeze": BollingerSqueeze,
}

# ======================================================
# Strategy factory
# ======================================================
def build_strategy(name, params):
    if name not in STRATEGY_CLASSES:
        raise ValueError(f"Unknown strategy: {name}")
    return STRATEGY_CLASSES[name](params=params)

# ================= Evaluation Function ==================
def evaluate_params(params, df, initial_balance, strategy_name):
    strat = build_strategy(strategy_name, params)
    engine = BacktestEngine(strategy=strat, initial_balance=initial_balance)
    eq, trades = engine.run(df)
    metrics = metrics_from_trades(trades, eq, initial_balance)
    net_profit = metrics.get("total_pnl", 0)
    pf = metrics.get("profit_factor", 0)
    return net_profit + (pf * 50)

# ================= Helper: Backtest + Plot ==================
def run_backtest_and_plot(params, df, initial_balance, strategy_name):
    print("\n\n=== Running Backtest on Best Params ===")
    print(f"Config Settings:")
    print(f"  Max Open Trades: {MAX_OPEN_TRADES}")
    print(f"  SL/TP Ratio: {SLTP_RATIO}")
    print(f"  Base Pips (SL): {BASE_PIPS}")
    print(f"  Fixed Lot: {FIXED_LOT}\n")

    strat = build_strategy(strategy_name, params)
    # Hanya kirim strategy dan initial_balance, engine ambil max_trades dari config
    engine = BacktestEngine(strategy=strat, initial_balance=initial_balance)
    eq, trades = engine.run(df)
    eq = pd.Series(eq)
    metrics = metrics_from_trades(trades, eq, initial_balance)

    print("Trades:", len(trades))
    print(ascii_box_table(metrics, "FULL TRADING METRICS"))

    plt.figure(figsize=(10, 4))
    plt.plot(eq, label="Equity")
    plt.title(f"Equity Curve ({strategy_name})")
    plt.xlabel("Step #")
    plt.ylabel("Balance")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    return metrics

# ============================== MAIN ==============================
def main():
    parser = argparse.ArgumentParser(description="Backtester OOP Runner")
    parser.add_argument("--source", choices=["mt5", "csv"], default="csv")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--csv", default=None)
    parser.add_argument("--bars", type=int, default=BARS)
    parser.add_argument("--initial-balance", type=float, default=INITIAL_BALANCE)
    parser.add_argument("--strategy", choices=list(STRATEGY_CLASSES.keys()), default="ma_atr", help="Select trading strategy")
    args = parser.parse_args()

    fetcher = DataFetcher(mt5_path=MT5_PATH)

    # Load data
    if args.source == "mt5":
        timeframe = mt5.TIMEFRAME_M15
        df = fetcher.fetch_mt5(args.symbol, timeframe, bars=args.bars)
    else:
        if args.csv is None:
            raise ValueError("CSV file missing")
        df = fetcher.fetch_csv(args.csv)

    strategy_name = args.strategy

    # ====================== LOG CONFIG ======================
    print(f"\n=== Backtest Configuration ===")
    print(f"Strategy: {strategy_name}")
    print(f"Initial Balance: {args.initial_balance}")
    print(f"Max Open Trades: {MAX_OPEN_TRADES}")
    print(f"SL/TP Ratio: {SLTP_RATIO}")
    print(f"Base Pips (for SL): {BASE_PIPS}")
    print(f"Fixed Lot: {FIXED_LOT}\n")

    # ====================== No optimizer ======================
    if OPTIMIZER == "none":
        params = {"ma_fast": 10, "ma_slow": 40, "atr_mul": 1.5}
        run_backtest_and_plot(params, df, args.initial_balance, strategy_name)
        return

    # ====================== GA only ===========================
    if OPTIMIZER == "ga":
        ga = GeneticOptimizer(
            search_space=SEARCH_SPACE,
            config=GA_CONFIG,
            fitness_function=lambda p: evaluate_params(p, df, args.initial_balance, strategy_name)
        )
        best_params, best_score = ga.run()
        print("\n=== GA Best Result ===")
        print("Best Params:", best_params)
        print("Best Score:", best_score)
        run_backtest_and_plot(best_params, df, args.initial_balance, strategy_name)
        return

    # ====================== MC only ===========================
    if OPTIMIZER == "mc":
        mc = MonteCarloOptimizer(
            search_space=SEARCH_SPACE,
            config=MC_CONFIG,
            fitness_function=lambda p: evaluate_params(p, df, args.initial_balance, strategy_name)
        )
        best_params, best_score = mc.run()
        print("\n=== Monte Carlo Best Result ===")
        print("Best Params:", best_params)
        print("Best Score:", best_score)
        return

    # ====================== GA → MC ===========================
    if OPTIMIZER == "ga_mc":
        print("\n=========== Running GA Optimization ===========")
        ga = GeneticOptimizer(
            search_space=SEARCH_SPACE,
            config=GA_CONFIG,
            fitness_function=lambda p: evaluate_params(p, df, args.initial_balance, strategy_name)
        )
        best_params_ga, best_score_ga = ga.run()
        print("\n=== GA Best Result ===")
        print("Best Params:", best_params_ga)
        print("Best Score:", best_score_ga)
        run_backtest_and_plot(best_params_ga, df, args.initial_balance, strategy_name)

        print("\n=========== Running Monte Carlo Following GA ===========")
        mc = MonteCarloOptimizer(
            search_space=SEARCH_SPACE,
            config=MC_CONFIG,
            fitness_function=lambda p: evaluate_params(p, df, args.initial_balance, strategy_name)
        )
        best_params_mc, best_score_mc = mc.run()
        print("\n=== MC Best Result ===")
        print("Best Params:", best_params_mc)
        print("Best Score:", best_score_mc)
        return

if __name__ == "__main__":
    main()
