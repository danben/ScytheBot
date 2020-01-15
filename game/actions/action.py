from game.exceptions import GameOver
from game.types import FactionName, ResourceType

from abc import ABC, abstractmethod
import logging


class Action(ABC):
    def __init__(self):
        super().__init__()


class StateChange(Action):
    def __init__(self, name=None):
        super().__init__()
        self.name = name

    @abstractmethod
    def do(self, game_state):
        pass

    def apply(self, game_state):
        if self.name:
            logging.debug(self.name)
        self.do(game_state)


class Choice(Action):
    def __init__(self, name=None):
        super().__init__()
        self.name = name

    def __repr__(self):
        return self.name

    @abstractmethod
    def choose(self, agent, game_state):
        pass

    @abstractmethod
    def do(self, game_state, chosen):
        pass

    def apply(self, game_state, chosen):
        if self.name:
            logging.debug(f'{self.name}')
        self.do(game_state, chosen)


class Boolean(Choice):
    def __init__(self, action1, action2):
        super().__init__(f'Choosing between {action1.name} and {action2.name}')
        self.action1 = action1
        self.action2 = action2

    def choose(self, agent, game_state):
        return agent.choose_boolean(game_state)

    def do(self, game_state, chosen):
        if chosen:
            game_state.action_stack.append(self.action1)
        else:
            game_state.action_stack.append(self.action2)


class Optional(Choice):
    def __init__(self, action):
        self.name = f'Optional: {action.name}' if action.name else None
        super().__init__(self.name)
        self.action = action

    def choose(self, agent, game_state):
        return agent.choose_boolean(game_state)

    def do(self, game_state, chosen):
        if chosen:
            logging.debug('Lets do it!')
            game_state.action_stack.append(self.action)
        else:
            logging.debug('Decided not to')


class EndGame(StateChange):
    def __init__(self):
        super().__init__('End game')

    def do(self, game_state):
        raise GameOver()


class MaybePayCost(Choice):
    def __init__(self, name, if_paid):
        super().__init__(name)
        self.if_paid = if_paid

    @abstractmethod
    def cost(self):
        pass

    def choose(self, agent, game_state):
        if self.cost().is_free():
            return True
        return agent.choose_boolean(game_state)

    def do(self, game_state, chosen):
        if chosen:
            # We decided to pay, but because of Crimea we might need to figure out how we're going to pay
            game_state.action_stack.append(self.if_paid)
            cost = self.cost()
            if game_state.current_player.faction_name() is not FactionName.CRIMEA or cost.uses_no_resources \
                    or game_state.current_player.has_no_resources():
                # Just pay the cost and move on
                if not cost.is_free():
                    game_state.charge_player(game_state.current_player, cost)
            else:
                game_state.choice_stack.append(CrimeaMaybeChooseResource(cost))
        else:
            logging.debug('Skipping; decided not to pay')


class SpendAResource(Choice):
    def __init__(self, resource_typ):
        super().__init__(f'Choose {resource_typ!r} to spend')
        self.resource_typ = resource_typ

    def choose(self, agent, game_state):
        return agent.choose_board_space(game_state,
                                        game_state.current_player.controlled_spaces_with_resource(
                                            self.resource_typ))

    def do(self, game_state, chosen):
        chosen.remove_resources(self.resource_typ)


class CrimeaMaybeChooseResource(Choice):
    def __init__(self, cost):
        super().__init__('Crimea can choose to substitute a combat card for a resource')
        self.cost = cost

    def choose(self, agent, game_state):
        return agent.choose_optional_resource_type_for_cost_substitution(game_state, self.cost)

    def do(self, game_state, chosen):
        if chosen:
            self.cost.reduce_by_1(chosen)
            game_state.charge_player(game_state.current_player, self.cost)


class TopAction:
    def __init__(self, name, num_cubes, structure_typ):
        self.name = name
        self.structure_is_built = False
        self.structure_typ = structure_typ
        self.cubes_upgraded = [False] * num_cubes

    def structure_typ(self):
        return self.structure_typ

    def structure_is_built(self):
        return self.structure_is_built

    def build_structure(self):
        assert not self.structure_is_built
        self.structure_is_built = True

    def place_upgrade_cube(self, spot):
        logging.debug(f'Placed cube in spot {spot} of {self.name}')
        assert spot < len(self.cubes_upgraded) and not self.cubes_upgraded[spot]
        self.cubes_upgraded[spot] = True

    def upgradeable_cubes(self):
        return [i for i in range(len(self.cubes_upgraded)) if not self.cubes_upgraded[i]]


class Cost:
    def __init__(self, power=0, popularity=0, coins=0, oil=0, metal=0, wood=0, food=0, combat_cards=0):
        self.power = power
        self.popularity = popularity
        self.combat_cards = combat_cards
        self.coins = coins
        self.resource_cost = {ResourceType.METAL: metal, ResourceType.OIL: oil, ResourceType.WOOD: wood,
                              ResourceType.FOOD: food}

    def __repr__(self):
        strings = [f'{self.power} power; ' if self.power else '',
                   f'{self.popularity} popularity; ' if self.popularity else '',
                   f'{self.combat_cards} combat cards; ' if self.combat_cards else '',
                   f'{self.coins} coins; ' if self.coins else '']
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

    def uses_no_resources(self):
        return sum(self.resource_cost.values()) == 0

    def is_free(self):
        return self.uses_no_resources() and self.popularity == 0 and self.combat_cards == 0 \
            and self.popularity == 0 and self.coins == 0


class BottomAction(MaybePayCost):
    def __init__(self, bottom_action_typ, resource_type, maxcost, mincost, coins_payoff, enlist_benefit,
                 action_benefit):
        if_paid = BottomActionIfPaid(bottom_action_typ, coins_payoff, enlist_benefit, action_benefit)
        super().__init__(bottom_action_typ.__repr__(), if_paid)
        self.current_cost = maxcost
        self.mincost = mincost
        self.resource_type = resource_type
        self.if_paid = if_paid
        self.bottom_action_typ = bottom_action_typ

    def __repr__(self):
        return self.bottom_action_typ.__repr__()

    def cost(self):
        return Cost.of_resource_type(self.resource_type, self.current_cost)

    def is_upgradeable(self):
        return self.current_cost > self.mincost

    def remove_upgrade_cube(self):
        assert self.current_cost > self.mincost
        self.current_cost -= 1

    def enlist(self):
        self.if_paid.enlisted = True

    def has_enlisted(self):
        return self.if_paid.enlisted


class BottomActionIfPaid(StateChange):
    def __init__(self, bottom_action_typ, coins_payoff, enlist_benefit, action_benefit):
        super().__init__()
        self.coins_payoff = coins_payoff
        self.enlist_benefit = enlist_benefit
        self.action_benefit = action_benefit
        self.enlisted = False
        self.bottom_action_typ = bottom_action_typ

    def choose(self, agent, game_state):
        pass

    def do(self, game_state):
        logging.debug(f'Attempting bottom action: {self.bottom_action_typ!r}')
        current_player = game_state.current_player
        current_player.add_coins(self.coins_payoff)

        game_state.action_stack.append(GiveEnlistBenefitsToNeighbors(self.bottom_action_typ, self.enlist_benefit))
        game_over = False
        try:
            if self.enlisted:
                game_state.give_reward_to_player(current_player, self.enlist_benefit, 1)
        except GameOver:
            game_over = True
        finally:
            if game_over:
                game_state.action_stack.append(EndGame())
            if current_player.can_legally_receive_action_benefit(self.bottom_action_typ):
                game_state.action_stack.append(Optional(self.action_benefit))
            else:
                logging.debug('Cannot perform action {self._action_benefit.name} so skipping')


class GiveEnlistBenefitsToNeighbors(StateChange):
    def __init__(self, bottom_action_typ, enlist_benefit):
        super().__init__()
        self.bottom_action_typ = bottom_action_typ
        self.enlist_benefit = enlist_benefit

    def do(self, game_state):
        left_player = game_state.get_left_player()
        if left_player.has_enlisted(self.bottom_action_typ):
            game_state.give_reward_to_player(left_player, self.enlist_benefit, 1)

        right_player = game_state.get_right_player()
        if left_player is not right_player and right_player.has_enlisted(self.bottom_action_typ):
            game_state.give_reward_to_player(right_player, self.enlist_benefit, 1)


class ReceiveBenefit(StateChange):
    def __init__(self, typ, amt=1):
        super().__init__()
        self._typ = typ
        self._amt = amt

    def do(self, game_state):
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

    def do(self, game_state):
        logging.debug(f'Receive {self._amt} {self._typ!r} on space {self._space!r}')
        self._space.add_resources(self._typ, self._amt)
        if self._is_produce:
            game_state.spaces_produced_this_turn.add(self._space)
            self._space.produced_this_turn = True


class ReceiveWorkers(StateChange):
    def __init__(self, amt, space):
        super().__init__()
        self.amt = amt
        self.space = space

    def do(self, game_state):
        logging.debug(f'Receive {self.amt} workers on space {self.space!r}')
        game_state.current_player.add_workers(self.space, self.amt)
        game_state.current_player.remove_meeples_from_produce_space(self.amt)
        game_state.spaces_produced_this_turn.add(self.space)
        self.space.produced_this_turn = True
