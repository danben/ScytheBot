import game.constants as constants
import game.state_change as sc
from game.actions import Boolean, Choice, MaybeCombat, Optional, StateChange
from game.types import Benefit, ResourceType, TopActionType

import attr
import logging


@attr.s(frozen=True, slots=True)
class LoadResources(Choice):
    piece_key = attr.ib()
    resource_typ = attr.ib()

    @classmethod
    def new(cls, piece_key, resource_typ):
        return cls(f'Maybe load some {resource_typ} onto {piece_key}', piece_key, resource_typ)

    def choices(self, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        # TODO: replace magic constant
        amt = min(game_state.board.get_space(piece.board_coords).amount_of(self.resource_typ), 19)
        return list(range(amt+1))

    def do(self, game_state, amt):
        if amt:
            piece = game_state.pieces_by_key[self.piece_key]
            carrying_resources = piece.carrying_resources
            resource_amt = carrying_resources[self.resource_typ] + amt
            carrying_resources = carrying_resources.set(self.resource_typ, resource_amt)
            piece = attr.evolve(piece, carrying_resources=carrying_resources)
            game_state = sc.set_piece(game_state, piece)
        return game_state


@attr.s(frozen=True, slots=True)
class LoadWorkers(Choice):
    mech_key = attr.ib()

    @classmethod
    def new(cls, mech_key):
        return cls(f'Load workers onto {mech_key}', mech_key)

    def choices(self, game_state):
        board_coords = sc.get_board_coords_for_piece_key(game_state, self.mech_key)
        space = game_state.board.get_space(board_coords)
        assert len(space.worker_keys) <= constants.NUM_WORKERS
        return list(range(len(space.worker_keys)+1))

    def do(self, game_state, amt):
        if not amt:
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Chose not to load any workers')
            return game_state
        added = 0
        mech = game_state.pieces_by_key[self.mech_key]
        board_space = game_state.board.get_space(mech.board_coords)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Load {amt} workers from {board_space}')
        for worker_key in board_space.worker_keys:
            mech = attr.evolve(mech, carrying_worker_keys=mech.carrying_worker_keys.add(worker_key))
            added += 1
            if added == amt:
                return sc.set_piece(game_state, mech)
        assert False


@attr.s(frozen=True, slots=True)
class Gain(StateChange):
    @classmethod
    def new(cls):
        return cls('Gain coins')

    def do(self, game_state):
        current_player = sc.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.MOVEGAIN]
        coins_to_gain = 2 if top_action_cubes_and_structure.cubes_upgraded[1] else 1
        return sc.give_reward_to_player(game_state, current_player, Benefit.COINS, coins_to_gain)


@attr.s(frozen=True, slots=True)
class MovePieceToSpaceAndDropCarryables(StateChange):
    piece_key = attr.ib()
    board_coords = attr.ib()

    @classmethod
    def new(cls, piece_key, board_coords):
        return cls(f'Moving {piece_key} to {board_coords}', piece_key, board_coords)

    def do(self, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        assert piece.board_coords != self.board_coords
        new_space = game_state.board.get_space(self.board_coords)
        assert (not piece.is_worker()) or new_space.contains_no_enemy_workers(piece.faction_name)
        controller_of_new_space = sc.controller(game_state, new_space)
        current_player = sc.get_current_player(game_state)
        current_player_faction = current_player.faction_name()
        if controller_of_new_space and controller_of_new_space is not current_player_faction:
            if not new_space.controlled_by_structure():
                piece = attr.evolve(piece, moved_into_enemy_territory_this_turn=True)
                game_state = sc.set_piece(game_state, piece)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'{current_player_faction} moved {piece} into enemy territory ({new_space})'
                              f' controlled by {controller_of_new_space}')
                logging.debug(f'{new_space!r}')
            if piece.is_plastic() and new_space.contains_no_enemy_plastic(current_player_faction):
                to_scare = set()
                for worker_key in new_space.worker_keys:
                    assert worker_key.faction_name is not current_player_faction
                    to_scare.add(worker_key)

                for worker_key in to_scare:
                    if logging.getLogger().isEnabledFor(logging.DEBUG):
                        logging.debug(f'Worker {worker_key} got scared home')
                    game_state = sc.move_piece(game_state, worker_key,
                                               game_state.board.home_base(worker_key.faction_name).coords)

                game_state = sc.remove_popularity(game_state, sc.get_current_player(game_state), len(to_scare))
        old_space = game_state.board.get_space(piece.board_coords)
        new_space = game_state.board.get_space(self.board_coords)
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
                game_state = sc.set_piece(game_state, worker)
                if logging.getLogger().isEnabledFor(logging.DEBUG):
                    logging.debug(f'Mech carried worker to {self.board_coords}')
                new_worker_keys = new_worker_keys.add(worker_key)
                old_worker_keys = old_worker_keys.remove(worker_key)
            new_space = attr.evolve(new_space, worker_keys=new_worker_keys)
            old_space = attr.evolve(old_space, worker_keys=old_worker_keys)
        board = game_state.board.set_space(new_space).set_space(old_space)
        game_state = attr.evolve(game_state, board=board)
        piece = attr.evolve(piece, moved_this_turn=True)
        piece = piece.drop_everything()
        game_state = sc.set_piece(game_state, piece)
        return sc.move_piece(game_state, piece.key(), self.board_coords)


@attr.s(frozen=True, slots=True)
class MovePieceOneSpace(Choice):
    piece_key = attr.ib()

    @classmethod
    def new(cls, piece_key):
        return cls(f'Move {piece_key} one space', piece_key)

    def choices(self, game_state):
        ret = sc.effective_adjacent_space_coords(game_state, self.piece_key)
        assert game_state.pieces_by_key[self.piece_key].board_coords not in ret
        return ret

    def do(self, game_state, board_coords):
        assert self.piece_key in \
               game_state.board.get_space(game_state.pieces_by_key[self.piece_key].board_coords).all_piece_keys()
        return sc.push_action(game_state, MovePieceToSpaceAndDropCarryables.new(self.piece_key, board_coords))


@attr.s(frozen=True, slots=True)
class LoadAndMovePiece(StateChange):
    piece_key = attr.ib()

    @classmethod
    def new(cls, piece_key):
        return cls(f'Load and move piece: {piece_key}', piece_key)

    def do(self, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        # This is how we "short-circuit" the move action if a piece walked into an enemy-controlled
        # territory.
        if piece.moved_into_enemy_territory_this_turn:
            return game_state
        cur_space = game_state.board.get_space(piece.board_coords)
        assert self.piece_key in cur_space.all_piece_keys()
        assert piece.not_carrying_anything()
        assert not piece.moved_into_enemy_territory_this_turn
        game_state = sc.push_action(game_state, MovePieceOneSpace.new(self.piece_key))
        for r in ResourceType:
            if cur_space.amount_of(r):
                game_state = sc.push_action(game_state, LoadResources.new(self.piece_key, r))
        if piece.is_mech() and cur_space.worker_keys:
            game_state = sc.push_action(game_state, LoadWorkers.new(self.piece_key))
        return game_state

# The outer class represents the entire move action for a single piece. The steps are:
# 1. Choose a piece to move from pieces that haven't moved this turn. Only now do we know how much move we can have.
# 2. For each point of movement you have the option to:
# 2 Load as much stuff as you want (look at everything in your current square that's carryable by your piece type)
# 2b. Move to an adjacent hex
# 2bi. Update the new and old hexes for the piece being moved as well as each piece being carried.
# 2biii. Mark the piece as having moved this turn.
# 2c. Drop all your stuff


@attr.s(frozen=True, slots=True)
class MoveOnePiece(Choice):
    @classmethod
    def new(cls):
        return cls('Move one piece')

    def choices(self, game_state):
        # Here we don't let someone pick a piece if it happens to be a worker that was dropped into
        # enemy territory this turn. That would get around the [moved_this_turn] check, so we explicitly
        # check to see that we're not starting in enemy territory. There would be no legal way for a mech
        # or character to start in enemy territory anyway.
        current_player = sc.get_current_player(game_state)
        ret = [board_coords_and_piece_typ
               for board_coords_and_piece_typ in sc.movable_pieces(game_state, current_player)
               if sc.controller(game_state, game_state.board.get_space(board_coords_and_piece_typ[0]))
               is current_player.faction_name()]
        if not ret:
            return None
        return ret

    def do(self, game_state, board_coords_and_piece_typ):
        if not board_coords_and_piece_typ:
            logging.debug('No movable pieces')
            return game_state
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Chosen: {board_coords_and_piece_typ}')
        piece_key = sc.get_piece_by_board_coords_and_piece_typ(game_state, *board_coords_and_piece_typ)
        for _ in range(sc.get_current_player(game_state).base_move_for_piece_typ(piece_key.piece_typ) - 1):
            game_state = sc.push_action(game_state, Optional.new(LoadAndMovePiece.new(piece_key)))
        return sc.push_action(game_state, LoadAndMovePiece.new(piece_key))


class Move(StateChange):
    _maybe_combat = MaybeCombat.new()
    _move_one_piece = MoveOnePiece.new()
    _optional_move = Optional.new(_move_one_piece)

    @classmethod
    def new(cls):
        return cls('Move')

    def do(self, game_state):
        game_state = sc.push_action(game_state, Move._maybe_combat)
        player_mat = sc.get_current_player(game_state).player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.MOVEGAIN]
        if top_action_cubes_and_structure.cubes_upgraded[0]:
            game_state = sc.push_action(game_state, Move._optional_move)
        game_state = sc.push_action(game_state, Move._optional_move)
        return sc.push_action(game_state, Move._move_one_piece)


_move = Move.new()
_gain = Gain.new()


def action():
    return Boolean.new(_move, _gain)
