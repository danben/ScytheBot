from abc import ABC, abstractmethod


class Agent(ABC):
    @abstractmethod
    def choose_action(self, game_state, choices):
        pass

    @abstractmethod
    def choose_action_spot(self, game_state, choices):
        pass

    @abstractmethod
    def choose_boolean(self, game_state):
        pass

    @abstractmethod
    def choose_numeric(self, game_state, choices):
        pass

    @abstractmethod
    def choose_board_coords(self, game_state, choices):
        pass

    @abstractmethod
    def choose_piece(self, game_state, choices):
        pass

    @abstractmethod
    def choose_resource_typ(self, game_state, choices):
        pass

    @abstractmethod
    def choose_bottom_action_typ(self, game_state, choices):
        pass

    @abstractmethod
    def choose_enlist_reward(self, game_state, choices):
        pass

    @abstractmethod
    def choose_mech_typ_to_deploy(self, game_state, choices):
        pass

    @abstractmethod
    def choose_structure_typ(self, game_state, choices):
        pass

    @abstractmethod
    def choose_cube_space_to_upgrade(self, game_state, choices):
        pass

    @abstractmethod
    def choose_optional_combat_card(self, game_state, choices):
        pass
