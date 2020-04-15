import game.actions.action as a
import game.state_change as sc
from game.types import Benefit, BottomActionType, ResourceType

import attr


@attr.s(frozen=True, slots=True)
class ChooseDeploySpace(a.Choice):
    mech_type = attr.ib()

    @classmethod
    def new(cls, mech_type):
        return cls('Choose space to deploy mech to', mech_type)

    def choose(self, agent, game_state):
        eligible_spaces = \
            sc.board_coords_with_workers(game_state, sc.get_current_player(game_state))
        return agent.choose_board_coords(game_state, list(eligible_spaces))

    def do(self, game_state, board_coords):
        return sc.deploy_mech(game_state, sc.get_current_player(game_state), self.mech_type, board_coords)


@attr.s(frozen=True, slots=True)
class DeployMech(a.Choice):
    @classmethod
    def new(cls):
        return cls('Choose mech type to deploy')

    def choose(self, agent, game_state):
        return agent.choose_mech_type_to_deploy(game_state)

    def do(self, game_state, mech_type):
        return sc.push_action(game_state, ChooseDeploySpace.new(mech_type))


_deploy_mech = DeployMech.new()


def action(maxcost, mincost, payoff):
    return a.BottomAction.new(BottomActionType.DEPLOY, ResourceType.METAL, maxcost, mincost, payoff,
                              Benefit.COINS, _deploy_mech)
