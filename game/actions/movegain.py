from game.actions.action import *
from game.actions.combat import MaybeCombat
from game.components import Board
from game.types import Benefit, ResourceType, StructureType

import attr
import logging


@attr.s(frozen=True, slots=True)
class LoadResources(Choice):
    piece_key = attr.ib()
    resource_typ = attr.ib()

    @classmethod
    def new(cls, piece_key, resource_typ):
        return cls(f'Maybe load some {resource_typ} onto {piece_key}', piece_key, resource_typ)

    def choose(self, agent, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        return agent.choose_numeric(game_state, 0, piece.board_space.amount_of(self.resource_typ))

    def do(self, game_state, amt):
        piece = game_state.pieces_by_key[self.piece_key]
        assert self.piece_key in piece.board_space.all_piece_keys()
        if amt:
            carrying_resources = piece.carrying_resources
            resource_amt = carrying_resources[self.resource_typ] + amt
            carrying_resources = carrying_resources.set(self.resource_typ, resource_amt)
            piece = attr.evolve(piece, carrying_resources=carrying_resources)
            game_state = GameState.set_piece(game_state, piece)
        return game_state


@attr.s(frozen=True, slots=True)
class LoadWorkers(Choice):
    mech_key = attr.ib()

    @classmethod
    def new(cls, mech_key):
        return cls(f'Load workers onto {mech_key}', mech_key)

    def choose(self, agent, game_state):
        board_coords = GameState.get_board_coords_for_piece_key(game_state, self.mech_key)
        space = game_state.board.get_space(board_coords)
        max_workers = len(space.workers)
        logging.debug(f'Can choose up to {max_workers} workers from space {space}')
        return agent.choose_numeric(game_state, 0, max_workers)

    def do(self, game_state, amt):
        mech = game_state.pieces_by_key(self.mech_key)
        board_space = mech.board_space
        assert self.mech_key in board_space.all_piece_keys()
        if amt:
            added = 0
            logging.debug(f'Load {amt} workers from {board_space}')
            for worker_key in board_space.worker_keys:
                mech = attr.evolve(mech, carrying_worker_keys=mech.carrying_worker_keys.add(worker_key))
                added += 1
                if added == amt:
                    return GameState.set_piece(game_state, mech)
            assert False
        return game_state


@attr.s(frozen=True, slots=True)
class Gain(StateChange):
    @classmethod
    def new(cls):
        return cls('Gain coins')

    def do(self, game_state):
        current_player = GameState.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structure_by_top_action_typ[TopActionType.MOVEGAIN]
        coins_to_gain = 2 if top_action_cubes_and_structure.cubes_upgraded[1] else 1
        return GameState.give_reward_to_player(game_state, current_player, Benefit.COINS, coins_to_gain)


@attr.s(frozen=True, slots=True)
class MovePieceToSpaceAndDropCarryables(StateChange):
    piece_key = attr.ib()
    board_coords = attr.ib()

    @classmethod
    def new(cls, piece_key, board_coords):
        return cls(f'Moving from {piece_key} to {board_coords}', piece_key, board_coords)

    def do(self, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        assert piece.board_space.coords != self.board_coords
        new_space = game_state.board.get_space(self.board_coords)
        controller_of_new_space = new_space.controller()
        current_player = GameState.get_current_player(game_state)
        current_player_faction = current_player.faction_name()
        if controller_of_new_space and controller_of_new_space is not current_player_faction:
            piece = attr.evolve(piece, moved_into_enemy_territory_this_turn=True)
            game_state = GameState.set_piece(game_state, piece)
            logging.debug(f'{current_player_faction!r} moved a piece into enemy territory'
                          f' controlled by {controller_of_new_space!r}')
            if piece.is_plastic() and new_space.contains_no_enemy_plastic(current_player_faction):
                to_scare = set()
                for worker_key in new_space.worker_keys:
                    worker = game_state.pieces_by_key[worker_key]
                    if worker.faction_name is not current_player_faction:
                        to_scare.add(worker)

                for worker in to_scare:
                    game_state = GameState.move_piece(game_state, worker,
                                                      game_state.board.home_base(worker.faction_name).coords)

                current_player = current_player.remove_popularity(len(to_scare))
                game_state = GameState.set_player(game_state, current_player)

        old_space = game_state.board.get_space(piece.board_coords)
        for resource_typ in ResourceType:
            if piece.carrying_resources[resource_typ]:
                new_space = new_space.add_resources(resource_typ, piece.carrying_resources[resource_typ])
                old_space = old_space.remove_resources(resource_typ, piece.carrying_resources[resource_typ])

        if piece.is_mech():
            new_worker_keys = new_space.worker_keys
            old_worker_keys = old_space.worker_keys
            for worker_key in piece.carrying_worker_keys:
                worker = game_state.pieces_by_key[worker_key]
                assert worker.board_coords != self.board_coords
                worker = attr.evolve(worker, board_coords=self.board_coords)
                game_state = GameState.set_piece(game_state, worker)
                logging.debug(f'Mech carried worker to {self.board_coords}')
                new_worker_keys = new_worker_keys.add(worker)
                old_worker_keys = old_worker_keys.remove(worker)
                assert worker_key in worker.board_space.all_piece_keys()
            new_space = attr.evolve(new_space, worker_keys=new_worker_keys)
            old_space = attr.evolve(old_space, worker_keys=old_worker_keys)

        board = game_state.board.set_space(new_space).set_space(old_space)
        game_state = attr.evolve(game_state, board=board)
        game_state = GameState.move_piece(game_state, game_state.board, piece, self.board_coords)
        piece = attr.evolve(piece, moved_this_turn=True).drop_everything()
        game_state = GameState.set_piece(game_state, piece)
        return game_state


@attr.s(frozen=True, slots=True)
class MovePieceOneSpace(Choice):
    piece_key = attr.ib()

    @classmethod
    def new(cls, piece_key):
        return cls('Move {piece_key} one space', piece_key)

    def choose(self, agent, game_state):
        effective_adjacent_space_coords = GameState.effective_adjacent_space_coords(game_state, self.piece_key)
        logging.debug(f'Choosing from {effective_adjacent_space_coords}')
        assert game_state.pieces_by_key[self.piece_key].board_coords not in effective_adjacent_space_coords
        return agent.choose_board_space(game_state, effective_adjacent_space_coords)

    def do(self, game_state, board_coords):
        assert self.piece_key in \
               game_state.board.get_space(game_state.pieces_by_key[self.piece_key].board_coords).all_piece_keys()
        return GameState.push_action(game_state, MovePieceToSpaceAndDropCarryables.new(self.piece_key, board_coords))


@attr.s(frozen=True, slots=True)
class LoadAndMovePiece(StateChange):
    piece_key = attr.ib()

    @classmethod
    def new(cls, piece_key):
        return cls(None, piece_key)

    def do(self, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        cur_space = game_state.board.get_space(piece.board_coords)
        assert self.piece_key in cur_space.all_piece_keys()
        # This is how we "short-circuit" the move action if a piece walked into an enemy-controlled
        # territory.
        if piece.moved_into_enemy_territory_this_turn:
            return

        assert piece.not_carrying_anything()
        game_state.action_stack.append(MovePieceOneSpace.new(self.piece_key))
        for r in ResourceType:
            if cur_space.amount_of(r):
                game_state = GameState.push_action(game_state, LoadResources.new(self.piece_key, r))
        if piece.is_mech() and cur_space.workers:
            game_state = GameState.push_action(game_state, LoadWorkers.new(self.piece_key))
        return game_state

# The outer class represents the entire move action for a single piece. The steps are:
# 1. Choose a piece to move from pieces that haven't moved this turn. Only now do we know how much move we can have.
# 2. For each point of movement you have the option to:
# 2a. Load as much stuff as you want (look at everything in your current square that's carryable by your piece type)
# 2b. Move to an adjacent hex
# 2bi. Update the new and old hexes for the piece being moved as well as each piece being carried.
# 2biii. Mark the piece as having moved this turn.
# 2c. Drop all your stuff


@attr.s(frozen=True, slots=True)
class MoveOnePiece(Choice):
    @classmethod
    def new(cls):
        return cls('Move one piece')

    def choose(self, agent, game_state):
        # Here we don't let someone pick a piece if it happens to be a worker that was dropped into
        # enemy territory this turn. That would get around the [moved_this_turn] check, so we explicitly
        # check to see that we're not starting in enemy territory. There would be no legal way for a mech
        # or character to start in enemy territory anyway.
        current_player = GameState.get_current_player(game_state)
        movable_pieces = GameState.movable_pieces(game_state, current_player)
        movable_pieces = [piece for piece in movable_pieces
                          if game_state.board.get_space(piece.board_coords).controller()
                          is current_player.faction_name()]
        logging.debug(f'Choosing a piece from {movable_pieces}')
        return agent.choose_piece(game_state, movable_pieces)

    def do(self, game_state, piece):
        logging.debug(f'Chosen: {piece}')
        for _ in range(GameState.get_current_player(game_state).base_move_for_piece_type(piece.typ) - 1):
            game_state = GameState.push_action(game_state, Optional.new(LoadAndMovePiece.new(piece)))
        return GameState.push_action(game_state, LoadAndMovePiece.new(piece))


class Move(StateChange):
    _maybe_combat = MaybeCombat.new()
    _move_one_piece = MoveOnePiece.new()
    _optional_move = Optional.new(_move_one_piece)

    @classmethod
    def new(cls):
        return cls('Move')

    def do(self, game_state):
        game_state = GameState.push_action(game_state, Move._maybe_combat)
        game_state = GameState.push_action(game_state, Move._optional_move)
        player_mat = GameState.get_current_player(game_state).player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structure_by_top_action_typ[TopActionType.MOVEGAIN]
        if top_action_cubes_and_structure.cubes_upgraded[0]:
            game_state = GameState.push_action(game_state, Move._optional_move)
        return GameState.push_action(game_state, Move._move_one_piece)


_move = Move.new()
_gain = Gain.new()


def move_gain():
    return Boolean.new(_move, _gain)
