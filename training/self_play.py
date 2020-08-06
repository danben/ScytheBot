import logging
import multiprocessing as mp
import os
import tensorflow as tf


from training.evaluator import evaluator, profile_evaluator
from training.learner import Learner
from training.shared_memory_manager import SharedMemoryManager
from training.simulator import profile_manual_worker, manual_worker

NUM_PLAYERS = 2
NUM_WORKERS = 1
NUM_ENVS = 2
SIMULATIONS_PER_CHOICE = 10


def run_n_times(n, game_state, agents):
    from play import play
    for _ in range(n):
        play.play_game(game_state, agents)


def learner(model_base_path, training_queue):
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)
    tf.compat.v1.disable_eager_execution()
    Learner.from_file(model_base_path, training_queue).start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    workers = []
    ev_process = None
    # learner_queue = mp.Queue()
    smm = SharedMemoryManager.init(NUM_WORKERS, NUM_ENVS)
    try:
        for id in range(NUM_WORKERS):
            p = mp.Process(target=manual_worker, args=(id, NUM_PLAYERS, NUM_WORKERS,
                NUM_ENVS, SIMULATIONS_PER_CHOICE, 0.8, 2))
            workers.append(p)
            p.start()
            # os.system(f'taskset -p -c {id} {p.pid}')
        model_base_path = 'C:\\Users\\dan\\PycharmProjects\\ScytheBot\\training\\data'

        ev_process = mp.Process(target=profile_evaluator, args=(NUM_ENVS, NUM_WORKERS, model_base_path))
        ev_process.start()
        # os.system(f'taskset -p -c {NUM_WORKERS} {ev_process.pid}')
        for worker in workers:
            worker.join()
        ev_process.kill()
        smm.unlink()
        # mp.Process(target=learner, args=(model_base_path, learner_queue)).start()
    except KeyboardInterrupt:
        for worker in workers:
            worker.kill()
        ev_process.kill()
        smm.unlink()
