import game.state_change as sc
from game.actions import BottomAction, Choice
from game.types import Benefit, BottomActionType, ResourceType

import attr
import logging


@attr.s(frozen=True, slots=True)
class ChooseEnlistReward(Choice):
    bottom_action_typ = attr.ib()

    @classmethod
    def new(cls, bottom_action_typ):
        return cls('Choose enlist reward', bottom_action_typ)

    def choices(self, game_state):
        return sc.get_current_player(game_state).available_enlist_rewards()

    def choose(self, agent, game_state):
        return agent.choose_enlist_reward(game_state, self.choices(game_state))

    def do(self, game_state, enlist_reward):
        current_player = sc.get_current_player(game_state)
        logging.debug(f'{current_player} enlists the {self.bottom_action_typ} recruit, \
        taking the {enlist_reward} benefit')
        player_mat = current_player.player_mat.enlist(self.bottom_action_typ)
        current_player = attr.evolve(current_player, player_mat=player_mat)
        game_state = sc.set_player(game_state, current_player)
        game_state = sc.mark_enlist_benefit(game_state, current_player, enlist_reward)
        current_player = sc.get_current_player(game_state)
        return sc.give_reward_to_player(game_state, current_player, enlist_reward, 2)


@attr.s(frozen=True, slots=True)
class ChooseRecruitToEnlist(Choice):
    @classmethod
    def new(cls):
        return cls('Choose recruit to enlist')

    def choices(self, game_state):
        return sc.get_current_player(game_state).unenlisted_bottom_action_typs()

    def choose(self, agent, game_state):
        return agent.choose_bottom_action_typ(game_state, self.choices(game_state))

    def do(self, game_state, bottom_action_typ):
        return sc.push_action(game_state, ChooseEnlistReward.new(bottom_action_typ))


_choose_recruit_to_enlist = ChooseRecruitToEnlist.new()


def action(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.ENLIST, ResourceType.FOOD, maxcost,
                            mincost, payoff, Benefit.COMBAT_CARDS, _choose_recruit_to_enlist)
