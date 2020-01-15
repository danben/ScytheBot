from game.actions import Bolster, Build, Deploy, Enlist, Produce, Trade, Upgrade
from game.actions.movegain import MoveGain

from game.types import PlayerMatName

import logging
import numpy as np

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
                  [(Bolster(), Upgrade(maxcost=3, mincost=2, payoff=3)),
                   (Produce(), Deploy(maxcost=3, mincost=1, payoff=2)),
                   (MoveGain(), Build(maxcost=3, mincost=2, payoff=1)),
                   (Trade(), Enlist(maxcost=4, mincost=2, payoff=0))],
                  PlayerMatName.ENGINEERING:
                  [(Produce(), Upgrade(maxcost=3, mincost=2, payoff=2)),
                   (Trade(), Deploy(maxcost=4, mincost=2, payoff=0)),
                   (Bolster(), Build(maxcost=3, mincost=1, payoff=3)),
                   (MoveGain(), Enlist(maxcost=3, mincost=2, payoff=1))],
                  PlayerMatName.PATRIOTIC:
                  [(MoveGain(), Upgrade(maxcost=2, mincost=2, payoff=1)),
                   (Bolster(), Deploy(maxcost=4, mincost=1, payoff=3)),
                   (Trade(), Build(maxcost=4, mincost=2, payoff=0)),
                   (Produce(), Enlist(maxcost=3, mincost=2, payoff=2))],
                  PlayerMatName.MECHANICAL:
                  [(Trade(), Upgrade(maxcost=3, mincost=2, payoff=0)),
                   (Bolster(), Deploy(maxcost=3, mincost=1, payoff=2)),
                   (MoveGain(), Build(maxcost=3, mincost=2, payoff=2)),
                   (Produce(), Enlist(maxcost=4, mincost=2, payoff=2))],
                  PlayerMatName.AGRICULTURAL:
                  [(MoveGain(), Upgrade(maxcost=2, mincost=2, payoff=1)),
                   (Trade(), Deploy(maxcost=4, mincost=2, payoff=0)),
                   (Produce(), Build(maxcost=4, mincost=2, payoff=2)),
                   (Bolster(), Enlist(maxcost=3, mincost=1, payoff=3))]}


class PlayerMat:
    def __init__(self, name):
        self._starting_popularity = _starting_popularity[name]
        self._starting_money = _starting_money[name]
        self.action_spaces = _action_spaces[name]
        self.last_action_spot_taken = None
        self.name = name

    def name(self):
        return self.name

    def starting_popularity(self):
        return self._starting_popularity

    def starting_money(self):
        return self._starting_money

    def move_pawn_to(self, i):
        self.last_action_spot_taken = i
        logging.debug(f'Space chosen: {self.action_spaces[i]!r}')

    @staticmethod
    def choose(num):
        return np.random.choice([pmn for pmn in PlayerMatName], num, replace=False)

    def remove_meeples_from_produce_space(self, amt):
        for space in self.action_spaces:
            top = space[0]
            if isinstance(top, Produce):

                top.meeples_produced += amt
                return
        assert False
