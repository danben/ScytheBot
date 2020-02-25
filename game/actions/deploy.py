from game.actions.action import *
from game.types import Benefit, BottomActionType, ResourceType

import attr


@attr.s(frozen=True, slots=True)
class ChooseDeploySpace(Choice):
    mech = attr.ib()

    @classmethod
    def new(cls, mech):
        return cls('Choose space to deploy mech to', mech)

    def choose(self, agent, game_state):
        eligible_spaces = GameState.board_coords_with_workers(game_state, GameState.get_current_player(game_state))
        return agent.choose_board_space(game_state, eligible_spaces)

    def do(self, game_state, board_coords):
        return GameState.deploy_mech(game_state, GameState.get_current_player(game_state), self.mech, board_coords)


@attr.s(frozen=True, slots=True)
class DeployMech(Choice):
    @classmethod
    def new(cls):
        return cls('Choose mech to deploy')

    def choose(self, agent, game_state):
        return agent.choose_mech_to_deploy(game_state)

    def do(self, game_state, mech):
        return GameState.push_action(game_state, ChooseDeploySpace.new(mech))


_deploy_mech = DeployMech.new()


def deploy(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.DEPLOY, ResourceType.METAL, maxcost, mincost, payoff,
                            Benefit.COINS, _deploy_mech)