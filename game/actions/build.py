from game.actions.dsl import *
from game.actions.base import BottomAction, BottomActionType
from game.types import Benefit, ResourceType
from game.components.piece import Structure


class Build(BottomAction):
    def __init__(self, maxcost, mincost, payoff):
        enlist_benefit = Benefit.POPULARITY
        action_benefit = ChooseStructureToBuild()
        super().__init__(BottomActionType.BUILD, ResourceType.WOOD, maxcost,
                         mincost, payoff, enlist_benefit, action_benefit)

    def can_legally_receive_action_benefit(self, game_state):
        return game_state.current_player.can_build()


class ChooseStructureToBuild(DiscreteChoice):
    def choices(self, game_state):
        return [ChooseSpaceToBuildOn(top_action) for top_action in game_state.current_player.top_actions_with_unbuilt_structures()]


class ChooseSpaceToBuildOn(DiscreteChoice):
    def __init__(self, top_action):
        super().__init__()
        self._top_action = top_action

    def choices(self, game_state):
        return [BuildStructure(self._top_action, space) for space in game_state.current_player.legal_building_spots()]


class BuildStructure(StateChange):
    def __init__(self, top_action, space):
        super().__init__()
        self._top_action = top_action
        self._space = space

    def apply(self, game_state):
        self._top_action.build_structure()
        structure = Structure(self._space, self._top_action.structure_typ(),
                                                          game_state.current_player.faction_name())
        game_state.current_player.build_structure(structure)
