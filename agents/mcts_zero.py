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
            try:
                move_prob = move_visits[move] / sum(move_visits.values())
            except:
                print(f'Type of move probs: {type(move_visits)}')
                print(f'Output head: {output_head}')
                print(f'len(self.move_probs[i]): {len(move_visits)}')
                print(f'Move: {move}')
                print(f'Decoded: {decoder(move)}')
                assert False
            head = values_and_move_probs[output_head]
            head[row, decoder(move)] = move_prob

    @staticmethod
    def _assign_move_probs(values_and_move_probs, row, top_action_class, move_visits):
        output_head = decode.model_head_by_action_class[top_action_class].value
        decoder = decode.decoders[top_action_class]
        ExperienceCollector._assign_move_probs_aux(values_and_move_probs, row, output_head, decoder, move_visits)

    @staticmethod
    def _assign_move_probs__move_one_piece(values_and_move_probs, row, move_visits):
        board_coords_head = values_and_move_probs[model_const.Head.BOARD_COORDS_HEAD.value]
        piece_type_head = values_and_move_probs[model_const.Head.PIECE_TYP_HEAD.value]
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
        return self.branches.keys()

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


@attr.s(slots=True)
class MCTSZeroAgent(Agent):
    simulations_per_choice = attr.ib()
    c = attr.ib()
    evaluator_conn = attr.ib()
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
            return q + self.c * p * np.sqrt(total_n) / (n + 1)

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
            assert isinstance(choices, list)
            self.evaluator_conn.send((game_state, choices))
            values, move_priors = self.evaluator_conn.recv()
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
            node = root
            next_move = self.select_branch(node)
            while node.has_child(next_move):
                node = node.get_child(next_move)
                next_move = self.select_branch(node)
            new_state = play.apply_move(game_state, next_move)
            legal_moves = new_state.legal_moves()
            while not new_state.is_over() and (not legal_moves or len(legal_moves) == 1):
                new_state = play.apply_move(new_state, None) if not legal_moves \
                    else play.apply_move(new_state, legal_moves[0])
                legal_moves = new_state.legal_moves()
            child_node = self.create_node(new_state, legal_moves, parent=node)
            move = next_move
            while node is not None:
                value = child_node.values[sc.get_current_player(node.game_state).faction_name()]
                node.record_visit(move, value)
                move = node.last_move
                node = node.parent

        logging.getLogger().setLevel(old_level)
        move_visits = {}
        res = None
        max_visit_count = 0
        legal_moves = root.moves()
        for move in legal_moves:
            visit_count = root.visit_count(move)
            move_visits[move] = visit_count
            if visit_count > max_visit_count:
                max_visit_count = visit_count
                res = move
        assert len(legal_moves) == len(move_visits)
        for move in legal_moves:
            assert move in move_visits
        self.experience_collector.record_move(game_state, legal_moves, move_visits)
        assert max_visit_count > 0
        return res
