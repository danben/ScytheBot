from game.actions import Boolean, Choice, Cost, MaybePayCost, Optional, ReceiveBenefit, StateChange, TopAction
from game.types import Benefit, StructureType


class Trade(MaybePayCost):
    def __init__(self):
        self.if_paid = TradeIfPaid()
        super().__init__('Trade', self.if_paid)

    def cost(self):
        return Cost(coins=1)

    def top_action(self):
        return self.if_paid.top_action


class TradeIfPaid(StateChange):
    def __init__(self):
        super().__init__()
        self.top_action = TopAction('Trade', num_cubes=1, structure_typ=StructureType.ARMORY)
        self.choice = ResourcesVsPopularity(self.top_action)
        self.no_choice = GainPopularity(self.top_action)

    def do(self, game_state):
        if self.top_action.structure_is_built:
            game_state.action_stack.append(ReceiveBenefit(Benefit.POWER))
        if game_state.current_player.spaces_with_workers():
            game_state.action_stack.append(self.choice)
        else:
            game_state.action_stack.append(self.no_choice)


class ResourcesVsPopularity(Boolean):
    def __init__(self, top_action):
        super().__init__(GainResources(), GainPopularity(top_action))


class GainResources(StateChange):
    def __init__(self):
        super().__init__('Gain resources')
        self.gain_one_resource = ChooseResourceType()

    def do(self, game_state):
        game_state.action_stack.append(Optional(self.gain_one_resource))
        game_state.action_stack.append(self.gain_one_resource)


class ChooseResourceType(Choice):
    def __init__(self):
        super().__init__('Choose resource type')

    def choose(self, agent, game_state):
        return agent.choose_resource_type(game_state)

    def do(self, game_state, chosen):
        game_state.action_stack.append(ChooseBoardSpaceForResource(chosen))


class ChooseBoardSpaceForResource(Choice):
    def __init__(self, resource_typ):
        super().__init__('Choose board space to receive {resource_typ!r}')
        self.resource_typ = resource_typ

    def choose(self, agent, game_state):
        return agent.choose_board_space(game_state, list(game_state.current_player.spaces_with_workers()))

    def do(self, game_state, chosen):
        chosen.add_resources(self.resource_typ, 1)


class GainPopularity(StateChange):
    def __init__(self, top_action):
        super().__init__('Gain popularity')
        self.top_action = top_action

    def do(self, game_state):
        popularity = 2 if self.top_action.cubes_upgraded[0] else 1
        game_state.give_reward_to_player(game_state.current_player, Benefit.POPULARITY, popularity)
