from game.actions import Choice, MaybePayCost, StateChange, TakeTurn
from game.agents import RandomAgent
from game.exceptions import GameOver
from game.game_state import GameState
import game.components.structure_bonus as structure_bonus

from copy import deepcopy
import logging

logging.basicConfig(level=logging.DEBUG)

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


def advance(game_state):
    agent = game_state.agents_by_player[game_state.current_player]
    game_state = deepcopy(game_state)
    next_action = game_state.action_stack.pop()
    while next_action and isinstance(next_action, StateChange):
        next_action.apply(game_state)
        next_action = game_state.action_stack.pop() if game_state.action_stack else None

    if not next_action:
        return game_state

    if isinstance(next_action, MaybePayCost) and not game_state.current_player.can_pay_cost(next_action.cost()):
        logging.debug(f"Can't afford {next_action.cost()!r} so skipping {next_action!r}")
        return game_state
    else:
        assert isinstance(next_action, Choice)
        chosen = next_action.choose(agent, game_state)
        next_action.apply(game_state, chosen)
        return game_state


def play(game_state):
    num_turns = 0
    try:
        take_turn = TakeTurn()
        while True:
            game_state.current_player = game_state.players[game_state.current_player_idx]
            logging.debug(f'Next player: {game_state.current_player.faction_name()} / '
                          f'{game_state.current_player.player_mat.name}')
            logging.debug(f'{game_state.current_player.to_string()}')
            game_state.action_stack.append(take_turn)
            while game_state.action_stack:
                game_state = advance(game_state)
            game_state.current_player.end_turn()

            # TODO: Why is this not a property of the board?
            for space in game_state.spaces_produced_this_turn:
                space.produced_this_turn = False
            game_state.spaces_produced_this_turn.clear()
            game_state.current_player_idx += 1
            if game_state.current_player_idx == len(game_state.players):
                game_state.current_player_idx = 0
            num_turns += 1
            if num_turns == 500:
                logging.debug("500 turns without a winner")
                raise GameOver()
    except GameOver:
        player_scores = {faction_name: player.score() for faction_name, player in game_state.players_by_faction.items()}
        structure_bonus_scores = structure_bonus.score(game_state.structure_bonus, game_state.board)
        for faction_name, structure_bonus_score in structure_bonus_scores.items():
            player_scores[faction_name] += structure_bonus_score

        for (player, score) in player_scores.items():
            print(f'{player} scored {score} points')


if __name__ == '__main__':
    num_players = 2
    agents = [RandomAgent() for _ in range(num_players)]
    game_state = GameState(agents)
    play(game_state)
