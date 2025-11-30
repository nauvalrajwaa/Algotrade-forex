import argparse
import sys
import os
import time
import logging
import datetime as dt
import pandas as pd

# --- FIX IMPORT PATH ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from main.engine.live_engine_screening_crypto import LiveEngineScreeningCrypto
    from main.strategies.ma_atr import MA_ATR_Strategy
    from main.strategies.swing_engulf_base import Swing_Engulf_Strategy_Base
    from main.engine.market_scanner import MarketScanner
except ImportError:
    try:
        from main.engine.live_engine_screening_crypto import LiveEngineScreeningCrypto
        from main.strategies.ma_atr import MA_ATR_Strategy
        from main.strategies.swing_engulf_base import Swing_Engulf_Strategy_Base
        from main.engine.market_scanner import MarketScanner
    except ImportError as e:
        print("CRITICAL ERROR: Tidak bisa menemukan file engine atau strategi.")
        sys.exit(1)

import config

# ==============================================================================
# HELPER
# ==============================================================================
def get_target_symbols(use_scanner, top_n, manual_symbols):
    if use_scanner:
        print("\n🚀 [SCANNER] Memindai pasar untuk mencari Top Volatility...")
        # FIX PATH KE UNIVERSE.JSON
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "main", "strategies", "universe.json")
        
        if not os.path.exists(json_path):
            # Coba path alternatif jika di root
            json_path = "universe.json"

        try:
            scanner = MarketScanner(json_path)
            symbols = scanner.get_top_volatile(top_n)
            if not symbols:
                print("❌ Scanner gagal. Menggunakan fallback.")
                return ["BTC/USDT", "ETH/USDT"]
            return symbols
        except Exception as e:
            print(f"❌ Scanner Error: {e}")
            return ["BTC/USDT", "ETH/USDT"]
            
    elif manual_symbols:
        return clean_manual_symbols(manual_symbols)
    else:
        return ["BTC/USDT", "ETH/USDT"]

def clean_manual_symbols(raw_str):
    symbols = []
    for s in raw_str.split(","):
        s = s.strip().upper()
        if "/" not in s and "USDT" in s:
            s = s.replace("USDT", "/USDT")
        if s: symbols.append(s)
    return symbols

# ==============================================================================
# MAIN PROGRAM
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Run Crypto live trading engine")

    parser.add_argument("--strategy", required=True, choices=["ma_atr", "swing_engulf_base"])
    parser.add_argument("--symbols", default="", help="Manual symbols")
    parser.add_argument("--use_scanner", action="store_true", help="Auto Refresh")
    parser.add_argument("--top_n", type=int, default=10, help="Jumlah koin")
    parser.add_argument("--timeframe", default="15m", type=str)
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--bars", type=int, default=200)
    
    # DEFAULT POLL SAYA NAIKKAN KE 60 DETIK AGAR LEBIH AMAN
    parser.add_argument("--poll", type=float, default=60.0, help="Polling interval seconds")

    args = parser.parse_args()

    # Strategy Config
    strategy_map = {
        "ma_atr": (MA_ATR_Strategy, {"ma_fast": 10, "ma_slow": 40, "atr_period": 14, "atr_mult": 1.5, "cooldown": 3}),
        "swing_engulf_base": (Swing_Engulf_Strategy_Base, {"length": 5, "tolerance": 40}),
    }
    strategy_class, strategy_params = strategy_map[args.strategy]

    # Refresh Config
    refresh_hours = getattr(config, 'REFRESH_HOURS', 4) 
    refresh_seconds = refresh_hours * 3600
    last_refresh_time = time.time()

    # --- OUTER LOOP: SESSION ---
    while True:
        current_symbols = get_target_symbols(args.use_scanner, args.top_n, args.symbols)
        
        print("\n===== CRYPTO ENGINE SESSION STARTED =====")
        print(f"Strategy   : {args.strategy}")
        print(f"Watchlist  : {len(current_symbols)} Symbols")
        print(f"Refresh    : Every {refresh_hours} Hours")
        print("=========================================\n")

        engine = LiveEngineScreeningCrypto(
            strategy_class=strategy_class,
            symbols=current_symbols,
            timeframe=args.timeframe, 
            bars=args.bars,
            mode=args.mode,
            strategy_params=strategy_params
        )

        if engine.mode != "paper":
            try:
                engine.connect()
                engine._send_telegram(f"🔄 <b>AUTO REFRESH</b>\nNew Session: {len(current_symbols)} Pairs")
            except Exception as e:
                print(f"Connect Error: {e}. Retry 10s...")
                time.sleep(10)
                continue

        # --- INNER LOOP: TRADING ---
        try:
            engine.logger.info("===== SESSION RUNNING =====")
            
            while True:
                # A. Auto Refresh Logic
                if args.use_scanner: 
                    elapsed = time.time() - last_refresh_time
                    if elapsed > refresh_seconds:
                        open_positions = [sym for sym, pos in engine.current_position.items() if pos is not None]
                        if not open_positions:
                            engine.logger.info("Refreshing Session (Clean State)...")
                            last_refresh_time = time.time()
                            break 
                        else:
                            engine.logger.info(f"Delaying refresh, positions open: {open_positions}")
                            last_refresh_time = time.time() - refresh_seconds + 300 

                # B. Trading Logic
                trading_open = engine._is_trading_time()
                table_rows = []

                for symbol in engine.symbols:
                    # ---------------------------------------------------------
                    # ANTI-BAN PROTECTION: SLEEP ANTAR SIMBOL
                    # ---------------------------------------------------------
                    time.sleep(1.0) # Jeda 1 detik per simbol agar tidak dianggap SPAM
                    # ---------------------------------------------------------

                    try:
                        price = engine.client.get_ticker_price(symbol)
                    except: price = 0
                    
                    if price == 0: 
                        table_rows.append([symbol, "ERR", 0, "-", "-"])
                        continue

                    # Manage Position
                    if engine.current_position[symbol]:
                        engine.monitor_position(symbol, price)
                        
                        pos = engine.current_position[symbol]
                        close_reason = None
                        if pos['direction'] == 1:
                            if price <= pos['sl']: close_reason = "SL/Trailing"
                            elif price >= pos['tp']: close_reason = "TP Hit"
                        else:
                            if price >= pos['sl']: close_reason = "SL/Trailing"
                            elif price <= pos['tp']: close_reason = "TP Hit"
                            
                        if close_reason:
                            if "Trailing" in close_reason and engine.mode != "paper":
                                side = 'SELL' if pos['direction'] == 1 else 'BUY'
                                engine.client.create_order(symbol, side, 'MARKET', pos['amount'], reduce_only=True)
                                engine.client.cancel_all_open_orders(symbol)
                            
                            engine.logger.info(f"[{symbol}] Closed: {close_reason}")
                            engine._send_telegram(f"🏁 <b>CLOSED ({close_reason})</b>\n{symbol}")
                            engine.current_position[symbol] = None
                        else:
                            d_str = "BUY" if pos['direction'] == 1 else "SELL"
                            table_rows.append([symbol, price, d_str, pos['sl'], pos['tp']])
                    
                    # Scan Entry
                    else:
                        if trading_open:
                            raw_klines = engine.client.get_klines(symbol, engine.timeframe, limit=engine.bars + 5)
                            if raw_klines:
                                data = []
                                for k in raw_klines:
                                    data.append([int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
                                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                                
                                sig_df = engine.strategies[symbol].generate_signals(df)
                                if not sig_df.empty:
                                    sig = int(sig_df['signal'].iloc[-1])
                                    if sig != 0:
                                        engine.execute_entry(symbol, sig, price)
                                        table_rows.append([symbol, price, "ENTRY", "PEND", "PEND"])
                                        continue
                        table_rows.append([symbol, price, 0, "-", "-"])

                # Log
                if table_rows:
                    engine.logger.info("-" * 65)
                    engine.logger.info(f"{'SYMBOL':<10} | {'PRICE':<10} | {'POS':<6} | {'SL':<10} | {'TP':<10}")
                    engine.logger.info("-" * 65)
                    for r in table_rows:
                        p = f"{r[1]:.2f}" if isinstance(r[1], float) else r[1]
                        sl = f"{r[3]:.2f}" if isinstance(r[3], float) else r[3]
                        tp = f"{r[4]:.2f}" if isinstance(r[4], float) else r[4]
                        engine.logger.info(f"{r[0]:<10} | {p:<10} | {r[2]:<6} | {sl:<10} | {tp:<10}")
                
                if not trading_open: engine.logger.info("[FILTER] Trading Paused")

                # POLL INTERVAL (Istirahat antar siklus)
                # Gunakan 60 detik untuk swing trading agar akun aman
                time.sleep(args.poll)

        except KeyboardInterrupt:
            print("\nStopping Engine...")
            sys.exit(0)
        except Exception as e:
            print(f"Error in Loop: {e}. Sleep 30s...")
            time.sleep(30)

if __name__ == "__main__":
    main()