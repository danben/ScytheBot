from game.actions.action import Boolean, Cost, MaybePayCost, ReceiveBenefit, TopAction, StateChange
from game.types import Benefit, StructureType


class Bolster(MaybePayCost):
    def __init__(self):
        self.if_paid = BolsterIfPaid()
        super().__init__('Bolster', self.if_paid)

    def cost(self):
        return Cost(coins=1)

    def top_action(self):
        return self.if_paid.top_action


class BolsterIfPaid(StateChange):
    def __init__(self):
        super().__init__()
        self.top_action = TopAction('Bolster', num_cubes=2, structure_typ=StructureType.MONUMENT)
        self.choice = PowerVsCards(self.top_action)

    def do(self, game_state):
        if self.top_action.structure_is_built:
            game_state.action_stack.append(ReceiveBenefit(Benefit.POPULARITY))

        game_state.action_stack.append(self.choice)


class PowerVsCards(Boolean):
    def __init__(self, top_action):
        super().__init__(GainPower(top_action), GainCombatCards(top_action))


class GainPower(StateChange):
    def __init__(self, top_action):
        super().__init__('Gain power')
        self.top_action = top_action

    def do(self, game_state):
        power = 3 if self.top_action.cubes_upgraded[0] else 2
        game_state.give_reward_to_player(game_state.current_player, Benefit.POWER, power)


class GainCombatCards(StateChange):
    def __init__(self, top_action):
        super().__init__('Gain combat cards')
        self.top_action = top_action

    def do(self, game_state):
        cards = 2 if self.top_action.cubes_upgraded[1] else 1
        game_state.give_reward_to_player(game_state.current_player, Benefit.COMBAT_CARDS, cards)
