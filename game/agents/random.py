from game.agents import Agent

import logging
import numpy as np


class RandomAgent(Agent):
    def __init__(self):
        super().__init__()

    def choose_from(self, choices):
        choice = np.random.choice(choices)
        return choice

    def choose_numeric(self, low, high):
        return np.random.randint(low, high)

