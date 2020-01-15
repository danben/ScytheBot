from game.actions.action import *
from game.types import Benefit, BottomActionType, ResourceType


class ChooseStructureToBuild(Choice):
    def __init__(self):
        super().__init__('Choose structure to build')

    def choose(self, agent, game_state):
        return agent.choose_structure_to_build(game_state)

    def do(self, game_state, top_action):
        game_state.action_stack.append(ChooseSpaceToBuildOn(top_action))


class Build(BottomAction):
    enlist_benefit = Benefit.POPULARITY
    action_benefit = ChooseStructureToBuild()

    def __init__(self, maxcost, mincost, payoff):
        super().__init__(BottomActionType.BUILD, ResourceType.WOOD, maxcost,
                         mincost, payoff, Build.enlist_benefit, Build.action_benefit)


class ChooseSpaceToBuildOn(Choice):
    def __init__(self, top_action):
        super().__init__('Choose space to build on')
        self.top_action = top_action

    def choose(self, agent, game_state):
        return agent.choose_board_space(game_state, game_state.current_player.legal_building_spots())

    def do(self, game_state, space):
        self.top_action.build_structure()
        game_state.current_player.build_structure(space, self.top_action.structure_typ())
