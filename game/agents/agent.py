from abc import ABC, abstractmethod


class Agent(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def choose_action_spot(self, game_state, invalid):
        pass

    @abstractmethod
    def choose_boolean(self, game_state):
        pass

    @abstractmethod
    def choose_numeric(self, game_state, low, high):
        pass

    @abstractmethod
    def choose_board_space(self, game_state, board_spaces):
        pass

    @abstractmethod
    def choose_piece(self, game_state, pieces):
        pass

    @abstractmethod
    def choose_whether_to_pay_for_next_action(self, game_state):
        pass

    @abstractmethod
    def choose_resource_type(self, game_state):
        pass

    @abstractmethod
    def choose_bottom_action(self, game_state, bottom_actions):
        pass

    @abstractmethod
    def choose_enlist_reward(self, game_state):
        pass

    @abstractmethod
    def choose_mech_to_deploy(self, game_state):
        pass

    @abstractmethod
    def choose_structure_to_build(self, game_state):
        pass

    @abstractmethod
    def choose_cube_space_to_upgrade(self, game_state):
        pass

    @abstractmethod
    def choose_optional_combat_card(self, game_state):
        pass
