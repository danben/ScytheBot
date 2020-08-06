import asyncio
import multiprocessing as mp
import numpy as np

from encoders import game_state as gs_enc
from training import model, constants as model_const
from training import shared_memory_manager
from training.worker_env_conn import WorkerEnvConn


def board_value(env_id, worker_id, slot, row, col, plane):
    return row * 100000 + col * 10000 + plane * 1000 + env_id * 100 + worker_id * 10 + slot


def data_value(env_id, worker_id, slot, index):
    return index * 1000 + env_id * 100 + worker_id * 10 + slot


def pred_value(env_id, worker_id, slot, head, index):
    return head.value * 10000 + index * 1000 + env_id * 100 + worker_id * 10 + slot


def check_boards(boards, num_workers, slots_per_worker, env_id):
    w, r, c, p = boards.shape
    assert w == num_workers * slots_per_worker
    for worker_id in range(num_workers):
        for slot in range(slots_per_worker):
            for row in range(r):
                for col in range(c):
                    for plane in range(p):
                        assert boards[worker_id * slots_per_worker + slot, row, col, plane] ==\
                               board_value(env_id, worker_id, slot, row, col, plane)


def check_data(data, num_workers, slots_per_worker, env_id):
    w, l = data.shape
    assert w == num_workers * slots_per_worker
    for worker_id in range(w):
        for slot in range(slots_per_worker)
            for index in range(l):
                assert data[worker_id * slots_per_worker + slot, index] == data_value(env_id, worker_id, slot, index)


def check_preds(preds, env_id, worker_id, slots_per_worker):
    for head in model_const.Head:
        l = len(preds[head.value][0])
        assert l == model.head_sizes[head]
        for slot in range(slots_per_worker):
            for index in range(l):
                assert preds[head.value][slot, index] == pred_value(env_id, worker_id, slot, head, index)


def clear_preds(preds):
    for head in model_const.Head:
        preds[head.value][:] = 0


async def worker_coro(env_id, num_workers, slots_per_worker, worker_id):
    # A worker should write down some fake data into its reserved area for game encodings, sleep, and then
    # read back prediction data.
    print(f'Worker {worker_id+1} of {num_workers} starting for environment {env_id}')
    worker_env_conn = WorkerEnvConn.for_worker(env_id=env_id, worker_id=worker_id)
    env = shared_memory_manager.SharedMemoryManager.make_env(env_id)
    my_view = shared_memory_manager.View.for_worker(env, num_workers, worker_id)
    assert my_view.board.shape == gs_enc.EncodedGameState.board_shape
    assert my_view.data.shape == gs_enc.EncodedGameState.data_shape
    for i, p in enumerate(my_view.preds):
        assert p.shape == (model.head_sizes[model_const.Head(i)],)
    while True:
        board_data = np.fromfunction(lambda x, y, z: board_value(env_id, worker_id, x, y, z), my_view.board.shape)
        my_view.board[:] = board_data
        data_data = np.fromfunction(lambda x: data_value(env_id, worker_id, x), my_view.data.shape)
        my_view.data[:] = data_data
        print(f'Worker {worker_id+1} signalling evaluator for environment {env_id}')
        worker_env_conn.wake_up_env(worker_id)
        received_env_id = await worker_env_conn.worker_get_woken_up()
        print(f'Worker {worker_id+1} received signal from evaluator {received_env_id} (expected: {env_id})')
        check_preds(my_view.preds, env_id, worker_id)
        clear_preds(my_view.preds)


def worker(num_envs, num_workers, slots_per_worker, worker_id):
    asyncio.run(asyncio.wait([worker_coro(env_id, num_workers, slots_per_worker, worker_id) for env_id in range(num_envs)]))


async def evaluator_coro(num_workers, env_id):
    print(f'Evaluator {env_id} starting up')
    worker_env_conns = [WorkerEnvConn.for_env(env_id=env_id, worker_id=worker_id) for worker_id in range(num_workers)]
    # An evaluator should sleep, read data for game encodings, and then write back prediction data.
    env = shared_memory_manager.SharedMemoryManager.make_env(env_id)
    my_view = shared_memory_manager.View.for_evaluator(env, num_workers)
    assert my_view.board.shape == (num_workers,) + gs_enc.EncodedGameState.board_shape
    assert my_view.data.shape == (num_workers,) + gs_enc.EncodedGameState.data_shape
    for i, pred_head in enumerate(my_view.preds):
        assert pred_head.shape == (num_workers, model.head_sizes[model_const.Head(i)])

    while True:
        for conn in worker_env_conns:
            worker_id = await conn.env_get_woken_up()
            print(f'Evaluator {env_id} received a wake-up signal from worker {worker_id+1}')
        print(f'Evaluator {env_id} received all wake-up signals')
        check_boards(my_view.board, num_workers, env_id)
        my_view.board[:] = 0
        check_data(my_view.data, num_workers, env_id)
        my_view.data[:] = 0
        for head in model_const.Head:
            for worker_id in range(num_workers):
                for index in range(model.head_sizes[head]):
                    my_view.preds[head.value][worker_id, index] = pred_value(env_id, worker_id, head, index)
        print(f'Evaluator {env_id} notifying all workers that their predictions are ready')
        for conn in worker_env_conns:
            conn.wake_up_worker(env_id)


def evaluator(num_workers, num_envs):
    asyncio.run(asyncio.wait([evaluator_coro(num_workers, env_id) for env_id in range(num_envs)]))


def test():
    # Initialize some shared memory, then kick off some processes for reading and writing. These processes
    # should mimic workers and evaluators in that the workers should be reading from and writing to their own
    # specific slices of memory, and the evaluators should have access to everything.
    num_workers = 3
    envs_per_worker = 3
    slots_per_worker = 3
    smm = shared_memory_manager.SharedMemoryManager.init(num_workers, slots_per_worker, envs_per_worker)
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

    smm.unlink()


if __name__ == '__main__':
    # logging.getLogger().setLevel(logging.DEBUG)
    test()
