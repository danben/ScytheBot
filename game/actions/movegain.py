import game.actions.action as a
import game.state_change as sc
from game.actions.combat import MaybeCombat
from game.types import Benefit, ResourceType, TopActionType

import attr
import logging


@attr.s(frozen=True, slots=True)
class LoadResources(a.Choice):
    piece_key = attr.ib()
    resource_typ = attr.ib()

    @classmethod
    def new(cls, piece_key, resource_typ):
        return cls(f'Maybe load some {resource_typ} onto {piece_key}', piece_key, resource_typ)

    def choose(self, agent, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        amt = game_state.board.get_space(piece.board_coords).amount_of(self.resource_typ)
        return agent.choose_numeric(game_state, 0, amt)

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
class LoadWorkers(a.Choice):
    mech_key = attr.ib()

    @classmethod
    def new(cls, mech_key):
        return cls(f'Load workers onto {mech_key}', mech_key)

    def choose(self, agent, game_state):
        board_coords = sc.get_board_coords_for_piece_key(game_state, self.mech_key)
        space = game_state.board.get_space(board_coords)
        max_workers = len(space.worker_keys)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Can choose up to {max_workers} workers from space {space}')
        return agent.choose_numeric(game_state, 0, max_workers)

    def do(self, game_state, amt):
        mech = game_state.pieces_by_key[self.mech_key]
        board_space = game_state.board.get_space(mech.board_coords)
        if amt:
            added = 0
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Load {amt} workers from {board_space}')
            for worker_key in board_space.worker_keys:
                mech = attr.evolve(mech, carrying_worker_keys=mech.carrying_worker_keys.add(worker_key))
                added += 1
                if added == amt:
                    return sc.set_piece(game_state, mech)
            assert False
        return game_state


@attr.s(frozen=True, slots=True)
class Gain(a.StateChange):
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
class MovePieceToSpaceAndDropCarryables(a.StateChange):
    piece_key = attr.ib()
    board_coords = attr.ib()

    @classmethod
    def new(cls, piece_key, board_coords):
        return cls(f'Moving {piece_key} to {board_coords}', piece_key, board_coords)

    def do(self, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        assert piece.board_coords != self.board_coords
        new_space = game_state.board.get_space(self.board_coords)
        controller_of_new_space = sc.controller(game_state, new_space)
        current_player = sc.get_current_player(game_state)
        current_player_faction = current_player.faction_name()
        if controller_of_new_space and controller_of_new_space is not current_player_faction:
            piece = attr.evolve(piece, moved_into_enemy_territory_this_turn=True)
            game_state = sc.set_piece(game_state, piece)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'{current_player_faction} moved a piece into enemy territory'
                              f' controlled by {controller_of_new_space}')
            if piece.is_plastic() and new_space.contains_no_enemy_plastic(current_player_faction):
                to_scare = set()
                for worker_key in new_space.worker_keys:
                    if worker_key.faction_name is not current_player_faction:
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
        game_state = sc.move_piece(game_state, piece.key(), self.board_coords)
        return game_state


@attr.s(frozen=True, slots=True)
class MovePieceOneSpace(a.Choice):
    piece_key = attr.ib()

    @classmethod
    def new(cls, piece_key):
        return cls(f'Move {piece_key} one space', piece_key)

    def choose(self, agent, game_state):
        effective_adjacent_space_coords = sc.effective_adjacent_space_coords(game_state, self.piece_key)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Choosing from {effective_adjacent_space_coords}')
        assert game_state.pieces_by_key[self.piece_key].board_coords not in effective_adjacent_space_coords
        return agent.choose_board_coords(game_state, effective_adjacent_space_coords)

    def do(self, game_state, board_coords):
        assert self.piece_key in \
               game_state.board.get_space(game_state.pieces_by_key[self.piece_key].board_coords).all_piece_keys()
        return sc.push_action(game_state, MovePieceToSpaceAndDropCarryables.new(self.piece_key, board_coords))


@attr.s(frozen=True, slots=True)
class LoadAndMovePiece(a.StateChange):
    piece_key = attr.ib()

    @classmethod
    def new(cls, piece_key):
        return cls(f'Load and move piece: {piece_key}', piece_key)

    def do(self, game_state):
        piece = game_state.pieces_by_key[self.piece_key]
        cur_space = game_state.board.get_space(piece.board_coords)
        assert self.piece_key in cur_space.all_piece_keys()
        # This is how we "short-circuit" the move action if a piece walked into an enemy-controlled
        # territory.
        if piece.moved_into_enemy_territory_this_turn:
            return game_state

        assert piece.not_carrying_anything()
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
# 2a. Load as much stuff as you want (look at everything in your current square that's carryable by your piece type)
# 2b. Move to an adjacent hex
# 2bi. Update the new and old hexes for the piece being moved as well as each piece being carried.
# 2biii. Mark the piece as having moved this turn.
# 2c. Drop all your stuff


@attr.s(frozen=True, slots=True)
class MoveOnePiece(a.Choice):
    @classmethod
    def new(cls):
        return cls('Move one piece')

    def choose(self, agent, game_state):
        # Here we don't let someone pick a piece if it happens to be a worker that was dropped into
        # enemy territory this turn. That would get around the [moved_this_turn] check, so we explicitly
        # check to see that we're not starting in enemy territory. There would be no legal way for a mech
        # or character to start in enemy territory anyway.
        current_player = sc.get_current_player(game_state)
        movable_pieces = [piece for piece in sc.movable_pieces(game_state, current_player)
                          if sc.controller(game_state, game_state.board.get_space(piece.board_coords))
                          is current_player.faction_name()]
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Choosing a piece from {"; ".join([str(piece) for piece in movable_pieces])}')
        return agent.choose_piece(game_state, movable_pieces)

    def do(self, game_state, piece):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Chosen: {piece}')
        piece_key = piece.key()
        for _ in range(sc.get_current_player(game_state).base_move_for_piece_type(piece.typ) - 1):
            game_state = sc.push_action(game_state, a.Optional.new(LoadAndMovePiece.new(piece_key)))
        return sc.push_action(game_state, LoadAndMovePiece.new(piece_key))


class Move(a.StateChange):
    _maybe_combat = MaybeCombat.new()
    _move_one_piece = MoveOnePiece.new()
    _optional_move = a.Optional.new(_move_one_piece)

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
    return a.Boolean.new(_move, _gain)
