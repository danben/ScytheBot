import game.constants as constants
import game.state_change as sc
from game.types import FactionName, PieceType, TerrainType

import attr
import logging
import numpy as np


@attr.s(frozen=True, slots=True)
class Faction:
    name = attr.ib()
    starting_power = attr.ib()
    starting_combat_cards = attr.ib()
    riverwalk_destinations = attr.ib()

    def add_riverwalk_adjacencies(self, player_adjacencies, board):
        # If two hexes on the board are physically adjacent but not yet effectively adjacent,
        # this could only be because one is a lake or because they're separated by a river.
        def should_add(space, other_space):
            return space.terrain_typ is not TerrainType.LAKE \
                   and other_space.terrain_typ in self.riverwalk_destinations
        for piece_typ in [PieceType.CHARACTER, PieceType.MECH]:
            player_adjacencies = \
                Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add)
        return player_adjacencies

    def add_faction_specific_adjacencies(self, player_adjacencies, board):
        return player_adjacencies

    def add_teleport_adjacencies(self, player_adjacencies, board):
        return player_adjacencies

    def extra_adjacent_space_coords(self, piece, game_state):
        return []

    @staticmethod
    def add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add):
        logging.debug('Adding adjacencies from board adjacencies')
        piece_adjacencies = player_adjacencies[piece_typ]
        for coords, adjacent_coords in piece_adjacencies.items():
            for other_coords in board.base_adjacencies[coords]:
                if coords != other_coords and other_coords not in adjacent_coords:
                    space = board.get_space(coords)
                    other_space = board.get_space(other_coords)
                    if should_add(space, other_space):
                        adjacent_coords = adjacent_coords.cons(other_coords)
            piece_adjacencies = piece_adjacencies.set(coords, adjacent_coords)
        player_adjacencies = player_adjacencies.set(piece_typ, piece_adjacencies)
        return player_adjacencies

    @staticmethod
    def add_adjacencies_from_anywhere(player_adjacencies, piece_typ, should_add):
        piece_adjacencies = player_adjacencies[piece_typ]
        for space, adjacent_spaces in piece_adjacencies.items():
            for other_space in piece_adjacencies.keys():
                if space is not other_space and should_add(space, other_space) and other_space not in adjacent_spaces:
                    adjacent_spaces = adjacent_spaces.cons(other_space)
            piece_adjacencies = piece_adjacencies.set(space, adjacent_spaces)
        player_adjacencies = player_adjacencies.set(piece_typ, piece_adjacencies)
        return player_adjacencies


@attr.s(frozen=True, slots=True)
class Nordic(Faction):
    @classmethod
    def new(cls):
        return cls(FactionName.NORDIC, starting_power=4, starting_combat_cards=1,
                   riverwalk_destinations=[TerrainType.FOREST, TerrainType.MOUNTAIN])

    def add_teleport_adjacencies(self, player_adjacencies, board):
        # Can move to/from lakes. Lakes already are considered effectively adjacent to everything around them.
        def should_add(_space, other_space):
            return other_space.terrain_typ is TerrainType.LAKE
        for piece_typ in [PieceType.CHARACTER, PieceType.MECH]:
            player_adjacencies = \
                Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add)
        return player_adjacencies

    def add_faction_specific_adjacencies(self, player_adjacencies, board):
        # Workers can swim across rivers.
        def should_add(space, other_space):
            return space.is_blocked_by_river(other_space) and space.terrain_typ is not TerrainType.HOME_BASE
        return Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, PieceType.WORKER, should_add)


@attr.s(frozen=True, slots=True)
class Rusviet(Faction):
    @classmethod
    def new(cls):
        return cls(FactionName.RUSVIET, starting_power=3, starting_combat_cards=2,
                   riverwalk_destinations=[TerrainType.FARM, TerrainType.VILLAGE])

    def extra_adjacent_space_coords(self, piece, game_state):
        ret = []
        board = game_state.board
        piece_space = board.get_space(piece.board_coords)
        if piece_space.terrain_typ is TerrainType.VILLAGE or piece_space.terrain_typ is TerrainType.FACTORY:
            for other_coords in board.base_adjacencies.keys():
                other_space = board.get_space(other_coords)
                if other_space is not piece_space and other_space.terrain_typ is TerrainType.VILLAGE \
                        and sc.controller(game_state, other_space) is FactionName.RUSVIET:
                    ret.append(other_coords)

        if piece_space.terrain_typ is TerrainType.VILLAGE:
            ret.append(constants.FACTORY_COORDS)
        return ret


@attr.s(frozen=True, slots=True)
class Polania(Faction):
    @classmethod
    def new(cls):
        return cls(FactionName.POLANIA, starting_power=2, starting_combat_cards=3,
                   riverwalk_destinations=[TerrainType.VILLAGE, TerrainType.MOUNTAIN])

    def add_teleport_adjacencies(self, player_adjacencies, board):
        for piece_typ in [PieceType.CHARACTER, PieceType.MECH]:
            # All lakes are adjacent to each other
            def should_add(space, other_space):
                return space.terrain_typ is TerrainType.LAKE and other_space.terrain_typ is TerrainType.LAKE
            player_adjacencies = Faction.add_adjacencies_from_anywhere(player_adjacencies, piece_typ, should_add)

            # Can now move from regular spaces to lakes
            def should_add(_space, other):
                return other.terrain_typ is TerrainType.LAKE
            player_adjacencies = \
                Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add)
        return player_adjacencies


@attr.s(frozen=True, slots=True)
class Crimea(Faction):
    spent_combat_card_as_resource_this_turn = attr.ib(default=False)

    @classmethod
    def new(cls):
        return cls(FactionName.CRIMEA, starting_power=5, starting_combat_cards=5,
                   riverwalk_destinations=[TerrainType.FARM, TerrainType.TUNDRA])

    def add_teleport_adjacencies(self, player_adjacencies, board):
        my_home_base = board.home_bases[FactionName.CRIMEA]
        for piece_typ in [PieceType.CHARACTER, PieceType.MECH]:
            player_adjacencies_for_piece_typ = player_adjacencies[piece_typ]
            # Move from any territory or home base to either an inactive home base or my own
            for space, adjacent_spaces in player_adjacencies_for_piece_typ.items():
                if my_home_base not in adjacent_spaces:
                    adjacent_spaces = adjacent_spaces.cons(my_home_base)
                for inactive_home_base in board.inactive_home_bases:
                    if inactive_home_base not in adjacent_spaces:
                        adjacent_spaces = adjacent_spaces.cons(inactive_home_base)
                player_adjacencies_for_piece_typ = player_adjacencies_for_piece_typ.set(space, adjacent_spaces)
            player_adjacencies = player_adjacencies.set(piece_typ, player_adjacencies_for_piece_typ)
        return player_adjacencies


@attr.s(frozen=True, slots=True)
class Saxony(Faction):
    @classmethod
    def new(cls):
        return cls(FactionName.SAXONY, starting_power=1, starting_combat_cards=4,
                   riverwalk_destinations=[TerrainType.FOREST, TerrainType.MOUNTAIN])

    def extra_adjacent_space_coords(self, piece, game_state):
        def is_tunnel_or_my_mountain(space):
            return (space.terrain_typ is TerrainType.MOUNTAIN
                    and sc.controller(game_state, space) is FactionName.SAXONY) or space.has_tunnel(FactionName.SAXONY)
        ret = []
        board = game_state.board
        piece_space = board.get_space(piece.board_coords)
        if is_tunnel_or_my_mountain(piece_space):
            for coords in board.base_adjacencies.keys():
                if coords != piece.board_coords:
                    space = board.get_space(coords)
                    if is_tunnel_or_my_mountain(space):
                        ret.append(coords)
        return ret


def choose(num):
    assert num == 2
    ret = [Rusviet.new(), Saxony.new()]
    np.random.shuffle(ret)
    return ret
