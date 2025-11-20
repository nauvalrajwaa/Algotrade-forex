# optimizer/ga.py

import random
import numpy as np
import math
import traceback

class GeneticOptimizer:
    def __init__(self, search_space, config, fitness_function, strategy_name="UNKNOWN"):
        """
        search_space : dict parameter -> (low, high)
        config : GA config spesifik untuk strategi
        strategy_name : nama strategi (untuk logging)
        """

        self.strategy_name = strategy_name.upper()
        self.search_space = search_space
        self.fitness_function = fitness_function

        # --- GA CONFIG ---
        self.population_size = config.get("population_size", 20)
        self.generations = config.get("generations", 10)
        self.mutation_rate = config.get("mutation_rate", 0.1)
        self.crossover_rate = config.get("crossover_rate", 0.7)
        self.elitism = config.get("elitism", 2)

        if not isinstance(search_space, dict) or len(search_space) == 0:
            raise ValueError(f"[GA ERROR] Search space for {strategy_name} is EMPTY or invalid!")

    # ============================================================
    # Create individual
    # ============================================================
    def sample_individual(self):
        ind = {}
        for key, (low, high) in self.search_space.items():
            if low is None or high is None:
                raise ValueError(f"[GA ERROR] Invalid range for param {key} = ({low}, {high})")

            if isinstance(low, int) and isinstance(high, int):
                ind[key] = random.randint(low, high)
            else:
                ind[key] = random.uniform(low, high)

        return ind

    # ============================================================
    # Crossover
    # ============================================================
    def crossover(self, p1, p2):
        return {
            key: (p1[key] if random.random() < self.crossover_rate else p2[key])
            for key in p1.keys()
        }

    # ============================================================
    # Mutation
    # ============================================================
    def mutate(self, ind):
        for key, (low, high) in self.search_space.items():
            if random.random() < self.mutation_rate:
                if isinstance(low, int) and isinstance(high, int):
                    ind[key] = random.randint(low, high)
                else:
                    ind[key] = random.uniform(low, high)
        return ind

    # ============================================================
    # Safety check for score
    # ============================================================
    @staticmethod
    def clean_score(score):
        if score is None or isinstance(score, str):
            return -1e9

        if math.isnan(score) or math.isinf(score):
            return -1e9

        return float(score)

    # ============================================================
    # Evaluate fitness
    # ============================================================
    def evaluate_population(self, population):
        fitness_scores = []

        for ind in population:
            try:
                score = self.fitness_function(ind)

            except Exception as e:
                print(f"\n[!] Fitness exception in {self.strategy_name}: {e}")
                traceback.print_exc()
                score = -1e9

            score = self.clean_score(score)
            fitness_scores.append(score)

        return fitness_scores

    # ============================================================
    # Main GA Loop
    # ============================================================
    def run(self):
        print(f"\n=== Genetic Algorithm for Strategy: {self.strategy_name} ===")
        print(f"Population: {self.population_size}, Generations: {self.generations}")
        print(f"Search space: {list(self.search_space.keys())}\n")

        # initial pop
        population = [self.sample_individual() for _ in range(self.population_size)]

        best_global = None
        best_score_global = -1e12

        for g in range(1, self.generations + 1):
            fitness_scores = self.evaluate_population(population)

            # --- Best of generation ---
            gen_best_idx = int(np.argmax(fitness_scores))
            gen_best = population[gen_best_idx]
            gen_best_score = fitness_scores[gen_best_idx]

            # Update global best
            if gen_best_score > best_score_global:
                best_score_global = gen_best_score
                best_global = gen_best.copy()

            print(f"[{self.strategy_name}] Gen {g}/{self.generations} | Best score: {gen_best_score:.6f}")

            # --- Tournament selection ---
            def tournament():
                i1, i2 = random.sample(range(self.population_size), 2)
                return population[i1] if fitness_scores[i1] > fitness_scores[i2] else population[i2]

            # new population
            new_pop = []

            # === Elitism ===
            elite_idxs = np.argsort(fitness_scores)[-self.elitism:]
            for idx in elite_idxs:
                new_pop.append(population[idx].copy())

            # === Generate rest ===
            while len(new_pop) < self.population_size:
                p1 = tournament()
                p2 = tournament()
                child = self.crossover(p1, p2)
                child = self.mutate(child)
                new_pop.append(child)

            population = new_pop

        print(f"\n=== GA Finished for {self.strategy_name} ===")
        print("Best Params:", best_global)
        print("Best Score :", best_score_global)

        return best_global, best_score_global
