# run_live.py
import argparse
from backtester.engine.live_engine import LiveEngine

# === Import ALL strategies you want to allow ===
from backtester.strategies.ma_atr import MA_ATR_Strategy
from backtester.strategies.rsi_strategy import RSI_Strategy
from backtester.strategies.breakout_strategy import BreakoutStrategy


def main():
    parser = argparse.ArgumentParser(description="Run live trading engine (MT5)")

    parser.add_argument("--strategy", required=True,
                        choices=["ma_atr", "rsi", "breakout"],
                        help="Strategy to use")

    parser.add_argument("--symbol", required=True, help="Trading symbol, e.g. EURUSD")
    parser.add_argument("--timeframe", default=15, type=int, help="Timeframe in minutes")
    parser.add_argument("--mt5-path", default=None, help="Path to terminal64.exe")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--risk", type=float, default=0.01, help="Risk/fraction per trade")
    parser.add_argument("--bars", type=int, default=200, help="Bars to fetch every poll")
    parser.add_argument("--poll", type=float, default=10.0, help="Polling interval (seconds)")

    args = parser.parse_args()

    # === Strategy Factory ===
    strategy_map = {
        "ma_atr": MA_ATR_Strategy(params={"ma_fast": 10, "ma_slow": 40, "atr_n": 14, "atr_mul": 1.5}),
        "rsi": RSI_Strategy(params={"period": 14, "rsi_low": 30, "rsi_high": 70}),
        "breakout": BreakoutStrategy(params={"lookback": 20}),
    }

    strategy = strategy_map[args.strategy]

    # ====================
    # MAP TIMEFRAME → MT5
    # ====================
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

    # ====================
    # Create Live Engine
    # ====================
    engine = LiveEngine(
        strategy=strategy,
        mt5_path=args.mt5_path,
        symbol=args.symbol,
        timeframe=timeframe,
        bars=args.bars,
        mode=args.mode,
        risk_per_trade=args.risk,
    )

    print(f"\n===== LIVE ENGINE STARTED =====")
    print(f"Strategy : {args.strategy}")
    print(f"Symbol   : {args.symbol}")
    print(f"TF       : {args.timeframe} min")
    print(f"Mode     : {args.mode}")
    print(f"Risk     : {args.risk}")
    print("================================\n")

    try:
        engine.start(poll_interval=args.poll)
    except Exception as e:
        print("Live engine error:", e)
    finally:
        engine.disconnect()


if __name__ == "__main__":
    main()
