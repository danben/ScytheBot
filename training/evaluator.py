import asyncio
import cProfile
import os
import uvloop

from training.model import load as load_model
from training.shared_memory_manager import SharedMemoryManager, View
from training.worker_env_conn import WorkerEnvConn


def set_up_evaluator(num_envs, num_workers, model_base_path, in_test=False):
    # os.nice(-20)
    if not in_test:
        param = os.sched_param(os.sched_get_priority_max(os.SCHED_FIFO))
        os.sched_setscheduler(0, os.SCHED_FIFO, param)
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
    views = [View.for_evaluator(SharedMemoryManager.make_env(env_id), num_workers) for env_id in range(num_envs)]
    nn = load_model(model_base_path)
    return views, nn


def evaluator(num_envs, num_workers, model_base_path, in_test=False):
    views, nn = set_up_evaluator(num_envs, num_workers, model_base_path, in_test)
    while True:
        for view in views:
            view.wait_for_boards(num_workers)
            view.wait_for_data(num_workers)
            predictions = nn.predict([view.board, view.data], batch_size=num_workers)
            view.write_boards_clean(num_workers)
            view.write_data_clean(num_workers)
            view.write_preds(predictions, num_workers)


def profile_evaluator(num_envs, num_workers, model_base_path):
    cProfile.runctx('evaluator(num_envs, num_workers, model_base_path)', globals(), locals(), sort='cumtime')


def async_evaluator(num_envs, num_workers, model_base_path):
    views, nn = set_up_evaluator(num_envs, num_workers, model_base_path)
    print(f'Evaluator got shared memory and loaded model. Starting {num_envs} threads.')

    async def env_loop(env_id, worker_env_conns):
        while True:
            # Block until every worker has sent in a sample for evaluation in
            # this environment
            # print(f'Evaluator {env_id} waiting for workers')
            await asyncio.wait([worker_env_conn.env_get_woken_up() for worker_env_conn in worker_env_conns])

            # print(f'Evaluator {env_id} got a batch, making predictions')
            predictions = nn.predict([views[env_id].board, views[env_id].data], batch_size=num_workers)
            views[env_id].write_preds(predictions, num_workers)

            # Notify the workers that their predictions are ready
            for worker_env_conn in worker_env_conns:
                worker_env_conn.wake_up_worker()
            # print(f'Evaluator {env_id} woke up all its workers')

    uvloop.install()
    worker_env_conns = [[WorkerEnvConn.for_env(env_id, worker_id) for worker_id in range(num_workers)]
                        for env_id in range(num_envs)]

    # def on_kill(_signum, _stack_frame):
    #     for l in worker_env_conns:
    #         for worker_env_conn in l:
    #             worker_env_conn.clean_up()
    #
    # signal.signal(signal.SIGKILL, on_kill)
    asyncio.run(asyncio.wait([env_loop(env_id, worker_env_conns[env_id]) for env_id in range(num_envs)]))


def profile_async_evaluator(num_envs, num_workers, model_base_path):
    cProfile.runctx('async_evaluator(num_envs, num_workers, model_base_path)', globals(), locals(), sort='cumtime')

