from game.actions.base import *
from game.actions.dsl import *
from game.actions.misc import Cost, ReceiveBenefit, ReceiveResources
from game.types import Benefit, StructureType, ALL_RESOURCE_TYPES


class Trade(TopAction):
    def __init__(self):
        super().__init__(num_cubes=1, structure_typ=StructureType.ARMORY)

    def apply(self, game_state):
        if self._structure_is_built:
            game_state.action_stack.append(ReceiveBenefit(Benefit.POWER))
        popularity_gain = 2 if self._cubes_upgraded[0] else 1
        game_state.action_stack.append(Trade.ResourcesOrPopularity(popularity_gain=popularity_gain))

    class ResourcesOrPopularity(Action):
        def __init__(self, popularity_gain):
            super().__init__()
            self._popularity_gain = popularity_gain

        def choices(self, _game_state):
            return [Sequence.of_list_all_optional([GetTradeResource()] * 2),
                    ReceiveBenefit(Benefit.POPULARITY, amt=self._popularity_gain)]

    def cost(self, game_state):
        return Cost(coins=1)


class GetTradeResource(DiscreteChoice):
    def __init__(self):
        super().__init__()

    def choices(self, game_state):
        return [ReceiveResources(typ=resource, amt=1, space=board_space)
                for resource in ALL_RESOURCE_TYPES
                for board_space in game_state.next_player.spaces_with_workers()]
