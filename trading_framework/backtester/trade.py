class Trade:
    def __init__(self, direction, entry, sl, tp_levels, lot, time):
        self.direction = direction
        self.entry = entry
        self.sl = sl
        self.tp_levels = tp_levels
        self.lot = lot
        self.entry_time = time
        self.exit_time = None
        self.pnl = 0
        self.closed = False
