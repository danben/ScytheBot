import attr
import numpy as np
import logging

from enum import Enum

from encoders import game_state as gs_enc
from multiprocessing import shared_memory
from training import model, constants as model_const


def get_segment_name(env_id, data_type, head=None):
    prefix = f'shm-{env_id}-{data_type.value}'
    if head is None:
        return prefix
    return f'{prefix}-{head.value}'


class DataType(Enum):
    BOARDS = 0
    DATA = 1
    PREDS = 2


def get_boards_shape(num_workers):
    return (num_workers,) + gs_enc.EncodedGameState.board_shape


def get_data_shape(num_workers):
    return (num_workers,) + gs_enc.EncodedGameState.data_shape


def get_preds_shape(num_workers, head):
    return num_workers, model.head_sizes[head]


@attr.s(slots=True)
class Env:
    boards_shared = attr.ib()
    data_shared = attr.ib()
    preds_shared = attr.ib()

    @classmethod
    def init(cls, num_workers, env_id):
        boards_shape = get_boards_shape(num_workers)
        boards_dummy = np.ndarray(boards_shape, dtype=np.float64)
        data_shape = get_data_shape(num_workers)
        data_dummy = np.ndarray(data_shape, dtype=np.float64)
        preds_dummies = [np.ndarray(get_preds_shape(num_workers, head), dtype=np.float64) for head in model_const.Head]
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Creating segment \'{get_segment_name(env_id, DataType.BOARDS)}\' with size {boards_dummy.nbytes}')
            logging.debug(f'Creating segment \'{get_segment_name(env_id, DataType.DATA)}\' with size {data_dummy.nbytes}')
            for head in model_const.Head:
                logging.debug(f'Creating segment \'{get_segment_name(env_id, DataType.PREDS, head)}\' with size {preds_dummies[head.value].nbytes}')
        boards_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.BOARDS), create=True,
                                                   size=boards_dummy.nbytes)
        data_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.DATA), create=True,
                                                 size=data_dummy.nbytes)
        preds_shared = [shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.PREDS, head), create=True,
                                                   size=preds_dummies[head.value].nbytes)
                        for head in model_const.Head]
        return cls(boards_shared, data_shared, preds_shared)


@attr.s(slots=True)
class View:
    board = attr.ib()
    data = attr.ib()
    preds = attr.ib()

    @classmethod
    def for_evaluator(cls, env, num_workers):
        boards_shape = get_boards_shape(num_workers)
        data_shape = get_data_shape(num_workers)
        preds_shapes = [get_preds_shape(num_workers, head) for head in model_const.Head]
        board = np.ndarray(boards_shape, dtype=np.float64, buffer=env.boards_shared.buf)
        data = np.ndarray(data_shape, dtype=np.float64, buffer=env.data_shared.buf)
        preds = [np.ndarray(preds_shapes[i], dtype=np.float64, buffer=env.preds_shared[i].buf)
                 for i in range(len(preds_shapes))]
        return cls(board, data, preds)

    @classmethod
    def for_worker(cls, env, num_workers, worker_id):
        assert 0 <= worker_id < num_workers
        evaluator_view = View.for_evaluator(env, num_workers)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Shape of evaluator_view.board: {evaluator_view.board.shape}')
            logging.debug(f'Shape of board buffer for worker: {evaluator_view.board[worker_id].shape}')
        board = np.ndarray(gs_enc.EncodedGameState.board_shape, dtype=np.float64,
                           buffer=evaluator_view.board[worker_id])
        data = np.ndarray(gs_enc.EncodedGameState.data_shape, dtype=np.float64, buffer=evaluator_view.data[worker_id])
        preds = [np.ndarray((model.head_sizes[head],), dtype=np.float64,
                            buffer=evaluator_view.preds[head.value][worker_id]) for head in model_const.Head]
        return cls(board, data, preds)


@attr.s(slots=True)
class SharedMemoryManager:
    num_workers = attr.ib()
    envs_per_worker = attr.ib()
    envs = attr.ib()

    @classmethod
    def init(cls, num_workers, envs_per_worker):
        # Let's make empty numpy arrays for all the memory we need. Each worker needs to be able to send an encoded
        # board and game state, and read back a set of predictions. We need one of each of those for each
        # worker/environment pair.
        return cls(num_workers, envs_per_worker, [Env.init(num_workers, i) for i in range(envs_per_worker)])

    @staticmethod
    def make_env(env_id):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Requesting shared memory segment {get_segment_name(env_id, DataType.BOARDS)}')
            logging.debug(f'Requesting shared memory segment {get_segment_name(env_id, DataType.DATA)}')
            for head in model_const.Head:
                logging.debug(f'Requesting shared memory segment {get_segment_name(env_id, DataType.PREDS, head)}')
        boards_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.BOARDS))
        data_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.DATA))
        preds_shared = [shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.PREDS, head))
                        for head in model_const.Head]
        return Env(boards_shared, data_shared, preds_shared)

    @staticmethod
    def get_worker_view(env_id, num_workers, worker_id):
        env = SharedMemoryManager.make_env(env_id)
        return View.for_worker(env, num_workers, worker_id)

    @staticmethod
    def get_evaluator_view(env_id, num_workers):
        env = SharedMemoryManager.make_env(env_id)
        return View.for_evaluator(env, num_workers)
