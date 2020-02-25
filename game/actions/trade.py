from game.actions import Boolean, Choice, Cost, MaybePayCost, Optional, ReceiveBenefit, StateChange
from game.game_state import GameState
from game.types import Benefit, TopActionType

import attr


@attr.s(frozen=True, slots=True)
class ChooseBoardSpaceForResource(Choice):
    resource_typ = attr.ib()

    @classmethod
    def new(cls, chosen):
        return cls('Choose board space to receive {chosen}', chosen)

    def choose(self, agent, game_state):
        current_player = GameState.get_current_player(game_state)
        eligible_spaces = GameState.board_coords_with_workers(game_state, current_player)
        return agent.choose_board_space(game_state, eligible_spaces)

    def do(self, game_state, chosen):
        return attr.evolve(game_state, board=game_state.board.set_space(chosen.add_resources(self.resource_typ, 1)))


@attr.s(frozen=True, slots=True)
class ChooseResourceType(Choice):
    @classmethod
    def new(cls):
        return cls('Choose resource type')

    def choose(self, agent, game_state):
        return agent.choose_resource_type(game_state)

    def do(self, game_state, chosen):
        return GameState.push_action(game_state, ChooseBoardSpaceForResource.new(chosen))


@attr.s(frozen=True, slots=True)
class GainResources(StateChange):
    _choose_resource_type = ChooseResourceType.new()
    _choose_resource_type_opt = Optional.new(_choose_resource_type)

    @classmethod
    def new(cls):
        return cls('Gain resources for trade action')

    def do(self, game_state):
        game_state = GameState.push_action(game_state, GainResources._choose_resource_type_opt)
        game_state.action_stack.append(GainResources._choose_resource_type)


@attr.s(frozen=True, slots=True)
class GainPopularity(StateChange):
    @classmethod
    def new(cls):
        return cls('Gain popularity for Trade action')

    def do(self, game_state):
        current_player = GameState.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.TRADE]
        popularity = 2 if top_action_cubes_and_structure.cubes_upgraded[0] else 1
        return GameState.give_reward_to_player(game_state, current_player, Benefit.POPULARITY, popularity)


@attr.s(frozen=True, slots=True)
class TradeIfPaid(StateChange):
    gain_popularity = GainPopularity.new()
    resources_vs_popularity = Boolean.new(GainResources.new(), gain_popularity)

    @classmethod
    def new(cls):
        return cls('Attempting Trade action')

    def do(self, game_state):
        if game_state.get_current_player().structure_is_built(TopActionType.TRADE):
            game_state = game_state.push_action(ReceiveBenefit.new(Benefit.POWER, amt=1))
        if GameState.board_coords_with_workers(game_state, game_state.get_current_player()):
            return game_state.push_action(TradeIfPaid.resources_vs_popularity)
        else:
            return game_state.push_action(TradeIfPaid.gain_popularity)


@attr.s(frozen=True, slots=True)
class Trade(MaybePayCost):
    _if_paid = TradeIfPaid.new()

    @classmethod
    def new(cls):
        return cls('Trade', Trade.if_paid)

    def cost(self):
        return Cost.new(coins=1)
