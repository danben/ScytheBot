import logging
import multiprocessing as mp
import os
import tensorflow as tf


from training.learner import Learner
from training.shared_memory_manager import SharedMemoryManager
from training.simulator import profile_async_worker, async_worker

NUM_PLAYERS = 2
NUM_WORKERS = 4
NUM_ENVS = 4
SIMULATIONS_PER_CHOICE = 1


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
    learner_queue = mp.Queue()
    smm = SharedMemoryManager.init(NUM_WORKERS, NUM_ENVS)
    try:
        for id in range(NUM_WORKERS):
            p = mp.Process(target=profile_async_worker, args=(id, NUM_WORKERS, NUM_ENVS, learner_queue, NUM_PLAYERS,
                                                        SIMULATIONS_PER_CHOICE))
            workers.append(p)
            p.start()
            os.system(f'taskset -p -c {id} {p.pid}')
        model_base_path = 'C:\\Users\\dan\\PycharmProjects\\ScytheBot\\training\\data'

        p = mp.Process(target=evaluator, args=(NUM_ENVS, NUM_WORKERS, model_base_path))
        p.start()
        os.system(f'taskset -p -c {NUM_WORKERS} {p.pid}')
        for worker in workers:
            worker.join()
        p.kill()
        smm.unlink()
        # mp.Process(target=learner, args=(model_base_path, learner_queue)).start()
    except KeyboardInterrupt:
        for worker in workers:
            worker.kill()
        smm.unlink()
