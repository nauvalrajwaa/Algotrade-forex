# engine/live_engine_screening_crypto.py

import os
import time
import logging
import datetime as dt
import pandas as pd
import csv
import math
import ccxt  # Library untuk Crypto Exchange

# --- IMPORTS UTILS ---
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests

import config

class LiveEngineScreeningCrypto:
    def __init__(
        self,
        strategy_class,
        symbols: list,
        timeframe,
        bars=200,
        mode="paper",
        risk_per_trade=0.01,
        log_file=None,
        strategy_params=None
    ):
        self.strategy_class = strategy_class
        self.symbols = symbols  # Format harus: 'BTC/USDT' (ccxt format)
        self.timeframe = timeframe # Format ccxt: '15m', '1h', etc
        self.bars = bars
        self.mode = mode
        self.risk_per_trade = risk_per_trade
        self.strategy_params = strategy_params or {}

        # --- INITIALIZE EXCHANGE (BINANCE) ---
        # Menggunakan config dari config.py
        exchange_config = {
            'apiKey': getattr(config, 'API_KEY_BINANCE', ''),
            'secret': getattr(config, 'SECRET_KEY_BINANCE', ''),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Menggunakan Futures (bisa Long/Short)
            }
        }
        self.exchange = ccxt.binance(exchange_config)

        # --- GLOBAL LOG & CSV ---
        self.log_file = log_file or "logs/live_screening_crypto.log"
        self.trade_csv = "logs/trades_crypto.csv"

        log_dir = os.path.dirname(self.log_file) or "."
        os.makedirs(log_dir, exist_ok=True)

        # --- LOGGER ---
        self.logger = logging.getLogger("LiveEngineCrypto")
        self.logger.setLevel(logging.INFO)
        if self.logger.hasHandlers(): self.logger.handlers.clear()
        
        fh = logging.FileHandler(self.log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [CRYPTO] %(message)s"))
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("[CRYPTO] %(message)s"))
        self.logger.addHandler(sh)

        # --- PER SYMBOL LOGGER ---
        self.symbol_loggers = {}
        for sym in self.symbols:
            safe_sym = sym.replace("/", "")
            s_log = logging.getLogger(f"crypto_{safe_sym}")
            s_log.setLevel(logging.INFO)
            if s_log.hasHandlers(): s_log.handlers.clear()
            fh2 = logging.FileHandler(os.path.join(log_dir, f"{safe_sym}.log"))
            fh2.setFormatter(logging.Formatter("%(asctime)s [CRYPTO] %(message)s"))
            s_log.addHandler(fh2)
            self.symbol_loggers[sym] = s_log

        self.logger.info("===== LiveEngineCrypto initialized =====")

        # --- TELEGRAM & GSHEET SETUP ---
        self.use_telegram = getattr(config, "USE_TELEGRAM", False)
        self.tg_token = getattr(config, "TELEGRAM_BOT_TOKEN", "")
        self.tg_chat_id = getattr(config, "TELEGRAM_CHAT_ID", "")
        
        self.use_gsheet = getattr(config, "USE_GSHEET", False)
        self.sheet_instance = None
        if self.use_gsheet:
            try:
                scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(config.GSHEET_CREDENTIAL_FILE, scope)
                client = gspread.authorize(creds)
                self.sheet_instance = client.open_by_key(config.GSHEET_ID).sheet1
                if not self.sheet_instance.row_values(1):
                    header = ["timestamp", "symbol", "direction", "entry", "sl", "tp", "amount", "status", "comment", "sl_ratio", "base_pips", "timeframe"]
                    self.sheet_instance.append_row(header)
            except Exception as e:
                self.logger.error(f"GSheet Error: {e}")
                self.use_gsheet = False

        # --- Strategy Instances ---
        self.strategies = {}
        for sym in self.symbols:
            self.strategies[sym] = self.strategy_class(params=self.strategy_params)

        # --- CSV Init ---
        if not os.path.exists(self.trade_csv):
            with open(self.trade_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "symbol", "direction", "entry", "sl", "tp", "amount", "status", "comment", "sl_ratio", "base_pips", "timeframe"])

        # Local State Tracking (Since Crypto API rate limit is strict, we mirror state locally)
        self.current_position = {sym: None for sym in self.symbols}
        self.markets_loaded = False


    # =====================================================
    # CONNECT & MARKET DATA
    # =====================================================
    def connect(self):
        try:
            self.exchange.load_markets()
            self.markets_loaded = True
            bal = self.exchange.fetch_balance()
            usdt_free = bal['USDT']['free'] if 'USDT' in bal else 0
            self.logger.info(f"Connected to Binance Futures. Free USDT: {usdt_free}")
        except Exception as e:
            raise RuntimeError(f"Binance Connect Failed: {e}")

    def fetch(self, symbol):
        # Fetch OHLCV
        # limit=bars + sedikit buffer
        ohlcv = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=self.bars + 10)
        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        return df

    def _get_tick_size(self, symbol):
        # Pengganti _pip_size di Forex
        market = self.exchange.market(symbol)
        return market['precision']['price']

    def _get_min_amount(self, symbol):
        market = self.exchange.market(symbol)
        return market['limits']['amount']['min']

    # =====================================================
    # UTILS: LOGGING & TELEGRAM
    # =====================================================
    def _send_telegram(self, message):
        if not self.use_telegram: return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        data = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}
        try: requests.post(url, data=data, timeout=5)
        except: pass

    def _log_trade_row(self, timestamp, symbol, direction, entry, sl, tp, amount, status, comment, sl_ratio="-", base_pips="-", timeframe="-"):
        # CSV
        with open(self.trade_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([timestamp, symbol, direction, entry, sl, tp, amount, status, comment, sl_ratio, base_pips, timeframe])
        # GSheet
        if self.use_gsheet and self.sheet_instance:
            try:
                self.sheet_instance.append_row([str(timestamp), str(symbol), int(direction), str(entry), str(sl), str(tp), str(amount), str(status), str(comment), str(sl_ratio), str(base_pips), str(timeframe)])
            except: pass
        
        d_str = "BUY" if direction == 1 else "SELL"
        msg = f"[LOG] {symbol} {d_str} | Entry={entry} | SL={sl} | Status={status}"
        self.logger.info(msg)
        self.symbol_loggers[symbol].info(msg)

    # =====================================================
    # TIME FILTER
    # =====================================================
    def _is_trading_time(self):
        now_utc = dt.datetime.utcnow()
        now_wib = now_utc + dt.timedelta(hours=7)
        hour = now_wib.hour
        forbidden_hours = [0, 4, 5, 6, 12] # 12-1 malam, 4-7 pagi, 12-13 siang
        return hour not in forbidden_hours

    # =====================================================
    # LOT SIZING (QUANTITY)
    # =====================================================
    def compute_quantity(self, symbol, entry_price, sl_distance):
        if sl_distance == 0: return 0
        
        # Ambil Balance
        try:
            bal = self.exchange.fetch_balance()
            balance = bal['USDT']['total'] # Gunakan Total Balance (Margin + Free)
        except:
            return 0

        risk_amount = balance * self.risk_per_trade
        
        # Risk = |Entry - SL| * Quantity
        # Quantity = Risk / |Entry - SL|
        raw_qty = risk_amount / sl_distance
        
        # Adjust precision
        market = self.exchange.market(symbol)
        qty = self.exchange.amount_to_precision(symbol, raw_qty)
        qty = float(qty)

        # Cek minimum order notional (misal minimal order 5 USDT)
        min_cost = market['limits']['cost']['min'] if market['limits']['cost']['min'] else 5.0
        if (qty * entry_price) < min_cost:
            return 0 # Skip jika lot terlalu kecil (di bawah $5)

        return qty

    # =====================================================
    # SEND ORDER (CRYPTO)
    # =====================================================
    def send_order(self, symbol, direction, sl, tp, amount, sl_ratio, base_pips):
        timestamp = dt.datetime.utcnow().isoformat()
        tf_str = str(self.timeframe)
        side = 'buy' if direction == 1 else 'sell'
        
        if self.mode == "paper":
            self.logger.info(f"[PAPER] {symbol} {side.upper()} Amt={amount} SL={sl}")
            self._log_trade_row(timestamp, symbol, direction, None, sl, tp, amount, "PAPER_ENTRY", "Paper Mode", sl_ratio, base_pips, tf_str)
            return True

        # REAL EXECUTION
        try:
            # 1. Market Order untuk Entry
            order = self.exchange.create_order(symbol, 'market', side, amount)
            entry_price = float(order['average']) if order['average'] else float(order['price'])
            
            # Catatan: Di Binance Futures, SL/TP biasanya order terpisah (STOP_MARKET / TAKE_PROFIT_MARKET)
            # Untuk engine screening simple ini, kita akan manage SL/TP secara Client-Side (Bot monitor harga)
            # agar logic Trailing dan Partial lebih mudah dikontrol tanpa ribet manage Order ID di exchange.
            
            self._log_trade_row(timestamp, symbol, direction, entry_price, sl, tp, amount, "FILLED", "Market Entry", sl_ratio, base_pips, tf_str)
            
            # Telegram Notif
            icon = "🚀"
            self._send_telegram(f"{icon} <b>CRYPTO ENTRY {side.upper()}</b>\nSymbol: {symbol}\nPrice: {entry_price}\nAmt: {amount}\nSL: {sl}\nTF: {tf_str}")
            
            # Update Local Position dengan Entry Price yang real
            return entry_price 

        except Exception as e:
            self.logger.error(f"Order Failed {symbol}: {e}")
            self._log_trade_row(timestamp, symbol, direction, None, sl, tp, amount, "ERROR", str(e), sl_ratio, base_pips, tf_str)
            return False

    # =====================================================
    # PARTIAL CLOSE
    # =====================================================
    def _apply_partial_close(self, symbol, current_price):
        pos = self.current_position[symbol]
        if not pos or self.mode == "paper" or pos.get("partial_closed", False): return

        # Hitung Pips (Points)
        tick_size = self._get_tick_size(symbol)
        direction = pos['direction']
        
        if direction == 1: profit_points = (current_price - pos['entry']) 
        else: profit_points = (pos['entry'] - current_price)

        # Konversi Base Pips (Config) ke Price Distance
        # Asumsi: Config BASE_PIPS 50 di Crypto = 50 * TickSize
        # (User harus setting BASE_PIPS besar di crypto, misal 5000 untuk BTC)
        base_dist = pos['base_pips'] * tick_size
        target_dist = base_dist * 0.5 

        if profit_points >= target_dist:
            # Execute Partial
            amt_to_close = float(self.exchange.amount_to_precision(symbol, pos['amount'] * 0.5))
            
            # Check Min Amount
            if amt_to_close < self._get_min_amount(symbol): return 

            try:
                side = 'sell' if direction == 1 else 'buy' # Close logic
                self.exchange.create_order(symbol, 'market', side, amt_to_close, params={'reduceOnly': True})
                
                self.logger.info(f"[PARTIAL] {symbol} Closed {amt_to_close}")
                self.current_position[symbol]['partial_closed'] = True
                self.current_position[symbol]['amount'] -= amt_to_close
                
                self._send_telegram(f"💰 <b>PARTIAL CLOSE 50%</b>\n{symbol}\nClosed: {amt_to_close}")
                self._log_trade_row(dt.datetime.utcnow().isoformat(), symbol, direction, pos['entry'], pos['sl'], pos['tp'], amt_to_close, "PARTIAL", "Hit 50%", pos['sl_ratio'], pos['base_pips'], str(self.timeframe))
            except Exception as e:
                self.logger.error(f"Partial Close Error: {e}")

    # =====================================================
    # TRAILING STOP
    # =====================================================
    def _apply_trailing_stop(self, symbol, current_price):
        ts_pips = getattr(config, "TRAILING_STOP_PIP", 0)
        if ts_pips <= 0: return

        pos = self.current_position[symbol]
        if not pos or self.mode == "paper": return

        tick_size = self._get_tick_size(symbol)
        ts_dist = ts_pips * tick_size # Convert pips to price distance
        
        direction = pos['direction']
        new_sl = None

        if direction == 1: # BUY
            if (current_price - pos['entry']) > ts_dist:
                pot_sl = current_price - ts_dist
                if pot_sl > pos['sl']: new_sl = pot_sl
        else: # SELL
            if (pos['entry'] - current_price) > ts_dist:
                pot_sl = current_price + ts_dist
                if (pos['sl'] == 0) or (pot_sl < pos['sl']): new_sl = pot_sl

        if new_sl:
            # Client side update only (karena kita tidak pasang SL order di exchange)
            self.current_position[symbol]['sl'] = new_sl
            self.logger.info(f"[TRAILING] {symbol} New SL: {new_sl}")
            self._send_telegram(f"🛡️ <b>TRAILING UPDATE</b>\n{symbol}\nNew SL: {new_sl}")
            # Log update

    # =====================================================
    # UPDATE POSITION (CLIENT SIDE SL/TP CHECK)
    # =====================================================
    def update_position(self, symbol, current_price):
        pos = self.current_position[symbol]
        if not pos: return

        direction = pos['direction']
        hit_type = None
        
        if direction == 1: # BUY
            if current_price <= pos['sl']: hit_type = "SL_HIT"
            elif current_price >= pos['tp']: hit_type = "TP_HIT"
        else: # SELL
            if current_price >= pos['sl']: hit_type = "SL_HIT"
            elif current_price <= pos['tp']: hit_type = "TP_HIT"

        if hit_type:
            if self.mode != "paper":
                try:
                    side = 'sell' if direction == 1 else 'buy'
                    self.exchange.create_order(symbol, 'market', side, pos['amount'], params={'reduceOnly': True})
                except Exception as e:
                    self.logger.error(f"Close Position Error {symbol}: {e}")
                    return

            # Log & Notify
            label = "PROFIT" if hit_type == "TP_HIT" else "LOSS"
            icon = "✅" if label == "PROFIT" else "❌"
            self._send_telegram(f"{icon} <b>CLOSED ({hit_type})</b>\n{symbol}\nPrice: {current_price}\nResult: {label}")
            self._log_trade_row(dt.datetime.utcnow().isoformat(), symbol, direction, pos['entry'], pos['sl'], pos['tp'], pos['amount'], hit_type, "Market Close", pos['sl_ratio'], pos['base_pips'], str(self.timeframe))
            
            self.current_position[symbol] = None


    # =====================================================
    # MAIN LOOP
    # =====================================================
    def start(self, poll_interval=10.0):
        if self.mode != "paper": self.connect()
        self.logger.info("===== CRYPTO ENGINE STARTED =====")
        self._send_telegram(f"🤖 <b>CRYPTO BOT STARTED</b>\nSymbols: {self.symbols}\nTF: {self.timeframe}")

        while True:
            try:
                # --- MANAGEMENT LOOP ---
                for symbol in self.symbols:
                    if self.current_position[symbol]:
                        ticker = self.exchange.fetch_ticker(symbol)
                        price = ticker['last']
                        self._apply_partial_close(symbol, price)
                        self._apply_trailing_stop(symbol, price)
                        self.update_position(symbol, price)

                # --- ENTRY LOOP ---
                trading_open = self._is_trading_time()
                
                table_rows = []
                for symbol in self.symbols:
                    df = self.fetch(symbol)
                    sig_df = self.strategies[symbol].generate_signals(df)
                    
                    if sig_df.empty: continue
                    sig = int(sig_df['signal'].iloc[-1])
                    price = float(sig_df['close'].iloc[-1])

                    if not trading_open: sig = 0

                    if sig == 0:
                        table_rows.append([symbol, price, 0, "-", "-"])
                        continue

                    # Hitung SL/TP Distance
                    tick_size = self._get_tick_size(symbol)
                    base_pips = config.BASE_PIPS
                    # Di Crypto, BASE_PIPS diartikan sebagai kelipatan Tick Size
                    # Misal Tick BTC 0.1, BASE_PIPS 5000 -> Distance 500 USDT
                    sl_dist = base_pips * tick_size
                    
                    ratio_str = config.SLTP_RATIO
                    parts = ratio_str.split(":")
                    tp_mult = float(parts[1]) / float(parts[0])
                    tp_dist = sl_dist * tp_mult

                    sl = price - sl_dist if sig == 1 else price + sl_dist
                    tp = price + tp_dist if sig == 1 else price - tp_dist

                    # Compute Quantity
                    amount = self.compute_quantity(symbol, price, sl_dist)
                    
                    if amount > 0:
                        real_entry = self.send_order(symbol, sig, sl, tp, amount, ratio_str, base_pips)
                        if real_entry: # Entry success (paper returns True, Live returns float price)
                            entry_p = real_entry if isinstance(real_entry, float) else price
                            self.current_position[symbol] = {
                                'direction': sig, 'entry': entry_p, 'sl': sl, 'tp': tp, 
                                'amount': amount, 'sl_ratio': ratio_str, 'base_pips': base_pips,
                                'partial_closed': False
                            }
                    
                    table_rows.append([symbol, price, sig, sl, tp])

                # Print Table
                if table_rows:
                    self.logger.info("-" * 50)
                    for r in table_rows: self.logger.info(f"{r[0]:<10} | {r[1]:<10} | {r[2]:<2} | {r[3]:<10}")
                
                if not trading_open: self.logger.info("[FILTER] Trading Paused (Hours)")

                time.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"Loop Error: {e}")
                time.sleep(poll_interval)