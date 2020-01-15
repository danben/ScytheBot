from game.actions.action import *
from game.types import Benefit, BottomActionType, ResourceType


class MoveCubeToTop(StateChange):
    def do(self, game_state):
        game_state.action_stack.append(PlaceCubeInAnyTopSpace())
        game_state.action_stack.append(RemoveCubeFromAnyBottomSpace())


class Upgrade(BottomAction):
    enlist_benefit = Benefit.POWER
    action_benefit = MoveCubeToTop()

    def __init__(self, maxcost, mincost, payoff):
        super().__init__(BottomActionType.UPGRADE, ResourceType.OIL, maxcost,
                         mincost, payoff, Upgrade.enlist_benefit, Upgrade.action_benefit)


class PlaceCubeInAnyTopSpace(Choice):
    def choose(self, agent, game_state):
        return agent.choose_cube_space_to_upgrade(game_state)

    def do(self, game_state, top_space_and_pos):
        top_space, pos = top_space_and_pos
        top_space.place_upgrade_cube(pos)
        game_state.current_player.maybe_get_upgrade_star()


class RemoveCubeFromAnyBottomSpace(Choice):
    def choose(self, agent, game_state):
        return agent.choose_bottom_action(game_state, game_state.current_player.bottom_spaces_not_fully_upgraded())

    def do(self, game_state, bottom_action):
        logging.debug(f'Removed cube from {bottom_action!r}')
        bottom_action.remove_upgrade_cube()
