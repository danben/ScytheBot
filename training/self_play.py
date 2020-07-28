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
from training.shared_memory_manager import segment_name, DataType

NUM_PLAYERS = 2
NUM_WORKERS = 4
SIMULATIONS_PER_CHOICE = 5


def run_n_times(n, game_state, agents):
    from play import play
    for _ in range(n):
        play.play_game(game_state, agents)


def evaluator(envs):
    # An environment is a group of workers and a single index. Each worker will be simulating multiple
    # games sequentially; it will put game states from game N into environment N.
    from training import model
    import tensorflow as tf
    # import time
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)
    tf.compat.v1.disable_eager_execution()
    nn = model.network()
    # Set up shared memory buffers. Each contains all of the memory for one data type in a single environment.
    # Each element of preds will be a list of arrays corresponding to each model head.
    boards, data, preds, shms = [], [], [], []
    num_workers = len(envs[0])
    for env_id, worker_pipes in envs.items():
        # Get the batch from shared memory
        boards_buf = shared_memory.SharedMemory(name=segment_name(env_id, DataType.BOARDS))
        shms.append(boards_buf)
        data_buf = shared_memory.SharedMemory(name=segment_name(env_id, DataType.DATA))
        shms.append(data_buf)

        # Put into the right shapes
        boards_shape = (num_workers,) + EncodedGameState.board_shape
        boards.append(np.ndarray(boards_shape, buffer=boards_buf))

        data_shape = (num_workers,) + EncodedGameState.data_shape
        data.append(np.ndarray(data_shape, buffer=data_buf))

        heads = []
        for head in model_const.Head:
            head_buf = shared_memory.SharedMemory(name=f'{segment_name(env_id, DataType.PREDS)}-{head.value}')
            shms.append(head_buf)
            head_shape = (len(worker_pipes), model.head_sizes[head])
            heads.append(np.ndarray(head_shape, buffer=head_buf))
        preds.append(heads)

    while True:
        for env_id, worker_pipes in envs.items():
            # Block until every worker has sent in a sample for evaluation in
            # this environment
            for p in worker_pipes:
                p.recv()

            predictions = nn.predict(boards[env_id], data[env_id], batch_size=num_workers)
            for head in model_const.Head:
                assert preds[head.value].shape == predictions[head.value].shape
                preds[head.value][:] = predictions[head.value]

            # Notify the workers that their predictions are ready
            for p in worker_pipes:
                p.send(0)
        #
        # game_states = []
        # choices = []
        # # print(f'Evaluator waiting for inputs')
        # t = time.time()
        # for conn in conns:
        #     # TODO: don't fail if a worker dies
        #     gs, c = conn.recv()
        #     game_states.append(gs)
        #     choices.append(c)
        # # print(f'Took {time.time() - t}s to get all inputs')
        # start = time.time()
        # values, priors = model.evaluate(nn, game_states, choices)
        # # print(f'Prediction batch completed in {time.time() - start}s')
        # for i, conn in enumerate(conns):
        #     conn.send((values[i], priors[i]))


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
