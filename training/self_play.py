import asyncio
import cProfile
import logging
import multiprocessing as mp
import time

import numpy as np
import tensorflow as tf

from multiprocessing import shared_memory

import training.constants as model_const

from encoders.game_state import EncodedGameState
from training.learner import Learner
from training.model import load as load_model
from training.shared_memory_manager import get_segment_name, DataType, SharedMemoryManager
from training.simulator import worker
from training.worker_env_conn import WorkerEnvConn

NUM_PLAYERS = 2
NUM_WORKERS = 4
NUM_ENVS = 2
SIMULATIONS_PER_CHOICE = 5


def run_n_times(n, game_state, agents):
    from play import play
    for _ in range(n):
        play.play_game(game_state, agents)


def evaluator(num_envs, num_workers, model_base_path):
    # An environment is a group of workers and a single index. Each worker will be simulating multiple
    # games sequentially; it will put game states from game N into environment N.
    from training import model
    import tensorflow as tf
    # import time
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)
    tf.compat.v1.disable_eager_execution()
    # Set up shared memory buffers. Each contains all of the memory for one data type in a single environment.
    # Each element of preds will be a list of arrays corresponding to each model head.
    boards, data, preds, shms = [], [], [], []
    for env_id in range(num_envs):
        # Get the batch from shared memory
        boards_buf = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.BOARDS))
        shms.append(boards_buf)
        data_buf = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.DATA))
        shms.append(data_buf)

        # Put into the right shapes
        boards_shape = (num_workers,) + EncodedGameState.board_shape
        boards.append(np.ndarray(boards_shape, buffer=boards_buf))

        data_shape = (num_workers,) + EncodedGameState.data_shape
        data.append(np.ndarray(data_shape, buffer=data_buf))

        heads = []
        for head in model_const.Head:
            head_buf = shared_memory.SharedMemory(name=f'{get_segment_name(env_id, DataType.PREDS)}-{head.value}')
            shms.append(head_buf)
            head_shape = (num_workers, model.head_sizes[head])
            heads.append(np.ndarray(head_shape, buffer=head_buf))
        preds.append(heads)

    nn = load_model(model_base_path)

    def env_loop(env_id, worker_env_conns):
        while True:
            # Block until every worker has sent in a sample for evaluation in
            # this environment
            asyncio.wait([worker_env_conn.env_get_woken_up() for worker_env_conn in worker_env_conns])

            predictions = nn.predict(boards[env_id], data[env_id], batch_size=num_workers)
            for head in model_const.Head:
                assert preds[env_id][head.value].shape == predictions[head.value].shape
                preds[env_id][head.value][:] = predictions[head.value]

            # Notify the workers that their predictions are ready
            for worker_env_conn in worker_env_conns:
                worker_env_conn.wake_up_worker()

    asyncio.wait([env_loop(env_id, [WorkerEnvConn.for_env(env_id, worker_id) for worker_id in num_workers])
                  for env_id in range(num_envs)])


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
    smm = SharedMemoryManager.init(NUM_WORKERS, NUM_ENVS)
    for id in range(NUM_WORKERS):
        conn1, conn2 = mp.Pipe()
        worker_conns.append(conn1)
        p = mp.Process(target=worker, args=(id, NUM_WORKERS, NUM_ENVS, learner_queue, NUM_PLAYERS,
                                            SIMULATIONS_PER_CHOICE))
        workers.append(p)
        p.start()
    model_base_path = 'C:\\Users\\dan\\PycharmProjects\\ScytheBot\\training\\data'

    mp.Process(target=evaluator, args=(NUM_ENVS, NUM_WORKERS, model_base_path)).start()
    mp.Process(target=learner, args=(model_base_path, learner_queue)).start()
