from game.actions.base import *
from game.actions.misc import Cost, ReceiveResources, ReceiveWorkers
from game.types import StructureType, TerrainType


class Produce(TopAction):
    def __init__(self):
        super().__init__(num_cubes=1, structure_typ=StructureType.MILL)
        self._meeples_produced = 0

    def cost(self, game_state):
        power = 1 if self._meeples_produced < 1 else 0
        popularity = 1 if self._meeples_produced < 3 else 0
        coins = 1 if self._meeples_produced < 5 else 0
        return Cost(power=power, popularity=popularity, coins=coins)

    def apply(self, game_state):
        produce_actions = [OnOneHex(), OnOneHex()]
        if self._cubes_upgraded[0]:
            produce_actions.append(OnOneHex())
        if self._structure_is_built:
            produce_actions.append(OnMillHex())
        game_state.action_stack.append(Sequence.of_list_all_optional(produce_actions))


class OnOneHex(Action):
    @staticmethod
    def choices(game_state):
        ret = []
        for space in game_state.current_player.produceable_spaces():
            if space.terrain_type is TerrainType.VILLAGE:
                ret.append(ReceiveWorkers(space.num_workers(), space))
            else:
                ret.append(ReceiveResources(space.terrain_type.resource_type(), space.num_workers(), space,
                                            is_produce=True))
        return ret


class OnMillHex(Action):
    def apply(self, game_state):
        space = game_state.current_player.mill_space()
        assert space is not None
        if not space.produced_this_turn:
            game_state.spaces_produced_this_turn.add(space)
            space.produced_this_turn = True
            typ = space.terrain_type
            amt = space.num_workers()
            if typ is TerrainType.VILLAGE:
                ReceiveWorkers(amt, space).apply(game_state)
            else:
                ReceiveResources(typ, amt, space, is_produce=True).apply(game_state)
