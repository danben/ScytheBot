from game.types import FactionName, PieceType, TerrainType

import attr
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
            Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add)

    def add_faction_specific_adjacencies(self, player_adjacencies, board):
        pass

    def add_teleport_adjacencies(self, player_adjacencies, board):
        pass

    def extra_adjacent_spaces(self, piece, board):
        pass

    @staticmethod
    def add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add):
        piece_adjacencies = player_adjacencies[piece_typ]
        for space, adjacent_spaces in piece_adjacencies.items():
            for other_space in board.base_adjacencies[space]:
                if space is not other_space and should_add(space, other_space) and other_space not in adjacent_spaces:
                    adjacent_spaces.append(other_space)

    @staticmethod
    def add_adjacencies_from_anywhere(player_adjacencies, piece_typ, should_add):
        piece_adjacencies = player_adjacencies[piece_typ]
        for space, adjacent_spaces in piece_adjacencies.items():
            for other_space in piece_adjacencies.keys():
                if space is not other_space and should_add(space, other_space) and other_space not in adjacent_spaces:
                    adjacent_spaces.append(other_space)


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
            Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add)

    def add_faction_specific_adjacencies(self, player_adjacencies, board):
        # Workers can swim across rivers.
        def should_add(space, other_space):
            return space.is_blocked_by_river(other_space) and space.terrain_typ is not TerrainType.HOME_BASE
        Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, PieceType.WORKER, should_add)


@attr.s(frozen=True, slots=True)
class Rusviet(Faction):
    @classmethod
    def new(cls):
        return cls(FactionName.RUSVIET, starting_power=3, starting_combat_cards=2,
                   riverwalk_destinations=[TerrainType.FARM, TerrainType.VILLAGE])

    def extra_adjacent_spaces(self, piece, board):
        ret = []
        if piece.board_space.terrain_typ is TerrainType.VILLAGE or piece.board_space is board.factory:
            for other_space in board.base_adjacencies.keys():
                if other_space is not piece.board_space and other_space.terrain_typ is TerrainType.VILLAGE \
                        and other_space.controller() is FactionName.RUSVIET:
                    ret.append(other_space)

        if piece.board_space.terrain_typ is TerrainType.VILLAGE:
            ret.append(board.factory)
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
            Faction.add_adjacencies_from_anywhere(player_adjacencies, piece_typ, should_add)

            # Can now move from regular spaces to lakes
            def should_add(_space, other):
                return other.terrain_typ is TerrainType.LAKE
            Faction.add_adjacencies_from_board_adjacencies(player_adjacencies, board, piece_typ, should_add)


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
                    adjacent_spaces.append(my_home_base)
                for inactive_home_base in board.inactive_home_bases:
                    if inactive_home_base not in adjacent_spaces:
                        adjacent_spaces.append(inactive_home_base)


@attr.s(frozen=True, slots=True)
class Saxony(Faction):
    @classmethod
    def new(cls):
        return cls(FactionName.SAXONY, starting_power=1, starting_combat_cards=4,
                   riverwalk_destinations=[TerrainType.FOREST, TerrainType.MOUNTAIN])

    def extra_adjacent_spaces(self, piece, board):
        def is_tunnel_or_my_mountain(space):
            return (space.terrain_typ is TerrainType.MOUNTAIN and space.controller() is FactionName.SAXONY)\
                   or piece.board_space.has_tunnel(FactionName.SAXONY)
        ret = []
        if is_tunnel_or_my_mountain(piece.board_space):
            for space in board.base_adjacencies.keys():
                if space is not piece.board_space and is_tunnel_or_my_mountain(space):
                    ret.append(space)
        return ret


def choose(num):
    assert num == 2
    ret = [Rusviet.new(), Saxony.new()]
    np.random.shuffle(ret)
    return ret
