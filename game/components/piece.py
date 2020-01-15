from game.types import PieceType, ResourceType
from collections import defaultdict


class Piece:
    def __init__(self, board_space, typ, faction_name):
        self.board_space = board_space
        self.typ = typ
        self.faction_name = faction_name
        self.carrying_resources = defaultdict(int)

    def __repr__(self):
        return self.typ.__repr__()

    def is_plastic(self):
        return self.typ == PieceType.CHARACTER or self.typ == PieceType.MECH

    def is_mech(self):
        return self.typ == PieceType.MECH

    def is_character(self):
        return self.typ == PieceType.CHARACTER

    def is_structure(self):
        return self.typ == PieceType.STRUCTURE

    def is_worker(self):
        return self.typ == PieceType.WORKER

    def typ(self):
        return self.typ

    def drop_everything(self):
        self.carrying_resources = defaultdict(int)

    def not_carrying_anything(self):
        d = self.carrying_resources
        return not (d[ResourceType.WOOD] or d[ResourceType.OIL] or d[ResourceType.FOOD] or d[ResourceType.METAL])


class MovablePiece(Piece):
    def __init__(self, board_space, typ, faction_name):
        super().__init__(board_space, typ, faction_name)
        self.moved_this_turn = False
        self.moved_into_enemy_territory_this_turn = False


class Structure(Piece):
    def __init__(self, board_space, structure_typ, faction_name):
        assert not board_space.has_structure()
        super().__init__(board_space, PieceType.STRUCTURE, faction_name)
        self._structure_typ = structure_typ

    def structure_typ(self):
        return self._structure_typ


class Mech(MovablePiece):
    def __init__(self, board_space, faction_name):
        super().__init__(board_space, PieceType.MECH, faction_name)
        self.carrying_workers = set()

    def not_carrying_anything(self):
        return super().not_carrying_anything() and not self.carrying_workers

    def drop_everything(self):
        super().drop_everything()
        self.carrying_workers.clear()


class Character(MovablePiece):
    def __init__(self, board_space, faction_name):
        super().__init__(board_space, PieceType.CHARACTER, faction_name)


class Worker(MovablePiece):
    def __init__(self, board_space, faction_name):
        super().__init__(board_space, PieceType.WORKER, faction_name)
