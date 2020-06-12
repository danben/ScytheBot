from game import constants
from game.types import FactionName, PieceType, ResourceType, StructureType, TerrainType

import attr
import logging
from pyrsistent import plist, pmap, pset, pvector

# Each pair of coordinate pairs represents two hexes that are separated by a river.
ALL_RIVERS = {((0, 3), (1, 3)), ((0, 3), (0, 4)), ((0, 4), (1, 3)), ((0, 5), (0, 6)), ((0, 5), (1, 5)),
              ((1, 1), (2, 1)), ((1, 3), (1, 4)), ((1, 4), (1, 5)), ((1, 4), (2, 5)), ((1, 5), (2, 6)),
              ((1, 6), (2, 6)), ((2, 1), (2, 2)), ((2, 2), (3, 1)), ((2, 5), (2, 6)), ((2, 5), (3, 5)),
              ((3, 0), (4, 0)), ((3, 0), (4, 1)), ((3, 1), (4, 1)), ((3, 1), (4, 2)), ((3, 4), (3, 5)),
              ((3, 5), (4, 5)), ((4, 0), (5, 0)), ((4, 1), (5, 0)), ((4, 1), (5, 1)), ((4, 2), (5, 1)),
              ((5, 1), (5, 2)), ((5, 2), (6, 3)), ((5, 3), (6, 3)), ((5, 3), (6, 4)), ((5, 4), (6, 4)),
              ((6, 4), (6, 5)), ((-1, FactionName.RUSVIET.value), (1, 6))}


def blocked_by_river(from_coords, to_coords):
    return (from_coords, to_coords) in ALL_RIVERS or (to_coords, from_coords) in ALL_RIVERS


''' Adjacency should be a function of piece and board space. Adjacencies should be precomputed on launch
    or when they change. We can always start with adjacency based on hexes that touch (except where blocked
    by rivers) and tunnels. Adjacency structure should be owned by the player, not the board. '''


@attr.s(slots=True, frozen=True)
class BoardSpace:
    coords = attr.ib()
    terrain_typ = attr.ib()
    has_encounter = attr.ib()
    _has_tunnel = attr.ib()
    character_keys = attr.ib(default=pset())
    mech_keys = attr.ib(default=pset())
    worker_keys = attr.ib(default=pset())
    resources = attr.ib(default=pmap({r: 0 for r in ResourceType}))
    structure_key = attr.ib(default=None)
    encounter_used = attr.ib(default=False)
    produced_this_turn = attr.ib(default=False)

    def __str__(self):
        if self.coords:
            return f'{self.terrain_typ} : {self.coords}'
        else:
            return f'{self.terrain_typ}'

    # def to_string(self):
    #     return f'{self!r}, controlled by {self.controller()!r}\nResources: {self.resources}' \
    #            f'\nPieces: {self.all_pieces()}\n'

    def combat_factions(self):
        factions = set()
        for character_key in self.character_keys:
            factions.add(character_key.faction_name)
        for mech_key in self.mech_keys:
            factions.add(mech_key.faction_name)
        if len(factions) > 1:
            assert len(factions) == 2
            return plist(factions)
        return None

    def contains_no_enemy_plastic(self, faction_name):
        for c in self.character_keys:
            if c.faction_name is not faction_name:
                return False

        for m in self.mech_keys:
            if m.faction_name is not faction_name:
                return False

        return True

    def contains_no_enemy_workers(self, faction_name):
        for w in self.worker_keys:
            if w.faction_name is not faction_name:
                return False
        return True

    def controlled_by_structure(self):
        return (not self.mech_keys) and (not self.worker_keys) and (not self.character_keys) and self.structure_key

    def num_combat_cards(self, faction):
        ret = 0
        for c in self.character_keys:
            if c.faction_name is faction:
                ret += 1
        for m in self.mech_keys:
            if m.faction_name is faction:
                ret += 1
        if faction is FactionName.RUSVIET:
            for w in self.worker_keys:
                if w.faction_name is faction:
                    return ret + 1
        return ret

    def has_tunnel(self, faction_name=None):
        return self._has_tunnel or \
               (faction_name and self.structure_key and self.structure_key.id == StructureType.MINE.value
                and self.structure_key.faction_name is faction_name)

    def has_structure(self):
        return self.structure_key is not None

    def has_resource(self, resource_typ):
        return self.resources[resource_typ]

    def add_resources(self, resource_typ, amt=1):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'{amt} {resource_typ} added to {self}')
        new_resources = self.resources[resource_typ] + amt
        return attr.evolve(self, resources=self.resources.set(resource_typ, new_resources))

    def amount_of(self, resource_typ):
        return self.resources[resource_typ]

    def remove_resources(self, resource_typ, amt=1):
        assert self.resources[resource_typ] >= amt
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'{amt} {resource_typ} removed from {self}')
        new_resources = self.resources[resource_typ] - amt
        return attr.evolve(self, resources=self.resources.set(resource_typ, new_resources))

    def is_home_base(self):
        return self.terrain_typ is TerrainType.HOME_BASE

    def add_piece(self, key):
        if key.piece_typ is PieceType.CHARACTER:
            return attr.evolve(self, character_keys=self.character_keys.add(key))
        elif key.piece_typ is PieceType.MECH:
            return attr.evolve(self, mech_keys=self.mech_keys.add(key))
        elif key.piece_typ is PieceType.WORKER:
            return attr.evolve(self, worker_keys=self.worker_keys.add(key))
        else:
            raise TypeError("add_piece should only be called with a character, worker or mech")

    def remove_piece(self, key):
        if key.piece_typ is PieceType.CHARACTER:
            assert key in self.character_keys
            return attr.evolve(self, character_keys=self.character_keys.remove(key))
        elif key.piece_typ is PieceType.MECH:
            assert key in self.mech_keys
            return attr.evolve(self, mech_keys=self.mech_keys.remove(key))
        elif key.piece_typ is PieceType.WORKER:
            assert key in self.worker_keys
            return attr.evolve(self, worker_keys=self.worker_keys.remove(key))
        else:
            raise TypeError("remove_piece should only be called with a character, worker or mech")

    def all_piece_keys(self, faction=None):
        ret = []
        for key_set in [self.character_keys, self.mech_keys, self.worker_keys]:
            for key in key_set:
                if not faction or (key.faction_name is faction):
                    ret.append(key)
        return plist(ret)


def _mountain(coords, has_encounter=False, has_tunnel=False):
    return BoardSpace(coords, TerrainType.MOUNTAIN, has_encounter, has_tunnel)


def _farm(coords, has_encounter=False, has_tunnel=False):
    return BoardSpace(coords, TerrainType.FARM, has_encounter, has_tunnel)


def _village(coords, has_encounter=False, has_tunnel=False):
    return BoardSpace(coords, TerrainType.VILLAGE, has_encounter, has_tunnel)


def _tundra(coords, has_encounter=False, has_tunnel=False):
    return BoardSpace(coords, TerrainType.TUNDRA, has_encounter, has_tunnel)


def _forest(coords, has_encounter=False, has_tunnel=False):
    return BoardSpace(coords, TerrainType.FOREST, has_encounter, has_tunnel)


def _lake(coords):
    return BoardSpace(coords, TerrainType.LAKE, False, False)


def _factory(coords):
    return BoardSpace(coords, TerrainType.FACTORY, False, False)


@attr.s(frozen=True, slots=True)
class HomeBase(BoardSpace):
    is_active = attr.ib(default=False)


def _home_base(faction_name, is_active):
    return HomeBase((-1, faction_name.value), TerrainType.HOME_BASE, False, False, is_active=is_active)


# TODO: Get rid of the explicit coordinate pairs
_board_spaces = [
    [None, _mountain((0, 1)), _farm((0, 2)), _village((0, 3), has_encounter=True), _forest((0, 4)), _tundra((0, 5)),
     _village((0, 6))],
    [_lake((1, 0)), _tundra((1, 1), has_encounter=True), _lake((1, 2)), _tundra((1, 3), has_tunnel=True),
     _mountain((1, 4), has_encounter=True), _farm((1, 5)), _farm((1, 6), has_encounter=True)],
    [None, _forest((2, 1)), _mountain((2, 2), has_tunnel=True), _forest((2, 3)), _lake((2, 4)),
     _forest((2, 5), has_tunnel=True), _village((2, 6))],
    [_farm((3, 0)), _village((3, 1)), _lake((3, 2)), _factory(constants.FACTORY_COORDS), _mountain((3, 4)),
     _tundra((3, 5), has_encounter=True), _mountain((3, 6))],
    [_forest((4, 0), has_encounter=True), _forest((4, 1)), _farm((4, 2), has_tunnel=True), _tundra((4, 3)),
     _lake((4, 4)), _village((4, 5), has_tunnel=True), _lake((4, 6))],
    [_mountain((5, 0)), _village((5, 1), has_encounter=True), _village((5, 2), has_encounter=True),
     _tundra((5, 3), has_tunnel=True), _forest((5, 4)), _mountain((5, 5), has_encounter=True), _tundra((5, 6))],
    [None, _tundra((6, 1)), _lake((6, 2)), _farm((6, 3)), _mountain((6, 4), has_encounter=True), _village((6, 5)),
     _farm((6, 6))],
    [None, None, None, _village((7, 3)), None, None, None]]


def on_the_board (row, col):
    return 0 <= row < constants.BOARD_ROWS and 0 <= col < constants.BOARD_COLS


def _board_adjacencies(row, col):
    if row % 2 == 0:
        adj = [(row, col+1), (row, col-1), (row-1, col), (row-1, col-1), (row+1, col), (row+1, col-1)]
    else:
        adj = [(row, col+1), (row, col-1), (row-1, col), (row-1, col+1), (row+1, col), (row+1, col+1)]
    return list(filter(lambda x: on_the_board(*x), adj))


def move_down_and_right(row, col):
    if row % 2 == 0:
        return row+1, col
    else:
        return row+1, col+1


def move_up_and_right(row, col):
    if row % 2 == 0:
        return row - 1, col
    else:
        return row - 1, col + 1


_home_base_adjacencies = {FactionName.SAXONY: [(5, 0), (6, 1)],
                          FactionName.RUSVIET: [(1, 6), (2, 6), (3, 6)],
                          FactionName.POLANIA: [(1, 0), (2, 1), (3, 0)],
                          FactionName.NORDIC: [(0, 4), (0, 5)],
                          FactionName.CRIMEA: [(6, 2), (6, 3), (7, 3)]}


@attr.s(frozen=True, slots=True)
class Board:
    home_bases = attr.ib()
    board_spaces_by_coords = attr.ib()
    base_adjacencies = attr.ib()
    adjacencies_accounting_for_rivers_and_lakes = attr.ib()

    @classmethod
    def from_active_factions(cls, active_factions):
        home_bases = {FactionName.SAXONY: _home_base(FactionName.SAXONY, FactionName.SAXONY in active_factions),
                      FactionName.RUSVIET: _home_base(FactionName.RUSVIET, FactionName.RUSVIET in active_factions),
                      FactionName.POLANIA: _home_base(FactionName.POLANIA, FactionName.POLANIA in active_factions),
                      FactionName.NORDIC: _home_base(FactionName.NORDIC, FactionName.NORDIC in active_factions),
                      FactionName.CRIMEA: _home_base(FactionName.CRIMEA, FactionName.CRIMEA in active_factions)}
        board_spaces_by_coords = {space.coords: space for space in home_bases.values()}

        # inactive_home_bases = [home_base for home_base in self.home_bases.values() if not home_base.is_active]
        base_adjacencies = {}
        tunnel_spaces = [space for r in _board_spaces for space in r if space and space.has_tunnel()]
        for r, row in enumerate(_board_spaces):
            for c, space in enumerate(row):
                if space:
                    board_spaces_by_coords[space.coords] = space
                    adjacent_spaces = []
                    for (other_r, other_c) in _board_adjacencies(r, c):
                        other_space = _board_spaces[other_r][other_c]
                        if other_space:
                            adjacent_spaces.append(other_space.coords)
                    if space.has_tunnel():
                        for tunnel_space in tunnel_spaces:
                            if space is not tunnel_space:
                                adjacent_spaces.append(tunnel_space.coords)
                    base_adjacencies[space.coords] = adjacent_spaces

        for faction_name, home_base in home_bases.items():
            adjacent_spaces = _home_base_adjacencies[faction_name]
            base_adjacencies[home_base.coords] = adjacent_spaces

        adjacencies_accounting_for_rivers_and_lakes = {}
        for from_space_coords, all_adjacent_space_coords in base_adjacencies.items():
            adjacent_space_coords = [other for other in all_adjacent_space_coords
                                     if not (blocked_by_river(from_space_coords, other)
                                             or board_spaces_by_coords[other].terrain_typ is TerrainType.LAKE)]
            adjacencies_accounting_for_rivers_and_lakes[from_space_coords] = pvector(adjacent_space_coords)

        for space in board_spaces_by_coords.values():
            if space.terrain_typ is TerrainType.LAKE:
                assert space.coords in base_adjacencies
            elif space.terrain_typ is TerrainType.HOME_BASE:
                assert len(adjacencies_accounting_for_rivers_and_lakes[space.coords]) == 2

        home_bases = pmap({faction_name: home_base.coords for faction_name, home_base in home_bases.items()})
        return cls(home_bases, pmap(board_spaces_by_coords), pmap(base_adjacencies),
                   pmap(adjacencies_accounting_for_rivers_and_lakes))

    def __str__(self):
        s = []
        for space in self.board_spaces_by_coords.values():
            if space.all_piece_keys():
                s.append(space.to_string())
        return '; '.join(s)

    def invariant(self, game_state):
        for space in self.board_spaces_by_coords.values():
            worker_factions = set()
            for piece_key in space.all_piece_keys():
                piece_coords = game_state.pieces_by_key[piece_key].board_coords
                if piece_coords != space.coords:
                    raise Exception(f'{piece_key} on {space} but thinks it is on {piece_coords}')
                if piece_key.piece_typ is PieceType.WORKER:
                    worker_factions.add(piece_key.faction_name)
            if len(worker_factions) > 1:
                print(f'Multiple players\' workers on single spot:')
                print(f'{space!r}')
                assert False

    def get_space(self, coords):
        assert coords
        return self.board_spaces_by_coords[coords]

    def set_space(self, space):
        return attr.evolve(self, board_spaces_by_coords=self.board_spaces_by_coords.set(space.coords, space))

    def add_piece(self, key, coords):
        space = self.get_space(coords).add_piece(key)
        return attr.evolve(self, board_spaces_by_coords=self.board_spaces_by_coords.set(coords, space))

    def is_blocked_by_river(self, from_space, to_space):
        return blocked_by_river(from_space.coords, to_space.coords) \
               or (from_space.coords == self.board_spaces_by_coords(-1, FactionName.RUSVIET.value)
                   and to_space.terrain_typ is TerrainType.FARM)

    def home_base(self, faction_name):
        return self.board_spaces_by_coords[(-1, faction_name.value)]
