import numpy as np


class CombatCards:
    def __init__(self):
        self._deck = [2] * 16 + [3] * 12 + [4] * 8 + [5] * 6
        self._discard = []

        np.random.shuffle(self._deck)

    def discard(self, card):
        self._discard.append(card)

    def reshuffle(self):
        assert not self._deck
        self._deck = self._discard
        self._discard = []
        np.random.shuffle(self._deck)

    def draw(self, amt):
        if amt > len(self._deck):
            to_draw = len(self._deck)
        else:
            to_draw = amt
        drawn = self._deck[:to_draw]
        self._deck = self._deck[to_draw:]
        remaining = amt - to_draw
        if remaining:
            self.reshuffle()

        rest = min(remaining, len(self._deck))
        drawn.extend(self._deck[:rest])
        self._deck = self._deck[rest:]
        return drawn
