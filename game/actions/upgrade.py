import game.state_change as sc
from game.actions import BottomAction, Choice, StateChange
from game.types import Benefit, BottomActionType, ResourceType

import attr
import logging


@attr.s(frozen=True, slots=True)
class RemoveCubeFromAnyTopSpace(Choice):
    @classmethod
    def new(cls):
        return cls('Remove cube from top space')

    def choices(self, game_state):
        return sc.get_current_player(game_state).cube_spaces_not_fully_upgraded()

    def choose(self, agent, game_state):
        return agent.choose_cube_space_to_upgrade(game_state, self.choices(game_state))

    def do(self, game_state, top_action_typ_and_pos):
        top_action_typ, pos = top_action_typ_and_pos
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Removed cube from position {pos} of {top_action_typ}')
        return sc.remove_upgrade_cube(game_state, sc.get_current_player(game_state), top_action_typ, pos)


@attr.s(frozen=True, slots=True)
class PlaceCubeInAnyBottomSpace(Choice):
    @classmethod
    def new(cls):
        return cls('Place cube in bottom space')

    def choices(self, game_state):
        return sc.get_current_player(game_state).bottom_action_typs_not_fully_upgraded()

    def choose(self, agent, game_state):
        return agent.choose_bottom_action_typ(game_state, self.choices(game_state))

    def do(self, game_state, bottom_action_typ):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Added cube to {bottom_action_typ}')
        return sc.set_player(game_state, sc.get_current_player(game_state).upgrade_bottom_action(bottom_action_typ))


class MoveCubeToBottom(StateChange):
    _place_cube_in_any_bottom_space = PlaceCubeInAnyBottomSpace.new()
    _remove_cube_from_any_top_space = RemoveCubeFromAnyTopSpace.new()

    @classmethod
    def new(cls):
        return cls('Move cube from top space to bottom space')

    def do(self, game_state):
        game_state = sc.push_action(game_state, MoveCubeToBottom._place_cube_in_any_bottom_space)
        return sc.push_action(game_state, MoveCubeToBottom._remove_cube_from_any_top_space)


_move_cube_to_bottom = MoveCubeToBottom.new()


def action(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.UPGRADE, ResourceType.OIL, maxcost, mincost, payoff,
                              Benefit.POWER, _move_cube_to_bottom)
