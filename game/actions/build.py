from game.actions import BottomAction, Choice
import game.state_change as sc
from game.types import Benefit, BottomActionType, ResourceType, StructureType, TerrainType

import attr
import logging


@attr.s(frozen=True, slots=True)
class ChooseSpaceToBuildOn(Choice):
    structure_typ = attr.ib()

    @classmethod
    def new(cls, structure_typ):
        return cls('Choose space to build on', structure_typ)

    def choices(self, game_state):
        return sc.legal_building_spots(game_state, sc.get_current_player(game_state))

    def choose(self, agent, game_state):
        return agent.choose_board_coords(game_state, self.choices(game_state))

    def do(self, game_state, board_coords):
        assert game_state.board.get_space(board_coords).terrain_typ is not TerrainType.HOME_BASE
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Build {self.structure_typ} on {board_coords}')
        return sc.build_structure(game_state, sc.get_current_player(game_state), board_coords,
                                  self.structure_typ)


@attr.s(frozen=True, slots=True)
class ChooseStructureToBuild(Choice):
    @classmethod
    def new(cls):
        return cls('Choose structure to build')

    def choices(self, game_state):
        top_action_typs_with_unbuilt_structures = \
            sc.get_current_player(game_state).top_action_typs_with_unbuilt_structures()
        return list(map(StructureType.of_top_action_typ, top_action_typs_with_unbuilt_structures))

    def choose(self, agent, game_state):
        return agent.choose_structure_typ(game_state, self.choices(game_state))

    def do(self, game_state, structure_typ):
        return sc.push_action(game_state, ChooseSpaceToBuildOn.new(structure_typ))


_choose_structure_to_build = ChooseStructureToBuild.new()


def action(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.BUILD, ResourceType.WOOD, maxcost, mincost, payoff,
                              Benefit.POPULARITY, _choose_structure_to_build)
