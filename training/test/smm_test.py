import asyncio
import multiprocessing as mp
import numpy as np

from training import model, constants as model_const
from training import shared_memory_manager
from training.worker_env_conn import WorkerEnvConn


def board_value(*, env_id, worker_id, slot, row, col, plane):
    return row * 100000 + col * 10000 + plane * 1000 + env_id * 100 + worker_id * 10 + slot


def data_value(*, env_id, worker_id, slot, index):
    return index * 1000 + env_id * 100 + worker_id * 10 + slot


def pred_value(*, env_id, worker_id, slot, head, index):
    return head.value * 10000 + index * 1000 + env_id * 100 + worker_id * 10 + slot


def check_boards(*, boards, num_workers, slots_per_worker, env_id):
    w, r, c, p = boards.shape
    assert w == num_workers * slots_per_worker
    for worker_id in range(num_workers):
        for slot in range(slots_per_worker):
            for row in range(r):
                for col in range(c):
                    for plane in range(p):
                        assert boards[worker_id * slots_per_worker + slot, row, col, plane] ==\
                               board_value(env_id=env_id, worker_id=worker_id, slot=slot, row=row, col=col, plane=plane)


def check_data(*, data, num_workers, slots_per_worker, env_id):
    w, l = data.shape
    assert w == num_workers * slots_per_worker
    for worker_id in range(num_workers):
        for slot in range(slots_per_worker):
            for index in range(l):
                assert data[worker_id * slots_per_worker + slot, index] \
                       == data_value(env_id=env_id, worker_id=worker_id, slot=slot, index=index)


def check_preds(*, preds, env_id, worker_id, slots_per_worker):
    for head in model_const.Head:
        for slot in range(slots_per_worker):
            l = len(preds[slot][head.value])
            assert l == model.head_sizes[head]
            for index in range(l):
                try:
                    assert preds[slot][head.value][index] == pred_value(env_id=env_id, worker_id=worker_id, slot=slot,
                                                                    head=head, index=index)
                except AssertionError:
                    print(f'head: {head}; index: {index}; env_id: {env_id}; worker_id: {worker_id}; slot: {slot}')
                    print(f'expected: {pred_value(env_id=env_id, worker_id=worker_id, slot=slot, head=head, index=index)}')
                    print(f'actual: {preds[slot][head.value][index]}')
                    assert False


def clear_preds(preds, slots_per_worker):
    for slot in range(slots_per_worker):
        for head in model_const.Head:
            preds[slot][head.value][:] = 0


def view_for_worker(*, worker_id, slots_per_worker, num_workers, env_id):
    env = shared_memory_manager.SharedMemoryManager.make_env(env_id)
    my_view = shared_memory_manager.View.for_worker(env=env, slots_per_worker=slots_per_worker, num_workers=num_workers,
                                                    worker_id=worker_id)
    assert my_view.boards.shape == shared_memory_manager.get_boards_shape(slots_per_worker)
    assert my_view.data.shape == shared_memory_manager.get_data_shape(slots_per_worker)
    assert my_view.dirty.shape == (slots_per_worker, 3)
    for slot in range(slots_per_worker):
        for i, p in enumerate(my_view.preds[slot]):
            assert p.shape == (model.head_sizes[model_const.Head(i)],)
    return my_view


def worker_manual(num_envs, num_workers, slots_per_worker, worker_id):
    my_views = [view_for_worker(worker_id=worker_id, slots_per_worker=slots_per_worker, num_workers=num_workers,
                                env_id=env_id) for env_id in range(num_envs)]
    while True:
        for env_id, my_view in enumerate(my_views):
            for slot in range(slots_per_worker):
                board_data = np.fromfunction(lambda x, y, z: board_value(env_id=env_id, worker_id=worker_id, slot=slot, row=x,
                                                                         col=y, plane=z), my_view.boards[slot].shape)
                my_view.write_board(board_data, slot)
                data_data = np.fromfunction(lambda x: data_value(env_id=env_id, worker_id=worker_id, slot=slot, index=x),
                                            my_view.data[slot].shape)
                my_view.write_data(data_data, slot)

            for slot in range(slots_per_worker):
                my_view.wait_for_preds(slot)

            check_preds(preds=my_view.preds, env_id=env_id, worker_id=worker_id, slots_per_worker=slots_per_worker)
            clear_preds(my_view.preds, slots_per_worker)

            for slot in range(slots_per_worker):
                my_view.write_preds_clean(slot)


async def worker_coro(env_id, num_workers, slots_per_worker, worker_id):
    # A worker should write down some fake data into its reserved area for game encodings, sleep, and then
    # read back prediction data.
    print(f'Worker {worker_id+1} of {num_workers} starting for environment {env_id}')
    worker_env_conn = WorkerEnvConn.for_worker(env_id=env_id, worker_id=worker_id)
    my_view = view_for_worker(worker_id=worker_id, slots_per_worker=slots_per_worker, num_workers=num_workers,
                              env_id=env_id)
    while True:
        for slot in slots_per_worker:
            board_data = np.fromfunction(lambda x, y, z: board_value(env_id=env_id, worker_id=worker_id, slot=slot, row=x,
                                                                     col=y, plane=z), my_view.board.shape)
            my_view.write_board(board_data, slot)
            data_data = np.fromfunction(lambda x: data_value(env_id=env_id, worker_id=worker_id, slot=slot, index=x),
                                        my_view.data.shape)
            my_view.write_data(data_data, slot)

        print(f'Worker {worker_id+1} signalling evaluator for environment {env_id}')
        worker_env_conn.wake_up_env(worker_id)
        received_env_id = await worker_env_conn.worker_get_woken_up()
        print(f'Worker {worker_id+1} received signal from evaluator {received_env_id} (expected: {env_id})')
        check_preds(preds=my_view.preds, env_id=env_id, worker_id=worker_id, slots_per_worker=slots_per_worker)
        clear_preds(my_view.preds)


def worker_async(num_envs, num_workers, slots_per_worker, worker_id):
    asyncio.run(asyncio.wait([worker_coro(env_id, num_workers, slots_per_worker, worker_id) for env_id in range(num_envs)]))


def view_for_evaluator(env_id, num_slots):
    env = shared_memory_manager.SharedMemoryManager.make_env(env_id)
    view = shared_memory_manager.View.for_evaluator(env=env, num_slots=num_slots)
    assert view.boards.shape == shared_memory_manager.get_boards_shape(num_slots)
    assert view.data.shape == shared_memory_manager.get_data_shape(num_slots)
    assert view.dirty.shape == (num_slots, 3)
    for i, pred_head in enumerate(view.preds):
        assert pred_head.shape == (num_slots, model.head_sizes[model_const.Head(i)])
    return view


async def evaluator_coro(num_workers, slots_per_worker, env_id):
    print(f'Evaluator {env_id} starting up')
    worker_env_conns = [WorkerEnvConn.for_env(env_id=env_id, worker_id=worker_id) for worker_id in range(num_workers)]
    num_slots = num_workers * slots_per_worker
    # An evaluator should sleep, read data for game encodings, and then write back prediction data.
    my_view = view_for_evaluator(env_id, num_slots)
    while True:
        for conn in worker_env_conns:
            worker_id = await conn.env_get_woken_up()
            print(f'Evaluator {env_id} received a wake-up signal from worker {worker_id+1}')
        print(f'Evaluator {env_id} received all wake-up signals')
        check_boards(boards=my_view.board, num_workers=num_workers, slots_per_worker=slots_per_worker, env_id=env_id)
        my_view.board[:] = 0
        my_view.write_boards_clean()
        check_data(data=my_view.data, num_workers=num_workers, slots_per_worker=slots_per_worker, env_id=env_id)
        my_view.data[:] = 0
        my_view.write_data_clean()
        preds = [np.zeros(my_view.preds[head.value].shape) for head in model_const.Head]
        for head in model_const.Head:
            for worker_id in range(num_workers):
                for index in range(model.head_sizes[head]):
                    for slot in range(slots_per_worker):
                        preds[head.value][worker_id, index] = \
                            pred_value(env_id=env_id, worker_id=worker_id, slot=slot, head=head, index=index)
        my_view.write_preds(preds)
        print(f'Evaluator {env_id} notifying all workers that their predictions are ready')
        for conn in worker_env_conns:
            conn.wake_up_worker(env_id)


def evaluator_async(num_workers, slots_per_worker, num_envs):
    asyncio.run(asyncio.wait([evaluator_coro(num_workers, slots_per_worker, env_id) for env_id in range(num_envs)]))


def evaluator_manual(num_workers, slots_per_worker, num_envs):
    num_slots = num_workers * slots_per_worker
    views = [view_for_evaluator(env_id, num_slots) for env_id in range(num_envs)]
    for view in views:
        assert view.boards.shape == shared_memory_manager.get_boards_shape(num_slots)
        assert view.data.shape == shared_memory_manager.get_data_shape(num_slots)
        assert view.dirty.shape == (num_slots, 3)
        for head in model_const.Head:
            assert view.preds[head.value].shape == shared_memory_manager.get_preds_shape(num_slots, head)
    while True:
        for view in views:
            view.wait_for_boards()
            view.wait_for_data()
            check_boards(boards=view.boards, num_workers=num_workers, slots_per_worker=slots_per_worker,
                         env_id=view.env.id)
            check_data(data=view.data, num_workers=num_workers, slots_per_worker=slots_per_worker, env_id=view.env.id)
            view.write_boards_clean()
            view.write_data_clean()
            preds = [np.zeros(view.preds[head.value].shape) for head in model_const.Head]
            for head in model_const.Head:
                for worker_id in range(num_workers):
                    for index in range(model.head_sizes[head]):
                        for slot in range(slots_per_worker):
                            preds[head.value][worker_id * slots_per_worker + slot, index] =\
                                pred_value(env_id=view.env.id, worker_id=worker_id, slot=slot, head=head, index=index)
            view.write_preds(preds)


def test():
    # Initialize some shared memory, then kick off some processes for reading and writing. These processes
    # should mimic workers and evaluators in that the workers should be reading from and writing to their own
    # specific slices of memory, and the evaluators should have access to everything.
    num_workers = 3
    envs_per_worker = 3
    slots_per_worker = 3
    smm = shared_memory_manager.SharedMemoryManager.init(num_workers=num_workers, slots_per_worker=slots_per_worker,
                                                         envs_per_worker=envs_per_worker)
    procs = []
    for worker_id in range(num_workers):
            p = mp.Process(target=worker_manual, args=(envs_per_worker, num_workers, slots_per_worker, worker_id))
            procs.append(p)
            p.start()

    p = mp.Process(target=evaluator_manual, args=(num_workers, slots_per_worker, envs_per_worker))
    procs.append(p)
    p.start()

    for p in procs:
        p.join()

    smm.unlink()


if __name__ == '__main__':
    # logging.getLogger().setLevel(logging.DEBUG)
    test()
