from agents import Agent

import numpy as np


class RandomAgent(Agent):
    def __init__(self):
        super().__init__()

    def select_move(self, game_state):
        choices = game_state.action_stack.first.choices(game_state)
        if not choices:
            return None
        return choices[np.random.randint(len(choices))]
