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
    agent = attr.ib()
    num_players = attr.ib()
    view = attr.ib()
    learner_queue = attr.ib()
    worker_env_conn = attr.ib()

    @classmethod
    def init(cls, num_workers, worker_id, env, num_players, c, simulations_per_choice, learner_queue):
        view = shared_memory_manager.View.for_worker(env, num_workers, worker_id)
        worker_env_conn = WorkerEnvConn.for_worker(env.id, worker_id)
        agent = MCTSZeroAgent(c=c, simulations_per_choice=simulations_per_choice, view=view,
                                worker_env_conn=worker_env_conn)
        return cls(worker_id, env.id, agent, num_players, view, learner_queue, worker_env_conn)

    # As long as we haven't just started, there should be a probability distribution waiting for us.
    # Decode it to get the next move of the simulation, apply that to our game state, and encode
    # the new game state for the evaluator.
    async def run_async(self):
        for _ in range(5):
            game_state = GameState.from_num_players(self.num_players)
            self.agent.begin_episode()

            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Worker {self.worker_id} starting a self-play match in environment {self.env_id}')
            print(f'Worker {self.worker_id} starting a self-play match in environment{self.env_id}')
            start = time.time()
            game_state = await play.play_game(game_state, [self.agent for _ in range(self.num_players)])
            end = time.time()
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Worker {self.worker_id} finished a game at {end} ({end - start} seconds)')
            print(f'Worker {self.worker_id} finished a game at {end} ({end - start} seconds)')
            self.agent.complete_episode(game_state.winner)
            # if logging.getLogger().isEnabledFor(logging.DEBUG):
            #     logging.debug(f'Worker {self.worker_id} adding {len(agent.experience_collector.game_states)} '
            #                   f'samples to learner queue')
            # print(f'Worker {self.worker_id} adding {len(self.agent.experience_collector.game_states)} samples to learner queue')
            # self.learner_queue.put(agent.experience_collector.to_numpy())


@attr.s(slots=True)
class Simulator:
    worker_id = attr.ib()
    num_players_per_game = attr.ib()
    slots_per_worker = attr.ib()
    views = attr.ib()
    game_states = attr.ib()
    agents = attr.ib()
    num_games = attr.ib(default=None)

    @classmethod
    def init(cls, *, worker_id, num_players, num_workers, slots_per_worker, envs, simulations_per_choice, c, num_games=None):
        views = [shared_memory_manager.View.for_worker(env=env, slots_per_worker=slots_per_worker,
                                                       num_workers=num_workers, worker_id=worker_id) for env in envs]
        game_states = [([None] * slots_per_worker) for _ in range(len(envs))]
        agents = [[MCTSZeroAgentManual(worker_id=worker_id, env_slot=slot, c=c, simulations_per_choice=simulations_per_choice, view=views[env])
                    for slot in range(slots_per_worker)] for env in range(len(envs))]
        return cls(worker_id, num_players, slots_per_worker, views, game_states,
                   agents, num_games)

    def run(self):
        for env_num in range(len(self.game_states)):
            for slot_num in range(self.slots_per_worker):
                game_state = GameState.from_num_players(self.num_players_per_game)
                self.game_states[env_num][slot_num] = game_state
                self.agents[env_num][slot_num].begin_episode(game_state.player_idx_by_faction_name.keys())

        last_game = self.num_games if self.num_games else -1
        this_game = 0

        def handle_terminal_state(*, agent, game_state, env_num, slot_num):
            # We finished a self-play episode. Feed the learner and start over.
            agent.complete_episode(game_state.winner)
            print(f'If there were a learner, we would send {sum([len(e.game_states) for e in agent.experience_collectors.values()])} samples')
            # This is where we would feed stuff to the learner
            game_state = self.game_states[env_num][slot_num] = GameState.from_num_players(self.num_players_per_game)
            agent.begin_episode(game_state.player_idx_by_faction_name.keys())
            return MCTSZeroAgentManual.Result.NEXT_SIMULATION, None

        while this_game != last_game:
            for env_num, view in enumerate(self.views):
                for slot_num in range(self.slots_per_worker):
                    # For each environment, we want to move it forward until we need predictions. That means:
                    # - If there is no current game being played, start one. Create the game state and reset
                    #   the agents. Then we need to kick off the first select_move call, advancing until we need
                    #   predictions. However, it may be the case that the current game state has either 0 or 1 choices
                    #   available. In this case we should apply them until we get to a game state that has multiple
                    #   options available.
                    #
                    # - If we've gotten here, that means we have a move with multiple options available. The first time
                    #   we'll need predictions is when we create the root node, so we can go ahead and do that. Now we're
                    #   in the WAITING_ON_ROOT state.
                    #
                    # - If there is a current game, we must be inside of a select_move call. We don't need predictions,
                    #   so that means either that the current game state has no choices (in which case we apply None
                    #   or the singleton choice) or
                    game_state = self.game_states[env_num][slot_num]
                    choices = game_state.legal_moves()
                    agent = self.agents[env_num][slot_num]
                    result, move = agent.advance_until_predictions_needed_or_move_selected_or_game_over(game_state, choices)
                    while result is not MCTSZeroAgentManual.Result.PREDICTIONS_NEEDED and this_game != last_game:
                        game_state = self.game_states[env_num][slot_num]
                        choices = game_state.legal_moves()
                        if game_state.is_over():
                            this_game += 1
                            result, move = handle_terminal_state(agent=agent, game_state=game_state, env_num=env_num,
                                                                 slot_num=slot_num)
                        elif result is MCTSZeroAgentManual.Result.MOVE_SELECTED:
                            # We finished the current simulation. Apply the move and start the next simulation by
                            # updating the game state and current player.
                            game_state = apply_move(game_state, move)
                            if game_state.is_over():
                                this_game += 1
                                result, move = handle_terminal_state(agent=agent, game_state=game_state,
                                                                     env_num=env_num, slot_num=slot_num)
                            else:
                                choices = game_state.legal_moves()
                                while (not game_state.is_over()) and ((not choices) or len(choices) == 1):
                                    if not choices:
                                        game_state = apply_move(game_state, None)
                                    else:
                                        game_state = apply_move(game_state, choices[0])
                                    choices = game_state.legal_moves()
                                if game_state.is_over():
                                    this_game += 1
                                    result, move = handle_terminal_state(agent=agent, game_state=game_state,
                                                                         env_num=env_num, slot_num=slot_num)
                                else:
                                    assert len(choices) > 1
                                    self.game_states[env_num][slot_num]= game_state
                                    result, move = agent.advance_until_predictions_needed_or_move_selected_or_game_over(game_state,
                                                                                                                        choices)
                        else:
                            assert result is MCTSZeroAgentManual.Result.NEXT_SIMULATION
                            # We finished an iteration of the current simulation by hitting a terminal state. The
                            # agent should have updated its internal state to set the current node back to the root.
                            # Try again.
                            result, move = agent.advance_until_predictions_needed_or_move_selected_or_game_over(game_state,
                                                                                                                choices)

            if this_game != last_game:
                for env_num, view in enumerate(self.views):
                    for slot_num in range(slots_per_worker):
                        view.wait_for_preds(slot_num)
                        self.agents[env_num][slot_num].decode_predictions_and_propagate_values()


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
    cProfile.runctx('async_worker(wid, num_workers, num_envs, learner_queue, num_players, simulations_per_choice)',
                    globals(), locals(), sort='tottime')


def manual_worker(worker_id, num_players, num_workers, slots_per_worker, num_envs, simulations_per_choice, c, num_games=None):
    os.nice(-20)
    # param = os.sched_param(os.sched_get_priority_max(os.SCHED_FIFO))
    # os.sched_setscheduler(0, os.SCHED_FIFO, param)
    envs = [shared_memory_manager.SharedMemoryManager.make_env(env_id) for env_id in range(num_envs)]
    sim = Simulator.init(worker_id=worker_id, num_players=num_players, num_workers=num_workers,
                         slots_per_worker=slots_per_worker, envs=envs, simulations_per_choice=simulations_per_choice,
                         c=c, num_games=num_games)
    sim.run()


def profile_manual_worker(worker_id, num_players, num_workers, slots_per_worker, num_envs, simulations_per_choice, c, num_games=None):
    cProfile.runctx('manual_worker(worker_id, num_players, num_workers, slots_per_worker, num_envs, simulations_per_choice, c, num_games)',
                    globals(), locals(), sort='tottime')


if __name__ == '__main__':
    import multiprocessing as mp
    from training import evaluator
    # logging.getLogger().setLevel(logging.DEBUG)
    model_base_path = 'C:\\Users\\dan\\PycharmProjects\\ScytheBot\\training\\data'
    num_envs = 2
    num_workers = 6
    slots_per_worker = 6
    num_slots = num_workers * slots_per_worker
    smm = shared_memory_manager.SharedMemoryManager.init(num_workers=num_workers, slots_per_worker=slots_per_worker,
                                                         envs_per_worker=num_envs)
    ev = mp.Process(target=evaluator.evaluator, args=(num_envs, num_slots, model_base_path, True))
    ev.start()
    profile_manual_worker(worker_id=0, num_players=2, num_workers=num_workers, slots_per_worker=slots_per_worker,
                  num_envs=num_envs, simulations_per_choice=10, c=1, num_games=72)
    ev.kill()
    smm.unlink()