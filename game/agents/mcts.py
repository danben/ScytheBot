from game import play
from game.agents import Agent
from game.agents.random import RandomAgent
import game.state_change as sc

import math
import random
import time


def uct_score(parent_rollouts, child_rollouts, win_pct, temperature):
    exploration = math.sqrt(math.log(parent_rollouts) / child_rollouts)
    return win_pct + temperature * exploration


class MCTSNode:
    def __init__(self, game_state, players, parent=None, move=None, unvisited_moves=None):
        uvmoves = game_state.legal_moves() if not unvisited_moves else unvisited_moves
        if not uvmoves:
            print(game_state.action_stack.first)
            assert False
        self.game_state = game_state
        self.parent = parent
        self.move = move
        self.win_counts = {player: 0 for player in players}
        self.num_rollouts = 0
        self.children = []
        self.unvisited_moves = uvmoves

    def add_random_child(self):
        index = random.randint(0, len(self.unvisited_moves) - 1)
        new_move = self.unvisited_moves.pop(index)
        new_game_state = play.apply_move(self.game_state, new_move)
        while not new_game_state.legal_moves():
            print(f'Action with no choices: {new_game_state.action_stack.first}')
            new_game_state = play.apply_move(self.game_state, None)
        new_node = MCTSNode(new_game_state, self.win_counts.keys(), parent=self, move=new_move)
        self.children.append(new_node)
        return new_node

    def record_win(self, winner):
        self.win_counts[winner] += 1
        self.num_rollouts += 1

    def winning_frac(self, player):
        return float(self.win_counts[player]) / self.num_rollouts

    def is_terminal(self):
        return self.game_state.is_over()

    def can_add_child(self):
        return len(self.unvisited_moves) > 0


class MCTSAgent(Agent):
    def __init__(self, players, temperature, num_rounds):
        self.players = players
        self.temperature = temperature
        self.num_rounds = num_rounds

    @staticmethod
    def simulate_random_game(game_state):
        agent = RandomAgent()
        ctr = 0

        while not game_state.is_over():
            ctr += 1
            next_action = game_state.action_stack.first
            chosen = next_action.choose(agent, game_state)
            game_state = play.apply_move(game_state, chosen)

        return game_state.winner

    def select_move(self, game_state, choices):
        if not choices:
            return None
        if len(choices) == 1:
            return choices[0]
        if not isinstance(choices, list):
            print(choices)
            assert False
        if not choices:
            assert False
        root = MCTSNode(game_state, self.players, unvisited_moves=choices)
        for i in range(self.num_rounds):
            node = root
            while (not node.can_add_child()) and (not node.is_terminal()):
                node = self.select_child(node)

            if node.can_add_child():
                node = node.add_random_child()

            winner = MCTSAgent.simulate_random_game(node.game_state)

            while node is not None:
                node.record_win(winner)
                node = node.parent

        best_move = None
        best_pct = -1.0
        faction_name = sc.get_current_player(game_state).faction_name()
        for child in root.children:
            child_pct = child.winning_frac(faction_name)
            if child_pct > best_pct:
                best_pct = child_pct
                best_move = child.move

        return best_move

    def select_child(self, node):
        best_score = 0
        best_child = None
        if not node.children:
            print(node.game_state.action_stack.first)
            print(node)
            assert False
        if not isinstance(node.children, list):
            print(node.children)
            assert False
        for child in node.children:
            score = uct_score(node.num_rollouts, child.num_rollouts,
                              child.winning_frac(sc.get_current_player(node.game_state).faction_name()),
                              self.temperature)
            if score > best_score:
                best_score = score
                best_child = child

        if not (best_child and isinstance(node.children, list)):
            print(node.children)
            print(best_child)
            assert False
        return best_child

    def choose_action(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_action_spot(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_boolean(self, game_state):
        return self.select_move(game_state, [False, True])

    def choose_numeric(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_board_coords(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_piece(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_resource_typ(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_bottom_action_typ(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_enlist_reward(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_mech_typ_to_deploy(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_structure_typ(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_cube_space_to_upgrade(self, game_state, choices):
        return self.select_move(game_state, choices)

    def choose_optional_combat_card(self, game_state, choices):
        return self.select_move(game_state, choices)
