import game.state_change as sc
from game.actions import Boolean, Choice, Cost, MaybePayCost, ReceiveBenefit, StateChange
from game.types import Benefit, ResourceType, TopActionType

import attr


@attr.s(frozen=True, slots=True)
class ChooseBoardSpaceForResource(Choice):
    resource_typ = attr.ib()

    @classmethod
    def new(cls, chosen):
        return cls(f'Choose board space to receive {chosen}', chosen)

    def choices(self, game_state):
        current_player = sc.get_current_player(game_state)
        return list(sc.board_coords_with_workers(game_state, current_player))

    def choose(self, agent, game_state):
        return agent.choose_board_coords(game_state, self.choices(game_state))

    def do(self, game_state, chosen):
        space = game_state.board.get_space(chosen).add_resources(self.resource_typ, 1)
        return attr.evolve(game_state, board=game_state.board.set_space(space))


@attr.s(frozen=True, slots=True)
class ChooseResourceType(Choice):
    @classmethod
    def new(cls):
        return cls('Choose resource type')

    def choices(self, game_state):
        return [x for x in ResourceType]

    def choose(self, agent, game_state):
        return agent.choose_resource_typ(game_state, self.choices(game_state))

    def do(self, game_state, chosen):
        return sc.push_action(game_state, ChooseBoardSpaceForResource.new(chosen))


@attr.s(frozen=True, slots=True)
class GainResources(StateChange):
    _choose_resource_typ = ChooseResourceType.new()

    @classmethod
    def new(cls):
        return cls('Gain resources for trade action')

    def do(self, game_state):
        game_state = sc.push_action(game_state, GainResources._choose_resource_typ)
        return sc.push_action(game_state, GainResources._choose_resource_typ)


@attr.s(frozen=True, slots=True)
class GainPopularity(StateChange):
    @classmethod
    def new(cls):
        return cls('Gain popularity for Trade action')

    def do(self, game_state):
        current_player = sc.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.TRADE]
        popularity = 2 if top_action_cubes_and_structure.cubes_upgraded[0] else 1
        return sc.give_reward_to_player(game_state, current_player, Benefit.POPULARITY, popularity)


@attr.s(frozen=True, slots=True)
class TradeIfPaid(StateChange):
    gain_popularity = GainPopularity.new()
    resources_vs_popularity = Boolean.new(GainResources.new(), gain_popularity)

    @classmethod
    def new(cls):
        return cls('Attempting Trade action')

    def do(self, game_state):
        if sc.get_current_player(game_state).structure_is_built(TopActionType.TRADE):
            game_state = sc.push_action(game_state, ReceiveBenefit.new(Benefit.POWER, amt=1))
        if sc.board_coords_with_workers(game_state, sc.get_current_player(game_state)):
            return sc.push_action(game_state, TradeIfPaid.resources_vs_popularity)
        else:
            return sc.push_action(game_state, TradeIfPaid.gain_popularity)


@attr.s(frozen=True, slots=True)
class Trade(MaybePayCost):
    _if_paid = TradeIfPaid.new()

    @classmethod
    def new(cls):
        return cls('Trade', Trade._if_paid)

    def cost(self, game_state):
        return Cost.new(coins=1)


def action():
    return Trade.new()
