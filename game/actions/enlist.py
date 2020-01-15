from game.actions.action import BottomAction, Choice
from game.types import Benefit, BottomActionType, ResourceType


class ChooseRecruitToEnlist(Choice):
    def __init__(self):
        super().__init__('Choose recruit to enlist')

    def choose(self, agent, game_state):
        return agent.choose_bottom_action(game_state, game_state.current_player.unenlisted_bottom_actions())

    def do(self, game_state, bottom_action_typ):
        game_state.action_stack.append(ChooseEnlistReward(bottom_action_typ))


class Enlist(BottomAction):
    enlist_benefit = Benefit.COMBAT_CARDS
    action_benefit = ChooseRecruitToEnlist()

    def __init__(self, maxcost, mincost, payoff):
        super().__init__(BottomActionType.ENLIST, ResourceType.FOOD, maxcost,
                         mincost, payoff, Enlist.enlist_benefit, Enlist.action_benefit)


class ChooseEnlistReward(Choice):
    def __init__(self, bottom_action):
        super().__init__()
        self.bottom_action = bottom_action

    def choose(self, agent, game_state):
        return agent.choose_enlist_reward(game_state)

    def do(self, game_state, enlist_reward):
        self.bottom_action.enlist()
        game_state.give_reward_to_player(game_state.current_player, enlist_reward, 2)
        game_state.current_player.mark_enlist_benefit(enlist_reward)
