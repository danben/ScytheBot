from game.actions.action import Choice
from game.types import FactionName


class TakeTurn(Choice):
    def __init__(self):
        super().__init__('Choosing an action spot')

    def choose(self, agent, game_state):
        player_mat = game_state.current_player.player_mat
        if game_state.current_player.faction_name() is FactionName.RUSVIET:
            invalid = None
        else:
            invalid = player_mat.last_action_spot_taken

        return agent.choose_action_spot(game_state, invalid)

    def do(self, game_state, new_spot):
        action_combo = game_state.current_player.player_mat.action_spaces[new_spot]
        game_state = game_state.set_player(game_state.current_player.player_mat.move_pawn_to(new_spot))
        game_state = game_state.push_action(action_combo[1])
        return game_state.push_action(action_combo[0])
