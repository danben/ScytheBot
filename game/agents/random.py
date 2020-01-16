from game.agents import Agent
from game.types import ResourceType

import logging
import numpy as np


class RandomAgent(Agent):
    def __init__(self):
        super().__init__()

    def choose_action_spot(self, game_state, invalid):
        return np.random.choice([i for i in range(4) if i is not invalid])

    def choose_boolean(self, game_state):
        return np.random.choice([False, True])

    def choose_from(self, _game_state, choices):
        choice = np.random.choice(choices)
        return choice

    def choose_numeric(self, game_state, low, high):
        logging.debug(f'Choosing between {low} and {high}')
        return np.random.randint(low, high+1)

    def choose_board_space(self, game_state, board_spaces):
        return np.random.choice(board_spaces)

    def choose_piece(self, game_state, pieces):
        return np.random.choice(pieces)

    def choose_whether_to_pay_for_next_action(self, game_state):
        return self.choose_boolean(game_state)

    def choose_resource_type(self, game_state):
        return np.random.choice([r for r in ResourceType])

    def choose_bottom_action(self, game_state, bottom_actions):
        return np.random.choice(bottom_actions)

    def choose_enlist_reward(self, game_state):
        return np.random.choice([enlist_reward for enlist_reward in
                                 game_state.current_player.available_enlist_rewards()])

    def choose_mech_to_deploy(self, game_state):
        return np.random.choice([mech for mech in game_state.current_player.undeployed_mechs()])

    def choose_structure_to_build(self, game_state):
        return np.random.choice([top_action for top_action in
                                 game_state.current_player.top_actions_with_unbuilt_structures()])

    def choose_cube_space_to_upgrade(self, game_state):
        cube_spaces = game_state.current_player.cube_spaces_not_fully_upgraded()
        return cube_spaces[np.random.choice(len(cube_spaces))]

    def choose_optional_combat_card(self, game_state):
        return game_state.current_player.random_combat_card(optional=True)
