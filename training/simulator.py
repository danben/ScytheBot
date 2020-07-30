import asyncio
import attr
import logging
import time

from agents.mcts_zero import MCTSZeroAgent
from game.game_state import GameState
from play import play
from training import shared_memory_manager
from training.worker_env_conn import WorkerEnvConn


@attr.s(slots=True)
class Simulator:
    worker_id = attr.ib()
    env_id = attr.ib()
    agents = attr.ib()
    view = attr.ib()
    learner_queue = attr.ib()

    @classmethod
    def init(cls, num_workers, worker_id, env, num_players, c, simulations_per_choice, learner_queue):
        view = shared_memory_manager.View.for_worker(env, num_workers, worker_id)
        worker_env_conn = WorkerEnvConn.for_worker(env.id, worker_id)
        agents = [MCTSZeroAgent(c=c, simulations_per_choice=simulations_per_choice, view=view,
                                worker_env_conn=worker_env_conn)
                  for _ in range(num_players)]
        return cls(worker_id, env.id, agents, view, learner_queue)

    # As long as we haven't just started, there should be a probability distribution waiting for us.
    # Decode it to get the next move of the simulation, apply that to our game state, and encode
    # the new game state for the evaluator.
    async def run(self):
        while True:
            game_state = GameState.from_num_players(len(self.agents))
            for agent in self.agents:
                agent.begin_episode()

            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Worker {self.worker_id} starting a self-play match in environment {self.env_id}')
            print(f'Worker {self.worker_id} starting a self-play match in environment{self.env_id}')
            start = time.time()
            game_state = await play.play_game(game_state, self.agents)
            end = time.time()
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Worker {self.worker_id} finished a game at {end} ({end - start} seconds)')
            print(f'Worker {self.worker_id} finished a game at {end} ({end - start} seconds)')
            for agent in self.agents:
                agent.complete_episode(game_state.winner)
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(f'Worker {self.worker_id} adding {len(agent.experience_collector.game_states)} '
                                  f'samples to learner queue')
                print(f'Worker {self.worker_id} adding {len(agent.experience_collector.game_states)} samples to learner queue')
                self.learner_queue.put(agent.experience_collector.to_numpy())


def worker(wid, num_workers, num_envs, learner_queue, num_players, simulations_per_choice):
    print(f'Worker {wid} starting')
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'Worker {wid} starting')
    shm_envs = [shared_memory_manager.SharedMemoryManager.make_env(env_id) for env_id in range(num_envs)]

    # A single worker process is responsible for playing N simultaneous games, where N is the number
    # of environments. We need to get all of the shared memory blocks and then give each
    # simulator only the slices that it needs to do its job.
    sims = [Simulator.init(num_workers, wid, shm_envs[i], num_players, c=0.8,
                           simulations_per_choice=simulations_per_choice, learner_queue=learner_queue)
            for i in range(num_envs)]

    asyncio.run(asyncio.wait([sim.run() for sim in sims]))
