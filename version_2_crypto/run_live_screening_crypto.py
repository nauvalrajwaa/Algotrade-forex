# run_live_screening_crypto.py

import argparse
from main.engine.live_engine_screening_crypto import LiveEngineScreeningCrypto

# Import strategi (gunakan strategi yang sama dengan Forex)
from main.strategies.ma_atr import MA_ATR_Strategy
from main.strategies.swing_engulf_base import Swing_Engulf_Strategy_Base
import config

def main():
    parser = argparse.ArgumentParser(description="Run Crypto live trading engine (Binance)")

    parser.add_argument("--strategy", required=True,
                        choices=["ma_atr", "swing_engulf_base"],
                        help="Strategy to use")

    parser.add_argument("--symbols", required=True,
                        help="Comma-separated symbols, e.g. BTC/USDT,ETH/USDT")

    parser.add_argument("--timeframe", default="15m", type=str,
                        help="Timeframe string (1m, 5m, 15m, 1h, 4h, 1d)")

    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--bars", type=int, default=200, help="Bars to load")
    parser.add_argument("--poll", type=float, default=15.0, help="Polling interval seconds")

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
        "swing_engulf_base": (Swing_Engulf_Strategy_Base, {
            "length": 5,
            "tolerance": 40,
        }),
    }

    strategy_class, strategy_params = strategy_map[args.strategy]

    # ==========================
    # SYMBOL CLEANING
    # ==========================
    # Pastikan format simbol kapital dan bersih
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    # ==========================
    # ENGINE INIT
    # ==========================
    engine = LiveEngineScreeningCrypto(
        strategy_class=strategy_class,
        symbols=symbols,
        timeframe=args.timeframe, # Crypto pakai string: '15m', '1h'
        bars=args.bars,
        mode=args.mode,
        risk_per_trade=config.RISK_PER_TRADE if hasattr(config, 'RISK_PER_TRADE') else 0.01,
        strategy_params=strategy_params
    )

    print("\n===== CRYPTO ENGINE SCREENING STARTED =====")
    print(f"Strategy : {args.strategy}")
    print(f"Symbols  : {symbols}")
    print(f"TF       : {args.timeframe}")
    print(f"Mode     : {args.mode}")
    print(f"Config   : {config.SLTP_RATIO}")
    print("===========================================\n")

    try:
        engine.start(poll_interval=args.poll)
    except KeyboardInterrupt:
        print("\nStopping Engine...")
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    main()