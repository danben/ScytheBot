from game.actions import Choice, MaybePayCost, StateChange, TakeTurn
from game.agents import RandomAgent
from game.exceptions import GameOver
from game.game_state import GameState
import game.components.structure_bonus as structure_bonus

import attr
import cProfile
import logging

from pyrsistent import pset

logging.basicConfig(level=logging.ERROR)

''' TODO list
 - add reprs for types
 - agents need to be able to specify the amount of workers they take when producing (maybe use choose_numeric for now)
 - make sure all actions have the right level of optionality
 - implement NumericChoice actions
 - redo DiscreteChoice actions to be more specific
 - all of the faction abilities
  - Polania gets 2 encounters per card
 - encounter cards
 - factory cards
 - secret objectives
 - stringify everything
 - logging
 - random agent
 '''


def advance(game_state, agents):
    agent = agents[game_state.current_player_idx]
    game_state, next_action = GameState.pop_action(game_state)
    while next_action and isinstance(next_action, StateChange):
        game_state = next_action.apply(game_state)
        game_state, next_action = GameState.pop_action(game_state) if game_state.action_stack else game_state, None

    if not next_action:
        return game_state

    if isinstance(next_action, MaybePayCost) and \
            not game_state.current_player.can_pay_cost(next_action.cost(game_state)):
        logging.debug(f"Can't afford {next_action.cost(game_state)} so skipping {next_action}")
        return game_state
    else:
        assert isinstance(next_action, Choice)
        chosen = next_action.choose(agent, game_state)
        game_state = next_action.apply(game_state, chosen)
        return game_state


def play(game_state, agents):
    num_turns = 0
    try:
        take_turn = TakeTurn()
        while True:
            game_state.current_player = game_state.players[game_state.current_player_idx]
            logging.debug(f'Next player: {game_state.current_player.faction_name()} / '
                          f'{game_state.current_player.player_mat.name}')
            logging.debug(f'{game_state.current_player.to_string()}')
            logging.debug(f'Board: {game_state.board!r}')
            game_state.board.invariant()
            game_state.action_stack.append(take_turn)
            while game_state.action_stack:
                game_state = advance(game_state, agents)
            game_state = GameState.end_turn(game_state, game_state.current_player())
            game_state.current_player().invariant()

            # TODO: Why is this not a property of the board?
            board = game_state.board
            for space in game_state.spaces_produced_this_turn:
                board = board.set_space(attr.evolve(space, produced_this_turn=False))
            next_player_idx = game_state.current_player_idx + 1
            if next_player_idx == len(game_state.players_by_idx):
                next_player_idx = 0
            game_state = attr.evolve(game_state, board=board, current_player_idx=next_player_idx,
                                     spaces_produced_this_turn=pset())
            num_turns += 1
            if num_turns == 50:
                logging.debug("50 turns without a winner")
                raise GameOver(None)
    except GameOver as e:
        if e.player:
            game_state = GameState.set_player(game_state, e.player)
        player_scores = {faction_name: game_state.players_by_idx[player_idx].score()
                         for faction_name, player_idx in game_state.player_idx_by_faction_name.items()}
        structure_bonus_scores = structure_bonus.score(game_state.structure_bonus, game_state.board)
        for faction_name, structure_bonus_score in structure_bonus_scores.items():
            player_scores[faction_name] += structure_bonus_score

        for (player, score) in player_scores.items():
            print(f'{player} scored {score} points')


if __name__ == '__main__':
    num_players = 2
    agents = [RandomAgent() for _ in range(num_players)]
    game_state = GameState.from_num_players(num_players)
    cProfile.run('play(game_state, agents)', sort='tottime')
