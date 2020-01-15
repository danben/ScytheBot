from game.actions.action import *
from game.types import Benefit, BottomActionType, ResourceType


class DeployMech(Choice):
    def __init__(self):
        super().__init__('Choose mech to deploy')

    def choose(self, agent, game_state):
        return agent.choose_mech_to_deploy(game_state)

    def do(self, game_state, mech):
        game_state.action_stack.append(ChooseDeploySpace(mech))


class Deploy(BottomAction):
    enlist_benefit = Benefit.COINS
    action_benefit = DeployMech()

    def __init__(self, maxcost, mincost, payoff):
        super().__init__(BottomActionType.DEPLOY, ResourceType.METAL, maxcost,
                         mincost, payoff, Deploy.enlist_benefit, Deploy.action_benefit)


class ChooseDeploySpace(Choice):
    def __init__(self, mech):
        super().__init__()
        self.mech = mech

    def choose(self, agent, game_state):
        return agent.choose_board_space(game_state, list(game_state.current_player.spaces_with_workers()))

    def do(self, game_state, space):
        game_state.current_player.deploy_mech(self.mech, space, game_state.board)
