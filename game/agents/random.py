from game.agents import Agent
from game.types import ResourceType

import logging
import numpy as np


class RandomAgent(Agent):
    def __init__(self):
        super().__init__()

    def choose_action(self, game_state, actions):
        return np.random.choice(actions)

    def choose_action_spot(self, game_state, choices):
        return choices[np.random.randint(len(choices))]

    def choose_boolean(self, game_state):
        return np.random.choice([False, True])

    def choose_from(self, _game_state, choices):
        choice = np.random.choice(choices)
        return choice

    def choose_numeric(self, game_state, choices):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Available choices: {choices}')
        return np.random.choice(choices)

    def choose_board_coords(self, game_state, choices):
        return choices[np.random.randint(len(choices))]

    def choose_piece(self, game_state, choices):
        return np.random.choice(choices)

    def choose_resource_typ(self, game_state, choices):
        return np.random.choice([r for r in ResourceType])

    def choose_bottom_action_typ(self, game_state, choices):
        return np.random.choice(choices)

    def choose_enlist_reward(self, game_state, choices):
        return np.random.choice(choices)

    def choose_mech_typ_to_deploy(self, game_state, choices):
        return np.random.choice(choices)

    def choose_structure_typ(self, game_state, choices):
        return np.random.choice(choices)

    def choose_cube_space_to_upgrade(self, game_state, choices):
        return choices[np.random.randint(len(choices))]

    def choose_optional_combat_card(self, game_state, choices):
        return np.random.choice([None] + choices)

    def choose_optional_resource_typ(self, game_state, choices):
        return np.random.choice([None] + choices)
