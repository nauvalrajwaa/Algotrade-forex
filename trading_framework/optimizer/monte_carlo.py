import numpy as np
import random

class MonteCarlo:
    def __init__(self, iterations=200):
        self.iterations = iterations

    def run(self, trades, initial_balance):
        pl = [t.pnl for t in trades]
        results = []
        for _ in range(self.iterations):
            random.shuffle(pl)
            results.append(initial_balance + sum(pl))
        return np.array(results)
