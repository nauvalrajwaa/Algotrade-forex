# engine/live_engine_screening.py

import os
import time
import logging
import datetime as dt
import numpy as np
import MetaTrader5 as mt5
import pandas as pd
import csv

import config


class LiveEngineScreening:
    def __init__(
        self,
        strategy_class,      # pakai class, bukan instance → tiap symbol punya instance sendiri
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
            fh2 = logging.FileHandler(self.symbol_log_files[sym])
            fh2.setFormatter(logging.Formatter("%(asctime)s [LIVE] %(message)s"))
            sym_log.addHandler(fh2)
            self.symbol_loggers[sym] = sym_log

        self.logger.info("===== LiveEngineScreening initialized =====")
        self.logger.info(f"Symbols screened: {self.symbols}")
        self.logger.info(f"Strategy class : {self.strategy_class.__name__}")
        if self.strategy_params:
            self.logger.info(f"Strategy params: {self.strategy_params}")

        # --- Prepare strategy instance per-symbol ---
        self.strategies = {}
        for sym in self.symbols:
            self.strategies[sym] = self.strategy_class(params=self.strategy_params)
            if hasattr(self.strategies[sym], "params"):
                self.logger.info(f"{sym} strategy params: {self.strategies[sym].params}")

        # --- ensure CSV exists ---
        os.makedirs(os.path.dirname(self.trade_csv), exist_ok=True)
        if not os.path.exists(self.trade_csv):
            with open(self.trade_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "symbol", "direction",
                    "entry", "sl", "tp", "volume",
                    "status", "retcode", "comment"
                ])

        self.connected = False
        self.balance_start = None
        self.daily_start = None
        self.current_position = {sym: None for sym in self.symbols}


    # =====================================================
    # CONNECT / DISCONNECT
    # =====================================================
    def connect(self):
        if not self.connected:
            if not mt5.initialize(self.mt5_path):
                raise RuntimeError("MT5 init failed")

            acc_info = mt5.account_info()
            if acc_info is None:
                raise RuntimeError("MT5 account_info() is None")

            self.balance_start = acc_info.balance
            self.daily_start = acc_info.balance
            self.connected = True

            self.logger.info("Connected to MT5")


    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.logger.info("Disconnected from MT5")
        self.connected = False


    # =====================================================
    # FETCH OHLC
    # =====================================================
    def fetch(self, symbol):
        ohlc = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, self.bars)
        if ohlc is None:
            raise RuntimeError(f"No OHLC from MT5 for {symbol}")
        return pd.DataFrame(ohlc)


    # =====================================================
    # PIP SIZE
    # =====================================================
    def _pip_size(self, info):
        symbol = info.name.upper()
        if symbol == "XAUUSD":
            return 0.10
        if symbol in ("EURUSD", "GBPUSD"):
            return 0.00001
        if symbol == "GBPJPY":
            return 0.001
        return info.point * 10


    # =====================================================
    # LOG TRADE PER BARIS
    # =====================================================
    def _log_trade_row(self, timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment):
        # CSV
        with open(self.trade_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment])

        # Global & per-symbol log
        d = "BUY" if direction == 1 else "SELL"
        msg = (f"[TRADE] {timestamp:<25} | {symbol:<8} | {d:<5} | "
               f"entry={entry} | SL={sl} | TP={tp} | lot={volume} | "
               f"status={status} | ret={retcode}")
        self.logger.info(msg)
        self.symbol_loggers[symbol].info(msg)


    # =====================================================
    # SEND ORDER
    # =====================================================
    def send_order(self, symbol, direction, sl, tp, volume):
        timestamp = dt.datetime.utcnow().isoformat()

        if self.mode == "paper":
            msg = f"[PAPER] {symbol} dir={direction}, vol={volume}, SL={sl}, TP={tp}"
            self.logger.info(msg)
            self.symbol_loggers[symbol].info(msg)
            self._log_trade_row(timestamp, symbol, direction, None, sl, tp, volume, "PAPER", None, "Paper mode")
            return True

        open_positions = mt5.positions_get(symbol=symbol) or []
        if len(open_positions) >= config.MAX_OPEN_TRADES:
            msg = f"Max trades reached for {symbol}"
            self._log_trade_row(timestamp, symbol, direction, None, sl, tp, volume, "SKIPPED_MAX", None, msg)
            return False

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"{symbol} tick is None")
            self.symbol_loggers[symbol].error("tick is None")
            return False

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

        self._log_trade_row(timestamp, symbol, direction, entry, sl, tp, volume, status, ret, result.comment)

        return (ret == mt5.TRADE_RETCODE_DONE)


    # =====================================================
    # LOT SIZING
    # =====================================================
    def compute_lot(self, symbol, price):
        info = mt5.symbol_info(symbol)
        if info is None:
            self.logger.error(f"{symbol} symbol_info None")
            self.symbol_loggers[symbol].error("symbol_info None")
            return None

        step = info.volume_step
        min_lot = info.volume_min
        contract = info.trade_contract_size
        pip = self._pip_size(info)

        acc = mt5.account_info()
        balance = acc.balance
        risk_value = balance * self.risk_per_trade

        stop_distance = config.BASE_PIPS * pip
        tick_value = info.trade_tick_value or (contract * info.point)

        ticks = stop_distance / info.point
        loss_per_lot = ticks * tick_value

        raw = risk_value / loss_per_lot
        lot = max(min_lot, round(raw / step) * step)

        return lot


    # =====================================================
    # POSITION UPDATE
    # =====================================================
    def update_position(self, symbol, price):
        pos = self.current_position[symbol]
        if pos is None:
            return

        d = pos["direction"]

        if d == 1:  # BUY
            if price <= pos["sl"]:
                self.logger.info(f"[SL HIT] {symbol} BUY hit SL at {price}")
                self.symbol_loggers[symbol].info(f"BUY hit SL at {price}")
                self.current_position[symbol] = None
            elif price >= pos["tp"]:
                self.logger.info(f"[TP HIT] {symbol} BUY hit TP at {price}")
                self.symbol_loggers[symbol].info(f"BUY hit TP at {price}")
                self.current_position[symbol] = None
        else:  # SELL
            if price >= pos["sl"]:
                self.logger.info(f"[SL HIT] {symbol} SELL hit SL at {price}")
                self.symbol_loggers[symbol].info(f"SELL hit SL at {price}")
                self.current_position[symbol] = None
            elif price <= pos["tp"]:
                self.logger.info(f"[TP HIT] {symbol} SELL hit TP at {price}")
                self.symbol_loggers[symbol].info(f"SELL hit TP at {price}")
                self.current_position[symbol] = None


    # =====================================================
    # MAIN LOOP MULTI-SYMBOL
    # =====================================================
    def start(self, poll_interval=5.0):
        self.connect()
        self.logger.info("===== LiveEngineScreening started =====")

        while True:
            try:
                table_rows = []

                for symbol in self.symbols:
                    df = self.fetch(symbol)
                    sig_df = self.strategies[symbol].generate_signals(df)

                    if sig_df.empty:
                        continue

                    sig = int(sig_df["signal"].iloc[-1])
                    price = float(sig_df["close"].iloc[-1])

                    if self.current_position[symbol]:
                        self.update_position(symbol, price)

                    if sig == 0:
                        table_rows.append([symbol, price, 0, "-", "-"])
                        continue

                    # ============ SL / TP ============
                    direction = sig
                    info = mt5.symbol_info(symbol)
                    pip = self._pip_size(info)
                    base_pips = config.BASE_PIPS

                    sl_distance = base_pips * pip
                    parts = config.SLTP_RATIO.split(":")
                    tp_mult = float(parts[1]) / float(parts[0])
                    tp_distance = sl_distance * tp_mult

                    if direction == 1:
                        sl = price - sl_distance
                        tp = price + tp_distance
                    else:
                        sl = price + sl_distance
                        tp = price - tp_distance

                    # ============ LOT ============
                    # gunakan lot spesifik per symbol jika ada
                    fixed_lot_map = {
                        "XAUUSD": getattr(config, "FIXED_LOT_XAUUSD", None),
                        "EURUSD": getattr(config, "FIXED_LOT_EURUSD", None),
                        "GBPUSD": getattr(config, "FIXED_LOT_GBPUSD", None),
                        "GBPJPY": getattr(config, "FIXED_LOT_GBPJPY", None),
                    }

                    if fixed_lot_map.get(symbol) is not None:
                        vol = fixed_lot_map[symbol]
                        self.logger.info(f"[LOT] Using fixed lot for {symbol}: {vol}")
                        self.symbol_loggers[symbol].info(f"[LOT] Using fixed lot: {vol}")
                    else:
                        vol = self.compute_lot(symbol, price)
                        step = info.volume_step
                        min_lot = info.volume_min
                        max_lot = min(info.volume_max, config.MAX_LOT_CAP)
                        vol = max(min_lot, min(max_lot, round(vol / step) * step))
                        self.logger.info(f"[LOT] Computed lot for {symbol}: {vol}")
                        self.symbol_loggers[symbol].info(f"[LOT] Computed lot: {vol}")

                    # EXECUTE
                    ok = self.send_order(symbol, direction, sl, tp, vol)
                    if ok:
                        self.current_position[symbol] = {
                            "direction": direction,
                            "entry": price,
                            "sl": sl,
                            "tp": tp,
                            "volume": vol
                        }

                    table_rows.append([symbol, f"{price}", direction, f"{sl}", f"{tp}"])

                # PRINT SCREENING TABLE
                if table_rows:
                    self.logger.info("-----------------------------------------------------------")
                    self.logger.info(" SYMBOL |   PRICE   | SIG |        SL        |        TP")
                    self.logger.info("-----------------------------------------------------------")
                    for r in table_rows:
                        self.logger.info(f"{r[0]:<6} | {r[1]:<9} | {r[2]:<3} | {r[3]:<14} | {r[4]:<14}")
                    self.logger.info("-----------------------------------------------------------")

                time.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"ERROR: {e}")
                time.sleep(poll_interval)
