from game.actions.dsl import *
from game.actions.base import BottomAction, BottomActionType
from game.types import Benefit, ResourceType


class Upgrade(BottomAction):
    def __init__(self, maxcost, mincost, payoff):
        enlist_benefit = Benefit.POWER
        action_benefit = MoveCubeToTop()
        super().__init__(BottomActionType.UPGRADE, ResourceType.OIL, maxcost,
                         mincost, payoff, enlist_benefit, action_benefit)

    def can_legally_receive_action_benefit(self, game_state):
        return game_state.current_player.can_upgrade()


class MoveCubeToTop(StateChange):
    def apply(self, game_state):
        game_state.action_stack.append(PlaceCubeInAnyTopSpace())
        game_state.action_stack.append(RemoveCubeFromAnyBottomSpace())


class PlaceCubeInAnyTopSpace(DiscreteChoice):
    def choices(self, game_state):
        return [PlaceCubeInTopSpace(top_space, pos)
                for (top_space, pos) in game_state.current_player.cube_spaces_not_fully_upgraded()]


class PlaceCubeInTopSpace(StateChange):
    def __init__(self, top_space, pos):
        super().__init__()
        self._top_space = top_space
        self._pos = pos

    def apply(self, game_state):
        self._top_space.place_upgrade_cube(self._pos)


class RemoveCubeFromAnyBottomSpace(DiscreteChoice):
    def choices(self, game_state):
        return [RemoveCubeFromBottomSpace(bottom_space)
                for bottom_space in game_state.current_player.bottom_spaces_not_fully_upgraded]


class RemoveCubeFromBottomSpace(StateChange):
    def __init__(self, bottom_space):
        super().__init__()
        self._bottom_space = bottom_space

    def apply(self, game_state):
        self._bottom_space.remove_upgrade_cube()
