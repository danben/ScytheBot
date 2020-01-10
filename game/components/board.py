from game import constants
from game.types import FactionName, StructureType, TerrainType
from collections import defaultdict

# Each pair of coordinate pairs represents two hexes that are separated by a river.
ALL_RIVERS = {((0, 3), (1, 3)), ((0, 3), (0, 4)), ((0, 4), (1, 3)), ((0, 5), (0, 6)), ((0, 5), (1, 5)),
              ((1, 1), (2, 1)), ((1, 3), (1, 4)), ((1, 4), (1, 5)), ((1, 4), (2, 5)), ((1, 5), (2, 6)),
              ((1, 6), (2, 6)), ((2, 1), (2, 2)), ((2, 2), (3, 1)), ((2, 5), (2, 6)), ((2, 5), (3, 5)),
              ((3, 0), (4, 0)), ((3, 0), (4, 1)), ((3, 1), (4, 1)), ((3, 1), (4, 2)), ((3, 4), (3, 5)),
              ((4, 0), (5, 0)), ((4, 1), (5, 0)), ((4, 1), (5, 1)), ((4, 2), (5, 1)), ((5, 1), (5, 2)),
              ((5, 2), (6, 3)), ((5, 3), (6, 3)), ((5, 3), (6, 4)), ((5, 4), (6, 4)), ((6, 4), (6, 5))}


''' Adjacency should be a function of piece and board space. Adjacencies should be precomputed on launch
    or when they change. We can always start with adjacency based on hexes that touch (except where blocked
    by rivers) and tunnels. Adjacency structure should be owned by the player, not the board. '''


class BoardSpace:
    def __init__(self, terrain_typ, has_encounter=False, has_tunnel=False):
        self.terrain_typ = terrain_typ
        self.characters = set()
        self.mechs = set()
        self.workers = set()
        self._resources = defaultdict(int)
        self.has_encounter = has_encounter
        self.encounter_used = False
        self._has_tunnel = has_tunnel
        self.structure = None
        self.produced_this_turn = False

    def combat_factions(self):
        factions = set()
        for character in self.characters:
            factions.add(character.faction_name)
        for mech in self.mechs:
            factions.add(mech.faction_name)
        if len(factions) > 1:
            assert len(factions) == 2
            return list(factions)
        return None

    def contains_no_enemy_plastic(self, faction_name):
        for c in self.characters:
            if c.faction_name is not faction_name:
                return False

        for m in self.mechs:
            if m.faction_name is not faction_name:
                return False

        return True

    def controller(self):
        candidates = set()
        for character in self.characters:
            if not character.moved_into_enemy_territory_this_turn:
                candidates.add(character.faction_name)

        for mech in self.mechs:
            if not mech.moved_into_enemy_territory_this_turn:
                candidates.add(mech.faction_name)

        if len(candidates) > 1:
            assert False

        if len(candidates) == 1:
            return candidates.pop()

        for worker in self.workers:
            candidates.add(worker.faction_name)

        if len(candidates) > 1:
            assert False

        if len(candidates) == 1:
            return candidates.pop()

        if self.structure:
            return self.structure.faction_name

        return None

    def num_combat_cards(self, faction):
        ret = 0
        for c in self.characters:
            if c.faction_name is faction:
                ret += 1
        for m in self.mechs:
            if m.faction_name is faction:
                ret += 1
        if faction is FactionName.RUSVIET:
            for w in self.workers:
                if w.faction_name is faction:
                    return ret + 1
        return ret

    def has_tunnel(self, faction_name=None):
        return self.has_tunnel or \
               (faction_name and self.structure and self.structure.structure_typ() is StructureType.MINE
                and self.structure.faction_name is faction_name)

    def has_structure(self):
        return self.structure is not None

    def has_resource(self, resource_typ):
        return self._resources[resource_typ]

    def add_resources(self, resource_typ, amt=1):
        self._resources[resource_typ] += amt

    def amount_of(self, resource_typ):
        return self._resources[resource_typ]

    def remove_resources(self, resource_typ, amt=1):
        assert self._resources[resource_typ] >= amt
        self._resources[resource_typ] -= amt

    def is_home_base(self):
        return self.terrain_typ is TerrainType.HOME_BASE

    def set_structure(self, structure):
        assert self.structure is None
        self.structure = structure

    def add_piece(self, piece):
        if piece.is_character():
            self.characters.add(piece)
        elif piece.is_mech():
            self.mechs.add(piece)
        elif piece.is_worker():
            self.workers.add(piece)

        raise TypeError("add_piece should only be called with a character, worker or mech")

    def remove_piece(self, piece):
        if piece.is_character():
            assert piece in self.characters
            self.characters.remove(piece)
        elif piece.is_mech():
            assert piece in self.mechs
            self.mechs.remove(piece)
        elif piece.is_worker():
            assert piece in self.workers
            self.workers.remove(piece)

        raise TypeError("add_piece should only be called with a character, worker or mech")

    def all_pieces(self, faction):
        ret = []
        for character in self.characters:
            if character.faction_name is faction:
                ret.append(character)
        for mech in self.mechs:
            if mech.faction_name is faction:
                ret.append(mech)
        for worker in self.workers:
            if worker.faction_name is faction:
                ret.append(worker)


def _mountain(has_encounter=False, has_tunnel=False):
    return BoardSpace(TerrainType.MOUNTAIN, has_encounter, has_tunnel)


def _farm(has_encounter=False, has_tunnel=False):
    return BoardSpace(TerrainType.FARM, has_encounter, has_tunnel)


def _village(has_encounter=False, has_tunnel=False):
    return BoardSpace(TerrainType.VILLAGE, has_encounter, has_tunnel)


def _tundra(has_encounter=False, has_tunnel=False):
    return BoardSpace(TerrainType.TUNDRA, has_encounter, has_tunnel)


def _forest(has_encounter=False, has_tunnel=False):
    return BoardSpace(TerrainType.FOREST, has_encounter, has_tunnel)


def _lake():
    return BoardSpace(TerrainType.LAKE)


def _factory():
    return BoardSpace(TerrainType.FACTORY)


class HomeBase(BoardSpace):
    def __init__(self, is_active):
        super().__init__(TerrainType.HOME_BASE)
        self.is_active = is_active


def _home_base(is_active):
    return HomeBase(is_active)


THE_FACTORY = _factory()

_board_spaces = [
    [None, _mountain(), _farm(), _village(has_encounter=True), _forest(), _tundra(), _village()],
    [_lake(), _tundra(has_encounter=True), _lake(), _tundra(has_tunnel=True), _mountain(has_encounter=True), _farm(),
     _farm(has_encounter=True)],
    [None, _forest(), _mountain(has_tunnel=True), _forest(), _lake(), _forest(has_tunnel=True), _village()],
    [_farm(), _village(), _lake(), THE_FACTORY, _mountain(), _tundra(has_encounter=True), _mountain()],
    [_forest(has_encounter=True), _forest(), _farm(has_tunnel=True), _tundra(), _lake(), _village(has_tunnel=True),
     _lake()],
    [_mountain(), _village(has_encounter=True), _village(has_encounter=True), _tundra(has_tunnel=True), _forest(),
     _mountain(has_encounter=True), _tundra()],
    [None, _tundra(), _lake(), _farm(), _mountain(has_encounter=True), _village(), _farm()],
    [None, None, None, _village(), None, None, None]
]

tunnel_spaces = [space for r in _board_spaces for space in r if space.has_tunnel()]

lake_spaces = [space for r in _board_spaces for space in r if space.terrain_typ is TerrainType.LAKE]

encounter_spaces = [space for r in _board_spaces for space in r if space.has_encounter]


def on_the_board(row, col):
    return 0 <= row < constants.BOARD_ROWS and 0 <= col < constants.BOARD_COLS


def _board_adjacencies(row, col):
    if row % 2 == 0:
        return [(row, col+1), (row, col-1), (row-1, col), (row-1, col-1), (row+1, col), (row+1, col-1)]
    else:
        return [(row, col+1), (row, col-1), (row-1, col), (row-1, col+1), (row+1, col), (row+1, col+1)]


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


class Board:
    def __init__(self, active_factions):
        self.all_spaces_except_home_bases = _board_spaces
        self.factory = THE_FACTORY
        self.home_bases = {FactionName.SAXONY: _home_base(FactionName.SAXONY in active_factions),
                           FactionName.RUSVIET: _home_base(FactionName.RUSVIET in active_factions),
                           FactionName.POLANIA: _home_base(FactionName.POLANIA in active_factions),
                           FactionName.NORDIC: _home_base(FactionName.NORDIC in active_factions),
                           FactionName.CRIMEA: _home_base(FactionName.CRIMEA in active_factions)}
        self.inactive_home_bases = [home_base for home_base in self.home_bases.values() if not home_base.is_active]
        self.base_adjacencies = {}
        for r, row in enumerate(_board_spaces):
            for c, space in enumerate(row):
                adjacent_spaces = []
                for (other_r, other_c) in _board_adjacencies(r, c):
                    other_space = _board_spaces[other_r][other_c] if _on_the_board(other_r, other_c) else None
                    if other_space:
                        adjacent_spaces.append(other_space)
                    if space.has_tunnel():
                        for tunnel_space in tunnel_spaces:
                            if space is not tunnel_space:
                                adjacent_spaces.append(tunnel_space)
                self.base_adjacencies[space] = adjacent_spaces
        for faction_name, home_base in self.home_bases.items():
            adjacent_spaces = map(lambda x: _board_spaces[x[0]][x[1]], _home_base_adjacencies[faction_name])
            self.base_adjacencies[home_base] = adjacent_spaces

        def to_space_pair(coord_pair):
            space1 = _board_spaces[coord_pair[0][0]][coord_pair[0][1]]
            space2 = _board_spaces[coord_pair[1][0]][coord_pair[1][1]]
            return space1, space2

        self._blocked_by_rivers = set(map(to_space_pair, list(ALL_RIVERS)))

        def is_blocked_by_river(from_space, to_space):
            return (from_space, to_space) in self._blocked_by_rivers \
                   or (to_space, from_space) in self._blocked_by_rivers \
                   or (from_space is self.home_bases[FactionName.RUSVIET]
                       and to_space.terrain_type() is TerrainType.FARM)

        self.adjacencies_accounting_for_rivers_and_lakes = {}
        for space, all_adjacent_spaces in self.base_adjacencies.items():
            adjacent_spaces = [other_space for other_space in all_adjacent_spaces
                               if not (is_blocked_by_river(space, other_space)
                                       or other_space.terrain_typ() is TerrainType.LAKE)]
            self.adjacencies_accounting_for_rivers_and_lakes[space] = adjacent_spaces

        for home_base in self.home_bases.values():
            assert len(self.adjacencies_accounting_for_rivers_and_lakes[home_base]) == 2

    def home_base(self, faction_name):
        return self.home_bases[faction_name]

    @staticmethod
    def move_piece(piece, to_space):
        piece.board_space.remove_piece(piece)
        to_space.add_piece(piece)
        piece.board_space = to_space
