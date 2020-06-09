from game.actions import Choice
from game.types import FactionName


import game.state_change as sc

from pyrsistent import thaw

import attr
import logging


class TakeTurn(Choice):
    def __init__(self):
        super().__init__('New turn')

    def choices(self, game_state):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            current_player = sc.get_current_player(game_state)
            logging.debug(f'{current_player} choosing an action spot')
        current_player = sc.get_current_player(game_state)
        player_mat = current_player.player_mat
        action_spaces = thaw(player_mat.action_spaces)
        if current_player.faction_name() is FactionName.RUSVIET:
            return list(enumerate(action_spaces))
        else:
            return [(i, action_space) for i, action_space in enumerate(action_spaces)
                    if i != player_mat.last_action_spot_taken]

    def choose(self, agent, game_state):
        return agent.choose_action_spot(game_state, self.choices(game_state))

    def do(self, game_state, chosen):
        index, action_combo = chosen
        current_player = sc.get_current_player(game_state)
        current_player = attr.evolve(current_player, player_mat=current_player.player_mat.move_pawn_to(index))
        game_state = sc.set_player(game_state, current_player)
        game_state = sc.push_action(game_state, action_combo[1])
        return sc.push_action(game_state, action_combo[0])
