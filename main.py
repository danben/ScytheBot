from agents import MCTSAgent, MCTSZeroAgent, RandomAgent
from game.game_state import GameState
from training import model
import game.play as play
import game.state_change as sc

import cProfile
import keras.backend as K
import tensorflow as tf
import logging

logging.basicConfig(level=logging.ERROR)

''' TODO list
 - all of the faction abilities
  - Polania gets 2 encounters per card
 - encounter cards
 - factory cards
 - secret objectives
 '''


def play_game(game_state, agents):
    logging.debug('\nNEW GAME\n')
    while not game_state.is_over():
        # logging.debug(f'Board: {game_state.board}')
        agent = agents[game_state.current_player_idx]
        chosen = agent.select_move(game_state)
        if logging.getLogger().isEnabledFor(logging.INFO):
            next_action = game_state.action_stack.first
            logging.info(f'{sc.get_current_player(game_state)} chooses {chosen} for {next_action}')
        game_state = play.apply_move(game_state, chosen)
        # game_state.board.invariant(game_state)
        # sc.get_current_player(game_state).invariant(game_state)

    if logging.getLogger().isEnabledFor(logging.INFO):
        logging.info(f'Game ended in {game_state.num_turns} turns')
        for (faction_name, score) in game_state.player_scores.items():
            player = sc.get_player_by_faction_name(game_state, faction_name)
            logging.info(f'\n{faction_name} scored {score} points!\n'
                         f'Popularity: {player.popularity}\n'
                         f'Stars: {player.stars.count} ({player.stars.__str__()})\n'
                         f'Territories: {len(sc.controlled_spaces(game_state, player))}\n'
                         f'Resource pairs: {sc.resource_pair_count(game_state, player)}\n'
                         f'Coins: {player.coins}\n')
            logging.info(f'Winner is {game_state.winner}')
    return game_state


def play_one_game(num_players):
    game_state = GameState.from_num_players(num_players)
    players = list(map(lambda x: x.faction_name(), game_state.players_by_idx))
    agents = [MCTSZeroAgent(model.network(), c=0.8, simulations_per_choice=5)] * num_players
    # agents = [MCTSAgent(players, temperature=0.8, num_rounds=100), RandomAgent()]
    return play_game(game_state, agents)


def play_randomly_forever(num_players):
    # agents = [RandomAgent() for _ in range(num_players)]
    # physical_devices = tf.config.list_physical_devices('GPU')
    # tf.config.experimental.set_memory_growth(physical_devices[0], True)
    agents = [MCTSZeroAgent(model.network(), c=0.8, simulations_per_choice=10)] * num_players
    while True:
        game_state = GameState.from_num_players(num_players)
        play_game(game_state, agents)


if __name__ == '__main__':
    num_players = 2
    # K.set_floatx('float16')
    # K.set_epsilon(1e-4)
    K.set_learning_phase(0)

    # V1
    # physical_devices = tf.config.experimental.list_physical_devices('GPU')
    # tf.config.experimental.set_memory_growth(physical_devices[0], True)
    # tf.compat.v1.config.optimizer.set_experimental_options({'layout_optimizer':True})

    # V2
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)

    # play_one_game(num_players)
    # tf.config.set_visible_devices([], 'GPU')
    # tf.debugging.set_log_device_placement(True)
    # import os
    # os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    cProfile.run('play_one_game(num_players)', sort='cumtime')
    # play_randomly_forever(num_players)
    # mcts_wins = 0
    # for i in range(100):
    #     end_state = play_one_game(num_players)
    #     mcts_player = end_state.players_by_idx[0].faction_name()
    #     if mcts_player is end_state.winner:
    #         print(f'Game {i} won by MCTS ({mcts_player})')
    #         mcts_wins += 1
    #     else:
    #         print(f'Game {i} won by random ({end_state.winner})')
    # print(f'MCTS won {mcts_wins} out of 100 games')
    # cProfile.run('play_game(agents)', sort='cumtime')
