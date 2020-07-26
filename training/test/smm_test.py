import multiprocessing as mp
import numpy as np
import logging
import os
import time

from encoders import game_state as gs_enc
from training import model, constants as model_const
from training import shared_memory_manager


def board_value(env_id, worker_id, row, col, plane):
    return row * 10000 + col * 1000 + plane * 100 + env_id * 10 + worker_id


def data_value(env_id, worker_id, index):
    return index * 100 + env_id * 10 + worker_id


def pred_value(env_id, worker_id, head, index):
    return head * 1000 + index * 100 + env_id * 10 + worker_id


def check_boards(boards, num_workers, env_id):
    w, r, c, p = boards.shape
    assert w == num_workers
    for worker_id in range(w):
        for row in range(r):
            for col in range(c):
                for plane in range(p):
                    assert boards[w, r, c, p] == board_value(env_id, w, r, c, p)


def check_data(data, num_workers, env_id):
    w, l = data.shape
    assert w == num_workers
    for worker_id in range(w):
        for index in range(l):
            assert data[w, index] == data_value(env_id, w, index)


def check_preds(preds, env_id, worker_id):
    for head in model_const.Head:
        l = len(preds[head.value])
        assert l == model.head_sizes[head]
        for index in range(l):
            assert preds[head][index] == pred_value(env_id, worker_id, head, index)


def worker(env_id, num_workers, worker_id, conn):
    # A worker should write down some fake data into its reserved area for game encodings, sleep, and then
    # read back prediction data.
    print(f'Worker {worker_id+1} of {num_workers} starting for environment {env_id}')
    board = shared_memory_manager.SharedMemoryManager.get_worker_view(env_id, num_workers, worker_id)
    print(f'In smm_test, about to look at id {id(board)} (process {os.getpid()})')
    print(board)
    print(f'Worker {worker_id} got shared memory view for environment {env_id}')
    # assert my_view.board.shape == gs_enc.EncodedGameState.board_shape
    # assert my_view.data.shape == gs_enc.EncodedGameState.data_shape
    # for i, p in enumerate(my_view.preds):
    #     assert p.shape == (model.head_sizes[model_const.Head(i)],)
    # board_data = np.fromfunction(lambda x, y, z: board_value(env_id, worker_id, x, y, z), my_view.board.shape)
    # print(f'Worker {worker_id} created fake board data')
    # print(f'Shape of view data: {my_view.board.shape}')
    # print(type(my_view.board))
    # print(f'About to segfault (process {os.getpid()}) trying to look at {id(my_view.board)}')
    # print(my_view.board)
    # for x in range(my_view.board.shape[0]):
    #     for y in range(my_view.board.shape[1]):
    #         for z in range(my_view.board.shape[2]):
    #             print(f'Attempting to access ({x, y, z})')
    #             print(my_view.board[x][y][z])
    # my_view.board[:] = board_data
    # print(f'Worker {worker_id} copied fake board data to shared memory')
    # data_data = np.fromfunction(lambda x: data_value(env_id, worker_id, x), my_view.data.shape)
    # my_view.data[:] = data_data
    # print(f'Worker {worker_id} done writing data for environment {env_id}')
    # conn.send(worker_id)
    # print(f'Worker {worker_id} signalling evaluator for environment {env_id}')
    # received_env_id = conn.recv()
    # print(f'Worker {worker_id} received signal from environment {received_env_id} (expected: {env_id})')
    # check_preds(my_view.preds, env_id, worker_id)


def evaluator(num_workers, env_id, conns):
    print(f'Evaluator {env_id} starting up')
    # An evaluator should sleep, read data for game encodings, and then write back prediction data.
    my_view = shared_memory_manager.SharedMemoryManager.get_evaluator_view(env_id, num_workers)
    assert my_view.board.shape == (num_workers,) + gs_enc.EncodedGameState.board_shape
    # assert my_view.data.shape == (num_workers,) + gs_enc.EncodedGameState.data_shape
    # for i, pred_head in enumerate(my_view.preds):
    #     assert pred_head.shape == (num_workers, model.head_sizes[model_const.Head(i)])
    # for conn in conns:
    #     print(f'Evaluator {env_id} waiting for a wake-up signal')
    #     worker_id = conn.recv()
    #     print(f'Evaluator {env_id} received a wake-up signal from worker {worker_id}')
    # print(f'Evaluator {env_id} received all wake-up signals')
    check_boards(my_view.board, num_workers, env_id)
    # check_data(my_view.data, num_workers, env_id)
    # for head in model_const.Head:
    #     for worker_id in range(num_workers):
    #         for index in range(model.head_sizes[head]):
    #             my_view[head.value][worker_id, index] = pred_value(env_id, worker_id, head, index)
    # for conn in conns:
    #     conn.send(env_id)


def test():
    # Initialize some shared memory, then kick off some processes for reading and writing. These processes
    # should mimic workers and evaluators in that the workers should be reading from and writing to their own
    # specific slices of memory, and the evaluators should have access to everything.
    num_workers = 1
    envs_per_worker = 1
    # smm = shared_memory_manager.SharedMemoryManager.init(num_workers, envs_per_worker)
    shared_memory_manager.Env.init(num_workers, 0)
    # conns = {(worker_id, env_id): mp.Pipe(duplex=True) for worker_id in range(num_workers)
    #          for env_id in range(envs_per_worker)}
    # procs = []
    # for worker_id in range(num_workers):
    #     for env_id in range(envs_per_worker):
    #         p = mp.Process(target=worker, args=(env_id, num_workers, worker_id, conns[worker_id, env_id][0]))
    #         procs.append(p)
            # p.start()
            # worker(env_id, num_workers, worker_id, None)
    worker(0, num_workers, 0, None)
    # for p in procs:
    #     p.join()

    # for env_id in range(envs_per_worker):
    #     p = mp.Process(target=evaluator, args=(num_workers, env_id,
    #                                        [conns[worker_id, env_id][1] for worker_id in range(num_workers)]))
    #     procs.append(p)
    #     p.start()
    #     p.join()

    # for p in procs:
    #     p.join()


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    test()
