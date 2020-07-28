import attr
import logging
import numpy as np
import time

from agents.mcts_zero import MCTSZeroAgent
from encoders import game_state as gs_enc
from game.game_state import GameState
from game import state_change as sc
from game import play as gp
from training import constants as model_const, shared_memory_manager


@attr.s(slots=True)
class WorkerEnv:
    id = attr.ib()
    worker_id = attr.ib()
    agents = attr.ib()
    shm_envs = attr.ib()
    board_buf = attr.ib()
    data_buf = attr.ib()
    preds_bufs = attr.ib()
    game_state = attr.ib(default=None)
    select_move_gen = attr.ib(default=None)

    @classmethod
    def init(cls, id, worker_id, num_envs, num_players, c, simulations_per_choice):
        agents = [MCTSZeroAgent(c=c, simulations_per_choice=simulations_per_choice) for _ in range(num_players)]
        shm_envs = [shared_memory_manager.SharedMemoryManager.make_env(env_id) for env_id in range(num_envs)]
        board_buf = shared_memory_manager.get_buffer(id, worker_id, shared_memory_manager.DataType.BOARDS)
        data_buf = shared_memory_manager.get_buffer(id, worker_id, shared_memory_manager.DataType.DATA)
        preds_bufs = [shared_memory_manager.get_buffer(id, worker_id, shared_memory_manager.DataType.PREDS, h)
                      for h in model_const.Head]
        return cls(id, worker_id, agents, shm_envs, board_buf, data_buf, preds_bufs)

    # As long as we haven't just started, there should be a probability distribution waiting for us.
    # Decode it to get the next move of the simulation, apply that to our game state, and encode
    # the new game state for the evaluator.
    def step(self):
        if self.game_state is None:
            self.game_state = GameState.from_num_players(len(self.agents))
            for agent in self.agents:
                agent.begin_episode()
            agent = self.agents[self.game_state.current_player_idx]
            self.select_move_gen = agent.select_move(self.game_state)
            # Since we're starting a new game, prime the generator by advancing
            # to the first yield. This will give us the next game state (which in this case we have),
            # and expect us to send back the chosen move.
            next(self.select_move_gen)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Worker {self.worker_id} starting a self-play match in environment {self.id}')
            print(f'Worker {self.worker_id} starting a self-play match in environment{self.id}')

        else:
            # Get the predicted probabilities from shared memory. Decode them into a move and send that to the
            # generator. If [StopIteration] is raised, its value will contain the actual next move. Apply
            # that to our game state and continue.



def worker(wid, evaluator_conns, learner_queue):
    print(f'Worker {wid} starting')
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'Worker {wid} starting')
    num_envs = len(evaluator_conns)
    envs = [WorkerEnv.from_num_players(NUM_PLAYERS, c=0.8, simulations_per_choice=SIMULATIONS_PER_CHOICE)
            for _ in range(num_envs)]

    # In a loop, step through each environment round-robin style. Read the most recent result from the evaluator,
    # then query for the next one. When the generator returns a move, apply it to the game state and advance
    # to the next decision point. When a game completes, send its episode to the learner and start over.
    while True:
        for env in envs:
            if env.game_state.num_turns == 0:
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(f'Worker {wid} starting a self-play match in environment {env}')
                print(f'Worker {wid} starting a self-play match in environment{env}')
                for agent in env.agents:
                    agent.begin_episode()

            # Single step, do not wait for evaluation
            agent = env.agents[env.game_state.current_player_idx]
            if env.select_move_gen is None:
                env.select_move_gen = agent.select_move(env.game_state)

            try:
                next_state = next(env.select_move_gen)
                encoded = gs_enc.encode(env.game_state)
                encoded_data = encoded.encoded_data()
                board = encoded.board

            except StopIteration as si:
                print(f'Move selected by {sc.get_current_player(env.game_state)}')
                if logging.getLogger().isEnabledFor(logging.INFO):
                    next_action = env.game_state.action_stack.first
                    logging.info(f'{sc.get_current_player(game_state)} chooses {si.value} for {next_action}')
                game_state = gp.apply_move(game_state, si.value)

            if game_state.is_over():
                # if logging.getLogger().isEnabledFor(logging.DEBUG):
                #     logging.debug(f'Worker {wid} finished a game at {end} ({end - start} seconds)')
                # print(f'Worker {wid} finished a game at {end} ({end - start} seconds)')
                for agent in agents[env]:
                    agent.complete_episode(game_state.winner)
                    if logging.getLogger().isEnabledFor(logging.DEBUG):
                        logging.debug(f'Worker {wid} adding {len(agent.experience_collector.game_states)} '
                                      f'samples to learner queue')
                    print(f'Worker {wid} adding {len(agent.experience_collector.game_states)} samples to learner queue')
                    learner_queue.put(agent.experience_collector.to_numpy())
                game_state = GameState.from_num_players(NUM_PLAYERS)
            env_states[env] = game_state
