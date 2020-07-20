from game import play
from game.actions import MoveOnePiece
from agents import Agent
from training import constants as model_const, decode, model
import encoders.game_state as gs_enc
import game.state_change as sc

import attr
import numpy as np
import logging

from collections import  defaultdict

logger = logging.getLogger('mcts_zero_debug_logger')
logger.setLevel(logging.ERROR)


@attr.s(slots=True)
class ExperienceCollector:
    indices_by_faction_name = attr.ib()
    game_states = attr.ib(factory=list)
    legal_moves = attr.ib(factory=list)
    move_visits = attr.ib(factory=list)
    winner = attr.ib(default=None)

    def record_move(self, game_state, choices, move_visits):
        self.game_states.append(game_state)
        self.legal_moves.append(choices)
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
        values_and_move_probs[model_const.Head.VALUE_HEAD.value][:, self.winner] = 1
        for i, game_state in enumerate(self.game_states):
            assert len(self.legal_moves[i]) == len(self.move_visits[i])
            for move in self.legal_moves[i]:
                assert move in self.move_visits[i]
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


@attr.s(slots=True)
class MCTSZeroAgent(Agent):
    simulations_per_choice = attr.ib()
    c = attr.ib()
    evaluator_conn = attr.ib(default=None)
    evaluator_network = attr.ib(default=None)
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
            if logger.isEnabledFor((logging.DEBUG)):
                logger.debug(f'Evaluating move {move}')
                logger.debug(f'EV: {q}; P: {p}; VC: {n}; Score: {score}')
            return score

        return max(node.moves(), key=score_branch)

    # Even though [choices] is implied by [game_state], we pass it in here to avoid recomputing it
    # since we needed to compute it in the initial call to [select_move] in order to shortcut in the
    # event that there are 0 or 1 choices.
    def create_node(self, game_state, choices, move=None, parent=None):
        if game_state.is_over():
            values = {}
            for player in game_state.players_by_idx:
                faction_name = player.faction_name()
                values[faction_name] = 1 if faction_name is game_state.winner else 0
            move_priors = {}
        else:
            if self.evaluator_conn is not None:
                self.evaluator_conn.send((game_state, choices))
                values, move_priors = self.evaluator_conn.recv()
            else:
                values, move_priors = model.evaluate(self.evaluator_network, [game_state], [choices])
        new_node = Node.from_state(game_state, values, parent, move, move_priors)
        if parent is not None:
            parent.add_child(move, new_node)
        return new_node

    def select_move(self, game_state):
        if not self.experience_collector:
            indices_by_faction_name = gs_enc.get_indices_by_faction_name(game_state)
            self.experience_collector = ExperienceCollector(indices_by_faction_name)

        choices = game_state.legal_moves()
        if not choices:
            return None
        if len(choices) == 1:
            return choices[0]

        old_level = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)
        root = self.create_node(game_state, choices)

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
                node = self.create_node(new_state, legal_moves, move, parent=node)
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
        move_visits = [root.visit_count(move) for move in legal_moves]
        assert len(legal_moves) == len(move_visits)
        self.experience_collector.record_move(game_state, legal_moves, move_visits)
        total_moves = sum(move_visits)
        probas = [mv / total_moves for mv in move_visits]
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f'Probability distribution for {legal_moves}: {probas}')
        # Have to do this annoying thing because [legal_moves] might contain tuples
        return legal_moves[np.random.choice(range(len(legal_moves)), p=probas)]
