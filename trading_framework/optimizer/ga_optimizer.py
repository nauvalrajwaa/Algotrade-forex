import random
from copy import deepcopy

class GAOptimizer:
    def __init__(self, space, backtester, population=20, generations=10):
        self.space = space
        self.backtester = backtester
        self.population = population
        self.generations = generations

    def random_individual(self):
        ind = {}
        for k,(a,b) in self.space.items():
            if isinstance(a,int):
                ind[k] = random.randint(a,b)
            else:
                ind[k] = random.uniform(a,b)
        return ind

    def evaluate(self, params, df):
        strategy = self.backtester.strategy.__class__(**params)
        bt = self.backtester.__class__(self.backtester.config, strategy)
        eq, trades = bt.run(df)
        return sum([t.pnl for t in trades])

    def run(self, df):
        pop = [self.random_individual() for _ in range(self.population)]
        scores = [self.evaluate(ind, df) for ind in pop]

        for g in range(self.generations):
            # selection + mutation + crossover
            pass  # tinggal copy logic Anda

        best_idx = scores.index(max(scores))
        return pop[best_idx]
