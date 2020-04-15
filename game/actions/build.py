import game.actions.action as a
import game.state_change as sc
from game.types import Benefit, BottomActionType, ResourceType, TerrainType

import attr


@attr.s(frozen=True, slots=True)
class ChooseSpaceToBuildOn(a.Choice):
    structure_typ = attr.ib()

    @classmethod
    def new(cls, structure_typ):
        return cls('Choose space to build on', structure_typ)

    def choose(self, agent, game_state):
        eligible_spaces = sc.legal_building_spots(game_state, sc.get_current_player(game_state))
        return agent.choose_board_coords(game_state, eligible_spaces)

    def do(self, game_state, board_coords):
        assert game_state.board.get_space(board_coords).terrain_typ is not TerrainType.HOME_BASE
        return sc.build_structure(game_state, sc.get_current_player(game_state), board_coords,
                                  self.structure_typ)


@attr.s(frozen=True, slots=True)
class ChooseStructureToBuild(a.Choice):
    @classmethod
    def new(cls):
        return cls('Choose structure to build')

    def choose(self, agent, game_state):
        return agent.choose_structure_to_build(game_state)

    def do(self, game_state, structure_typ):
        return sc.push_action(game_state, ChooseSpaceToBuildOn.new(structure_typ))


_choose_structure_to_build = ChooseStructureToBuild.new()


def action(maxcost, mincost, payoff):
    return a.BottomAction.new(BottomActionType.BUILD, ResourceType.WOOD, maxcost, mincost, payoff,
                              Benefit.POPULARITY, _choose_structure_to_build)
