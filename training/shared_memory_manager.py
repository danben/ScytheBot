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
    DIRTY = 3


def get_boards_shape(num_workers):
    return (num_workers,) + gs_enc.EncodedGameState.board_shape


def get_data_shape(num_workers):
    return (num_workers,) + gs_enc.EncodedGameState.data_shape


def get_preds_shape(num_workers, head):
    return num_workers, model.head_sizes[head]


@attr.s(slots=True)
class Env:
    id = attr.ib()
    boards_shared = attr.ib()
    data_shared = attr.ib()
    preds_shared = attr.ib()
    dirty_shared = attr.ib()

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

        dirty_shape = (num_workers, 3)
        dirty_dummy = np.ndarray(dirty_shape, dtype=np.float64)
        boards_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.BOARDS), create=True,
                                                   size=boards_dummy.nbytes)
        data_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.DATA), create=True,
                                                 size=data_dummy.nbytes)
        preds_shared = [shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.PREDS, head), create=True,
                                                   size=preds_dummies[head.value].nbytes)
                        for head in model_const.Head]
        dirty_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.DIRTY), create=True,
                                                  size=dirty_dummy.nbytes)
        return cls(env_id, boards_shared, data_shared, preds_shared, dirty_shared)


@attr.s(slots=True)
class View:
    env = attr.ib()  # Make sure to keep a reference to the env as long as we need this view
    board = attr.ib()
    data = attr.ib()
    preds = attr.ib()
    dirty = attr.ib()

    @classmethod
    def for_evaluator(cls, env, num_workers):
        boards_shape = get_boards_shape(num_workers)
        data_shape = get_data_shape(num_workers)
        preds_shapes = [get_preds_shape(num_workers, head) for head in model_const.Head]
        dirty_shape = (num_workers, 3)
        board = np.ndarray(boards_shape, dtype=np.float64, buffer=env.boards_shared.buf)
        data = np.ndarray(data_shape, dtype=np.float64, buffer=env.data_shared.buf)
        preds = [np.ndarray(preds_shapes[i], dtype=np.float64, buffer=env.preds_shared[i].buf)
                 for i in range(len(preds_shapes))]
        dirty = np.ndarray(dirty_shape, dtype=np.float64, buffer=env.dirty_shared.buf)
        return cls(env, board, data, preds, dirty)

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
        dirty = np.ndarray((3,), dtype=np.float64, buffer=evaluator_view.dirty[worker_id])
        return cls(env, board, data, preds, dirty)

    def write_board(self, board):
        assert board.shape == self.board.shape
        try:
            assert self.dirty[DataType.BOARDS.value] == 0
        except AssertionError:
            print(f'Dirty: {self.dirty[DataType.BOARDS.value]}')
            assert False
        print('Wrote a board for a prediction')
        self.board[:] = board
        self.dirty[DataType.BOARDS.value] = 1

    def write_data(self, data):
        assert data.shape == self.data.shape
        assert self.dirty[DataType.DATA.value] == 0
        self.data[:] = data
        self.dirty[DataType.DATA.value] = 1

    def write_preds(self, preds, num_workers):
        for i in range(num_workers):
            assert self.dirty[i, DataType.PREDS.value] == 0
            self.dirty[i, DataType.PREDS.value] = 1

        for head in model_const.Head:
            v = head.value
            assert preds[v].shape == self.preds[v].shape
            self.preds[v][:] = preds[v]

    def wait_for_boards(self, num_workers):
        for i in range(num_workers):
            while self.dirty[i, DataType.BOARDS.value] == 0:
                pass

    def write_boards_clean(self, num_workers):
        for i in range(num_workers):
            self.dirty[i, DataType.BOARDS.value] = 0

    def wait_for_data(self, num_workers):
        for i in range(num_workers):
            while self.dirty[i, DataType.DATA.value] == 0:
                pass

    def write_data_clean(self, num_workers):
        for i in range(num_workers):
            self.dirty[i, DataType.DATA.value] = 0

    def wait_for_preds(self):
        while self.dirty[DataType.PREDS.value] == 0:
            pass

    def write_preds_clean(self):
        self.dirty[DataType.PREDS.value] = 0


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
        dirty_shared = shared_memory.SharedMemory(name=get_segment_name(env_id, DataType.DIRTY))
        return Env(env_id, boards_shared, data_shared, preds_shared, dirty_shared)

    @staticmethod
    def get_worker_view(env_id, num_workers, worker_id):
        env = SharedMemoryManager.make_env(env_id)
        return View.for_worker(env, num_workers, worker_id)

    @staticmethod
    def get_evaluator_view(env_id, num_workers):
        env = SharedMemoryManager.make_env(env_id)
        return View.for_evaluator(env, num_workers)

    def unlink(self):
        for env in self.envs:
            env.boards_shared.unlink()
            env.data_shared.unlink()
            for pred in env.preds_shared:
                pred.unlink()
