from game.actions import Bolster, Build, Deploy, enlist, Produce, Trade, upgrade
from game.actions.movegain import MoveGain

from game.types import BottomActionType, PlayerMatName, StructureType, TopActionType

import attr
import logging
import numpy as np

from pyrsistent import pmap, pvector

_starting_popularity = {PlayerMatName.INDUSTRIAL: 2,
                        PlayerMatName.ENGINEERING: 2,
                        PlayerMatName.PATRIOTIC: 2,
                        PlayerMatName.MECHANICAL: 3,
                        PlayerMatName.AGRICULTURAL: 4}

_starting_money = {PlayerMatName.INDUSTRIAL: 4,
                   PlayerMatName.ENGINEERING: 5,
                   PlayerMatName.PATRIOTIC: 6,
                   PlayerMatName.MECHANICAL: 6,
                   PlayerMatName.AGRICULTURAL: 7}

_action_spaces = {PlayerMatName.INDUSTRIAL:
                  pvector([(Bolster(), upgrade(maxcost=3, mincost=2, payoff=3)),
                           (Produce(), Deploy(maxcost=3, mincost=1, payoff=2)),
                           (MoveGain(), Build(maxcost=3, mincost=2, payoff=1)),
                           (Trade(), enlist(maxcost=4, mincost=2, payoff=0))]),
                  PlayerMatName.ENGINEERING:
                  pvector([(Produce(), upgrade(maxcost=3, mincost=2, payoff=2)),
                           (Trade(), Deploy(maxcost=4, mincost=2, payoff=0)),
                           (Bolster(), Build(maxcost=3, mincost=1, payoff=3)),
                           (MoveGain(), enlist(maxcost=3, mincost=2, payoff=1))]),
                  PlayerMatName.PATRIOTIC:
                  pvector([(MoveGain(), upgrade(maxcost=2, mincost=2, payoff=1)),
                           (Bolster(), Deploy(maxcost=4, mincost=1, payoff=3)),
                           (Trade(), Build(maxcost=4, mincost=2, payoff=0)),
                           (Produce(), enlist(maxcost=3, mincost=2, payoff=2))]),
                  PlayerMatName.MECHANICAL:
                  pvector([(Trade(), upgrade(maxcost=3, mincost=2, payoff=0)),
                           (Bolster(), Deploy(maxcost=3, mincost=1, payoff=2)),
                           (MoveGain(), Build(maxcost=3, mincost=2, payoff=2)),
                           (Produce(), enlist(maxcost=4, mincost=2, payoff=2))]),
                  PlayerMatName.AGRICULTURAL:
                  pvector([(MoveGain(), upgrade(maxcost=2, mincost=2, payoff=1)),
                           (Trade(), Deploy(maxcost=4, mincost=2, payoff=0)),
                           (Produce(), Build(maxcost=4, mincost=2, payoff=2)),
                           (Bolster(), enlist(maxcost=3, mincost=1, payoff=3))])}


@attr.s(frozen=True, slots=True)
class TopActionCubesAndStructure:
    structure_typ = attr.ib()
    cubes_upgraded = attr.ib()
    structure_is_built = attr.ib(default=False)

    @classmethod
    def new(cls, structure_typ, num_cubes):
        return cls(structure_typ, cubes_upgraded=pvector([False] * num_cubes))

    def build_structure(self):
        assert not self.structure_is_built
        return attr.evolve(self, structure_is_built=True)

    def remove_upgrade_cube(self, spot):
        assert spot < len(self.cubes_upgraded) and not self.cubes_upgraded[spot]
        return attr.evolve(self, cubes_upgraded=self.cubes_upgraded.set(spot, True))

    def upgradeable_cubes(self):
        return [i for i in range(len(self.cubes_upgraded)) if not self.cubes_upgraded[i]]


@attr.s(frozen=True, slots=True)
class PlayerMat:
    name = attr.ib()
    starting_popularity = attr.ib()
    starting_money = attr.ib()
    action_spaces = attr.ib()
    top_action_cubes_and_structures_by_top_action_typ = attr.ib()
    has_enlisted_by_bottom_action_typ = attr.ib()
    bottom_spaces_by_bottom_action_typ = attr.ib()
    last_action_spot_taken = attr.ib(default=None)

    @classmethod
    def from_player_mat_name(cls, name):
        top_action_cubes_and_structures_by_top_action_typ = \
            pmap({TopActionType.TRADE: TopActionCubesAndStructure.new(StructureType.ARMORY, num_cubes=1),
                  TopActionType.BOLSTER: TopActionCubesAndStructure.new(StructureType.MONUMENT, num_cubes=2),
                  TopActionType.MOVEGAIN: TopActionCubesAndStructure.new(StructureType.MINE, num_cubes=2),
                  TopActionType.PRODUCE: TopActionCubesAndStructure.new(StructureType.MILL, num_cubes=1)})
        has_enlisted_by_bottom_action_typ = pmap({b: False for b in BottomActionType})
        action_spaces = _action_spaces[name]
        bottom_spaces_by_bottom_action_typ = pmap({a[1].bottom_action_typ: i for i, a in enumerate(action_spaces)})

        return cls(name, _starting_popularity[name], _starting_money[name], action_spaces,
                   top_action_cubes_and_structures_by_top_action_typ, has_enlisted_by_bottom_action_typ,
                   bottom_spaces_by_bottom_action_typ)

    def move_pawn_to(self, i):
        logging.debug(f'Space chosen: {self.action_spaces[i]!r}')
        return attr.evolve(self, last_action_spot_taken=i)

    @staticmethod
    def choose(num):
        return np.random.choice([pmn for pmn in PlayerMatName], num, replace=False)

    def cube_spaces_not_fully_upgraded(self):
        return [(t, i) for (t, s) in self.top_action_cubes_and_structures_by_top_action_typ.items()
                for i in s.upgradeable_cubes()]

    def remove_upgrade_cube(self, top_action_typ, spot):
        top_action_cubes_and_structure = self.top_action_cubes_and_structures_by_top_action_typ[top_action_typ]
        top_action_cubes_and_structure = top_action_cubes_and_structure.remove_upgrade_cube(spot)
        x = self.top_action_cubes_and_structures_by_top_action_typ.set(top_action_typ, top_action_cubes_and_structure)
        return attr.evolve(self, top_action_cubes_and_structures_by_top_action_typ=x)

    def enlist(self, bottom_action_typ):
        assert not self.has_enlisted_by_bottom_action_typ[bottom_action_typ]
        has_enlisted_by_bottom_action_typ = self.has_enlisted_by_bottom_action_typ.set(bottom_action_typ, True)
        return attr.evolve(self, has_enlisted_by_bottom_action_typ=has_enlisted_by_bottom_action_typ)

    def upgrade_bottom_action(self, bottom_action_typ):
        action_space_index = self.bottom_spaces_by_bottom_action_typ[bottom_action_typ]
        action_pair = self.action_spaces[action_space_index]
        top_action = action_pair[0]
        bottom_action = action_pair[1].upgrade()
        action_pair = top_action, bottom_action
        action_spaces = self.action_spaces.set(action_space_index, action_pair)
        return attr.evolve(self, action_spaces=action_spaces)