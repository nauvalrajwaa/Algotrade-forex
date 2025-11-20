# backtester_oop/run_backtest.py

import argparse
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from config import (
    MT5_PATH,
    BARS,
    INITIAL_BALANCE,
    OPTIMIZER,
    SEARCH_SPACE_DEFAULT,
    SEARCH_SPACE_BY_STRATEGY,
    GA_CONFIG_DEFAULT,
    GA_CONFIG_BY_STRATEGY,
    MC_CONFIG,
    MAX_OPEN_TRADES,
    SLTP_RATIO,
    BASE_PIPS,
    FIXED_LOT,
)

from backtester.data.fetcher import DataFetcher
from backtester.strategies.ma_atr import MA_ATR_Strategy
from backtester.strategies.rsi_ma_reversal import RSI_MA_Reversal
from backtester.strategies.ict_hybrid import ICTHybridStrategy
from backtester.strategies.ict_time import ICTAdvancedStrategy

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
    "ict_hybrid": ICTHybridStrategy,
    "ict_time": ICTAdvancedStrategy,
}


# ======================================================
# Strategy factory
# ======================================================
def build_strategy(name, params):
    if name not in STRATEGY_CLASSES:
        raise ValueError(f"Unknown strategy: {name}")
    return STRATEGY_CLASSES[name](params=params)


# ======================================================
# Fitness Function (NOW SAFE)
# ======================================================
def evaluate_params(params, df, initial_balance, strategy_name):
    try:
        strat = build_strategy(strategy_name, params)
        engine = BacktestEngine(strategy=strat, initial_balance=initial_balance)

        eq, trades = engine.run(df)
        metrics = metrics_from_trades(trades, eq, initial_balance)

        if len(trades) == 0:
            return -1e9

        net_profit = metrics.get("total_pnl", -1e9)
        pf = metrics.get("profit_factor", 0)

        score = net_profit + (pf * 50)

        if score is None or np.isnan(score) or np.isinf(score):
            return -1e9

        return float(score)

    except Exception as e:
        print(f"[FITNESS ERROR] {params} => {e}")
        return -1e9


# ======================================================
# Run Backtest + Plot
# ======================================================
def run_backtest_and_plot(params, df, initial_balance, strategy_name):
    print("\n\n=== Running Backtest ===")
    print(f"Config:")
    print(f"  Max Open Trades : {MAX_OPEN_TRADES}")
    print(f"  SL/TP Ratio     : {SLTP_RATIO}")
    print(f"  SL Base Pips    : {BASE_PIPS}")
    print(f"  Fixed Lot       : {FIXED_LOT}")
    print(f"  Strategy Params : {params}\n")

    strat = build_strategy(strategy_name, params)
    engine = BacktestEngine(strategy=strat, initial_balance=initial_balance)

    eq, trades = engine.run(df)
    eq = pd.Series(eq)

    metrics = metrics_from_trades(trades, eq, initial_balance)
    print("Trades:", len(trades))
    print(ascii_box_table(metrics, "FULL TRADING METRICS"))

    # Plot equity curve
    plt.figure(figsize=(10, 4))
    plt.plot(eq, label="Equity")
    plt.title(f"Equity Curve ({strategy_name})")
    plt.xlabel("Step")
    plt.ylabel("Balance")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    return metrics


# ======================================================
# MAIN
# ======================================================
def main():
    parser = argparse.ArgumentParser(description="Backtester OOP Runner")
    parser.add_argument("--source", choices=["mt5", "csv"], default="csv")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--csv", default=None)
    parser.add_argument("--bars", type=int, default=BARS)
    parser.add_argument("--initial-balance", type=float, default=INITIAL_BALANCE)
    parser.add_argument("--strategy", choices=list(STRATEGY_CLASSES.keys()), default="ma_atr")
    args = parser.parse_args()

    fetcher = DataFetcher(mt5_path=MT5_PATH)

    # ---------------- Load Data ----------------
    if args.source == "mt5":
        import MetaTrader5 as mt5
        mt5.initialize()
        timeframe = mt5.TIMEFRAME_M15
        df = fetcher.fetch_mt5(args.symbol, timeframe, bars=args.bars)
    else:
        if args.csv is None:
            raise ValueError("CSV file missing")
        df = fetcher.fetch_csv(args.csv)

    strategy_name = args.strategy

    # ---------------- Load Search Space ----------------
    strategy_space = SEARCH_SPACE_BY_STRATEGY.get(strategy_name, SEARCH_SPACE_DEFAULT)

    # ---------------- Load GA Config ----------------
    ga_config = GA_CONFIG_BY_STRATEGY.get(strategy_name, GA_CONFIG_DEFAULT)

    print("\n=== Backtest Configuration ===")
    print(f" Strategy           : {strategy_name}")
    print(f" Initial Balance    : {args.initial_balance}")
    print(f" Search Space       : {strategy_space}")
    print(f" Optimizer          : {OPTIMIZER}")
    print(f" Max Open Trades    : {MAX_OPEN_TRADES}\n")

    # ======================================================
    # MODE 1: NO OPTIMIZER
    # ======================================================
    if OPTIMIZER == "none":
        params = {k: (v[0] + v[1]) / 2 for k, v in strategy_space.items()}
        run_backtest_and_plot(params, df, args.initial_balance, strategy_name)
        return

    # ======================================================
    # MODE 2: GA ONLY
    # ======================================================
    if OPTIMIZER == "ga":
        ga = GeneticOptimizer(
            search_space=strategy_space,
            config=ga_config,
            fitness_function=lambda p: evaluate_params(
                p, df, args.initial_balance, strategy_name
            ),
            strategy_name=strategy_name
        )
        best_params, best_score = ga.run()
        print("\n=== GA Best Result ===")
        print(best_params, best_score)

        run_backtest_and_plot(best_params, df, args.initial_balance, strategy_name)
        return

    # ======================================================
    # MODE 3: MC ONLY
    # ======================================================
    if OPTIMIZER == "mc":
        mc = MonteCarloOptimizer(
            search_space=strategy_space,
            config=MC_CONFIG,
            fitness_function=lambda p: evaluate_params(
                p, df, args.initial_balance, strategy_name
            ),
        )
        best_params, best_score = mc.run()
        print("\n=== MC Best Result ===", best_params, best_score)

        run_backtest_and_plot(best_params, df, args.initial_balance, strategy_name)
        return

    # ======================================================
    # MODE 4: GA → MC
    # ======================================================
    if OPTIMIZER == "ga_mc":
        print("\n========== Running GA Phase ==========")

        ga = GeneticOptimizer(
            search_space=strategy_space,
            config=ga_config,
            fitness_function=lambda p: evaluate_params(
                p, df, args.initial_balance, strategy_name
            ),
            strategy_name=strategy_name
        )
        best_ga_params, _ = ga.run()

        run_backtest_and_plot(best_ga_params, df, args.initial_balance, strategy_name)

        print("\n========== Running MC Phase ==========")
        mc = MonteCarloOptimizer(
            search_space=strategy_space,
            config=MC_CONFIG,
            fitness_function=lambda p: evaluate_params(
                p, df, args.initial_balance, strategy_name
            )
        )

        best_mc_params, best_mc_score = mc.run()
        print("MC Best:", best_mc_params, best_mc_score)
        return


if __name__ == "__main__":
    main()
