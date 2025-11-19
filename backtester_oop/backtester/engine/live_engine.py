import os
import time
import logging
import datetime as dt
import numpy as np
import MetaTrader5 as mt5
import pandas as pd
import csv

# load config
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

        # use config paths if not passed
        self.log_file = log_file or config.LOG_FILE
        self.trade_csv = config.TRADE_CSV

        # Ensure logs directory exists
        log_dir = os.path.dirname(self.log_file) or "."
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Setup logger (basic)
        logging.basicConfig(filename=self.log_file,
                            level=logging.INFO,
                            format='%(asctime)s [LIVE] %(message)s')
        logging.info("===== LiveEngine initialized =====")

        # Ensure trade csv exists with header
        if not os.path.exists(self.trade_csv):
            with open(self.trade_csv, "w", newline='', encoding="utf-8") as f:
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
    # CONNECT TO MT5
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
            logging.info("Connected to MT5")


    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            logging.info("Disconnected from MT5")
        self.connected = False


    # =====================================================
    # FETCH NEW DATA
    # =====================================================
    def fetch_data(self):
        ohlc = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars)
        if ohlc is None:
            raise RuntimeError("No MT5 OHLC returned")

        df = pd.DataFrame(ohlc)
        df.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
        }, inplace=True)
        return df


    # =====================================================
    # HELPER: pip size
    # =====================================================
    def _pip_size(self, info):
        # Typical pip = 10 * point. This works for normal FX and JPY pairs.
        return info.point * 10


    # =====================================================
    # LOG TRADE ROW (CSV) & pretty table line to logger
    # =====================================================
    def _log_trade_row(self, timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment):
        # append to csv
        with open(self.trade_csv, "a", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, symbol, direction, entry, sl, tp, volume, status, retcode, comment])

        # formatted table-like line in main log
        dir_str = "BUY" if direction == 1 else "SELL"
        logging.info(f"TRADE | {timestamp} | {symbol} | {dir_str} | entry={entry:.5f} sl={sl:.5f} tp={tp:.5f} vol={volume} status={status} ret={retcode} comment={comment}")


    # =====================================================
    # ORDER EXECUTION
    # =====================================================
    def send_order(self, direction, sl, tp, volume):
        timestamp = dt.datetime.utcnow().isoformat()
        if self.mode == "paper":
            # log paper trade as "PAPER"
            self._log_trade_row(timestamp, self.symbol, direction, None, sl, tp, volume, "PAPER", None, "Paper trade simulated")
            logging.info(f"[PAPER] ORDER {direction} | vol={volume} sl={sl} tp={tp}")
            return True

        # LIVE MODE: check max open trades before sending
        open_positions = mt5.positions_get(symbol=self.symbol) or []
        if len(open_positions) >= config.MAX_OPEN_TRADES:
            msg = f"Max open trades reached ({len(open_positions)}) >= {config.MAX_OPEN_TRADES}. Skipping order."
            logging.info(msg)
            self._log_trade_row(timestamp, self.symbol, direction, None, sl, tp, volume, "SKIPPED_MAX_TRADES", None, msg)
            return False

        type_map = {1: mt5.ORDER_TYPE_BUY, -1: mt5.ORDER_TYPE_SELL}
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logging.error("symbol_info_tick returned None")
            self._log_trade_row(timestamp, self.symbol, direction, None, sl, tp, volume, "FAILED", None, "No tick")
            return False

        price = tick.ask if direction == 1 else tick.bid

        request = {
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
        result = mt5.order_send(request)

        # log result
        retcode = getattr(result, "retcode", None)
        comment = getattr(result, "comment", "")
        status = "OK" if retcode == mt5.TRADE_RETCODE_DONE else "REJECTED"
        entry = price if retcode == mt5.TRADE_RETCODE_DONE else None

        self._log_trade_row(timestamp, self.symbol, direction, entry, sl, tp, volume, status, retcode, comment)
        logging.info(f"Order send result: {result}")
        return retcode == mt5.TRADE_RETCODE_DONE


    # =====================================================
    # MAIN LOOP
    # =====================================================
    def start(self, poll_interval=5.0):
        self.connect()
        logging.info("===== LiveEngine started =====")

        while True:
            try:
                df = self.fetch_data()

                # Generate signals using strategy (must return df with 'signal')
                df_sig = self.strategy.generate_signals(df)

                if df_sig.empty:
                    time.sleep(poll_interval)
                    continue

                # Take latest signal
                sig = int(df_sig["signal"].iloc[-1])
                price = float(df_sig["close"].iloc[-1])

                # If there is open position, handle SL/TP/trailing here (not implemented fully)
                if self.current_position:
                    self.update_position(price, None)

                # No new signal
                if sig == 0:
                    logging.info("Signal 0 (flat). No trade.")
                    time.sleep(poll_interval)
                    continue

                # Must flip or open new position
                direction = sig

                # ------------------------
                # SL/TP: use config ratio + base pips (1 = 30 pip)
                # ------------------------
                info = mt5.symbol_info(self.symbol)
                if info is None:
                    logging.error("symbol_info() is None; skipping")
                    time.sleep(poll_interval)
                    continue

                pip = self._pip_size(info)
                base_pips = config.BASE_PIPS  # expected 30
                sl_distance = base_pips * pip  # e.g., 30 * pip_size
                # parse ratio "1:2" -> tp_multiplier = 2
                parts = config.SLTP_RATIO.split(":")
                try:
                    tp_multiplier = float(parts[1]) / float(parts[0])
                except Exception:
                    tp_multiplier = 1.0

                tp_distance = sl_distance * tp_multiplier

                if direction == 1:
                    sl = price - sl_distance
                    tp = price + tp_distance
                else:
                    sl = price + sl_distance
                    tp = price - tp_distance

                # ------------------------
                # Volume sizing: use FIXED_LOT if configured, otherwise compute
                # ------------------------
                if config.FIXED_LOT is not None:
                    vol = float(config.FIXED_LOT)
                    logging.info(f"Using FIXED_LOT from config: {vol}")
                else:
                    # fallback to previous/dynamic sizing (keeps compute_lot_sizing)
                    vol = self.compute_lot_sizing(price, None)

                # sanity: cap to config.MAX_LOT_CAP and ensure >= min volume
                info = mt5.symbol_info(self.symbol)
                step = getattr(info, "volume_step", 0.01)
                min_lot = getattr(info, "volume_min", 0.01)
                max_lot = getattr(info, "volume_max", config.MAX_LOT_CAP)
                # round to step
                try:
                    vol = max(min_lot, min(max_lot, round(vol / step) * step))
                except Exception:
                    vol = max(min_lot, min(max_lot, float(vol)))

                logging.info(f"Computed/used lot: {vol} | SL pips={base_pips} TP mult={tp_multiplier}")

                if vol is None or vol <= 0:
                    logging.warning("Computed lot is zero or invalid — skipping order")
                    time.sleep(poll_interval)
                    continue

                ok = self.send_order(direction, sl, tp, vol)
                if ok:
                    self.current_position = {
                        "direction": direction,
                        "entry": price,
                        "sl": sl,
                        "tp": tp,
                        "volume": vol
                    }
                    logging.info(f"Opened position: {self.current_position}")

                time.sleep(poll_interval)

            except Exception as e:
                logging.error(f"Error in live loop: {e}")
                time.sleep(poll_interval)


    # =====================================================
    # DYNAMIC LOT SIZING (kept as fallback)
    # =====================================================
    def compute_lot_sizing(self, price, atr):
        # simplified fallback: compute lot using risk_per_trade and an approximate pip-value
        info = mt5.symbol_info(self.symbol)
        if info is None:
            logging.error("symbol_info() returned None")
            return None

        step = getattr(info, "volume_step", 0.01)
        min_lot = getattr(info, "volume_min", 0.01)
        contract_size = getattr(info, "trade_contract_size", 100000.0)
        pip = self._pip_size(info)

        acc = mt5.account_info()
        if acc is None:
            logging.error("account_info() returned None")
            return None
        balance = acc.balance

        risk_value = balance * float(self.risk_per_trade)

        # if atr not provided, approximate stop distance using config.BASE_PIPS
        stop_distance = config.BASE_PIPS * pip

        # approximate tick_value: contract_size * point -> per-lot per-tick
        tick_value = getattr(info, "trade_tick_value", None)
        if not tick_value:
            tick_value = contract_size * info.point

        number_of_ticks = stop_distance / info.point
        loss_per_lot = number_of_ticks * tick_value

        if loss_per_lot <= 0:
            logging.error("Loss per lot non-positive")
            return None

        raw_lot = risk_value / loss_per_lot
        try:
            rounded_lot = max(min_lot, round(raw_lot / step) * step)
        except Exception:
            rounded_lot = max(min_lot, float(raw_lot))

        logging.info(f"Fallback lot sizing: balance={balance}, risk_value={risk_value}, loss_per_lot={loss_per_lot}, raw_lot={raw_lot}, rounded_lot={rounded_lot}")
        return rounded_lot


    # =====================================================
    # POSITION UPDATE
    # =====================================================
    def update_position(self, price, atr):
        if self.current_position is None:
            return

        pos = self.current_position

        # Check SL hit
        if pos["direction"] == 1 and price <= pos["sl"]:
            logging.info("SL hit — closing BUY (internal state)")
            self.current_position = None

        if pos["direction"] == -1 and price >= pos["sl"]:
            logging.info("SL hit — closing SELL (internal state)")
            self.current_position = None

        # Check TP hit
        if pos["direction"] == 1 and price >= pos["tp"]:
            logging.info("TP hit — closing BUY (internal state)")
            self.current_position = None

        if pos["direction"] == -1 and price <= pos["tp"]:
            logging.info("TP hit — closing SELL (internal state)")
            self.current_position = None
