# engine/live_engine_screening_online.py

import os
import time
import logging
import datetime as dt
import numpy as np
import MetaTrader5 as mt5
import pandas as pd
import csv
import math # Diperlukan untuk pembulatan lot

# --- NEW IMPORTS UNTUK GOOGLE SHEETS & TELEGRAM ---
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests # Wajib install: pip install requests

import config


class LiveEngineScreening:
    def __init__(
        self,
        strategy_class,       # pakai class, bukan instance → tiap symbol punya instance sendiri
        mt5_path,
        symbols: list,
        timeframe,
        bars=200,
        mode="paper",
        risk_per_trade=0.01,
        log_file=None,
        max_daily_loss=0.05,
        max_drawdown=0.20,
        strategy_params=None   # <-- params untuk tiap strategy instance
    ):
        self.strategy_class = strategy_class
        self.mt5_path = mt5_path
        self.symbols = [s.upper() for s in symbols]
        self.timeframe = timeframe
        self.bars = bars
        self.mode = mode
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.strategy_params = strategy_params or {}

        # --- GLOBAL LOG & CSV ---
        self.log_file = log_file or config.LOG_FILE_SCREENING
        self.trade_csv = config.TRADE_CSV_SCREENING

        # logging directory
        log_dir = os.path.dirname(self.log_file) or "."
        os.makedirs(log_dir, exist_ok=True)

        # --- GLOBAL LOGGER ---
        self.logger = logging.getLogger("LiveEngineScreening")
        self.logger.setLevel(logging.INFO)
        # Clear existing handlers to prevent duplicate logs if re-initialized
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        fh = logging.FileHandler(self.log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [LIVE] %(message)s"))
        self.logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("[LIVE] %(message)s"))
        self.logger.addHandler(sh)

        # --- LOGGER PER SYMBOL ---
        self.symbol_log_files = {sym: os.path.join(log_dir, f"{sym}.log") for sym in self.symbols}
        self.symbol_loggers = {}
        for sym in self.symbols:
            sym_log = logging.getLogger(f"screening_{sym}")
            sym_log.setLevel(logging.INFO)
            if sym_log.hasHandlers():
                sym_log.handlers.clear() 
            fh2 = logging.FileHandler(self.symbol_log_files[sym])
            fh2.setFormatter(logging.Formatter("%(asctime)s [LIVE] %(message)s"))
            sym_log.addHandler(fh2)
            self.symbol_loggers[sym] = sym_log

        self.logger.info("===== LiveEngineScreening initialized =====")

        # --- TELEGRAM SETUP ---
        self.use_telegram = getattr(config, "USE_TELEGRAM", False)
        self.tg_token = getattr(config, "TELEGRAM_BOT_TOKEN", "")
        self.tg_chat_id = getattr(config, "TELEGRAM_CHAT_ID", "")

        # --- GOOGLE SHEETS SETUP ---
        self.use_gsheet = getattr(config, "USE_GSHEET", False)
        self.sheet_instance = None
        
        if self.use_gsheet:
            try:
                self.logger.info("Connecting to Google Sheets...")
                scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(config.GSHEET_CREDENTIAL_FILE, scope)
                client = gspread.authorize(creds)
                self.sheet_instance = client.open_by_key(config.GSHEET_ID).sheet1
                self.logger.info("Connected to Google Sheets successfully.")
                
                if not self.sheet_instance.row_values(1):
                    header = ["timestamp", "symbol", "direction", "entry", "sl", "tp", "volume", "status", "retcode", "comment", "sl_ratio", "base_pips", "timeframe"]
                    self.sheet_instance.append_row(header)
            except Exception as e:
                self.logger.error(f"Failed to connect to Google Sheets: {e}")
                self.use_gsheet = False

        # --- Prepare strategy ---
        self.strategies = {}
        for sym in self.symbols:
            self.strategies[sym] = self.strategy_class(params=self.strategy_params)

        # --- ensure CSV exists ---
        os.makedirs(os.path.dirname(self.trade_csv), exist_ok=True)
        if not os.path.exists(self.trade_csv):
            with open(self.trade_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "symbol", "direction", "entry", "sl", "tp", "volume", "status", "retcode", "comment", "sl_ratio", "base_pips", "timeframe"])

        self.connected = False
        self.current_position = {sym: None for sym in self.symbols}


    # =====================================================
    # CONNECT / DISCONNECT
    # =====================================================
    def connect(self):
        if not self.connected:
            if not mt5.initialize(self.mt5_path): raise RuntimeError("MT5 init failed")
            if mt5.account_info() is None: raise RuntimeError("MT5 account_info None")
            self.connected = True
            self.logger.info("Connected to MT5")

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.logger.info("Disconnected from MT5")
        self.connected = False

    def fetch(self, symbol):
        ohlc = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, self.bars)
        if ohlc is None: raise RuntimeError(f"No OHLC {symbol}")
        return pd.DataFrame(ohlc)

    def _pip_size(self, info):
        symbol = info.name.upper()
        if symbol == "XAUUSD": return 0.10
        if symbol in ("EURUSD", "GBPUSD"): return 0.00001
        if symbol == "GBPJPY": return 0.001
        return info.point * 10


    # =====================================================
    # TIME FILTER (RULE NO. 3)
    # =====================================================
    def _is_trading_time(self):
        """
        Mengembalikan True jika sekarang adalah jam trading yang diperbolehkan.
        Mengembalikan False jika masuk jam terlarang.
        WIB = UTC + 7
        """
        # Ambil waktu sekarang dalam UTC, lalu tambah 7 jam untuk WIB
        now_utc = dt.datetime.utcnow()
        now_wib = now_utc + dt.timedelta(hours=7)
        hour = now_wib.hour

        # Rules Jam Terlarang (WIB):
        # 00:00 - 01:00 (12-1 malam) -> hour 0
        # 04:00 - 07:00 (4-7 pagi) -> hour 4, 5, 6
        # 12:00 - 13:00 (12-13 siang) -> hour 12
        forbidden_hours = [0, 4, 5, 6, 12]

        if hour in forbidden_hours:
            return False
        return True


    # =====================================================
    # TELEGRAM SENDER
    # =====================================================
    def _send_telegram(self, message):
        if not self.use_telegram or not self.tg_token or not self.tg_chat_id: return
        url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
        data = {"chat_id": self.tg_chat_id, "text": message, "parse_mode": "HTML"}
        try: requests.post(url, data=data, timeout=5)
        except Exception as e: self.logger.error(f"Telegram Error: {e}")


    # =====================================================
    # LOG TRADE PER BARIS
    # =====================================================
    def _log_trade_row(self, timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment, sl_ratio="-", base_pips="-", timeframe="-"):
        with open(self.trade_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment, sl_ratio, base_pips, timeframe])

        if self.use_gsheet and self.sheet_instance:
            try:
                row_data = [str(timestamp), str(symbol), int(direction), str(entry), str(sl), str(tp), str(volume), str(status), str(retcode), str(comment), str(sl_ratio), str(base_pips), str(timeframe)]
                self.sheet_instance.append_row(row_data)
            except Exception as e: self.logger.error(f"GSheet Error: {e}")

        d = "BUY" if direction == 1 else "SELL"
        msg = (f"[LOG] {timestamp:<25} | {symbol:<8} | {d:<5} | entry={entry} | SL={sl} | status={status}")
        self.logger.info(msg)
        self.symbol_loggers[symbol].info(msg)


    # =====================================================
    # SEND ORDER
    # =====================================================
    def send_order(self, symbol, direction, sl, tp, volume, sl_ratio, base_pips):
        timestamp = dt.datetime.utcnow().isoformat()
        tf_str = str(self.timeframe)
        dir_str = "BUY" if direction == 1 else "SELL"

        if self.mode == "paper":
            msg = f"[PAPER] {symbol} {dir_str}, vol={volume}"
            self.logger.info(msg)
            self._log_trade_row(timestamp, symbol, direction, None, sl, tp, volume, "PAPER", None, "Paper mode", sl_ratio, base_pips, tf_str)
            return True

        open_positions = mt5.positions_get(symbol=symbol) or []
        if len(open_positions) >= config.MAX_OPEN_TRADES:
            self._log_trade_row(timestamp, symbol, direction, None, sl, tp, volume, "SKIPPED_MAX", None, "Max trades reached", sl_ratio, base_pips, tf_str)
            return False

        tick = mt5.symbol_info_tick(symbol)
        if tick is None: return False

        price = tick.ask if direction == 1 else tick.bid
        type_map = {1: mt5.ORDER_TYPE_BUY, -1: mt5.ORDER_TYPE_SELL}

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "type": type_map[direction],
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 55667788,
            "comment": "LiveEngineScreening",
            "type_filling": mt5.ORDER_FILLING_FOK
        }

        result = mt5.order_send(req)
        ret = result.retcode
        status = "OK" if ret == mt5.TRADE_RETCODE_DONE else "REJECTED"
        entry = price if status == "OK" else None

        self._log_trade_row(timestamp, symbol, direction, entry, sl, tp, volume, status, ret, result.comment, sl_ratio, base_pips, tf_str)

        if status == "OK":
            icon = "🚀"
            tg_msg = (
                f"{icon} <b>NEW ENTRY {dir_str}</b>\n"
                f"Symbol: {symbol}\nPrice: {entry}\nVol: {volume}\nSL: {sl}\nTP: {tp}\nTF: {tf_str}"
            )
            self._send_telegram(tg_msg)

        return (ret == mt5.TRADE_RETCODE_DONE)


    # =====================================================
    # LOT SIZING
    # =====================================================
    def compute_lot(self, symbol, price):
        info = mt5.symbol_info(symbol)
        if info is None: return None
        step = info.volume_step
        min_lot = info.volume_min
        contract = info.trade_contract_size
        pip = self._pip_size(info)
        acc = mt5.account_info()
        balance = acc.balance
        risk_value = balance * self.risk_per_trade
        stop_distance = config.BASE_PIPS * pip
        if info.point == 0: return min_lot
        tick_value = info.trade_tick_value or (contract * info.point)
        ticks = stop_distance / info.point
        loss_per_lot = ticks * tick_value
        if loss_per_lot == 0: return min_lot
        raw = risk_value / loss_per_lot
        lot = max(min_lot, round(raw / step) * step)
        return lot


    # =====================================================
    # PARTIAL CLOSE LOGIC (RULE NO. 1 & 2)
    # =====================================================
    def _apply_partial_close(self, symbol, current_price):
        """
        Close 50% volume saat profit mencapai 50% dari base_pips
        """
        # Cek apakah kita punya catatan posisi lokal
        local_pos = self.current_position.get(symbol)
        if not local_pos: return
        
        # Cek apakah sudah pernah partial close (agar tidak looping close terus)
        if local_pos.get("partial_closed", False):
            return

        if self.mode == "paper": return

        # Cek posisi real di MT5
        positions = mt5.positions_get(symbol=symbol)
        if not positions: return
        pos = positions[0]

        info = mt5.symbol_info(symbol)
        pip_size = self._pip_size(info)
        direction = 1 if pos.type == mt5.ORDER_TYPE_BUY else -1
        
        # Logic perhitungan Pips
        profit_pips = 0
        if direction == 1: # BUY
            profit_pips = (current_price - pos.price_open) / pip_size
        else: # SELL
            profit_pips = (pos.price_open - current_price) / pip_size

        # Target Partial = 50% dari Base Pip config
        base_pips_cfg = local_pos.get("base_pips", config.BASE_PIPS)
        partial_target = base_pips_cfg * 0.5

        if profit_pips >= partial_target:
            # Hitung Volume Partial (50% dari current volume)
            current_vol = pos.volume
            partial_vol = current_vol * 0.5
            
            # Rounding sesuai step volume symbol
            step = info.volume_step
            min_lot = info.volume_min
            
            # Pastikan volume valid (kelipatan step)
            partial_vol = max(min_lot, round(partial_vol / step) * step)
            
            # Jika sisa volume nanti < min_lot, jangan partial (close all saja nanti di TP)
            if (current_vol - partial_vol) < min_lot:
                return

            # Eksekusi Partial Close (Opposite Deal)
            action_type = mt5.ORDER_TYPE_SELL if direction == 1 else mt5.ORDER_TYPE_BUY
            
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "position": pos.ticket, # Wajib menyertakan tiket posisi
                "type": action_type,
                "volume": partial_vol,
                "price": current_price,
                "deviation": 20,
                "magic": pos.magic,
                "comment": "Partial Close 50%",
                "type_filling": mt5.ORDER_FILLING_FOK
            }
            
            res = mt5.order_send(req)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                msg = f"Partial Close {partial_vol} lot (Profit > {partial_target} pips)"
                self.logger.info(f"[PARTIAL] {symbol} {msg}")
                
                # Update status lokal
                self.current_position[symbol]["partial_closed"] = True
                self.current_position[symbol]["volume"] -= partial_vol # Kurangi volume di memory
                
                # Log to CSV/Sheet
                self._log_trade_row(
                    dt.datetime.utcnow().isoformat(), symbol, direction, pos.price_open, pos.sl, pos.tp, partial_vol, 
                    "PARTIAL_CLOSE", res.retcode, msg, local_pos.get("sl_ratio"), base_pips_cfg, str(self.timeframe)
                )
                
                # Telegram Notif
                self._send_telegram(f"💰 <b>PARTIAL CLOSE 50%</b>\nSymbol: {symbol}\nSecured Vol: {partial_vol}\nRemaining: {self.current_position[symbol]['volume']}")


    # =====================================================
    # TRAILING STOP LOGIC
    # =====================================================
    def _apply_trailing_stop(self, symbol, current_price):
        ts_pips = getattr(config, "TRAILING_STOP_PIP", 0)
        if ts_pips <= 0: return

        positions = mt5.positions_get(symbol=symbol)
        if not positions: return
        pos = positions[0]
        if self.mode == "paper": return

        info = mt5.symbol_info(symbol)
        pip_size = self._pip_size(info)
        direction = 1 if pos.type == mt5.ORDER_TYPE_BUY else -1
        new_sl = None
        should_modify = False

        if direction == 1: # BUY
            profit_pips = (current_price - pos.price_open) / pip_size
            if profit_pips > ts_pips:
                potential_sl = current_price - (ts_pips * pip_size)
                if potential_sl > pos.sl:
                    new_sl = potential_sl
                    should_modify = True
        else: # SELL
            profit_pips = (pos.price_open - current_price) / pip_size
            if profit_pips > ts_pips:
                potential_sl = current_price + (ts_pips * pip_size)
                if (pos.sl == 0) or (potential_sl < pos.sl):
                    new_sl = potential_sl
                    should_modify = True

        if should_modify and new_sl is not None:
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": pos.ticket,
                "symbol": symbol,
                "sl": new_sl,
                "tp": pos.tp, 
                "magic": pos.magic,
                "comment": pos.comment
            }
            res = mt5.order_send(req)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                msg_comment = f"Moved SL to {new_sl} (Profit > {ts_pips} pips)"
                self.logger.info(f"[TRAILING] {symbol} {msg_comment}")
                
                local_pos = self.current_position.get(symbol)
                s_ratio = local_pos.get("sl_ratio", "-") if local_pos else "-"
                b_pips = local_pos.get("base_pips", "-") if local_pos else "-"
                vol = local_pos.get("volume", 0) if local_pos else 0
                
                self._log_trade_row(
                    dt.datetime.utcnow().isoformat(), symbol, direction, pos.price_open, new_sl, pos.tp, vol, 
                    "TRAILING_UPDATE", res.retcode, msg_comment, s_ratio, b_pips, str(self.timeframe)
                )

                if self.current_position[symbol]:
                    self.current_position[symbol]["sl"] = new_sl
                
                tg_msg = (f"🛡️ <b>TRAILING STOP</b>\nSymbol: {symbol}\nNew SL: {new_sl}")
                self._send_telegram(tg_msg)


    # =====================================================
    # POSITION UPDATE
    # =====================================================
    def update_position(self, symbol, price):
        pos = self.current_position[symbol]
        if pos is None: return

        d = pos["direction"]
        s_ratio = pos.get("sl_ratio", "-")
        b_pips = pos.get("base_pips", "-")
        vol = pos.get("volume", "-")
        timestamp = dt.datetime.utcnow().isoformat()
        tf_str = str(self.timeframe)

        hit_type = None
        comment_msg = ""
        icon = ""

        if d == 1:  # BUY
            if price <= pos["sl"]:
                hit_type = "SL_HIT"
                comment_msg = f"BUY hit SL at {price}"
                icon = "❌"
            elif price >= pos["tp"]:
                hit_type = "TP_HIT"
                comment_msg = f"BUY hit TP at {price}"
                icon = "✅"
        else:  # SELL
            if price >= pos["sl"]:
                hit_type = "SL_HIT"
                comment_msg = f"SELL hit SL at {price}"
                icon = "❌"
            elif price <= pos["tp"]:
                hit_type = "TP_HIT"
                comment_msg = f"SELL hit TP at {price}"
                icon = "✅"

        if hit_type:
            self.logger.info(f"[{hit_type}] {symbol} {comment_msg}")
            self._log_trade_row(timestamp, symbol, d, pos["entry"], pos["sl"], pos["tp"], vol, hit_type, 0, comment_msg, s_ratio, b_pips, tf_str)
            
            label = "PROFIT" if hit_type == "TP_HIT" else "LOSS"
            tg_msg = (f"{icon} <b>CLOSED ({hit_type})</b>\nSymbol: {symbol}\nPrice: {price}\nStatus: {label}")
            self._send_telegram(tg_msg)
            
            self.current_position[symbol] = None


    # =====================================================
    # MAIN LOOP
    # =====================================================
    def start(self, poll_interval=5.0):
        self.connect()
        self.logger.info("===== LiveEngineScreening started =====")
        self._send_telegram(f"🤖 <b>BOT STARTED</b>\nSymbols: {self.symbols}\nTF: {self.timeframe}")

        while True:
            try:
                # --- 1. MANAGEMENT SECTION (SELALU JALAN) ---
                for symbol in self.symbols:
                    if self.current_position[symbol]:
                        tick = mt5.symbol_info_tick(symbol)
                        if tick:
                            curr_price = tick.bid # Simplifikasi, atau sesuaikan direction
                            
                            self._apply_partial_close(symbol, curr_price)
                            self._apply_trailing_stop(symbol, curr_price)
                            self.update_position(symbol, curr_price)

                # --- 2. ENTRY SECTION (FILTER WAKTU) ---
                trading_open = self._is_trading_time()
                
                table_rows = []
                for symbol in self.symbols:
                    df = self.fetch(symbol)
                    sig_df = self.strategies[symbol].generate_signals(df)
                    if sig_df.empty: continue
                    sig = int(sig_df["signal"].iloc[-1])
                    price = float(sig_df["close"].iloc[-1])

                    if not trading_open:
                        sig = 0

                    if sig == 0:
                        table_rows.append([symbol, price, 0, "-", "-"])
                        continue

                    # --- LOGIC ENTRY ---
                    direction = sig
                    info = mt5.symbol_info(symbol)
                    pip = self._pip_size(info)
                    base_pips = config.BASE_PIPS
                    ratio_str = config.SLTP_RATIO 
                    sl_distance = base_pips * pip
                    parts = ratio_str.split(":")
                    tp_mult = float(parts[1]) / float(parts[0])
                    tp_distance = sl_distance * tp_mult

                    if direction == 1:
                        sl = price - sl_distance
                        tp = price + tp_distance
                    else:
                        sl = price + sl_distance
                        tp = price - tp_distance

                    fixed_lot_map = {"XAUUSD": getattr(config, "FIXED_LOT_XAUUSD", None), "EURUSD": getattr(config, "FIXED_LOT_EURUSD", None), "GBPUSD": getattr(config, "FIXED_LOT_GBPUSD", None), "GBPJPY": getattr(config, "FIXED_LOT_GBPJPY", None)}
                    if fixed_lot_map.get(symbol) is not None: vol = fixed_lot_map[symbol]
                    else:
                        vol = self.compute_lot(symbol, price)
                        step = info.volume_step
                        min_lot = info.volume_min
                        max_lot = min(info.volume_max, config.MAX_LOT_CAP)
                        vol = max(min_lot, min(max_lot, round(vol / step) * step))

                    ok = self.send_order(symbol, direction, sl, tp, vol, ratio_str, base_pips)
                    if ok:
                        self.current_position[symbol] = {
                            "direction": direction, "entry": price, "sl": sl, "tp": tp, "volume": vol, 
                            "sl_ratio": ratio_str, "base_pips": base_pips,
                            "partial_closed": False # Init status partial
                        }

                    table_rows.append([symbol, f"{price}", direction, f"{sl}", f"{tp}"])

                if table_rows:
                    self.logger.info("-" * 60)
                    for r in table_rows: self.logger.info(f"{r[0]:<6} | {r[1]:<9} | {r[2]:<3} | {r[3]:<14} | {r[4]:<14}")
                
                if not trading_open:
                    self.logger.info("[FILTER] Trading Paused (Restricted Hours)")

                time.sleep(poll_interval)
            except Exception as e:
                self.logger.error(f"ERROR: {e}")
                time.sleep(poll_interval)