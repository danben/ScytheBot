from game.agents import Agent
from game.types import ResourceType, StructureType
import game.state_change as sc

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
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Choosing between {low} and {high}')
        return np.random.randint(low, high+1)

    def choose_board_coords(self, game_state, board_coords):
        return board_coords[np.random.randint(len(board_coords))]

    def choose_piece(self, game_state, pieces):
        return np.random.choice(pieces)

    def choose_whether_to_pay_for_next_action(self, game_state):
        return self.choose_boolean(game_state)

    def choose_resource_type(self, game_state):
        return np.random.choice([r for r in ResourceType])

    def choose_bottom_action_type(self, game_state, bottom_action_types):
        return np.random.choice(bottom_action_types)

    def choose_enlist_reward(self, game_state):
        return np.random.choice(sc.get_current_player(game_state).available_enlist_rewards())

    def choose_mech_type_to_deploy(self, game_state):
        return np.random.choice(sc.get_current_player(game_state).undeployed_mech_types())

    def choose_structure_to_build(self, game_state):
        choices = sc.get_current_player(game_state).top_action_types_with_unbuilt_structures()
        return StructureType.of_top_action_typ(np.random.choice([top_action_type for top_action_type in choices]))

    def choose_cube_space_to_upgrade(self, game_state):
        cube_spaces = sc.get_current_player(game_state).cube_spaces_not_fully_upgraded()
        return cube_spaces[np.random.choice(len(cube_spaces))]

    def choose_optional_combat_card(self, game_state):
        return sc.get_current_player(game_state).random_combat_card(optional=True)
