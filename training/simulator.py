import asyncio
import attr
import cProfile
import logging
import os
import signal
import time
import uvloop

from agents.mcts_zero import MCTSZeroAgent, MCTSZeroAgentManual
from game.game_state import GameState
from game.play import apply_move
from play import play
from training import shared_memory_manager
from training.worker_env_conn import WorkerEnvConn


@attr.s(slots=True)
class AsyncSimulator:
    worker_id = attr.ib()
    env_id = attr.ib()
    agents = attr.ib()
    view = attr.ib()
    learner_queue = attr.ib()
    worker_env_conn = attr.ib()

    @classmethod
    def init(cls, num_workers, worker_id, env, num_players, c, simulations_per_choice, learner_queue):
        view = shared_memory_manager.View.for_worker(env, num_workers, worker_id)
        worker_env_conn = WorkerEnvConn.for_worker(env.id, worker_id)
        agents = [MCTSZeroAgent(c=c, simulations_per_choice=simulations_per_choice, view=view,
                                worker_env_conn=worker_env_conn)
                  for _ in range(num_players)]
        return cls(worker_id, env.id, agents, view, learner_queue, worker_env_conn)

    # As long as we haven't just started, there should be a probability distribution waiting for us.
    # Decode it to get the next move of the simulation, apply that to our game state, and encode
    # the new game state for the evaluator.
    async def run_async(self):
        for _ in range(5):
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
                # if logging.getLogger().isEnabledFor(logging.DEBUG):
                #     logging.debug(f'Worker {self.worker_id} adding {len(agent.experience_collector.game_states)} '
                #                   f'samples to learner queue')
                # print(f'Worker {self.worker_id} adding {len(agent.experience_collector.game_states)} samples to learner queue')
                # self.learner_queue.put(agent.experience_collector.to_numpy())


@attr.s(slots=True)
class Simulator:
    worker_id = attr.ib()
    num_players_per_game = attr.ib()
    views = attr.ib()
    game_states = attr.ib()
    agents = attr.ib()

    @classmethod
    def init(cls, worker_id, num_players_per_game, num_workers, envs):
        views = [shared_memory_manager.View.for_worker(env, num_workers, worker_id) for env in envs]
        return cls(worker_id, num_players_per_game, views, [None] * len(envs),
                   [[MCTSZeroAgent(c=c, simulations_per_choice=simulations_per_choice, view=views[i],
                                worker_env_conn=worker_env_conn) for _ in num_players_per_game]
                    for i in len(envs)])

    def run(self):
        for i in len(self.game_states):
            self.game_states[i] = GameState.from_num_players(self.num_players_per_game)
            for agent in self.agents[i]:
                agent.begin_episode()

        while True:
            for i, view in enumerate(self.views):
                # For each environment, we want to move it forward until we need predictions. That means:
                # - If there is no current game being played, start one. Create the game state and reset
                #   the agents. Then we need to kick off the first select_move call, advancing until we need
                #   predictions. However, it may be the case that the current game state has either 0 or 1 choices
                #   available. In this case we should apply them until we get to a game state that has multiple
                #   options available.
                #
                # - If we've gotten here, that means we have a move with multiple options available. The first time we'll
                #   need predictions is when we create the root node, so we can go ahead and do that. Now we're in the
                #   WAITING_ON_ROOT state.
                #
                # - If there is a current game, we must be inside of a select_move call. We don't need predictions,
                #   so that means either that the current game state has no choices (in which case we apply None
                #   or the singleton choice) or
                game_state = self.game_states[i]
                agent = self.agents[i][game_state.current_player_idx]
                result, move = agent.advance_until_predictions_needed_or_move_selected_or_game_over()
                while result is not MCTSZeroAgentManual.Result.PREDICTIONS_NEEDED:
                    if game_state.is_over():
                        # We finished a self-play episode. Feed the learner and start over.
                        for agent in self.agents[i]:
                            agent.complete_episode(game_state.winner)
                        # This is where we would feed stuff to the learner
                        game_state = self.game_states[i] = GameState.from_num_players(self.num_players_per_game)
                        for agent in self.agents[i]:
                            agent.begin_episode()
                        agent = self.agents[i][self.game_states[i].current_player_idx]
                        result, move = agent.advance_until_predictions_needed_or_move_selected_or_game_over(game_state)
                    elif result is MCTSZeroAgentManual.Result.MOVE_SELECTED:
                        # We finished the current simulation. Apply the move and start the next simulation by
                        # updating the game state and current player.
                        game_state = self.game_states[i] = apply_move(game_state, move)
                        agent = self.agents[i][game_state.current_player_idx]
                        result, move = agent.advance_until_predictions_needed_or_move_selected_or_game_over(game_state)
                    else:
                        assert result is MCTSZeroAgentManual.Result.NEXT_ITERATION
                        # We finished an iteration of the current simulation by hitting a terminal state. The
                        # agent should have updated its internal state to set the current node back to the root.
                        # Try again.
                        result, move = agent.advance_until_predictions_needed_or_move_selected_or_game_over(game_state)

                agent.send_prediction_request(view)

            for i, view in enumerate(self.views):
                game_state = self.game_states[i]
                agent = self.agents[i][game_state.current_player_idx]
                agent.decode_predictions_and_propagate_values(view)


def async_worker(wid, num_workers, num_envs, learner_queue, num_players, simulations_per_choice):
    # os.nice(-20)
    param = os.sched_param(os.sched_get_priority_max(os.SCHED_FIFO))
    os.sched_setscheduler(0, os.SCHED_FIFO, param)
    print(f'Worker {wid} starting')
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'Worker {wid} starting')
    shm_envs = [shared_memory_manager.SharedMemoryManager.make_env(env_id) for env_id in range(num_envs)]

    # A single worker process is responsible for playing N simultaneous games, where N is the number
    # of environments. We need to get all of the shared memory blocks and then give each
    # simulator only the slices that it needs to do its job.
    sims = [AsyncSimulator.init(num_workers, wid, shm_envs[i], num_players, c=0.8,
                           simulations_per_choice=simulations_per_choice, learner_queue=learner_queue)
            for i in range(num_envs)]

    # def on_kill(_signum, _stack_frame):
    #     for sim in sims:
    #         sim.worker_env_conn.clean_up()
    #
    # signal.signal(signal.SIGKILL, on_kill)
    uvloop.install()
    asyncio.run(asyncio.wait([sim.run_async() for sim in sims]))
    for sim in sims:
        sim.worker_env_conn.clean_up()


def profile_async_worker(wid, num_workers, num_envs, learner_queue, num_players, simulations_per_choice):
    cProfile.runctx('worker(wid, num_workers, num_envs, learner_queue, num_players, simulations_per_choice)', globals(), locals(), sort='cumtime')