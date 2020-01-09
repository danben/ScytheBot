from game.actions.dsl import *
from game.actions.base import BottomAction, BottomActionType
from game.types import Benefit, ResourceType


class Deploy(BottomAction):
    def __init__(self, maxcost, mincost, payoff):
        enlist_benefit = Benefit.COINS
        action_benefit = DeployMech()
        super().__init__(BottomActionType.DEPLOY, ResourceType.METAL, maxcost,
                         mincost, payoff, enlist_benefit, action_benefit)

    def can_legally_receive_action_benefit(self, game_state):
        return game_state.current_player.can_deploy()


class DeployMech(DiscreteChoice):
    def choices(self, game_state):
        return [ChooseDeploySpace(mech) for mech in game_state.current_player.undeployed_mechs()]


class ChooseDeploySpace(DiscreteChoice):
    def __init__(self, mech):
        super().__init__()
        self._mech = mech

    def choices(self, game_state):
        return [PlaceMechAtSpace(self._mech, space) for space in game_state.current_player.spaces_with_workers()]


class PlaceMechAtSpace(StateChange):
    def __init__(self, mech, space):
        super().__init__()
        self._mech = mech
        self._space = space

    def apply(self, game_state):
        game_state.current_player.deploy_mech(self._mech, self._space, game_state.board)
