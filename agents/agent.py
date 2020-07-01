from abc import ABC, abstractmethod


class Agent(ABC):
    @abstractmethod
    def select_move(self, game_state):
        pass
