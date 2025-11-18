import random
import numpy as np

class GeneticOptimizer:
    def __init__(self, search_space, config, fitness_function):
        self.search_space = search_space
        self.config = config
        self.fitness_function = fitness_function

        self.population_size = config.get("population_size", 20)
        self.generations = config.get("generations", 15)
        self.mutation_rate = config.get("mutation_rate", 0.1)
        self.crossover_rate = config.get("crossover_rate", 0.7)
        self.elitism = config.get("elitism", 2)

    # --------------------------- Create individual -------------------------
    def sample_individual(self):
        ind = {}
        for key, (low, high) in self.search_space.items():
            if isinstance(low, int) and isinstance(high, int):
                ind[key] = random.randint(low, high)
            else:
                ind[key] = random.uniform(low, high)
        return ind

    # --------------------------- Crossover -------------------------
    def crossover(self, p1, p2):
        child = {}
        for key in p1.keys():
            if random.random() < self.crossover_rate:
                child[key] = p1[key]
            else:
                child[key] = p2[key]
        return child

    # --------------------------- Mutation -------------------------
    def mutate(self, ind):
        for key, (low, high) in self.search_space.items():
            if random.random() < self.mutation_rate:
                if isinstance(low, int):
                    ind[key] = random.randint(low, high)
                else:
                    ind[key] = random.uniform(low, high)
        return ind

    # --------------------------- Fitness wrapper -------------------------
    def evaluate_population(self, population):
        fitness_scores = []
        for ind in population:
            score = self.fitness_function(ind)
            fitness_scores.append(score)
        return fitness_scores

    # --------------------------- Main GA Loop -------------------------
    def run(self):
        population = [self.sample_individual() for _ in range(self.population_size)]
        best_global = None
        best_score_global = -np.inf

        for g in range(self.generations):
            fitness_scores = self.evaluate_population(population)

            # Track best of generation
            gen_best_idx = np.argmax(fitness_scores)
            gen_best_score = fitness_scores[gen_best_idx]
            gen_best = population[gen_best_idx]

            if gen_best_score > best_score_global:
                best_score_global = gen_best_score
                best_global = gen_best.copy()

            print(f"Gen {g+1}/{self.generations} | Best Score: {gen_best_score}")

            # Select parents (tournament selection)
            def tournament():
                i1, i2 = random.sample(range(self.population_size), 2)
                return population[i1] if fitness_scores[i1] > fitness_scores[i2] else population[i2]

            new_population = []

            # Elitism
            elite_indices = np.argsort(fitness_scores)[-self.elitism:]
            for idx in elite_indices:
                new_population.append(population[idx].copy())

            # Fill new population
            while len(new_population) < self.population_size:
                parent1 = tournament()
                parent2 = tournament()
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                new_population.append(child)

            population = new_population

        return best_global, best_score_global
