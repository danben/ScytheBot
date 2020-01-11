from game.actions.base import *
from game.actions.dsl import *
from game.actions.misc import Cost, ReceiveBenefit
from game.types import Benefit, StructureType

import logging


class Bolster(TopAction):
    def __init__(self):
        super().__init__(num_cubes=2, structure_typ=StructureType.MONUMENT)

    def cost(self, game_state):
        return Cost(coins=1)

    def apply(self, game_state):
        logging.debug("Space chosen: Bolster")
        if self._structure_is_built:
            game_state.action_stack.append(ReceiveBenefit(Benefit.POPULARITY))
        power = 3 if self._cubes_upgraded[0] else 2
        cards = 2 if self._cubes_upgraded[1] else 1
        game_state.action_stack.append(PowerOrCards(power=power, cards=cards))


class PowerOrCards(DiscreteChoice):
    def __init__(self, power, cards):
        super().__init__()
        self._power = power
        self._cards = cards

    def choices(self, game_state):
        return [ReceiveBenefit(Benefit.POWER, amt=self._power), ReceiveBenefit(Benefit.COMBAT_CARDS, amt=self._cards)]
