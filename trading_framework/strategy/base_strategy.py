class BaseStrategy:
    def generate_signals(self, df):
        """
        Harus return dataframe dengan kolom:
        - signal: 1 (buy), -1 (sell), 0 (no trade)
        """
        raise NotImplementedError
