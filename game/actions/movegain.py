from game.actions.action import *
from game.actions.combat import MaybeCombat
from game.components import Board
from game.types import Benefit, ResourceType, StructureType

import logging


class MoveGain(Boolean):
    def __init__(self):
        self._top_action = TopAction('Move / Gain', num_cubes=2, structure_typ=StructureType.MINE)
        self.move = Move(self._top_action)
        self.gain = Gain(self._top_action)
        super().__init__(self.move, self.gain)

    def top_action(self):
        return self._top_action


# The outer class represents the entire move action for a single piece. The steps are:
# 1. Choose a piece to move from pieces that haven't moved this turn. Only now do we know how much move we can have.
# 2. For each point of movement you have the option to:
# 2a. Load as much stuff as you want (look at everything in your current square that's carryable by your piece type)
# 2b. Move to an adjacent hex
# 2bi. Update the new and old hexes for the piece being moved as well as each piece being carried.
# 2biii. Mark the piece as having moved this turn.
# 2c. Drop all your stuff

class Gain(StateChange):
    def __init__(self, top_action):
        super().__init__('Gain coins')
        self._top_action = top_action

    def do(self, game_state):
        coins_to_gain = 2 if self._top_action.cubes_upgraded[1] else 1
        game_state.give_reward_to_player(game_state.current_player, Benefit.COINS, coins_to_gain)


class MoveOnePiece(Choice):
    def __init__(self):
        super().__init__()

    def choose(self, agent, game_state):
        # Here we don't let someone pick a piece if it happens to be a worker that was dropped into
        # enemy territory this turn. That would get around the [moved_this_turn] check, so we explicitly
        # check to see that we're not starting in enemy territory. There would be no legal way for a mech
        # or character to start in enemy territory anyway.
        movable_pieces = [piece for piece in game_state.current_player.movable_pieces()
                          if piece.board_space.controller() is game_state.current_player.faction_name()]
        logging.debug(f'Choosing a piece from {movable_pieces}')
        return agent.choose_piece(game_state, movable_pieces)

    def do(self, game_state, piece):
        logging.debug(f'Chosen: {piece}')
        for _ in range(game_state.current_player.base_move_for_piece_type(piece.typ) - 1):
            game_state.action_stack.append(Optional(LoadAndMovePiece(piece)))
        game_state.action_stack.append(LoadAndMovePiece(piece))


class Move(StateChange):
    maybe_combat = MaybeCombat()
    move_one_piece = MoveOnePiece()
    optional_move = Optional(move_one_piece)

    def __init__(self, top_action):
        super().__init__('Move')
        self._top_action = top_action

    def do(self, game_state):
        game_state.action_stack.append(Move.maybe_combat)
        game_state.action_stack.append(Move.optional_move)
        if self._top_action.cubes_upgraded[0]:
            game_state.action_stack.append(Move.optional_move)
        game_state.action_stack.append(Move.move_one_piece)


class LoadAndMovePiece(StateChange):
    def __init__(self, piece):
        super().__init__()
        self.piece = piece

    def do(self, game_state):
        assert self.piece in self.piece.board_space.all_pieces()
        # This is how we "short-circuit" the move action if a piece walked into an enemy-controlled
        # territory.
        if self.piece.moved_into_enemy_territory_this_turn:
            return

        assert self.piece.not_carrying_anything()
        cur_space = self.piece.board_space
        game_state.action_stack.append(MovePieceOneSpace(self.piece))
        for r in ResourceType:
            if cur_space.amount_of(r):
                game_state.action_stack.append(LoadResources(self.piece, r))
        if self.piece.is_mech() and cur_space.workers:
            game_state.action_stack.append(LoadWorkers(self.piece))


class LoadResources(Choice):
    def __init__(self, piece, resource_typ):
        super().__init__()
        self.piece = piece
        self.resource_typ = resource_typ

    def choose(self, agent, game_state):
        return agent.choose_numeric(game_state, 0, self.piece.board_space.amount_of(self.resource_typ))

    def do(self, game_state, amt):
        assert self.piece in self.piece.board_space.all_pieces()
        if amt:
            logging.debug(f'Load {amt} {self.resource_typ!r} onto {self.piece!r}')
            self.piece.carrying_resources[self.resource_typ] += amt


class LoadWorkers(Choice):
    def __init__(self, mech):
        super().__init__(f'Load workers onto {mech!r}')
        self.mech = mech

    def choose(self, agent, game_state):
        logging.debug(f'Can choose up to {len(self.mech.board_space.workers)} workers'
                      f' from space {self.mech.board_space!r}')
        return agent.choose_numeric(game_state, 0, len(self.mech.board_space.workers))

    def do(self, game_state, amt):
        assert self.mech in self.mech.board_space.all_pieces()
        if amt:
            added = 0
            logging.debug(f'Load {amt} workers from {self.mech.board_space!r}')
            for worker in self.mech.board_space.workers:
                self.mech.carrying_workers.add(worker)
                added += 1
                if added == amt:
                    return
            assert False


class MovePieceOneSpace(Choice):
    def __init__(self, piece):
        super().__init__()
        self.piece = piece

    def choose(self, agent, game_state):
        logging.debug(f'{self.piece} leaving from {self.piece.board_space}')
        effective_adjacent_spaces = game_state.current_player.effective_adjacent_spaces(self.piece, game_state.board)
        logging.debug(f'Choosing from {effective_adjacent_spaces}')
        assert self.piece.board_space not in effective_adjacent_spaces
        return agent.choose_board_space(game_state, effective_adjacent_spaces)

    def do(self, game_state, space):
        assert self.piece in self.piece.board_space.all_pieces()
        game_state.action_stack.append(MovePieceToSpaceAndDropCarryables(self.piece, space))


class MovePieceToSpaceAndDropCarryables(StateChange):
    def __init__(self, piece, board_space):
        super().__init__()
        self.piece = piece
        self.board_space = board_space

    def do(self, game_state):
        if self.piece.board_space is self.board_space:
            logging.debug(f'Moving from {self.piece.board_space} to {self.board_space}')
        assert self.piece.board_space is not self.board_space
        controller_of_new_space = self.board_space.controller()
        current_player_faction = game_state.current_player.faction_name()
        if controller_of_new_space and controller_of_new_space is not current_player_faction:
            self.piece.moved_into_enemy_territory_this_turn = True
            logging.debug(f'{current_player_faction!r} moved a piece into enemy territory'
                          f' controlled by {controller_of_new_space!r}')
            if self.piece.is_plastic() and self.board_space.contains_no_enemy_plastic(current_player_faction):
                to_scare = set()
                for worker in self.board_space.workers:
                    if worker.faction_name is not current_player_faction:
                        to_scare.add(worker)

                for worker in to_scare:
                    Board.move_piece(worker, game_state.board.home_base(worker.faction_name))
                game_state.current_player.remove_popularity(min(len(to_scare), game_state.current_player.popularity()))

        for resource_typ in ResourceType:
            if self.piece.carrying_resources[resource_typ]:
                self.board_space.add_resources(resource_typ, self.piece.carrying_resources[resource_typ])
                self.piece.board_space.remove_resources(resource_typ, self.piece.carrying_resources[resource_typ])
        if self.piece.is_mech():
            for worker in self.piece.carrying_workers:
                assert worker.board_space is not self.board_space
                worker.board_space = self.board_space
                logging.debug(f'Mech carried worker to {self.board_space}')
                self.board_space.workers.add(worker)
                self.piece.board_space.workers.remove(worker)
                assert worker in worker.board_space.all_pieces()
        Board.move_piece(self.piece, self.board_space)
        self.piece.moved_this_turn = True
        self.piece.drop_everything()
