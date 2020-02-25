from game.actions.action import BottomAction, Choice
from game.game_state import GameState
from game.types import Benefit, BottomActionType, ResourceType

import attr


@attr.s(frozen=True, slots=True)
class ChooseEnlistReward(Choice):
    bottom_action_typ = attr.ib()

    @classmethod
    def new(cls, bottom_action_typ):
        return cls('Choose enlist reward', bottom_action_typ)

    def choose(self, agent, game_state):
        return agent.choose_enlist_reward(game_state)

    def do(self, game_state, enlist_reward):
        current_player = GameState.get_current_player(game_state)
        player_mat = current_player.player_mat.enlist(self.bottom_action_typ)
        current_player = attr.evolve(current_player, player_mat=player_mat).mark_enlist_benefit(enlist_reward)
        game_state = game_state.set_player(current_player)
        return game_state.give_reward_to_player(game_state.current_player, enlist_reward, 2)


@attr.s(frozen=True, slots=True)
class ChooseRecruitToEnlist(Choice):
    @classmethod
    def new(cls):
        return cls('Choose recruit to enlist')

    def choose(self, agent, game_state):
        return agent.choose_bottom_action_type(game_state, game_state.current_player.unenlisted_bottom_action_types())

    def do(self, game_state, bottom_action_typ):
        game_state.action_stack.append(ChooseEnlistReward.new(bottom_action_typ))


_choose_recruit_to_enlist = ChooseRecruitToEnlist.new()


def enlist(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.ENLIST, ResourceType.FOOD, maxcost,
                            mincost, payoff, Benefit.COMBAT_CARDS, _choose_recruit_to_enlist)
