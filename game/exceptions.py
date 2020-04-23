class GameOver(Exception):
    def __init__(self, game_state):
        self.game_state = game_state
