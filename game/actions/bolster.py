import game.actions.action as a
import game.state_change as sc
from game.types import Benefit, TopActionType

import attr


@attr.s(frozen=True, slots=True)
class GainPower(a.StateChange):
    @classmethod
    def new(cls):
        return cls('Gain power')

    def do(self, game_state):
        current_player = sc.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.BOLSTER]
        power = 3 if top_action_cubes_and_structure.cubes_upgraded[0] else 2
        return sc.give_reward_to_player(game_state, current_player, Benefit.POWER, power)


@attr.s(frozen=True, slots=True)
class GainCombatCards(a.StateChange):
    @classmethod
    def new(cls):
        return cls('Gain combat cards')

    def do(self, game_state):
        current_player = sc.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.BOLSTER]
        cards = 2 if top_action_cubes_and_structure.cubes_upgraded[1] else 1
        return sc.give_reward_to_player(game_state, sc.get_current_player(game_state), Benefit.COMBAT_CARDS, cards)


@attr.s(frozen=True, slots=True)
class BolsterIfPaid(a.StateChange):
    _power_vs_cards = a.Boolean.new(GainPower.new(), GainCombatCards.new())

    @classmethod
    def new(cls):
        return cls('Bolster')

    def do(self, game_state):
        if sc.get_current_player(game_state).structure_is_built(TopActionType.BOLSTER):
            game_state = sc.push_action(game_state, a.ReceiveBenefit.new(Benefit.POPULARITY, 1))

        return sc.push_action(game_state, BolsterIfPaid._power_vs_cards)


@attr.s(frozen=True, slots=True)
class Bolster(a.MaybePayCost):
    _if_paid = BolsterIfPaid.new()

    @classmethod
    def new(cls):
        return cls('Bolster', Bolster._if_paid)

    def cost(self, game_state):
        return a.Cost.new(coins=1)


def action():
    return Bolster.new()
