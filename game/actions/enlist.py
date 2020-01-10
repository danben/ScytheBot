from game.actions.dsl import DiscreteChoice, StateChange
from game.actions.base import BottomAction, BottomActionType
from game.types import Benefit, ResourceType


class Enlist(BottomAction):
    def __init__(self, maxcost, mincost, payoff):
        enlist_benefit = Benefit.COMBAT_CARDS
        action_benefit = ChooseRecruitToEnlist()
        super().__init__(BottomActionType.ENLIST, ResourceType.FOOD, maxcost,
                         mincost, payoff, enlist_benefit, action_benefit)

    def can_legally_receive_action_benefit(self, game_state):
        return game_state.current_player.can_enlist()


class ChooseRecruitToEnlist(DiscreteChoice):
    def choices(self, game_state):
        return [ChooseEnlistReward(bottom_action)
                for bottom_action in game_state.current_player.unenlisted_bottom_actions()]


class ChooseEnlistReward(DiscreteChoice):
    def __init__(self, bottom_action):
        super().__init__()
        self._bottom_action = bottom_action

    def choices(self, game_state):
        return [CommitEnlist(self._bottom_action, enlist_reward)
                for enlist_reward in game_state.current_player.available_enlist_rewards()]


class CommitEnlist(StateChange):
    def __init__(self, bottom_action, enlist_reward):
        super().__init__()
        self._bottom_action = bottom_action
        self._enlist_reward = enlist_reward

    def apply(self, game_state):
        self._bottom_action.enlisted = True
        game_state.give_reward_to_player(game_state.current_player, self._enlist_reward, 2)
        game_state.current_player.mark_enlist_benefit(self._enlist_reward)
