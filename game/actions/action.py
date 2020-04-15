from game.exceptions import GameOver
from game.types import FactionName, ResourceType

import game.state_change as sc

from abc import ABC, abstractmethod
import attr
import logging

from pyrsistent import pmap


@attr.s(frozen=True, slots=True)
class Action(ABC):
    name = attr.ib()

    def __str__(self):
        return self.name


@attr.s(frozen=True, slots=True)
class StateChange(Action, ABC):
    @abstractmethod
    def do(self, game_state):
        pass

    def apply(self, game_state):
        if self.name:
            logging.debug(self.name)
        return self.do(game_state)


@attr.s(frozen=True, slots=True)
class Choice(Action, ABC):
    @abstractmethod
    def choose(self, agent, game_state):
        pass

    @abstractmethod
    def do(self, game_state, chosen):
        pass

    def apply(self, game_state, chosen):
        if self.name:
            logging.debug(f'{self.name}')
        return self.do(game_state, chosen)


@attr.s(frozen=True, slots=True)
class Boolean(Choice):
    action1 = attr.ib()
    action2 = attr.ib()

    @classmethod
    def new(cls, action1, action2):
        return cls(f'Choosing between {action1.name} and {action2.name}', action1, action2)

    def choose(self, agent, game_state):
        return agent.choose_boolean(game_state)

    def do(self, game_state, chosen):
        if chosen:
            return sc.push_action(game_state, self.action1)
        else:
            return sc.push_action(game_state, self.action2)


@attr.s(frozen=True, slots=True)
class Optional(Choice):
    action = attr.ib()

    @classmethod
    def new(cls, action):
        return cls(f'Optional: {action.name}', action)

    def choose(self, agent, game_state):
        return agent.choose_boolean(game_state)

    def do(self, game_state, chosen):
        if chosen:
            logging.debug('Lets do it!')
            return sc.push_action(game_state, self.action)
        else:
            logging.debug('Decided not to')
            return game_state


@attr.s(frozen=True, slots=True)
class EndGame(StateChange):
    @classmethod
    def new(cls):
        return cls('End game')

    def do(self, game_state):
        raise GameOver(None)


@attr.s(frozen=True, slots=True)
class MaybePayCost(Choice, ABC):
    if_paid = attr.ib()

    @abstractmethod
    def cost(self, game_state):
        pass

    def choose(self, agent, game_state):
        if self.cost(game_state).is_free():
            return True
        return agent.choose_boolean(game_state)

    def do(self, game_state, chosen):
        if chosen:
            # We decided to pay, but because of Crimea we might need to figure out how we're going to pay
            game_state = sc.push_action(game_state, self.if_paid)
            cost = self.cost(game_state)
            if sc.get_current_player(game_state).faction_name() is not FactionName.CRIMEA or cost.uses_no_resources \
                    or sc.get_current_player(game_state).has_no_resources():
                # Just pay the cost and move on
                if not cost.is_free():
                    game_state = sc.charge_player(game_state, sc.get_current_player(game_state), cost)
            else:
                game_state = sc.push_action(game_state, CrimeaMaybeChooseResource.new(cost))
        else:
            logging.debug('Skipping; decided not to pay')

        return game_state


@attr.s(frozen=True, slots=True)
class SpendAResource(Choice):
    player_id = attr.ib()
    resource_typ = attr.ib()

    @classmethod
    def new(cls, player_id, resource_typ):
        return cls(f'Choose {resource_typ} to spend', player_id, resource_typ)

    def choose(self, agent, game_state):
        eligible_spaces = sc.controlled_spaces_with_resource(game_state,
                                                             sc.get_player_by_idx(game_state, self.player_id),
                                                             self.resource_typ)
        return agent.choose_board_coords(game_state, list(map(lambda x: x.coords, eligible_spaces)))

    def do(self, game_state, chosen):
        logging.debug(f'1 from {chosen}')
        board = game_state.board
        space = board.get_space(chosen)
        space = space.remove_resources(self.resource_typ)
        board = board.set_space(space)
        return attr.evolve(game_state, board=board)


@attr.s(frozen=True, slots=True)
class CrimeaMaybeChooseResource(Choice):
    cost = attr.ib()

    @classmethod
    def new(cls, cost):
        return cls('Crimea can choose to substitute a combat card for a resource', cost)

    def choose(self, agent, game_state):
        return agent.choose_optional_resource_type_for_cost_substitution(game_state, self.cost)

    def do(self, game_state, chosen):
        if chosen:
            new_cost = self.cost.reduce_by_1(chosen)
            game_state = sc.charge_player(game_state, sc.get_current_player(game_state), new_cost)
            current_player, combat_cards =\
                sc.get_current_player(game_state).discard_lowest_combat_cards(1, game_state.combat_cards)
            game_state = attr.evolve(game_state, combat_cards=combat_cards)
            game_state = sc.set_player(game_state, current_player)
        else:
            game_state = sc.charge_player(game_state, sc.get_current_player(game_state), self.cost)
        return game_state


@attr.s(frozen=True, slots=True)
class TopAction:
    top_action_typ = attr.ib()


@attr.s(frozen=True, slots=True)
class Cost:
    power = attr.ib()
    popularity = attr.ib()
    combat_cards = attr.ib()
    coins = attr.ib()
    resource_cost = attr.ib()

    @classmethod
    def new(cls, power=0, popularity=0, coins=0, oil=0, metal=0, wood=0, food=0, combat_cards=0):
        return cls(power, popularity, combat_cards, coins,
                   pmap({ResourceType.METAL: metal, ResourceType.OIL: oil, ResourceType.WOOD: wood,
                         ResourceType.FOOD: food}))

    def __str__(self):
        strings = [f'{self.power} power; ' if self.power else '',
                   f'{self.popularity} popularity; ' if self.popularity else '',
                   f'{self.combat_cards} combat cards; ' if self.combat_cards else '',
                   f'{self.coins} coins; ' if self.coins else '']
        for resource_typ in ResourceType:
            strings.append(f'{self.resource_cost[resource_typ]} {resource_typ}; '
                           if self.resource_cost[resource_typ] else '')
        return ''.join(strings)

    @staticmethod
    def of_resource_type(resource_typ, amt):
        if resource_typ is ResourceType.METAL:
            return Cost.new(metal=amt)
        elif resource_typ is ResourceType.FOOD:
            return Cost.new(food=amt)
        elif resource_typ is ResourceType.OIL:
            return Cost.new(oil=amt)
        elif resource_typ is ResourceType.WOOD:
            return Cost.new(wood=amt)
        assert False

    def reduce_by_1(self, resource_typ):
        assert self.resource_cost[resource_typ]
        new_amt = self.resource_cost[resource_typ] - 1
        return attr.evolve(self, resource_cost=self.resource_cost.set(resource_typ, new_amt))

    def uses_no_resources(self):
        return not sum(self.resource_cost.values())

    def is_free(self):
        return self.uses_no_resources() and not self.popularity and not self.combat_cards \
            and not self.popularity and not self.coins


@attr.s(frozen=True, slots=True)
class GiveEnlistBenefitsToNeighbors(StateChange):
    bottom_action_typ = attr.ib()
    enlist_benefit = attr.ib()

    @classmethod
    def new(cls, bottom_action_typ, enlist_benefit):
        return cls(f'Give enlist benefits ({enlist_benefit}) to neighbors', bottom_action_typ, enlist_benefit)

    def do(self, game_state):
        left_player = sc.get_left_player(game_state)
        if left_player.has_enlisted(self.bottom_action_typ):
            game_state = sc.give_reward_to_player(game_state, left_player, self.enlist_benefit, 1)

        right_player = sc.get_right_player(game_state)
        if left_player is not right_player and right_player.has_enlisted(self.bottom_action_typ):
            game_state = sc.give_reward_to_player(game_state, right_player, self.enlist_benefit, 1)

        return game_state


@attr.s(frozen=True, slots=True)
class BottomActionIfPaid(StateChange):
    bottom_action_typ = attr.ib()
    coins_payoff = attr.ib()
    enlist_benefit = attr.ib()
    action_benefit = attr.ib()
    enlisted = attr.ib(default=False)

    @classmethod
    def new(cls, bottom_action_typ, coins_payoff, enlist_benefit, action_benefit):
        return cls(f'Attempting bottom action: {bottom_action_typ}', bottom_action_typ, coins_payoff, enlist_benefit,
                   action_benefit)

    def choose(self, agent, game_state):
        pass

    def do(self, game_state):
        current_player = sc.get_current_player(game_state)
        sc.set_player(game_state, current_player.add_coins(self.coins_payoff))

        game_state = sc.push_action(game_state, GiveEnlistBenefitsToNeighbors.new(self.bottom_action_typ,
                                                                                  self.enlist_benefit))
        game_over = False
        try:
            if self.enlisted:
                game_state = sc.give_reward_to_player(game_state, current_player, self.enlist_benefit, 1)
        except GameOver as e:
            game_over = True
            game_state = sc.set_player(game_state, e.player)
        finally:
            if game_over:
                game_state = sc.push_action(game_state, EndGame.new())
            if sc.can_legally_receive_action_benefit(game_state, current_player, self.bottom_action_typ):
                game_state = sc.push_action(game_state, Optional.new(self.action_benefit))
            else:
                logging.debug(f'Cannot receive benefit from action {self.bottom_action_typ} so skipping')
        return game_state


@attr.s(frozen=True, slots=True)
class BottomAction(MaybePayCost):
    current_cost = attr.ib()  # maxcost
    mincost = attr.ib()
    resource_type = attr.ib()
    bottom_action_typ = attr.ib()

    @classmethod
    def new(cls, bottom_action_typ, resource_type, maxcost, mincost, coins_payoff, enlist_benefit,
            action_benefit):
        if_paid = BottomActionIfPaid.new(bottom_action_typ, coins_payoff, enlist_benefit, action_benefit)
        return cls(bottom_action_typ.__str__(), if_paid, maxcost, mincost, resource_type, bottom_action_typ)

    def cost(self, game_state):
        return Cost.of_resource_type(self.resource_type, self.current_cost)

    def is_upgradeable(self):
        return self.current_cost > self.mincost

    def upgrade(self):
        assert self.current_cost > self.mincost
        return attr.evolve(self, current_cost=self.current_cost - 1)

    def enlist(self):
        return attr.evolve(self, if_paid=attr.evolve(self.if_paid, enlisted=True))

    def has_enlisted(self):
        return self.if_paid.enlisted


@attr.s(frozen=True, slots=True)
class ReceiveBenefit(StateChange):
    typ = attr.ib()
    amt = attr.ib()

    @classmethod
    def new(cls, typ, amt):
        return cls('Current player gets {amt} {typ}', typ, amt)

    def do(self, game_state):
        return sc.give_reward_to_player(game_state, sc.get_current_player(game_state), self.typ, self.amt)

    @staticmethod
    def optional(typ, amt):
        return Optional.new(ReceiveBenefit.new(typ, amt))


@attr.s(frozen=True, slots=True)
class ReceiveResources(StateChange):
    typ = attr.ib()
    amt = attr.ib()
    coords = attr.ib()
    is_produce = attr.ib(default=False)

    @classmethod
    def new(cls, typ, amt, coords):
        return cls(f'Receive {amt} {typ} on space {coords}', typ, amt, coords)

    def do(self, game_state):
        game_state = sc.add_resources_to_space(game_state, self.coords, self.typ, self.amt)
        if self.is_produce:
            game_state = attr.evolve(game_state,
                                     spaces_produced_this_turn=game_state.spaces_produced_this_turn.add(self.coords))
        return game_state


@attr.s(frozen=True, slots=True)
class ReceiveWorkers(StateChange):
    amt = attr.ib()
    coords = attr.ib()

    @classmethod
    def new(cls, amt, coords):
        return cls(f'Receive {amt} workers on space {coords}', amt, coords)

    def do(self, game_state):
        game_state = sc.add_workers(game_state, sc.get_current_player(game_state), self.coords, self.amt)
        return attr.evolve(game_state,
                           spaces_produced_this_turn=game_state.spaces_produced_this_turn.add(self.coords))
