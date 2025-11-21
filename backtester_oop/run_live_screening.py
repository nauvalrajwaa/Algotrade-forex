# run_live_screening.py
import argparse
from backtester.engine.live_engine_screening import LiveEngineScreening

from backtester.strategies.ma_atr import MA_ATR_Strategy
from backtester.strategies.rsi_ma_reversal import RSI_MA_Reversal
from backtester.strategies.m1_scalper import M1ScalperStrategy
import config


def main():
    parser = argparse.ArgumentParser(description="Run live trading engine (MT5) with multi-symbol screening")

    parser.add_argument("--strategy", required=True,
                        choices=["ma_atr", "rsi", "m1_scalper"],
                        help="Strategy to use")

    parser.add_argument("--symbols", required=True,
                        help="Comma-separated list of symbols, e.g. EURUSD,GBPUSD,XAUUSD")

    parser.add_argument("--timeframe", default=15, type=int,
                        help="Timeframe in minutes")

    parser.add_argument("--mt5-path", default=None,
                        help="Path to terminal64.exe")

    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--bars", type=int, default=200, help="Bars to load each polling")
    parser.add_argument("--poll", type=float, default=10.0, help="Polling interval in seconds")

    args = parser.parse_args()

    # ==========================
    # STRATEGY FACTORY
    # ==========================
    strategy_map = {
        "ma_atr": (MA_ATR_Strategy, {
            "ma_fast": 10,
            "ma_slow": 40,
            "atr_period": 14,
            "atr_mult": 1.5,
            "cooldown": 3
        }),
        "rsi": (RSI_MA_Reversal, {
            "ma_fast": 10,
            "ma_slow": 50,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "atr_period": 14,
            "atr_mult": 0.8,
            "cooldown": 5
        }),
        "m1_scalper": (M1ScalperStrategy, {
            "ma_fast": 3,
            "ma_slow": 8,
            "atr_period": 5,
            "atr_mult": 0.3,
            "mom_period": 2,
            "mom_threshold": 0.0,
            "cooldown": 1
        }),
    }

    strategy_class, strategy_params = strategy_map[args.strategy]

    # ==========================
    # TIMEFRAME MAP
    # ==========================
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

    # ==========================
    # SYMBOL LIST
    # ==========================
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    # ==========================
    # ENGINE INIT
    # ==========================
    engine = LiveEngineScreening(
        strategy_class=strategy_class,
        mt5_path=args.mt5_path or config.MT5_PATH,
        symbols=symbols,
        timeframe=timeframe,
        bars=args.bars,
        mode=args.mode,
        strategy_params=strategy_params  # <-- ini baru diteruskan ke engine
    )

    print("\n===== LIVE ENGINE SCREENING STARTED =====")
    print(f"Strategy : {args.strategy}")
    print(f"Symbols  : {symbols}")
    print(f"TF       : {args.timeframe} min")
    print(f"Mode     : {args.mode}")
    print(f"SLTP Ratio       : {config.SLTP_RATIO}")

    # ===============================
    # Logging FIXED LOT per symbol
    # ===============================
    fixed_lot_map = {
        "XAUUSD": getattr(config, "FIXED_LOT_XAUUSD", None),
        "EURUSD": getattr(config, "FIXED_LOT_EURUSD", None),
        "GBPUSD": getattr(config, "FIXED_LOT_GBPUSD", None),
        "GBPJPY": getattr(config, "FIXED_LOT_GBPJPY", None),
    }

    print("Fixed Lot per Symbol:")
    for sym in symbols:
        lot = fixed_lot_map.get(sym, None)
        print(f"  {sym:<6} : {lot}")

    print("==========================================\n")

    try:
        engine.start(poll_interval=args.poll)
    except Exception as e:
        print("Live engine screening error:", e)
    finally:
        engine.disconnect()


if __name__ == "__main__":
    main()
