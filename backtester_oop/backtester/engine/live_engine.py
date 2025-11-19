# backtester/engine/live_engine.py
import time
import logging
import datetime as dt
import numpy as np
import MetaTrader5 as mt5
import pandas as pd


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
        log_file="logs/live_default.log",
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

        # Setup logger
        logging.basicConfig(filename=log_file,
                            level=logging.INFO,
                            format='%(asctime)s [LIVE] %(message)s')
        logging.info("===== LiveEngine initialized =====")

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
    # ORDER EXECUTION
    # =====================================================
    def send_order(self, direction, sl, tp, volume):
        if self.mode == "paper":
            logging.info(f"[PAPER] ORDER {direction} | vol={volume} sl={sl} tp={tp}")
            return True

        # LIVE MODE
        type_map = {1: mt5.ORDER_TYPE_BUY, -1: mt5.ORDER_TYPE_SELL}
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "type": type_map[direction],
            "volume": volume,
            "price": mt5.symbol_info_tick(self.symbol).ask if direction == 1 else mt5.symbol_info_tick(self.symbol).bid,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 55667788,
            "comment": "LiveEngine",
            "type_filling": mt5.ORDER_FILLING_FOK
        }
        result = mt5.order_send(request)
        logging.info(f"Order send result: {result}")

        return result.retcode == mt5.TRADE_RETCODE_DONE


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
                atr_val = float(df_sig["atr"].iloc[-1])
                price = float(df_sig["close"].iloc[-1])

                # If there is open position, handle SL/TP/trailing here (not implemented fully)
                # --------------------------------------------
                if self.current_position:
                    self.update_position(price, atr_val)
                # --------------------------------------------

                # No new signal
                if sig == 0:
                    logging.info("Signal 0 (flat). No trade.")
                    time.sleep(poll_interval)
                    continue

                # Must flip or open new position
                direction = sig

                # Compute SL/TP basic ATR rule
                sl = price - self.strategy.params.get("atr_mul", 1.5) * atr_val if direction == 1 else \
                     price + self.strategy.params.get("atr_mul", 1.5) * atr_val

                tp = price + self.strategy.params.get("atr_mul", 1.5) * atr_val if direction == 1 else \
                     price - self.strategy.params.get("atr_mul", 1.5) * atr_val

                # Volume sizing (simple)
                vol = self.compute_lot_sizing(price, atr_val)

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
    # DYNAMIC LOT SIZING
    # =====================================================
    def compute_lot_sizing(self, price, atr):
        info = mt5.symbol_info(self.symbol)
        step = info.volume_step
        min_lot = info.volume_min

        acc = mt5.account_info()
        balance = acc.balance

        risk_value = balance * self.risk_per_trade
        stop_distance = atr * self.strategy.params.get("atr_mul", 1.5)

        # lot = risk / (stop distance * tick value)
        tick_value = info.trade_tick_value
        lot = risk_value / (stop_distance * tick_value)

        # round to broker lot-step
        lot = max(min_lot, round(lot / step) * step)
        return lot


    # =====================================================
    # POSITION UPDATE
    # =====================================================
    def update_position(self, price, atr):
        if self.current_position is None:
            return

        pos = self.current_position

        # Check SL hit
        if pos["direction"] == 1 and price <= pos["sl"]:
            logging.info("SL hit — closing BUY")
            self.current_position = None

        if pos["direction"] == -1 and price >= pos["sl"]:
            logging.info("SL hit — closing SELL")
            self.current_position = None

        # Check TP hit
        if pos["direction"] == 1 and price >= pos["tp"]:
            logging.info("TP hit — closing BUY")
            self.current_position = None

        if pos["direction"] == -1 and price <= pos["tp"]:
            logging.info("TP hit — closing SELL")
            self.current_position = None
