from game import play
from agents import Agent
from training import model
import game.state_change as sc

import attr
import numpy as np


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
    branches = attr.ib(default={})
    children = attr.ib(default={})

    @classmethod
    def from_state(cls, state, values, parent, last_move, priors):
        node = cls(state, values, parent, last_move)
        for move, p in priors:
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


class MCTSZeroAgent(Agent):
    model = attr.ib()
    num_rounds = attr.ib()
    c = attr.ib()

    def select_branch(self, node):
        total_n = node.total_visit_count

        def score_branch(move):
            q = node.expected_value(move)
            p = node.prior(move)
            n = node.visit_count(move)
            return q + self.c * p * np.sqrt(total_n) / (n + 1)

        return max(node.moves(), key=score_branch)

    def create_node(self, game_state, move=None, parent=None):
        values, move_priors = model.evaluate(game_state, self.model)
        new_node = Node.from_state(game_state, values, parent, move, move_priors)
        if parent is not None:
            parent.add_child(move, new_node)
        return new_node

    def select_move(self, game_state):
        root = self.create_node(game_state)

        for i in range(self.num_rounds):
            node = root
            next_move = self.select_branch(node)
            while node.has_child(next_move):
                node = node.get_child(next_move)
                next_move = self.select_branch(node)
            new_state = play.apply_move(game_state, next_move)
            child_node = self.create_node(new_state, parent=node)
            move = next_move
            while node is not None:
                value = child_node.values[sc.get_current_player(node.game_state)]
                node.record_visit(move, value)
                move = node.last_move
                node = node.parent
            return max(root.moves(), key=root.visit_count)

    def choose_action(self, game_state, choices):
        pass

    def choose_action_spot(self, game_state, choices):
        pass

    def choose_boolean(self, game_state):
        pass

    def choose_board_coords(self, game_state, choices):
        pass

    def choose_piece(self, game_state, choices):
        pass

    def choose_resource_typ(self, game_state, choices):
        pass

    def choose_bottom_action_typ(self, game_state, choices):
        pass

    def choose_enlist_reward(self, game_state, choices):
        pass

    def choose_mech_typ_to_deploy(self, game_state, choices):
        pass

    def choose_structure_typ(self, game_state, choices):
        pass

    def choose_cube_space_to_upgrade(self, game_state, choices):
        pass

    def choose_optional_combat_card(self, game_state, choices):
        pass

    def choose_num_workers(self, game_state, choices):
        pass

    def choose_combat_wheel_power(self, game_state, choices):
        pass

    def choose_num_resources(self, game_state, choices):
        pass
