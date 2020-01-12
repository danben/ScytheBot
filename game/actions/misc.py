from game.actions.base import *
from game.types import ResourceType


class ReceiveBenefit(StateChange):
    def __init__(self, typ, amt=1):
        super().__init__()
        self._typ = typ
        self._amt = amt

    def apply(self, game_state):
        game_state.give_reward_to_player(game_state.current_player, self._typ, self._amt)

    @staticmethod
    def optional(typ, amt):
        return Optional(ReceiveBenefit(typ, amt))


class ReceiveResources(StateChange):
    def __init__(self, typ, amt, space, is_produce=False):
        super().__init__()
        self._typ = typ
        self._amt = amt
        self._space = space
        self._is_produce = is_produce

    def apply(self, game_state):
        logging.debug(f'Receive {self._amt} {self._typ!r} on space {self._space!r}')
        self._space.add_resources(self._typ, self._amt)
        if self._is_produce:
            game_state.spaces_produced_this_turn.add(self._space)
            self._space.produced_this_turn = True


class ReceiveWorkers(StateChange):
    def __init__(self, amt, space):
        super().__init__()
        self._amt = amt
        self._space = space

    def apply(self, game_state):
        logging.debug(f'Receive {self._amt} workers on space {self._space!r}')
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

    def __repr__(self):
        strings = []
        strings.append(f'{self.power} power; ' if self.power else '')
        strings.append(f'{self.popularity} popularity; ' if self.popularity else '')
        strings.append(f'{self.combat_cards} combat cards; ' if self.combat_cards else '')
        strings.append(f'{self.coins} coins; ' if self.coins else '')
        for resource_typ in ResourceType:
            strings.append(f'{self.resource_cost[resource_typ]} {resource_typ!r}; '
                           if self.resource_cost[resource_typ] else '')
        return ''.join(strings)

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
