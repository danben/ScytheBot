from game.actions.action import *
from game.types import Benefit, BottomActionType, ResourceType

import attr


@attr.s(frozen=True, slots=True)
class ChooseSpaceToBuildOn(Choice):
    structure_typ = attr.ib()

    @classmethod
    def new(cls, structure_typ):
        return cls('Choose space to build on', structure_typ)

    def choose(self, agent, game_state):
        eligible_spaces = GameState.legal_building_spots(game_state, GameState.get_current_player(game_state))
        return agent.choose_board_space(game_state, eligible_spaces)

    def do(self, game_state, board_coords):
        return GameState.build_structure(game_state, GameState.get_current_player(game_state), board_coords,
                                         self.structure_typ)
        self.top_action.build_structure()


@attr.s(frozen=True, slots=True)
class ChooseStructureToBuild(Choice):
    @classmethod
    def new(cls):
        return cls('Choose structure to build')

    def choose(self, agent, game_state):
        return agent.choose_structure_to_build(game_state)

    def do(self, game_state, structure_typ):
        return GameState.push_action(game_state, ChooseSpaceToBuildOn.new(structure_typ))


_choose_structure_to_build = ChooseStructureToBuild.new()


def build(maxcost, mincost, payoff):
    return BottomAction.new(BottomActionType.BUILD, ResourceType.WOOD, maxcost, mincost, payoff,
                            Benefit.POPULARITY, _choose_structure_to_build)
