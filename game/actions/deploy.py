import game.state_change as sc
from game.actions import BottomAction, Choice
from game.types import Benefit, BottomActionType, ResourceType

import attr


@attr.s(frozen=True, slots=True)
class ChooseDeploySpace(Choice):
    mech_typ = attr.ib()

    @classmethod
    def new(cls, mech_typ):
        return cls('Choose space to deploy mech to', mech_typ)

    def choices(self, game_state):
        return list(sc.board_coords_with_workers(game_state, sc.get_current_player(game_state)))

    def do(self, game_state, board_coords):
        return sc.deploy_mech(game_state, sc.get_current_player(game_state), self.mech_typ, board_coords)


@attr.s(frozen=True, slots=True)
class DeployMech(Choice):
    @classmethod
    def new(cls):
        return cls('Choose mech type to deploy')

    def choices(self, game_state):
        return sc.get_current_player(game_state).undeployed_mech_typs()

    def do(self, game_state, mech_typ):
        return sc.push_action(game_state, ChooseDeploySpace.new(mech_typ))


_deploy_mech = DeployMech.new()


def action(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.DEPLOY, ResourceType.METAL, maxcost, mincost, payoff,
                            Benefit.COINS, _deploy_mech)
