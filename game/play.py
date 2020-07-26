from game.actions import Choice, MaybePayCost, StateChange
from game.actions.take_turn import TakeTurn
from game.exceptions import GameOver
import game.constants as constants
import game.state_change as sc
import game.components.structure_bonus as gc_structure_bonus

import attr
import logging


def finalize(game_state):
    player_scores = {faction_name: game_state.players_by_idx[player_idx].score(game_state)
                     for faction_name, player_idx in game_state.player_idx_by_faction_name.items()}
    structure_bonus_scores = gc_structure_bonus.score(game_state.structure_bonus, game_state.board)
    for faction_name in game_state.player_idx_by_faction_name.keys():
        if faction_name not in structure_bonus_scores:
            structure_bonus_scores[faction_name] = 0
    winning_score = 0
    winner = None
    for faction_name, structure_bonus_score in structure_bonus_scores.items():
        player_scores[faction_name] += structure_bonus_score
        if player_scores[faction_name] > winning_score:
            winning_score = player_scores[faction_name]
            winner = faction_name
    game_state = attr.evolve(game_state, player_scores=player_scores, winner=winner)
    logging.debug(f'Returning game state with winner: {game_state.winner}')
    return game_state


_take_turn = TakeTurn()


def apply_move(game_state, move):
    try:
        game_state, next_action = sc.pop_action(game_state)
        assert isinstance(next_action, Choice)
        game_state = next_action.apply(game_state, move)
        while game_state.action_stack and isinstance(game_state.action_stack.first, StateChange):
            # get_current_player(game_state).invariant(game_state)
            game_state, next_action = sc.pop_action(game_state)
            game_state = next_action.apply(game_state)
        if not game_state.action_stack:
            game_state = sc.end_turn(game_state)
            if game_state.num_turns == constants.MAX_TURNS_PER_PLAYER * len(game_state.players_by_idx):
                logging.debug(f'Finalizing game after maximum of {game_state.num_turns} turns reached')
                return finalize(game_state)
            game_state = sc.push_action(game_state, _take_turn)
        elif isinstance(game_state.action_stack.first, MaybePayCost) and \
                not sc.can_pay_cost(game_state, sc.get_current_player(game_state),
                                    game_state.action_stack.first.cost(game_state)):
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f"Can't afford {game_state.action_stack.first.cost(game_state)} so skipping "
                              f"{game_state.action_stack.first}")
            return apply_move(game_state, False)
        return game_state
    except GameOver as e:
        game_state = sc.end_turn(e.game_state)
        logging.debug(f'Finalizing game since end condition was reached')
        return finalize(game_state)
