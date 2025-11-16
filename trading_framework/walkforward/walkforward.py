class WalkForward:
    def __init__(self, optimizer, step, is_window, oos_window):
        self.optimizer = optimizer
        self.step = step
        self.is_window = is_window
        self.oos_window = oos_window

    def run(self, df):
        results = []
        start = 0

        while start + self.is_window + self.oos_window <= len(df):
            is_df = df.iloc[start:start+self.is_window]
            oos_df = df.iloc[start+self.is_window:start+self.is_window+self.oos_window]

            best = self.optimizer.run(is_df)
            results.append(best)

            start += self.step

        return results
