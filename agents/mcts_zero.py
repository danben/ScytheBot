from game import play
from agents import Agent
from training import model
import encoders.game_state as gs_enc
import game.state_change as sc

import attr
import numpy as np
import logging


@attr.s
class Branch:
    # Prior probability of choosing this branch, based on the model's prediction
    # for the parent state
    prior = attr.ib()
    visit_count = attr.ib(default=0)
    total_value = attr.ib(default=0.0)


@attr.s
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


@attr.s
class MCTSZeroAgent(Agent):
    model = attr.ib()
    simulations_per_choice = attr.ib()
    c = attr.ib()

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
            values, move_priors = model.evaluate(self.model, game_state, choices)
        new_node = Node.from_state(game_state, values, parent, move, move_priors)
        if parent is not None:
            parent.add_child(move, new_node)
        return new_node

    def select_move(self, game_state):
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
            child_node = self.create_node(new_state, new_state.legal_moves(), parent=node)
            move = next_move
            while node is not None:
                value = child_node.values[sc.get_current_player(node.game_state).faction_name()]
                node.record_visit(move, value)
                move = node.last_move
                node = node.parent

        logging.getLogger().setLevel(old_level)
        res = max(root.moves(), key=root.visit_count)
        return res
