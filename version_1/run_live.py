# run_live.py
import argparse
from backtester.engine.live_engine import LiveEngine
from backtester.strategies.ma_atr import MA_ATR_Strategy
from backtester.strategies.rsi_ma_reversal import RSI_MA_Reversal
from backtester.strategies.m1_scalper import M1ScalperStrategy
import config


def main():
    parser = argparse.ArgumentParser(description="Run live trading engine (MT5)")

    parser.add_argument("--strategy", required=True,
                        choices=["ma_atr", "rsi", "m1_scalper"],
                        help="Strategy to use")

    parser.add_argument("--symbol", required=True, help="Trading symbol, e.g. EURUSD")
    parser.add_argument("--timeframe", default=15, type=int, help="Timeframe in minutes")
    parser.add_argument("--mt5-path", default=None, help="Path to terminal64.exe")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--bars", type=int, default=200, help="Bars to fetch every poll")
    parser.add_argument("--poll", type=float, default=10.0, help="Polling interval")

    args = parser.parse_args()

    # --- Strategy Factory ---
    strategy_map = {
        "ma_atr": MA_ATR_Strategy(params={
            "ma_fast": 10,
            "ma_slow": 40,

            "atr_period": 14,
            "atr_mult": 1.5,

            "cooldown": 3
        }),

        "rsi": RSI_MA_Reversal(params={
            "ma_fast": 10,
            "ma_slow": 50,

            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,

            "atr_period": 14,
            "atr_mult": 0.8,

            "cooldown": 5
        }),

        "m1_scalper": M1ScalperStrategy(params={
            "ma_fast": 3, "ma_slow": 8,
            "atr_period": 5, "atr_mult": 0.3,
            "mom_period": 2, "mom_threshold": 0.0,
            "cooldown": 1
        }),
    }

    strategy = strategy_map[args.strategy]

    # --- Timeframe Mapping ---
    import MetaTrader5 as mt5
    tf_map = {
        1: mt5.TIMEFRAME_M1,
        5: mt5.TIMEFRAME_M5,
        15: mt5.TIMEFRAME_M15,
        30: mt5.TIMEFRAME_M30,
        60: mt5.TIMEFRAME_H1,
        240: mt5.TIMEFRAME_H4,
        1440: mt5.TIMEFRAME_D1,
    }
    timeframe = tf_map.get(args.timeframe, mt5.TIMEFRAME_M15)

    # --- Create LiveEngine (risk_per_trade REMOVED) ---
    engine = LiveEngine(
        strategy=strategy,
        mt5_path=args.mt5_path or config.MT5_PATH,
        symbol=args.symbol,
        timeframe=timeframe,
        bars=args.bars,
        mode=args.mode,
    )

    print("\n===== LIVE ENGINE STARTED =====")
    print(f"Strategy : {args.strategy}")
    print(f"Symbol   : {args.symbol}")
    print(f"TF       : {args.timeframe} min")
    print(f"Mode     : {args.mode}")
    print(f"Using SL/TP Ratio  : {config.SLTP_RATIO}")
    print(f"Using FIXED LOT    : {config.FIXED_LOT_LIVE}")
    print("================================\n")

    try:
        engine.start(poll_interval=args.poll)
    except Exception as e:
        print("Live engine error:", e)
    finally:
        engine.disconnect()


if __name__ == "__main__":
    main()
