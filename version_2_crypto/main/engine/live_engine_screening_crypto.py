import os
import time
import logging
import datetime as dt
import pandas as pd
import csv
import math
import requests
import hmac
import hashlib
from typing import Dict, List, Optional

# --- IMPORTS UTILS ---
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import config

# ==============================================================================
# 1. CLIENT CLASS (RAW API)
# ==============================================================================
class BinanceFuturesClient:
    def __init__(self, api_key, api_secret, base_url="https://testnet.binancefuture.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.recv_window = 5000
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/json'
        })

    def _generate_signature(self, params: Dict) -> str:
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        url = f"{self.base_url}{endpoint}"
        if params is None: params = {}
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['recvWindow'] = self.recv_window
            params['signature'] = self._generate_signature(params)

        try:
            if method == 'GET': response = self.session.get(url, params=params, timeout=10)
            elif method == 'POST': response = self.session.post(url, params=params, timeout=10)
            elif method == 'DELETE': response = self.session.delete(url, params=params, timeout=10)
            else: raise ValueError(f"Method {method} not supported")
            
            if response.status_code >= 400: 
                # Print error untuk debugging, tapi return empty agar flow tidak crash
                print(f"API Error {response.status_code}: {response.text}")
                return {}
            return response.json()
        except Exception as e:
            print(f"Request error: {e}")
            return {}

    def get_exchange_info(self) -> Dict:
        return self._request('GET', '/fapi/v1/exchangeInfo')

    def get_ticker_price(self, symbol: str) -> float:
        params = {'symbol': symbol}
        result = self._request('GET', '/fapi/v1/ticker/price', params)
        return float(result.get('price', 0))

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List:
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        return self._request('GET', '/fapi/v1/klines', params)

    def get_usdt_balance(self) -> float:
        balances = self._request('GET', '/fapi/v2/balance', signed=True)
        if not balances: return 0.0
        for balance in balances:
            if balance.get('asset') == 'USDT':
                return float(balance.get('availableBalance', 0))
        return 0.0

    def change_leverage(self, symbol: str, leverage: int) -> Dict:
        params = {'symbol': symbol, 'leverage': leverage}
        return self._request('POST', '/fapi/v1/leverage', params, signed=True)

    # --- UPDATE: Create Order Supports SL/TP Params ---
    def create_order(self, symbol: str, side: str, order_type: str, quantity: float, 
                     reduce_only: bool = False, sl_price: float = None, tp_price: float = None) -> Dict:
        """
        Mengirim order ke Binance.
        Jika sl_price / tp_price diisi, order akan dikirim sebagai OTO (One-Triggers-Other) 
        atau Strategi order jika didukung, namun di Raw API futures standar,
        SL/TP biasanya dikirim sebagai order terpisah (STOP_MARKET / TAKE_PROFIT_MARKET).
        
        Disini kita gunakan pendekatan pengiriman BATCH atau Sequential.
        Untuk kesederhanaan dan stabilitas, kita kirim Entry dulu, lalu kirim SL/TP.
        """
        # 1. Kirim ENTRY Order
        params = {'symbol': symbol, 'side': side, 'type': order_type, 'quantity': quantity}
        if reduce_only: params['reduceOnly'] = 'true'
        
        entry_res = self._request('POST', '/fapi/v1/order', params, signed=True)
        
        # Jika Entry Gagal, stop
        if not entry_res or 'orderId' not in entry_res:
            return entry_res

        # 2. Jika Entry Sukses & Ada SL/TP, Kirim Order Proteksi
        # Kita perlu tahu arah posisi (BUY -> SL/TP nya SELL, dan sebaliknya)
        close_side = 'SELL' if side == 'BUY' else 'BUY'
        
        if sl_price:
            sl_params = {
                'symbol': symbol, 'side': close_side, 'type': 'STOP_MARKET',
                'stopPrice': sl_price, 'closePosition': 'true' # Close full position
            }
            self._request('POST', '/fapi/v1/order', sl_params, signed=True)
            
        if tp_price:
            tp_params = {
                'symbol': symbol, 'side': close_side, 'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': tp_price, 'closePosition': 'true'
            }
            self._request('POST', '/fapi/v1/order', tp_params, signed=True)

        return entry_res

    def cancel_all_open_orders(self, symbol: str):
        # Hapus semua SL/TP pending jika posisi diclose manual/terkena salah satu
        self._request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': symbol}, signed=True)


# ==============================================================================
# 2. MAIN ENGINE
# ==============================================================================
class LiveEngineScreeningCrypto:
    def __init__(
        self,
        strategy_class,
        symbols: list,
        timeframe,
        bars=200,
        mode="paper",
        log_file=None,
        strategy_params=None
    ):
        self.strategy_class = strategy_class
        self.symbols = [s.replace("/", "") for s in symbols]
        self.timeframe = timeframe 
        self.bars = bars
        self.mode = mode
        self.strategy_params = strategy_params or {}

        # Client Setup
        api_key = getattr(config, 'API_KEY_BINANCE', '')
        secret_key = getattr(config, 'SECRET_KEY_BINANCE', '')
        testnet_url = "https://testnet.binancefuture.com"
        self.client = BinanceFuturesClient(api_key, secret_key, base_url=testnet_url)
        
        self.symbol_precision = {} 
        self.current_position = {sym: None for sym in self.symbols}
        
        # --- CONFIG FEATURE LOGGING ---
        self.ts_pct = getattr(config, "TRAILING_STOP_PERCENT", 0.0)
        # Ambil config BEP, default 50% (0.5) dari jarak TP
        self.bep_trigger_pct = getattr(config, "BEP_TRIGGER_PCT", 0.5) 
        
        # Setup Logging
        self.log_file = log_file or "logs/live_screening_crypto.log"
        self.trade_csv = "logs/trades_crypto.csv"
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

        self.logger = logging.getLogger("LiveEngineCrypto")
        self.logger.setLevel(logging.INFO)
        if self.logger.hasHandlers(): self.logger.handlers.clear()
        
        fh = logging.FileHandler(self.log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [LIVE] %(message)s"))
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("[LIVE] %(message)s"))
        self.logger.addHandler(sh)

        self.symbol_loggers = {}
        for sym in self.symbols:
            s_log = logging.getLogger(f"crypto_{sym}")
            s_log.setLevel(logging.INFO)
            if s_log.hasHandlers(): s_log.handlers.clear()
            fh2 = logging.FileHandler(os.path.join(os.path.dirname(self.log_file), f"{sym}.log"))
            fh2.setFormatter(logging.Formatter("%(asctime)s [LIVE] %(message)s"))
            s_log.addHandler(fh2)
            self.symbol_loggers[sym] = s_log

        # --- LOGGING FEATURE STATUS ---
        self.logger.info("===== LiveEngineCrypto Initialized =====")
        self.logger.info(f"Mode: {self.mode.upper()}")
        
        if self.ts_pct > 0:
            self.logger.info(f"Feature: Trailing Stop ACTIVE ({self.ts_pct*100}%)")
        else:
            self.logger.info("Feature: Trailing Stop DISABLED")
            
        self.logger.info(f"Feature: Auto Break-Even ACTIVE (Trigger @ {self.bep_trigger_pct*100}% towards TP)")

        # Integrations
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
                    header = ["timestamp", "symbol", "direction", "entry", "sl", "tp", "volume", "status", "retcode", "comment", "sl_ratio", "sl_pct", "timeframe"]
                    self.sheet_instance.append_row(header)
            except: self.use_gsheet = False

        self.strategies = {}
        for sym in self.symbols:
            self.strategies[sym] = self.strategy_class(params=self.strategy_params)

        if not os.path.exists(self.trade_csv):
            with open(self.trade_csv, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["timestamp", "symbol", "direction", "entry", "sl", "tp", "volume", "status", "retcode", "comment", "sl_ratio", "sl_pct", "timeframe"])

    def connect(self):
        self.logger.info("Connecting to Binance Futures...")
        info = self.client.get_exchange_info()
        if 'symbols' in info:
            for s in info['symbols']:
                if s['symbol'] in self.symbols:
                    self.symbol_precision[s['symbol']] = {
                        'qty': s['quantityPrecision'], 'price': s['pricePrecision']
                    }
        
        lev = getattr(config, 'TARGET_LEVERAGE', 5)
        for sym in self.symbols: 
            self.client.change_leverage(sym, lev)
        
        bal = self.client.get_usdt_balance()
        self.logger.info(f"Connected. Available USDT: {bal}")

    # =====================================================
    # HELPERS
    # =====================================================
    def _send_telegram(self, message):
        if not self.use_telegram: return
        try: requests.post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", 
                      data={"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}, timeout=5)
        except: pass

    def _log_trade_row(self, timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment, sl_ratio="-", sl_pct="-", timeframe="-"):
        with open(self.trade_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment, sl_ratio, sl_pct, timeframe])
        
        if self.use_gsheet and self.sheet_instance:
            try: self.sheet_instance.append_row([str(timestamp), str(symbol), int(direction), str(entry), str(sl), str(tp), str(volume), str(status), str(retcode), str(comment), str(sl_ratio), str(sl_pct), str(timeframe)])
            except: pass
        
        d = "BUY" if direction == 1 else "SELL"
        self.symbol_loggers[symbol].info(f"[LOG] {symbol} {d} | Entry={entry} | SL={sl} | Status={status}")

    def _is_trading_time(self):
        now_utc = dt.datetime.utcnow()
        hour_wib = (now_utc + dt.timedelta(hours=7)).hour
        return hour_wib not in [0, 4, 5, 6, 12]

    # =====================================================
    # LOGIC: MONITORING (BEP & TRAILING)
    # =====================================================
    def monitor_position(self, symbol, current_price):
        pos = self.current_position[symbol]
        if not pos: return

        # 1. AUTO BREAK-EVEN CHECK
        # Cek apakah fitur sudah aktif (is_be = True) atau belum
        if not pos.get('is_be', False):
            self.check_auto_breakeven(symbol, current_price, pos)

        # 2. VIRTUAL TRAILING STOP
        if self.ts_pct > 0:
            self.apply_trailing_stop(symbol, current_price, pos)

    def check_auto_breakeven(self, symbol, current_price, pos):
        """
        Geser SL ke Entry jika harga sudah profit X% dari target TP.
        """
        direction = pos['direction']
        entry = pos['entry']
        tp = pos['tp']
        
        # Hitung jarak Entry ke TP (Max Potential Profit)
        total_dist = abs(tp - entry)
        
        # Hitung profit saat ini (jarak)
        current_profit_dist = 0
        if direction == 1: # BUY
            current_profit_dist = current_price - entry
        else: # SELL
            current_profit_dist = entry - current_price
            
        # Hitung Persentase Pencapaian
        # Jika profit > (Total Jarak * Trigger %), maka geser SL
        target_dist = total_dist * self.bep_trigger_pct
        
        if current_profit_dist > target_dist:
            # Hitung New SL (Entry + sedikit buffer fee)
            new_sl = 0
            if direction == 1:
                new_sl = entry * 1.001 # Sedikit di atas entry
            else:
                new_sl = entry * 0.999 # Sedikit di bawah entry
                
            # Update SL di Exchange (Modify Order)
            # Di Raw API, cara termudah adalah Cancel Old SL -> Place New SL
            if self.mode != "paper":
                # 1. Cancel semua open order (SL lama)
                self.client.cancel_all_open_orders(symbol)
                # 2. Pasang SL baru
                close_side = 'SELL' if direction == 1 else 'BUY'
                params = {
                    'symbol': symbol, 'side': close_side, 'type': 'STOP_MARKET',
                    'stopPrice': new_sl, 'closePosition': 'true'
                }
                self.client._request('POST', '/fapi/v1/order', params, signed=True)
                # (Opsional) Pasang TP ulang jika TP juga kecancel
                # Untuk simple engine, kita biarkan TP manual atau pasang lagi disini
            
            # Update Memory
            self.current_position[symbol]['sl'] = new_sl
            self.current_position[symbol]['is_be'] = True
            
            self.logger.info(f"[BEP] {symbol} Moved SL to Break-Even: {new_sl}")
            self._send_telegram(f"🛡️ <b>AUTO BREAK-EVEN</b>\n{symbol}\nSL Moved to Entry!")

    def apply_trailing_stop(self, symbol, current_price, pos):
        dist = current_price * self.ts_pct
        direction = pos['direction']
        new_sl = None

        if direction == 1: # BUY
            if current_price > pos['entry']: 
                potential_sl = current_price - dist
                if potential_sl > pos['sl']:
                    new_sl = potential_sl
        else: # SELL
            if current_price < pos['entry']:
                potential_sl = current_price + dist
                if pos['sl'] == 0 or potential_sl < pos['sl']:
                    new_sl = potential_sl

        if new_sl:
            # Update Memory (Virtual)
            self.current_position[symbol]['sl'] = new_sl
            self.logger.info(f"[TRAILING] {symbol} Virtual SL updated: {new_sl}")
            # Note: Kita tidak update SL di Exchange untuk Trailing agar tidak spamming API limit.
            # SL Exchange tetap di BEP/Original sebagai hard stop. 
            # Trailing dieksekusi oleh bot (Client Side).

    # =====================================================
    # LOGIC: ENTRY
    # =====================================================
    def execute_entry(self, symbol, sig, price):
        # 1. Hitung SL & TP
        sl_pct = getattr(config, 'SL_PERCENTAGE', 0.02)
        sl_dist = price * sl_pct
        
        ratio_str = getattr(config, 'SLTP_RATIO', "1:2")
        parts = ratio_str.split(":")
        tp_mult = float(parts[1]) / float(parts[0])
        tp_dist = sl_dist * tp_mult

        if sig == 1:
            sl = price - sl_dist
            tp = price + tp_dist
        else:
            sl = price + sl_dist
            tp = price - tp_dist
            
        # Precision Adjust untuk Harga SL/TP
        price_prec = self.symbol_precision.get(symbol, {}).get('price', 2)
        sl = round(sl, price_prec)
        tp = round(tp, price_prec)

        # 2. Hitung Qty
        bal = self.client.get_usdt_balance()
        equity_pct = getattr(config, 'ENTRY_EQUITY_PERCENT', 0.05)
        lev = getattr(config, 'TARGET_LEVERAGE', 5)
        
        notional = bal * equity_pct * lev
        raw_qty = notional / price
        
        # Precision Qty
        qty_prec = self.symbol_precision.get(symbol, {}).get('qty', 3)
        qty = round(raw_qty, qty_prec)

        if (qty * price) < 5.0: return 

        # 3. Kirim Order (Entry + SL + TP Exchange Side)
        side = 'BUY' if sig == 1 else 'SELL'
        real_entry = price
        status = "OK"
        retcode = 0

        if self.mode == "paper":
            self.logger.info(f"[PAPER] Entry {symbol} {side} Qty={qty} (SL/TP Simulated)")
        else:
            # Kirim Entry dengan parameter SL & TP
            res = self.client.create_order(
                symbol, side, 'MARKET', qty, 
                sl_price=sl, tp_price=tp # Kirim params ini
            )
            
            if not res or 'orderId' not in res: 
                status = "REJECTED"
                retcode = 400
            else:
                real_entry = float(res.get('avgPrice', price))
                if real_entry == 0: real_entry = price 

        # 4. Save Position
        if status == "OK":
            self.current_position[symbol] = {
                'direction': sig,
                'entry': real_entry,
                'sl': sl,
                'tp': tp,
                'amount': qty,
                'is_be': False # Status Break Even
            }
            
            self._log_trade_row(dt.datetime.utcnow().isoformat(), symbol, sig, real_entry, sl, tp, qty, status, retcode, "Market Entry", ratio_str, f"{sl_pct:.1%}", str(self.timeframe))
            self._send_telegram(f"🚀 <b>ENTRY {side}</b>\n{symbol}\nPrice: {real_entry}\nSL: {sl}\nTP: {tp}")

    # =====================================================
    # MAIN LOOP
    # =====================================================
    def start(self, poll_interval=1.0):
        if self.mode != "paper": self.connect()
        self.logger.info("===== CRYPTO ENGINE STARTED (SINGLE LOOP) =====")
        self._send_telegram(f"🤖 <b>BOT STARTED</b>\nSymbols: {self.symbols}\nTF: {self.timeframe}")

        while True:
            try:
                trading_open = self._is_trading_time()
                table_rows = []

                for symbol in self.symbols:
                    # 1. Get Realtime Price
                    price = self.client.get_ticker_price(symbol)
                    if price == 0: 
                        table_rows.append([symbol, "ERR", 0, "-", "-"])
                        continue

                    # 2. Manage Position
                    if self.current_position[symbol]:
                        # Cek apakah posisi masih ada di exchange (opsional, via REST berat)
                        # Kita gunakan tracking harga lokal dulu
                        pos = self.current_position[symbol]
                        
                        # Jalankan Monitor Logic (BEP & Trailing)
                        self.monitor_position(symbol, price)
                        
                        # Check Virtual Exit (Trailing Stop Only)
                        # Hard SL/TP sudah dihandle exchange, tapi kita perlu update status lokal jika kena
                        # Disini kita asumsikan jika harga lewat SL/TP, posisi sudah closed di exchange
                        close_reason = None
                        if pos['direction'] == 1:
                            if price <= pos['sl']: close_reason = "SL/Trailing Hit"
                            elif price >= pos['tp']: close_reason = "TP Hit"
                        else:
                            if price >= pos['sl']: close_reason = "SL/Trailing Hit"
                            elif price <= pos['tp']: close_reason = "TP Hit"
                            
                        if close_reason:
                            # Jika trailing stop virtual kena, kita kirim perintah close market
                            # (Karena SL exchange mungkin masih di bawah)
                            if "Trailing" in close_reason and self.mode != "paper":
                                side = 'SELL' if pos['direction'] == 1 else 'BUY'
                                self.client.create_order(symbol, side, 'MARKET', pos['amount'], reduce_only=True)
                                self.client.cancel_all_open_orders(symbol) # Bersihkan sisa order
                            
                            self.logger.info(f"[{symbol}] Closed by Logic: {close_reason}")
                            self._send_telegram(f"🏁 <b>CLOSED ({close_reason})</b>\n{symbol}")
                            self.current_position[symbol] = None
                        
                        else:
                            # Tampilkan di tabel log
                            d_str = "BUY" if pos['direction'] == 1 else "SELL"
                            table_rows.append([symbol, price, d_str, pos['sl'], pos['tp']])
                    
                    # 3. Scan New Entry
                    else:
                        if trading_open:
                            raw_klines = self.client.get_klines(symbol, self.timeframe, limit=self.bars + 5)
                            if raw_klines:
                                data = []
                                for k in raw_klines:
                                    data.append([int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
                                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                                
                                sig_df = self.strategies[symbol].generate_signals(df)
                                if not sig_df.empty:
                                    sig = int(sig_df['signal'].iloc[-1])
                                    if sig != 0:
                                        self.execute_entry(symbol, sig, price)
                                        table_rows.append([symbol, price, "ENTRY", "PEND", "PEND"])
                                        continue

                        table_rows.append([symbol, price, 0, "-", "-"])

                # 4. Print Log Table
                if table_rows:
                    self.logger.info("-" * 65)
                    self.logger.info(f"{'SYMBOL':<10} | {'PRICE':<10} | {'POS':<6} | {'SL':<10} | {'TP':<10}")
                    self.logger.info("-" * 65)
                    for r in table_rows:
                        p = f"{r[1]:.2f}" if isinstance(r[1], float) else r[1]
                        sl = f"{r[3]:.2f}" if isinstance(r[3], float) else r[3]
                        tp = f"{r[4]:.2f}" if isinstance(r[4], float) else r[4]
                        self.logger.info(f"{r[0]:<10} | {p:<10} | {r[2]:<6} | {sl:<10} | {tp:<10}")
                
                if not trading_open: self.logger.info("[FILTER] Trading Paused (Hours)")

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                self.logger.info("Stopping...")
                break
            except Exception as e:
                self.logger.error(f"Loop Error: {e}")
                time.sleep(poll_interval)