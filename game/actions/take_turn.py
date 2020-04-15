from game.actions.action import Choice
from game.types import FactionName

import game.state_change as sc

import attr


class TakeTurn(Choice):
    def __init__(self):
        super().__init__('Choosing an action spot')

    def choose(self, agent, game_state):
        current_player = sc.get_current_player(game_state)
        player_mat = current_player.player_mat
        if current_player.faction_name() is FactionName.RUSVIET:
            invalid = None
        else:
            invalid = player_mat.last_action_spot_taken

        return agent.choose_action_spot(game_state, invalid)

    def do(self, game_state, new_spot):
        current_player = sc.get_current_player(game_state)
        action_combo = current_player.player_mat.action_spaces[new_spot]
        current_player = attr.evolve(current_player, player_mat=current_player.player_mat.move_pawn_to(new_spot))
        game_state = sc.set_player(game_state, current_player)
        game_state = sc.push_action(game_state, action_combo[1])
        return sc.push_action(game_state, action_combo[0])
