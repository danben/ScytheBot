import asyncio
import attr
import os


@attr.s(slots=True)
class WorkerEnvConn:
    env_id = attr.ib()
    worker_id = attr.ib()
    worker_to_env = attr.ib()
    env_to_worker = attr.ib()

    @staticmethod
    def get_worker_to_env_name(*, worker_id, env_id):
        return f'/tmp/fifo-worker-{worker_id}-{env_id}'

    @staticmethod
    def get_env_to_worker_name(*, env_id, worker_id):
        return f'/tmp/fifo-env-{env_id}-{worker_id}'

    @staticmethod
    def init_fifos(*, env_id, worker_id):
        worker_to_env_name = WorkerEnvConn.get_worker_to_env_name(worker_id=worker_id, env_id=env_id)
        env_to_worker_name = WorkerEnvConn.get_env_to_worker_name(env_id=env_id, worker_id=worker_id)
        for fname in [worker_to_env_name, env_to_worker_name]:
            if not os.path.exists(fname):
                try:
                    print(f'Creating {fname}')
                    os.mkfifo(fname)
                except FileExistsError:
                    print(f'{fname} exists somehow')

    @classmethod
    def for_worker(cls, env_id, worker_id):
        WorkerEnvConn.init_fifos(env_id=env_id, worker_id=worker_id)
        worker_to_env = open(WorkerEnvConn.get_worker_to_env_name(env_id=env_id, worker_id=worker_id),
                             'a+b', buffering=0)
        env_to_worker = open(WorkerEnvConn.get_env_to_worker_name(env_id=env_id, worker_id=worker_id),
                             'rb', buffering=0)
        return cls(env_id, worker_id, worker_to_env, env_to_worker)

    @classmethod
    def for_env(cls, env_id, worker_id):
        WorkerEnvConn.init_fifos(env_id=env_id, worker_id=worker_id)
        worker_to_env = open(WorkerEnvConn.get_worker_to_env_name(env_id=env_id, worker_id=worker_id),
                             'rb', buffering=0)
        env_to_worker = open(WorkerEnvConn.get_env_to_worker_name(env_id=env_id, worker_id=worker_id),
                             'a+b', buffering=0)
        return cls(env_id, worker_id, worker_to_env, env_to_worker)

    @staticmethod
    def _get_woken_up(fifo):
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # @staticmethod
        def set_determined():
            future.set_result(fifo.read(1)[0])
            asyncio.get_event_loop().remove_reader(fifo)

        loop.add_reader(fifo, set_determined)
        return future

    def env_get_woken_up(self):
        return WorkerEnvConn._get_woken_up(self.worker_to_env)

    def wake_up_env(self):
        self.worker_to_env.write(bytes([self.worker_id]))

    def worker_get_woken_up(self):
        return WorkerEnvConn._get_woken_up(self.env_to_worker)

    def wake_up_worker(self):
        self.env_to_worker.write(bytes([self.env_id]))

    def clean_up(self):
        os.unlink(self.worker_to_env)
        os.unlink(self.env_to_worker)
