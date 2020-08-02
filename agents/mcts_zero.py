from game import play
from game.actions import MoveOnePiece
from agents import Agent
from training import constants as model_const, decode, model
import encoders.game_state as gs_enc
import game.state_change as sc

import attr
import numpy as np
import logging
import time

from collections import  defaultdict
from enum import Enum

logger = logging.getLogger('mcts_zero_debug_logger')
logger.setLevel(logging.ERROR)


@attr.s(slots=True)
class ExperienceCollector:
    indices_by_faction_name = attr.ib()
    game_states = attr.ib(factory=list)
    move_visits = attr.ib(factory=list)
    winner = attr.ib(default=None)

    def record_move(self, game_state, move_visits):
        self.game_states.append(game_state)
        self.move_visits.append(move_visits)

    def complete_episode(self, winner):
        self.winner = winner

    @staticmethod
    def _assign_move_probs_aux(values_and_move_probs, row, output_head, decoder, move_visits):
        for move in move_visits.keys():
            move_prob = move_visits[move] / sum(move_visits.values())
            head = values_and_move_probs[output_head]
            head[row, decoder(move)] = move_prob

    @staticmethod
    def _assign_move_probs(values_and_move_probs, row, top_action_class, move_visits):
        output_head = decode.model_head_by_action_class[top_action_class].value
        decoder = decode.decoders[top_action_class]
        ExperienceCollector._assign_move_probs_aux(values_and_move_probs, row, output_head, decoder, move_visits)

    @staticmethod
    def _assign_move_probs__move_one_piece(values_and_move_probs, row, move_visits):
        board_coord_visits = defaultdict(int)
        piece_type_visits = defaultdict(int)
        for move, visits in move_visits.items():
            board_coords, piece_type = move
            board_coord_visits[board_coords] += visits
            piece_type_visits[piece_type] += visits
        ExperienceCollector._assign_move_probs_aux(values_and_move_probs, row, model_const.Head.BOARD_COORDS_HEAD.value,
                                                   decode.decode_board_space, board_coord_visits)
        ExperienceCollector._assign_move_probs_aux(values_and_move_probs, row, model_const.Head.PIECE_TYP_HEAD.value,
                                                   decode.decode_enum_value, piece_type_visits)

    def to_numpy(self):
        encoded_game_states = [gs_enc.encode(game_state) for game_state in self.game_states]
        encoded_boards = np.array([egs.board for egs in encoded_game_states])
        encoded_data = np.array([egs.encoded_data() for egs in encoded_game_states])
        values_and_move_probs = model.empty_heads(len(self.game_states))
        values_and_move_probs[model_const.Head.VALUE_HEAD.value][:, self.indices_by_faction_name[self.winner]] = 1
        for i, game_state in enumerate(self.game_states):
            top_action_class = game_state.action_stack.first.__class__
            if top_action_class is MoveOnePiece:
                ExperienceCollector._assign_move_probs__move_one_piece(values_and_move_probs, i, self.move_visits[i])
            else:
                ExperienceCollector._assign_move_probs(values_and_move_probs, i, top_action_class, self.move_visits[i])
            # If the action is [MoveOnePiece], we can't just use a decoder as normal. We need to compute probabilities
            # for both board space and piece type from the available choices.

        return encoded_boards, encoded_data, values_and_move_probs


@attr.s(slots=True)
class Branch:
    # Prior probability of choosing this branch, based on the model's prediction
    # for the parent state
    prior = attr.ib()
    visit_count = attr.ib(default=0)
    total_value = attr.ib(default=0.0)


@attr.s(slots=True)
class Node:
    game_state = attr.ib()
    # Mapping from player faction to value for this state
    values = attr.ib()
    # [parent] and [last_move] are stored to facilitate propagating values back up the tree
    parent = attr.ib()
    last_move = attr.ib()
    total_visit_count = attr.ib(default=1)
    branches = attr.ib(factory=dict)
    children = attr.ib(factory=dict)

    @classmethod
    def from_state(cls, state, values, parent, last_move, priors):
        node = cls(state, values, parent, last_move)
        for move, p in priors.items():
            node.branches[move] = Branch(p)
        return node

    def moves(self):
        return list(self.branches.keys())

    def add_child(self, move, child_node):
        self.children[move] = child_node

    def has_child(self, move):
        return move in self.children

    def expected_value(self, move):
        branch = self.branches[move]
        if branch.visit_count == 0:
            return 0.0
        return branch.total_value / branch.visit_count

    def prior(self, move):
        return self.branches[move].prior

    def visit_count(self, move):
        return self.branches[move].visit_count

    def record_visit(self, move, value):
        self.total_visit_count += 1
        self.branches[move].visit_count += 1
        self.branches[move].total_value += value

    def propagate_values(self, values, last_move):
        node = self
        while node is not None:
            value_for_current_node = values[sc.get_current_player(node.game_state).faction_name()]
            node.record_visit(last_move, value_for_current_node)
            last_move = node.last_move
            node = node.parent


# TODO: IMPORTANT - SHARE THE TREE BETWEEN SIMULATIONS OF THE SAME GAME
@attr.s(slots=True)
class MCTSZeroAgent(Agent):
    simulations_per_choice = attr.ib()
    c = attr.ib()
    view = attr.ib()
    worker_env_conn = attr.ib()
    experience_collector = attr.ib(default=None)

    def begin_episode(self):
        self.experience_collector = None

    def complete_episode(self, winner):
        self.experience_collector.complete_episode(winner)

    def select_branch(self, node):
        total_n = node.total_visit_count

        def score_branch(move):
            q = node.expected_value(move)
            p = node.prior(move)
            n = node.visit_count(move)
            score = q + self.c * p * np.sqrt(total_n) / (n + 1)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'Evaluating move {move}')
                logger.debug(f'EV: {q}; P: {p}; VC: {n}; Score: {score}')
            return score

        return max(node.moves(), key=score_branch)

    # Even though [choices] is implied by [game_state], we pass it in here to avoid recomputing it
    # since we needed to compute it in the initial call to [select_move] in order to shortcut in the
    # event that there are 0 or 1 choices.
    async def create_node_async(self, game_state, choices, move=None, parent=None):
        if game_state.is_over():
            values = {}
            for player in game_state.players_by_idx:
                faction_name = player.faction_name()
                values[faction_name] = 1 if faction_name is game_state.winner else 0
            move_priors = {}
        else:
            t = time.time()
            # Encode game state and write to shared memory
            encoded_game_state = gs_enc.encode(game_state)
            assert self.view.board.shape == encoded_game_state.board.shape
            self.view.board[:] = encoded_game_state.board
            encoded_data = encoded_game_state.encoded_data()
            assert self.view.data.shape == encoded_data.shape
            self.view.data[:] = encoded_data
            self.worker_env_conn.wake_up_env()
            await self.worker_env_conn.worker_get_woken_up()
            # Read the predictions out of shared memory and convert them to values and move priors
            values, move_priors = model.to_values_and_move_priors(game_state, choices, self.view.preds)
            # print(f'Took {time.time() - t}s to get evaluation results')
        new_node = Node.from_state(game_state, values, parent, move, move_priors)
        if parent is not None:
            parent.add_child(move, new_node)
        return new_node

    async def select_move_async(self, game_state):
        if self.experience_collector is None:
            indices_by_faction_name = gs_enc.get_indices_by_faction_name(game_state)
            self.experience_collector = ExperienceCollector(indices_by_faction_name)

        choices = game_state.legal_moves()
        if not choices:
            return None
        if len(choices) == 1:
            return choices[0]

        old_level = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)
        root = await self.create_node_async(game_state, choices)

        for i in range(self.simulations_per_choice * len(choices)):
            logger.debug('STARTING AT THE ROOT')
            node = root
            while node.moves():
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f'Selecting a branch for {node.game_state.action_stack.first.__class__}')
                move = self.select_branch(node)
                if node.has_child(move):
                    node = node.children[move]
                else:
                    break

            if node.game_state.is_over():
                values_to_propagate = {faction_name: 1 if faction_name is game_state.winner else 0
                                       for faction_name in game_state.player_idx_by_faction_name.keys()}
            else:
                new_state = play.apply_move(node.game_state, move)
                legal_moves = new_state.legal_moves()
                while not new_state.is_over() and (not legal_moves or len(legal_moves) == 1):
                    new_state = play.apply_move(new_state, None) if not legal_moves \
                        else play.apply_move(new_state, legal_moves[0])
                    legal_moves = new_state.legal_moves()
                node = await self.create_node_async(new_state, legal_moves, move, parent=node)
                values_to_propagate = node.values

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'Propagating values {values_to_propagate}')
            while node.parent is not None:
                faction_name = sc.get_current_player(node.parent.game_state).faction_name()
                value = values_to_propagate[faction_name]
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f'Recording a value of {value} for player {faction_name}')
                node.parent.record_visit(move, value)
                move = node.parent.last_move
                node = node.parent

        logging.getLogger().setLevel(old_level)
        legal_moves = root.moves()
        move_visits = {move: root.visit_count(move) for move in legal_moves}
        assert len(legal_moves) == len(move_visits)
        self.experience_collector.record_move(game_state, move_visits)
        total_moves = sum(move_visits.values())
        probas = [mv / total_moves for mv in move_visits.values()]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'Probability distribution for {legal_moves}: {probas}')
        # Have to do this annoying thing because [legal_moves] might contain tuples
        return legal_moves[np.random.choice(range(len(legal_moves)), p=probas)]


@attr.s(slots=True)
class MCTSZeroAgentManual:
    simulations_per_choice = attr.ib()
    c = attr.ib()
    view = attr.ib()
    current_tree_root = attr.ib(default=None)
    current_tree_node = attr.ib(default=None)
    current_simulation = attr.ib(default=0)
    experience_collector = attr.ib(default=None)
    old_logging_level = attr.ib(default=None)
    pending_game_state_and_choices = attr.ib(default=None)

    def begin_episode(self):
        self.experience_collector = None

    def complete_episode(self, winner):
        self.experience_collector.complete_episode(winner)

    def select_branch(self, node):
        total_n = node.total_visit_count

        def score_branch(move):
            q = node.expected_value(move)
            p = node.prior(move)
            n = node.visit_count(move)
            score = q + self.c * p * np.sqrt(total_n) / (n + 1)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'Evaluating move {move}')
                logger.debug(f'EV: {q}; P: {p}; VC: {n}; Score: {score}')
            return score

        return max(node.moves(), key=score_branch)

    class Result(Enum):
        PREDICTIONS_NEEDED = 0
        MOVE_SELECTED = 1
        GAME_OVER = 2
        NEXT_SIMULATION = 3

    def send_predictions_to_evaluator(self, game_state):
        encoded_game_state = gs_enc.encode(game_state)
        assert self.view.board.shape == encoded_game_state.board.shape
        self.view.board[:] = encoded_game_state.board
        self.view.board_dirty = 1
        encoded_data = encoded_game_state.encoded_data()
        assert self.view.data.shape == encoded_data.shape
        self.view.data[:] = encoded_data
        self.view.data_dirty = 1

    def advance_until_predictions_needed_or_move_selected_or_game_over(self, game_state):
        if self.experience_collector is None:
            indices_by_faction_name = gs_enc.get_indices_by_faction_name(game_state)
            self.experience_collector = ExperienceCollector(indices_by_faction_name)

        if self.current_tree_root is None:
            # Need to create the root of the tree. We'll need predictions just to do that, so we
            # can stop there.
            choices = game_state.legal_moves()
            if not choices:
                return MCTSZeroAgentManual.Result.MOVE_SELECTED, None
            if len(choices) == 1:
                return MCTSZeroAgentManual.Result.MOVE_SELECTED, choices[0]

            self.old_logging_level = logging.getLogger().level
            logging.getLogger().setLevel(logging.ERROR)

            if game_state.is_over():
                return MCTSZeroAgentManual.Result.GAME_OVER, None

            self.pending_game_state_and_choices = game_state, choices
            self.send_predictions_to_evaluator(game_state)
            return MCTSZeroAgentManual.Result.PREDICTIONS_NEEDED, None

        if self.current_simulation == self.simulations_per_choice:
            # We've done all of the simulating that we need to and can select a move
            logging.getLogger().setLevel(self.old_logging_level)
            legal_moves = self.current_tree_root.moves()
            move_visits = {move: self.current_tree_root.visit_count(move) for move in legal_moves}
            assert len(legal_moves) == len(move_visits)
            self.experience_collector.record_move(game_state, move_visits)
            total_moves = sum(move_visits.values())
            probas = [mv / total_moves for mv in move_visits.values()]
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'Probability distribution for {legal_moves}: {probas}')
            # Have to do this annoying thing because [legal_moves] might contain tuples
            return MCTSZeroAgentManual.Result.MOVE_SELECTED, legal_moves[np.random.choice(range(len(legal_moves)), p=probas)]

        # Perform the next simulation. Using [select_branch], find a node that's either terminal or needs exploration.
        self.current_simulation += 1

        while self.current_tree_node.moves():
            # We know this has to run at least once, because of the above.
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'Selecting a branch for {self.current_tree_node.game_state.action_stack.first.__class__}')
            move = self.select_branch(self.current_tree_node)
            if self.current_tree_node.has_child(move):
                self.current_tree_node = self.current_tree_node.children[move]
            else:
                break

        if not self.current_tree_node.game_state.is_over():
            # If we're not at a terminal state, apply the move from the last branch we selected and make a new node
            # from it. We're going to need to get predictions before we can finish creating the node, so save all
            # necessary state.
            new_state = play.apply_move(self.current_tree_node.game_state, move)
            legal_moves = new_state.legal_moves()
            while not new_state.is_over() and (not legal_moves or len(legal_moves) == 1):
                new_state = play.apply_move(new_state, None) if not legal_moves \
                    else play.apply_move(new_state, legal_moves[0])
                legal_moves = new_state.legal_moves()
            self.pending_game_state_and_choices = new_state, legal_moves
            self.send_predictions_to_evaluator(new_state)
        else:
            # Just do propagation and move to the next simulation
            values_to_propagate = {faction_name: 1 if faction_name is game_state.winner else 0
                                   for faction_name in game_state.player_idx_by_faction_name.keys()}
            propagate_values(self.current_tree_node, move, values_to_propagate)
            self.current_tree_node = self.current_tree_root
            return MCTSZeroAgentManual.Result.NEXT_SIMULATION


    def decode_predictions_and_apply_move(self, env):
        if self.pending_game_state_and_choices is not None:
            game_state, choices = self.pending_game_state_and_choices
            values, move_priors = model.to_values_and_move_priors(game_state, choices, self.view.preds)
            self.view.preds.dirty = 0
            self.current_tree_node = Node.from_state(game_state, values, parent=self.current_tree_node, move=None, move_priors=move_priors)
            if self.current_tree_root is None:
                self.current_tree_root = self.current_tree_node
            self.pending_game_state_and_choices = None
        else:

            node = Node.from_state(new_state, values, parent=node, last_move=move, move_priors=move_priors)
            values_to_propagate = node.values


def propagate_values(node, first_move, values_to_propagate):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'Propagating values {values_to_propagate}')
        move = first_move
        while node.parent is not None:
            faction_name = sc.get_current_player(node.parent.game_state).faction_name()
            value = values_to_propagate[faction_name]
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f'Recording a value of {value} for player {faction_name}')
            node.parent.record_visit(move, value)
            move = node.parent.last_move
            node = node.parent