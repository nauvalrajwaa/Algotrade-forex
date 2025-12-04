import argparse
import sys
import os
import time
import logging
import datetime as dt
import pandas as pd

# --- FIX IMPORT PATH ---
# Menambahkan folder project ke system path agar python bisa mengenali folder 'engine'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Coba import standar
    from main.engine.live_engine_screening_crypto import LiveEngineScreeningCrypto
    from main.strategies.ma_atr import MA_ATR_Strategy
    from main.strategies.swing_engulf_base import Swing_Engulf_Strategy_Base
    from main.market_scanner import MarketScanner
except ImportError:
    # Coba import alternatif (jika folder main/)
    try:
        from main.engine.live_engine_screening_crypto import LiveEngineScreeningCrypto
        from main.strategies.ma_atr import MA_ATR_Strategy
        from main.strategies.swing_engulf_base import Swing_Engulf_Strategy_Base
        from main.engine.market_scanner import MarketScanner
    except ImportError as e:
        print("CRITICAL ERROR: Tidak bisa menemukan file engine atau strategi.")
        print(f"Detail Error: {e}")
        sys.exit(1)

import config

# ==============================================================================
# HELPER: SELECT SYMBOLS
# ==============================================================================
def get_target_symbols(use_scanner, top_n, manual_symbols, sort_mode=None):
    """
    Memilih simbol:
    1. Jika use_scanner=True -> Ambil dari MarketScanner (Auto Volatility)
    2. Jika tidak -> Ambil dari input manual user
    """
    if use_scanner:
        print("\n🚀 [SCANNER] Memindai pasar untuk mencari Top Volatility...")
        # FIX PATH KE UNIVERSE.JSON
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "main", "strategies", "universe.json")
        
        # Cek apakah file benar-benar ada di path complex atau root
        if not os.path.exists(json_path):
            json_path = "universe.json" # Coba root

        try:
            scanner = MarketScanner(json_path)
            # PASSING SORT MODE KE SINI
            symbols = scanner.get_top_volatile(top_n, override_mode=sort_mode)
            
            if not symbols:
                print("❌ Scanner gagal atau kosong. Menggunakan fallback manual.")
                if manual_symbols: return clean_manual_symbols(manual_symbols)
                return ["BTC/USDT", "ETH/USDT"]
            return symbols
        except Exception as e:
            print(f"❌ Scanner Error: {e}")
            if manual_symbols: return clean_manual_symbols(manual_symbols)
            return ["BTC/USDT", "ETH/USDT"]
            
    elif manual_symbols:
        return clean_manual_symbols(manual_symbols)
    
    else:
        return ["BTC/USDT", "ETH/USDT"] # Default minimal

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
    parser = argparse.ArgumentParser(description="Run Crypto live trading engine (Binance)")

    parser.add_argument("--strategy", required=True,
                        choices=["ma_atr", "swing_engulf_base"],
                        help="Strategy to use")

    parser.add_argument("--symbols", default="",
                        help="Manual comma-separated symbols (e.g. BTC/USDT)")

    parser.add_argument("--use_scanner", action="store_true", 
                        help="Gunakan scanner otomatis (Auto Refresh)")
    
    parser.add_argument("--top_n", type=int, default=10, 
                        help="Jumlah koin teratas yang diambil jika pakai scanner")

    parser.add_argument("--sort", default="", 
                        choices=["activity", "volatility", "hybrid"],
                        help="Mode sorting scanner (override config)")

    parser.add_argument("--timeframe", default="15m", type=str,
                        help="Timeframe string (1m, 5m, 15m, 1h, 4h, 1d)")

    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--bars", type=int, default=200, help="Bars to load")
    parser.add_argument("--poll", type=float, default=60.0, help="Polling interval seconds")

    args = parser.parse_args()

    # --- STRATEGY CONFIG ---
    strategy_map = {
        "ma_atr": (MA_ATR_Strategy, {
            "ma_fast": 10, "ma_slow": 40, "atr_period": 14, "atr_mult": 1.5, "cooldown": 3
        }),
        "swing_engulf_base": (Swing_Engulf_Strategy_Base, {
            "length": 5, "tolerance": 40,
        }),
    }
    strategy_class, strategy_params = strategy_map[args.strategy]

    # --- REFRESH CONFIG ---
    # Ambil dari config.py, default 4 jam jika tidak ada
    refresh_hours = getattr(config, 'REFRESH_HOURS', 4) 
    refresh_seconds = refresh_hours * 3600
    
    # Timer Awal
    last_refresh_time = time.time()

    engine = None # Inisialisasi variabel engine di luar loop

    # ==========================================================================
    # OUTER LOOP: SESSION MANAGER (Untuk Auto Refresh)
    # ==========================================================================
    try:
        while True:
            # 1. TENTUKAN DAFTAR KOIN
            # Pass args.sort ke fungsi helper
            current_symbols = get_target_symbols(args.use_scanner, args.top_n, args.symbols, args.sort)
            
            # Display Status
            equity_pct = getattr(config, 'ENTRY_EQUITY_PERCENT', 0.05)
            leverage = getattr(config, 'TARGET_LEVERAGE', 10)
            
            print("\n===== CRYPTO ENGINE SESSION STARTED =====")
            print(f"Strategy   : {args.strategy}")
            print(f"Mode       : {args.mode.upper()}")
            print(f"Watchlist  : {len(current_symbols)} Symbols (Active Volatility)")
            print(f"List       : {current_symbols}")
            print("-" * 40)
            print(f"Auto Refresh: Every {refresh_hours} Hours")
            print(f"Leverage    : {leverage}x")
            print(f"Entry Size  : {equity_pct*100}% Equity")
            print("=========================================\n")

            # 2. INISIALISASI ENGINE
            engine = LiveEngineScreeningCrypto(
                strategy_class=strategy_class,
                symbols=current_symbols,
                timeframe=args.timeframe, 
                bars=args.bars,
                mode=args.mode,
                strategy_params=strategy_params
            )

            # 3. CONNECT
            if engine.mode != "paper":
                try:
                    engine.connect()
                    engine._send_telegram(f"🔄 <b>AUTO REFRESH</b>\nNew Session Started.\nWatchlist: {len(current_symbols)} Pairs")
                except Exception as e:
                    print(f"Connection Error: {e}. Retrying in 10s...")
                    time.sleep(10)
                    continue

            # ======================================================================
            # INNER LOOP: TRADING EXECUTION (Pengganti engine.start())
            # Kita jalankan manual agar bisa di-break untuk refresh
            # ======================================================================
            engine.logger.info("===== ENGINE SESSION STARTED =====")
            
            while True:
                # --- A. CEK WAKTU REFRESH ---
                if args.use_scanner: 
                    elapsed = time.time() - last_refresh_time
                    if elapsed > refresh_seconds:
                        # Cek apakah ada posisi terbuka?
                        # Kita harus iterasi dictionary current_position
                        open_positions = []
                        for sym, pos in engine.current_position.items():
                            if pos is not None:
                                open_positions.append(sym)
                        
                        if not open_positions:
                            engine.logger.info(f"[AUTO-REFRESH] Time limit ({refresh_hours}h) reached. No positions. Refreshing...")
                            last_refresh_time = time.time()
                            break # KELUAR DARI INNER LOOP -> BALIK KE OUTER LOOP (SCAN ULANG)
                        else:
                            engine.logger.info(f"[AUTO-REFRESH] Time limit reached but positions open: {open_positions}. Delaying refresh...")
                            # Reset timer sedikit (misal tambah 5 menit) biar gak spam log
                            last_refresh_time = time.time() - refresh_seconds + 300 

                # --- B. LOGIC TRADING (PERSIS SAMA DENGAN ENGINE) ---
                trading_open = engine._is_trading_time()
                table_rows = []

                for symbol in engine.symbols:
                    # ---------------------------------------------------------
                    # ANTI-BAN PROTECTION: SLEEP ANTAR SIMBOL
                    # ---------------------------------------------------------
                    time.sleep(1.0) # Jeda 1 detik per simbol agar tidak dianggap SPAM
                    # ---------------------------------------------------------

                    # 1. Get Price (Lightweight)
                    try:
                        price = engine.client.get_ticker_price(symbol)
                    except: price = 0
                    
                    if price == 0: 
                        table_rows.append([symbol, "ERR", 0, "-", "-"])
                        continue

                    # 2. Manage Position (Trailing, BEP, Exit)
                    if engine.current_position[symbol]:
                        engine.monitor_position(symbol, price)
                        
                        # Check Virtual Exit Logic (Salinan dari engine)
                        pos = engine.current_position[symbol]
                        close_reason = None
                        if pos['direction'] == 1:
                            if price <= pos['sl']: close_reason = "SL/Trailing Hit"
                            elif price >= pos['tp']: close_reason = "TP Hit"
                        else:
                            if price >= pos['sl']: close_reason = "SL/Trailing Hit"
                            elif price <= pos['tp']: close_reason = "TP Hit"
                            
                        if close_reason:
                            # Jika trailing stop virtual kena
                            if "Trailing" in close_reason and engine.mode != "paper":
                                side = 'SELL' if pos['direction'] == 1 else 'BUY'
                                engine.client.create_order(symbol, side, 'MARKET', pos['amount'], reduce_only=True)
                                engine.client.cancel_all_open_orders(symbol)
                            
                            engine.logger.info(f"[{symbol}] Closed by Logic: {close_reason}")
                            engine._send_telegram(f"🏁 <b>CLOSED ({close_reason})</b>\n{symbol}")
                            engine.current_position[symbol] = None
                        else:
                            # Data tabel log
                            d_str = "BUY" if pos['direction'] == 1 else "SELL"
                            table_rows.append([symbol, price, d_str, pos['sl'], pos['tp']])
                    
                    # 3. Scan New Entry (Jika tidak ada posisi)
                    else:
                        if trading_open:
                            # Fetch Candle
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
                                        # Update table row status
                                        table_rows.append([symbol, price, "ENTRY", "PEND", "PEND"])
                                        continue
                        table_rows.append([symbol, price, 0, "-", "-"])

                # --- C. DISPLAY LOG ---
                if table_rows:
                    engine.logger.info("-" * 85)
                    engine.logger.info(f"{'SYMBOL':<10} | {'PRICE':<12} | {'POS':<6} | {'SL':<12} | {'TP':<12}")
                    engine.logger.info("-" * 85)
                    for r in table_rows:
                        # Helper function untuk format harga dinamis
                        def fmt(val):
                            if isinstance(val, str): return val
                            if val == 0: return "0.00"
                            if val < 1: return f"{val:.6f}" # Koin Micin (6 desimal)
                            if val < 10: return f"{val:.4f}" # Koin Kecil (4 desimal)
                            return f"{val:.2f}" # Koin Besar (2 desimal)

                        price_str = fmt(r[1])
                        sl_str = fmt(r[3])
                        tp_str = fmt(r[4])
                        
                        engine.logger.info(f"{r[0]:<10} | {price_str:<12} | {r[2]:<6} | {sl_str:<12} | {tp_str:<12}")
                
                if not trading_open: engine.logger.info("[FILTER] Trading Paused (Hours)")

                # Sleep Loop (Poll Interval)
                time.sleep(args.poll)

    # --- EXCEPTION HANDLING ---
    except KeyboardInterrupt:
        print("\n🚨 DETECTED CTRL+C! CLOSING ALL POSITIONS & EXITING...")
        
        # --- EMERGENCY CLOSE CALL ---
        if engine and engine.mode != "paper":
            engine.emergency_close_all()
        else:
            print("Engine not active or in Paper Mode. No real positions to close.")
            
        sys.exit(0)
        
    except Exception as e:
        print(f"Critical Error: {e}. Sleep 30s...")
        time.sleep(30)

if __name__ == "__main__":
    main()