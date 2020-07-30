import asyncio
import multiprocessing as mp
import numpy as np
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
    return head.value * 1000 + index * 100 + env_id * 10 + worker_id


def check_boards(boards, num_workers, env_id):
    w, r, c, p = boards.shape
    assert w == num_workers
    for worker_id in range(w):
        for row in range(r):
            for col in range(c):
                for plane in range(p):
                    assert boards[worker_id, row, col, plane] == board_value(env_id, worker_id, row, col, plane)


def check_data(data, num_workers, env_id):
    w, l = data.shape
    assert w == num_workers
    for worker_id in range(w):
        for index in range(l):
            assert data[worker_id, index] == data_value(env_id, worker_id, index)


def check_preds(preds, env_id, worker_id):
    for head in model_const.Head:
        l = len(preds[head.value])
        assert l == model.head_sizes[head]
        for index in range(l):
            assert preds[head.value][index] == pred_value(env_id, worker_id, head, index)


def get_fifo_name(worker_id, env_id, suffix):
    return f'/tmp/fifo-{worker_id}-{env_id}-{suffix}'


def receive_from(fd):
    loop = asyncio.get_event_loop()
    future = loop.create_future()

    def set_determined():
        result = fd.read(1)
        future.set_result(result[0])
        loop.remove_reader(fd)

    loop.add_reader(fd, set_determined)
    return future


async def worker_coro(env_id, num_workers, worker_id):
    # A worker should write down some fake data into its reserved area for game encodings, sleep, and then
    # read back prediction data.
    print(f'Worker {worker_id+1} of {num_workers} starting for environment {env_id}')
    conn_out = open(get_fifo_name(worker_id, env_id, "encoding"), 'a+b', buffering=0)
    conn_in = open(get_fifo_name(worker_id, env_id, "preds"), 'rb', buffering=0)
    env = shared_memory_manager.SharedMemoryManager.make_env(env_id)
    my_view = shared_memory_manager.View.for_worker(env, num_workers, worker_id)
    assert my_view.board.shape == gs_enc.EncodedGameState.board_shape
    assert my_view.data.shape == gs_enc.EncodedGameState.data_shape
    for i, p in enumerate(my_view.preds):
        assert p.shape == (model.head_sizes[model_const.Head(i)],)
    board_data = np.fromfunction(lambda x, y, z: board_value(env_id, worker_id, x, y, z), my_view.board.shape)
    my_view.board[:] = board_data
    data_data = np.fromfunction(lambda x: data_value(env_id, worker_id, x), my_view.data.shape)
    my_view.data[:] = data_data
    print(f'Worker {worker_id+1} signalling evaluator for environment {env_id}')
    conn_out.write(bytes([worker_id]))
    received_env_id = await receive_from(conn_in)
    print(f'Worker {worker_id+1} received signal from evaluator {received_env_id} (expected: {env_id})')
    check_preds(my_view.preds, env_id, worker_id)


def worker(num_envs, num_workers, worker_id):
    asyncio.run(asyncio.wait([worker_coro(env_id, num_workers, worker_id) for env_id in range(num_envs)]))


async def evaluator_coro(num_workers, env_id):
    conns_in = [open(get_fifo_name(worker_id, env_id, "encoding"), 'rb', buffering=0) for worker_id in range(num_workers)]
    conns_out = [open(get_fifo_name(worker_id, env_id, "preds"), 'a+b', buffering=0) for worker_id in range(num_workers)]
    print(f'Evaluator {env_id} starting up')
    # An evaluator should sleep, read data for game encodings, and then write back prediction data.
    env = shared_memory_manager.SharedMemoryManager.make_env(env_id)
    my_view = shared_memory_manager.View.for_evaluator(env, num_workers)
    assert my_view.board.shape == (num_workers,) + gs_enc.EncodedGameState.board_shape
    assert my_view.data.shape == (num_workers,) + gs_enc.EncodedGameState.data_shape
    for i, pred_head in enumerate(my_view.preds):
        assert pred_head.shape == (num_workers, model.head_sizes[model_const.Head(i)])
    for conn in conns_in:
        worker_id = await receive_from(conn)
        print(f'Evaluator {env_id} received a wake-up signal from worker {worker_id+1}')
    print(f'Evaluator {env_id} received all wake-up signals')
    check_boards(my_view.board, num_workers, env_id)
    check_data(my_view.data, num_workers, env_id)
    for head in model_const.Head:
        for worker_id in range(num_workers):
            for index in range(model.head_sizes[head]):
                my_view.preds[head.value][worker_id, index] = pred_value(env_id, worker_id, head, index)
    print(f'Evaluator {env_id} notifying all workers that their predictions are ready')
    for conn in conns_out:
        conn.write(bytes([env_id]))


def evaluator(num_workers, num_envs):
    asyncio.run(asyncio.wait([evaluator_coro(num_workers, env_id) for env_id in range(num_envs)]))


def test():
    # Initialize some shared memory, then kick off some processes for reading and writing. These processes
    # should mimic workers and evaluators in that the workers should be reading from and writing to their own
    # specific slices of memory, and the evaluators should have access to everything.
    num_workers = 3
    envs_per_worker = 3
    smm = shared_memory_manager.SharedMemoryManager.init(num_workers, envs_per_worker)
    for worker_id in range(num_workers):
        for env_id in range(envs_per_worker):
            for suffix in ["encoding", "preds"]:
                fifo_name = get_fifo_name(worker_id, env_id, suffix)
                if os.path.exists(fifo_name):
                    os.unlink(fifo_name)
                os.mkfifo(fifo_name)
    procs = []
    for worker_id in range(num_workers):
            p = mp.Process(target=worker, args=(envs_per_worker, num_workers, worker_id))
            procs.append(p)
            p.start()

    p = mp.Process(target=evaluator, args=(num_workers, envs_per_worker))
    procs.append(p)
    p.start()

    for p in procs:
        p.join()

    for worker_id in range(num_workers):
        for env_id in range(envs_per_worker):
            for suffix in ["encoding", "preds"]:
                os.unlink(get_fifo_name(worker_id, env_id, suffix))

    smm.unlink()


if __name__ == '__main__':
    # logging.getLogger().setLevel(logging.DEBUG)
    test()
