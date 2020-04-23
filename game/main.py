import game.actions.action as action
import game.actions.take_turn as take_turn
from game.agents import RandomAgent
from game.exceptions import GameOver
from game.game_state import GameState
import game.components.structure_bonus as structure_bonus
import game.state_change as sc

import attr
import cProfile
import logging

from pyrsistent import pset

logging.basicConfig(level=logging.ERROR)

''' TODO list
 - all of the faction abilities
  - Polania gets 2 encounters per card
 - encounter cards
 - factory cards
 - secret objectives
 '''


def advance(game_state, agents):
    agent = agents[game_state.current_player_idx]
    game_state, next_action = sc.pop_action(game_state)
    while next_action and isinstance(next_action, action.StateChange):
        game_state = next_action.apply(game_state)
        sc.get_current_player(game_state).invariant(game_state)
        if game_state.action_stack:
            game_state, next_action = sc.pop_action(game_state)
        else:
            game_state, next_action = game_state, None

    if not next_action:
        return game_state

    if isinstance(next_action, action.MaybePayCost) and \
            not sc.can_pay_cost(game_state, sc.get_current_player(game_state), next_action.cost(game_state)):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"Can't afford {next_action.cost(game_state)} so skipping {next_action}")
        return game_state
    else:
        assert isinstance(next_action, action.Choice)
        chosen = next_action.choose(agent, game_state)
        game_state = next_action.apply(game_state, chosen)
        # sc.get_current_player(game_state).invariant(game_state)
        return game_state


def play(game_state, agents):
    num_turns = 0
    try:
        tt = take_turn.TakeTurn()
        while True:
            current_player = sc.get_current_player(game_state)
            logging.debug(current_player)
            # logging.debug(f'Board: {game_state.board}')
            # game_state.board.invariant(game_state)
            game_state = sc.push_action(game_state, tt)
            while game_state.action_stack:
                game_state = advance(game_state, agents)
            game_state = sc.end_turn(game_state, sc.get_current_player(game_state))
            sc.get_current_player(game_state).invariant(game_state)

            board = game_state.board
            for space_coords in game_state.spaces_produced_this_turn:
                space = attr.evolve(board.get_space(space_coords), produced_this_turn=False)
                board = board.set_space(space)
            next_player_idx = game_state.current_player_idx + 1
            if next_player_idx == len(game_state.players_by_idx):
                next_player_idx = 0
            game_state = attr.evolve(game_state, board=board, current_player_idx=next_player_idx,
                                     spaces_produced_this_turn=pset())
            num_turns += 1
            # if num_turns == 50:
            #     logging.info("50 turns without a winner")
            #     raise GameOver(None)
    except GameOver as e:
        if e.game_state:
            game_state = e.game_state
        player_scores = {faction_name: game_state.players_by_idx[player_idx].score(game_state)
                         for faction_name, player_idx in game_state.player_idx_by_faction_name.items()}
        structure_bonus_scores = structure_bonus.score(game_state.structure_bonus, game_state.board)
        for faction_name, structure_bonus_score in structure_bonus_scores.items():
            player_scores[faction_name] += structure_bonus_score

        logging.info(f'Game ended in {num_turns} turns')
        for (faction_name, score) in player_scores.items():
            player = sc.get_player_by_faction_name(game_state, faction_name)
            logging.info(f'{faction_name} scored {score} points ({player.stars.__str__()}')


if __name__ == '__main__':
    num_players = 2
    agents = [RandomAgent() for _ in range(num_players)]
    game_state = GameState.from_num_players(num_players)
    while True:
        play(game_state, agents)
    # cProfile.run('play(game_state, agents)', sort='tottime')
