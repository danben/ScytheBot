from enum import Enum
from game.actions.dsl import *
from game.actions.misc import Cost


class TopAction(Action):
    def __init__(self, num_cubes, structure_typ):
        super().__init__()
        self._structure_is_built = False
        self._structure_typ = structure_typ
        self._cubes_upgraded = [False] * num_cubes

    def structure_typ(self):
        return self._structure_typ

    def structure_is_built(self):
        return self._structure_is_built

    def build_structure(self):
        assert not self._structure_is_built
        self._structure_is_built = True

    def place_upgrade_cube(self, spot):
        assert spot < len(self._cubes_upgraded) and not self._cubes_upgraded[spot]
        self._cubes_upgraded[spot] = True

    def upgradeable_cubes(self):
        return [i for i in range(len(self._cubes_upgraded)) if not self._cubes_upgraded[i]]


class BottomActionType(Enum):
    UPGRADE = 1
    DEPLOY = 2
    BUILD = 3
    ENLIST = 4


class BottomAction(Action):
    def __init__(self, typ, resource_type, maxcost, mincost, payoff, enlist_benefit, action_benefit):
        super().__init__()
        self._typ = typ
        self._cost = maxcost
        self._mincost = mincost
        self._payoff = payoff
        self.enlisted = False
        self._resource_type = resource_type
        self._enlist_benefit = enlist_benefit
        self._action_benefit = action_benefit

    def apply(self, game_state):
        current_player = game_state.current_player
        current_player.pay(self._resource_type, self._cost)

        if self.enlisted:
            game_state.give_player(current_player, self._enlist_benefit)

        left_player = game_state.get_left_player()
        if game_state.has_enlisted(left_player, self._typ):
            game_state.give_reward_to_player(left_player, self._enlist_benefit)

        right_player = game_state.get_right_player()
        if left_player is not right_player and game_state.has_enlisted(right_player, self._typ):
            game_state.give_reward_to_player(right_player, self._enlist_benefit)

        current_player.add_coins(self._payoff)
        game_state.action_stack.append(Optional(self._action_benefit))

    def can_legally_receive_action_benefit(self, game_state):
        raise NotImplementedError()

    def cost(self, game_state):
        return Cost.of_resource_type(self._resource_type, self._cost)

    def is_upgradeable(self):
        return self._cost > self._mincost

    def remove_upgrade_cube(self):
        assert self._cost > self._mincost
        self._cost = self._cost - 1
