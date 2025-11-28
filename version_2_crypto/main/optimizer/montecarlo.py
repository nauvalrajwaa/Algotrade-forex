import random
import numpy as np
import math

class MonteCarloOptimizer:
    def __init__(self, search_space, config, fitness_function):
        self.search_space = search_space
        self.fitness_function = fitness_function

        self.iterations = config.get("iterations", 3000)
        self.temperature = config.get("temperature", 1.0)
        self.cooling_rate = config.get("cooling_rate", 0.999)

    # ---------------- Random solution ----------------
    def random_solution(self):
        sol = {}
        for key, (low, high) in self.search_space.items():
            if isinstance(low, int) and isinstance(high, int):
                sol[key] = random.randint(low, high)
            else:
                sol[key] = random.uniform(low, high)
        return sol

    # ---------------- Neighbor solution ----------------
    def neighbor(self, solution):
        new = solution.copy()
        key = random.choice(list(self.search_space.keys()))
        low, high = self.search_space[key]

        if isinstance(low, int):
            new[key] = random.randint(low, high)
        else:
            new[key] = new[key] + random.uniform(-(high - low) * 0.1, (high - low) * 0.1)
            new[key] = max(low, min(high, new[key]))  # clamp

        return new

    # ---------------- SA / Monte Carlo Loop ----------------
    def run(self):
        current = self.random_solution()
        current_score = self.fitness_function(current)

        best = current.copy()
        best_score = current_score

        T = self.temperature

        for i in range(self.iterations):
            candidate = self.neighbor(current)
            candidate_score = self.fitness_function(candidate)

            delta = candidate_score - current_score

            # Accept always if better
            if delta > 0 or random.random() < math.exp(delta / T):
                current = candidate
                current_score = candidate_score

            # Track global best
            if current_score > best_score:
                best = current.copy()
                best_score = current_score

            # Cooling
            T *= self.cooling_rate

            if i % 200 == 0:
                print(f"Iter {i}/{self.iterations} | Best: {best_score:.4f}")

        return best, best_score
