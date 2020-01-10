from game.actions.base import *
from game.types import ResourceType


class ReceiveBenefit(Action):
    def __init__(self, typ, amt=1):
        super().__init__()
        self._typ = typ
        self._amt = amt

    def apply(self, game_state):
        game_state.give_reward_to_player(game_state.current_player, self._typ, self._amt)

    @staticmethod
    def optional(typ, amt):
        return Optional(ReceiveBenefit(typ, amt))


class ReceiveResources(Action):
    def __init__(self, typ, amt, space, is_produce=False):
        super().__init__()
        self._typ = typ
        self._amt = amt
        self._space = space
        self._is_produce = is_produce

    def apply(self, game_state):
        game_state.board.place_resources_at(self._typ, self._amt, self._space)
        if self._is_produce:
            game_state.spaces_produced_on_this_turn.add(self._space)
            self._space.produced_this_turn = True


class ReceiveWorkers(Action):
    def __init__(self, amt, space):
        super().__init__()
        self._amt = amt
        self._space = space

    def apply(self, game_state):
        for _ in range(self._amt):
            game_state.current_player.add_worker(self._space)
        game_state.spaces_produced_this_turn.add(self._space)
        self._space.produced_this_turn = True


class Cost:
    def __init__(self, power=0, popularity=0, coins=0, oil=0, metal=0, wood=0, food=0, combat_cards=0):
        self.power = power
        self.popularity = popularity
        self.combat_cards = combat_cards
        self.coins = coins
        self.resource_cost = {ResourceType.METAL: metal, ResourceType.OIL: oil, ResourceType.WOOD: wood,
                              ResourceType.FOOD: food}

    @staticmethod
    def of_resource_type(resource_typ, amt):
        if resource_typ is ResourceType.METAL:
            return Cost(metal=amt)
        elif resource_typ is ResourceType.FOOD:
            return Cost(food=amt)
        elif resource_typ is ResourceType.OIL:
            return Cost(oil=amt)
        elif resource_typ is ResourceType.WOOD:
            return Cost(wood=amt)
        assert False

    def reduce_by_1(self, resource_typ):
        assert self.resource_cost[resource_typ]
        self.resource_cost[resource_typ] -= 1
