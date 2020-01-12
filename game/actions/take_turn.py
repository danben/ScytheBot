from game.actions.dsl import *
from game.types import FactionName

import logging


class TakeTurn(DiscreteChoice):
    def __init__(self):
        super().__init__()

    def choices(self, game_state):
        player_mat = game_state.current_player.player_mat
        if game_state.current_player.faction_name() is FactionName.RUSVIET:
            action_combos = [(i, action_combo) for i, action_combo in enumerate(player_mat.action_spaces())]
        else:
            action_combos = [(i, action_combo) for i, action_combo in enumerate(player_mat.action_spaces())
                             if player_mat.last_action_spot_taken != i]

        return [Sequence.of_list([MovePawn(i), Optional(action_combo[0]), Optional(action_combo[1])])
                for i, action_combo in action_combos]


class MovePawn(StateChange):
    def __init__(self, new_spot):
        super().__init__()
        self._new_spot = new_spot

    def apply(self, game_state):
        game_state.current_player.player_mat.move_pawn_to(self._new_spot)
