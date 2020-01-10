from game.agents import Agent

import numpy as np

class RandomAgent(Agent):
    def __init__(self):
        super().__init__()

    def choose_from(self, choices):
        return np.random.choice(choices)

    def choose_numeric(self, low, high):
        return np.random.randint(low, high)

