import cProfile
import logging
import multiprocessing as mp
import time

import tensorflow as tf

from training.learner import Learner

NUM_PLAYERS = 2
NUM_WORKERS = 4
SIMULATIONS_PER_CHOICE = 5


def run_n_times(n, game_state, agents):
    from play import play
    for _ in range(n):
        play.play_game(game_state, agents)


def worker(wid, evaluator_conn, learner_queue, stop_after=None):
    from agents.mcts_zero import MCTSZeroAgent
    from game.game_state import GameState
    from play import play
    import time
    print(f'Worker {wid} starting')
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'Worker {wid} starting')
    game_state = GameState.from_num_players(NUM_PLAYERS)
    agents = [MCTSZeroAgent(c=0.8, simulations_per_choice=SIMULATIONS_PER_CHOICE, evaluator_conn=evaluator_conn)
              for _ in range(NUM_PLAYERS)]
    # cProfile.runctx('run_n_times(1, game_state, agents)', globals(), locals(), sort='cumtime')
    # time.sleep(10000)

    num_games = 0
    while stop_after is None or num_games >= stop_after:
        for agent in agents:
            agent.begin_episode()
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Worker {wid} starting a self-play match')
        print(f'Worker {wid} starting a self-play match')
        start = time.time()
        play.play_game(game_state, agents)
        end = time.time()
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Worker {wid} finished a game at {end} ({end - start} seconds)')
        print(f'Worker {wid} finished a game at {end} ({end - start} seconds)')
        for agent in agents:
            agent.complete_episode(game_state.winner)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Worker {wid} adding {len(agent.experience_collector.game_states)} '
                              f'samples to learner queue')
            print(f'Worker {wid} adding {len(agent.experience_collector.game_states)} samples to learner queue')
            learner_queue.put(agent.experience_collector.to_numpy())
        num_games += 1


def evaluator(conns):
    from training import model
    import tensorflow as tf
    # import time
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)
    tf.compat.v1.disable_eager_execution()
    nn = model.network()
    while True:
        game_states = []
        choices = []
        # print(f'Evaluator waiting for inputs')
        t = time.time()
        for conn in conns:
            # TODO: don't fail if a worker dies
            gs, c = conn.recv()
            game_states.append(gs)
            choices.append(c)
        # print(f'Took {time.time() - t}s to get all inputs')
        start = time.time()
        values, priors = model.evaluate(nn, game_states, choices)
        # print(f'Prediction batch completed in {time.time() - start}s')
        for i, conn in enumerate(conns):
            conn.send((values[i], priors[i]))


def learner(model_base_path, training_queue):
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)
    tf.compat.v1.disable_eager_execution()
    Learner.from_file(model_base_path, training_queue).start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    worker_conns = []
    workers = []
    learner_queue = mp.Queue()
    for id in range(NUM_WORKERS):
        conn1, conn2 = mp.Pipe()
        worker_conns.append(conn1)
        p = mp.Process(target=worker, args=(id, conn2, learner_queue))
        workers.append(p)
        p.start()
    model_base_path = 'C:\\Users\\dan\\PycharmProjects\\ScytheBot\\training\\data'
    mp.Process(target=evaluator, args=(worker_conns,)).start()
    mp.Process(target=learner, args=(model_base_path, learner_queue)).start()
