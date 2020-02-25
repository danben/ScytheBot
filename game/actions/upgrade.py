from game.actions.action import *
from game.types import Benefit, BottomActionType, ResourceType

import attr


@attr.s(frozen=True, slots=True)
class RemoveCubeFromAnyTopSpace(Choice):
    @classmethod
    def new(cls):
        return cls('Remove cube from top space')

    def choose(self, agent, game_state):
        return agent.choose_cube_space_to_upgrade(game_state)

    def do(self, game_state, top_action_typ_and_pos):
        top_action_typ, pos = top_action_typ_and_pos
        logging.debug(f'Removed cube from position {pos} of {top_action_typ}')
        return game_state.set_player(game_state.current_player.remove_upgrade_cube(top_action_typ, pos))


@attr.s(frozen=True, slots=True)
class PlaceCubeInAnyBottomSpace(Choice):
    @classmethod
    def new(cls):
        return cls('Place cube in bottom space')

    def choose(self, agent, game_state):
        return agent.choose_bottom_action_typ(game_state,
                                              game_state.current_player.bottom_action_types_not_fully_upgraded())

    def do(self, game_state, bottom_action_typ):
        logging.debug(f'Removed cube from {bottom_action_typ}')
        return game_state.set_player(game_state.current_player.upgrade_bottom_action(bottom_action_typ))


class MoveCubeToBottom(StateChange):
    _place_cube_in_any_bottom_space = PlaceCubeInAnyBottomSpace.new()
    _remove_cube_from_any_top_space = RemoveCubeFromAnyTopSpace.new()

    @classmethod
    def new(cls):
        return cls('Move cube from top space to bottom space')

    def do(self, game_state):
        game_state = game_state.push_action(MoveCubeToBottom._place_cube_in_any_bottom_space)
        return game_state.push_action(MoveCubeToBottom._remove_cube_from_any_top_space)


_move_cube_to_bottom = MoveCubeToBottom.new()


def upgrade(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.UPGRADE, ResourceType.OIL, maxcost, mincost, payoff,
                            Benefit.POWER, _move_cube_to_bottom)
