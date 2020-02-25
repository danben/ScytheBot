from game.types import PieceType, ResourceType

import attr
from pyrsistent import pmap, pset

_no_resources = pmap({r: 0 for r in ResourceType})


@attr.s(frozen=True, slots=True)
class PieceKey:
    piece_typ = attr.ib()
    faction_name = attr.ib()
    id = attr.ib()


@attr.s(frozen=True, slots=True)
class _Piece:
    board_coords = attr.ib()
    typ = attr.ib()
    faction_name = attr.ib()
    id = attr.ib()

    def __str__(self):
        return f'{self.typ} {self.board_coords}'

    def key(self):
        return PieceKey(self.typ, self.faction_name, self.id)

    def is_plastic(self):
        return self.typ is PieceType.CHARACTER or self.typ is PieceType.MECH

    def is_mech(self):
        return self.typ is PieceType.MECH

    def is_character(self):
        return self.typ is PieceType.CHARACTER

    def is_structure(self):
        return self.typ is PieceType.STRUCTURE

    def is_worker(self):
        return self.typ is PieceType.WORKER


@attr.s(frozen=True, slots=True)
class _MovablePiece(_Piece):
    moved_this_turn = attr.ib(default=False)
    moved_into_enemy_territory_this_turn = attr.ib(default=False)
    carrying_resources = attr.ib(default=_no_resources)

    def drop_everything(self):
        return attr.evolve(self, carrying_resources=_no_resources)

    def not_carrying_anything(self):
        d = self.carrying_resources
        return not (d[ResourceType.WOOD] or d[ResourceType.OIL] or d[ResourceType.FOOD] or d[ResourceType.METAL])


@attr.s(frozen=True, slots=True)
class Structure(_Piece):
    structure_typ = attr.ib()
    typ = attr.ib(default=PieceType.STRUCTURE)

    @classmethod
    def of_typ(cls, board_coords, faction_name, structure_typ):
        return cls(board_coords, faction_name, structure_typ.value, structure_typ)


@attr.s(frozen=True, slots=True)
class Mech(_MovablePiece):
    carrying_worker_keys = attr.ib(factory=pset)
    typ = attr.ib(default=PieceType.MECH)

    def not_carrying_anything(self):
        return super().not_carrying_anything() and not self.carrying_worker_keys

    def drop_everything(self):
        return attr.evolve(self.drop_everything(), carrying_worker_keys=pset())


@attr.s(frozen=True, slots=True)
class Character(_MovablePiece):
    typ = attr.ib(default=PieceType.CHARACTER)
    id = attr.ib(default=0)


@attr.s(frozen=True, slots=True)
class Worker(_MovablePiece):
    typ = attr.ib(default=PieceType.WORKER)


def character_key(faction_name):
    return PieceKey(PieceType.CHARACTER, faction_name, 0)


def worker_key(faction_name, id):
    return PieceKey(PieceType.WORKER, faction_name, id)


def mech_key(faction_name, mech_typ):
    return PieceKey(PieceType.MECH, faction_name, mech_typ.value)


def structure_key(faction_name, structure_typ):
    return PieceKey(PieceType.MECH, faction_name, structure_typ.value)
