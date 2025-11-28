# engine/live_engine.py

import os
import time
import logging
import datetime as dt
import numpy as np
import MetaTrader5 as mt5
import pandas as pd
import csv

import config


class LiveEngine:
    def __init__(
        self,
        strategy,
        mt5_path,
        symbol,
        timeframe,
        bars=200,
        mode="paper",
        risk_per_trade=0.01,
        log_file=None,
        max_daily_loss=0.05,
        max_drawdown=0.20
    ):
        self.strategy = strategy
        self.mt5_path = mt5_path
        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars
        self.mode = mode
        self.risk_per_trade = risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown

        self.log_file = log_file or config.LOG_FILE
        self.trade_csv = config.TRADE_CSV

        log_dir = os.path.dirname(self.log_file) or "."
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # ================================================
        # LOGGER – WRITE TO FILE + TERMINAL (StreamHandler)
        # ================================================
        self.logger = logging.getLogger("LiveEngine")
        self.logger.setLevel(logging.INFO)

        # file handler
        fh = logging.FileHandler(self.log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s [LIVE] %(message)s"))
        self.logger.addHandler(fh)

        # terminal handler
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("[LIVE] %(message)s"))
        self.logger.addHandler(sh)

        self.logger.info("===== LiveEngine initialized =====")
        self.logger.info(f"Strategy used: {self.strategy.__class__.__name__}")

        # print strategy parameters if available
        if hasattr(self.strategy, "params"):
            self.logger.info(f"Strategy params: {self.strategy.params}")
        else:
            self.logger.info("Strategy params: <none>")

        # ensure trade csv exists
        if not os.path.exists(self.trade_csv):
            with open(self.trade_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "symbol", "direction", "entry",
                    "sl", "tp", "volume", "status", "retcode", "comment"
                ])

        self.connected = False
        self.balance_start = None
        self.daily_start = None
        self.current_position = None


    # =====================================================
    # CONNECT
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
    def fetch_data(self):
        ohlc = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars)
        if ohlc is None:
            raise RuntimeError("No OHLC from MT5")

        df = pd.DataFrame(ohlc)
        return df


    # =====================================================
    # PIP SIZE
    # =====================================================
    def _pip_size(self, info):
        symbol = info.name.upper()
        digits = info.digits

    # =======================
    # XAUUSD
    # =======================
        if symbol == "XAUUSD":
        # 4082.864 → 3 digit → 1 pip = 0.10
            return 0.10

    # =======================
    # EURUSD & GBPUSD
    # =======================
        if symbol in ("EURUSD", "GBPUSD"):
        # 1.12345 → 5 digit → 1 pip = 0.00001
            return 0.00001

    # =======================
    # GBPJPY
    # =======================
        if symbol == "GBPJPY":
        # 150.123 → 3 digit → 1 pip = 0.001
            return 0.001

    # =======================
    # FALLBACK SAFE
    # (Jika pair lain muncul)
    # =======================
    # Default FX-style: point * 10
        return info.point * 10


    # =====================================================
    # LOG ROW TO CSV + FILE
    # =====================================================
    def _log_trade_row(self, timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment):
        with open(self.trade_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, symbol, direction, entry, sl, tp, volume,
                status, retcode, comment
            ])

        d = "BUY" if direction == 1 else "SELL"
        self.logger.info(
            f"[TRADE] {timestamp} | {symbol} | {d} | entry={entry} | "
            f"SL={sl} | TP={tp} | lot={volume} | status={status} | ret={retcode}"
        )


    # =====================================================
    # EXECUTE ORDER
    # =====================================================
    def send_order(self, direction, sl, tp, volume):
        timestamp = dt.datetime.utcnow().isoformat()

        if self.mode == "paper":
            self.logger.info(
                f"[PAPER ORDER] dir={direction} vol={volume} SL={sl} TP={tp}"
            )
            self._log_trade_row(timestamp, self.symbol, direction, None, sl, tp,
                                volume, "PAPER", None, "Paper trade simulated")
            return True

        open_positions = mt5.positions_get(symbol=self.symbol) or []
        if len(open_positions) >= config.MAX_OPEN_TRADES:
            msg = f"Max trades reached: {len(open_positions)}"
            self.logger.info(msg)
            self._log_trade_row(timestamp, self.symbol, direction, None, sl, tp,
                                volume, "SKIPPED_MAX", None, msg)
            return False

        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.logger.error("symbol_info_tick = None")
            return False

        price = tick.ask if direction == 1 else tick.bid
        type_map = {1: mt5.ORDER_TYPE_BUY, -1: mt5.ORDER_TYPE_SELL}

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "type": type_map[direction],
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 55667788,
            "comment": "LiveEngine",
            "type_filling": mt5.ORDER_FILLING_FOK
        }

        result = mt5.order_send(req)
        ret = result.retcode
        comment = result.comment
        status = "OK" if ret == mt5.TRADE_RETCODE_DONE else "REJECTED"
        entry = price if status == "OK" else None

        self._log_trade_row(timestamp, self.symbol, direction, entry, sl, tp,
                            volume, status, ret, comment)

        self.logger.info(f"[ORDER SEND] result={result}")
        return (ret == mt5.TRADE_RETCODE_DONE)


    # =====================================================
    # MAIN LOOP
    # =====================================================
    def start(self, poll_interval=5.0):
        self.connect()
        self.logger.info("===== LiveEngine started =====")

        while True:
            try:
                df = self.fetch_data()
                df_sig = self.strategy.generate_signals(df)

                if df_sig.empty:
                    time.sleep(poll_interval)
                    continue

                sig = int(df_sig["signal"].iloc[-1])
                price = float(df_sig["close"].iloc[-1])

                if self.current_position:
                    self.update_position(price, None)

                if sig == 0:
                    self.logger.info("Signal = 0, flat.")
                    time.sleep(poll_interval)
                    continue

                direction = sig

                # ============ SL / TP COMPUTATION ============
                info = mt5.symbol_info(self.symbol)
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

                # ============ LOT SIZING ============
                if config.FIXED_LOT_LIVE is not None:
                    vol = float(config.FIXED_LOT_LIVE)
                else:
                    vol = self.compute_lot_sizing(price, None)

                info = mt5.symbol_info(self.symbol)
                step = info.volume_step
                min_lot = info.volume_min
                max_lot = min(info.volume_max, config.MAX_LOT_CAP)

                vol = max(min_lot, min(max_lot, round(vol / step) * step))

                # PRINT ENTRY DETAILS TO TERMINAL
                self.logger.info("----------------------------------------------------")
                self.logger.info(f"New ENTRY SIGNAL: {direction} ({'BUY' if direction==1 else 'SELL'})")
                self.logger.info(f"Price     : {price}")
                self.logger.info(f"SL / TP   : {sl} / {tp}")
                self.logger.info(f"Lot       : {vol}")
                self.logger.info(f"BasePips  : {base_pips}")
                self.logger.info(f"TP Ratio  : {tp_mult}")
                self.logger.info(f"Strategy  : {self.strategy.__class__.__name__}")
                if hasattr(self.strategy, 'params'):
                    self.logger.info(f"Parameters: {self.strategy.params}")
                self.logger.info("----------------------------------------------------")

                ok = self.send_order(direction, sl, tp, vol)
                if ok:
                    self.current_position = {
                        "direction": direction,
                        "entry": price,
                        "sl": sl,
                        "tp": tp,
                        "volume": vol
                    }
                    self.logger.info(f"Opened position: {self.current_position}")

                time.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"ERROR in live loop: {e}")
                time.sleep(poll_interval)


    # =====================================================
    # LOT SIZING (FALLBACK)
    # =====================================================
    def compute_lot_sizing(self, price, atr):
        info = mt5.symbol_info(self.symbol)
        if info is None:
            self.logger.error("symbol_info() None")
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

        if loss_per_lot <= 0:
            self.logger.error("loss_per_lot <= 0")
            return None

        raw = risk_value / loss_per_lot
        lot = max(min_lot, round(raw / step) * step)

        self.logger.info(f"[LotSizing] balance={balance} risk={risk_value} raw={raw} lot={lot}")
        return lot


    # =====================================================
    # UPDATE POSITION (CHECK SL & TP)
    # =====================================================
    def update_position(self, price, atr):
        if not self.current_position:
            return

        pos = self.current_position

        d = "BUY" if pos["direction"] == 1 else "SELL"

        if pos["direction"] == 1:
            if price <= pos["sl"]:
                self.logger.info(f"[SL HIT] Closing BUY at {price}")
                self.current_position = None
            if price >= pos["tp"]:
                self.logger.info(f"[TP HIT] Closing BUY at {price}")
                self.current_position = None

        else:
            if price >= pos["sl"]:
                self.logger.info(f"[SL HIT] Closing SELL at {price}")
                self.current_position = None
            if price <= pos["tp"]:
                self.logger.info(f"[TP HIT] Closing SELL at {price}")
                self.current_position = None
