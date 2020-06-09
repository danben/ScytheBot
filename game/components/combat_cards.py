import attr
import numpy as np

from pyrsistent import pvector, thaw


def build_deck():
    deck = [2] * 16 + [3] * 12 + [4] * 8 + [5] * 6
    np.random.shuffle(deck)
    return pvector(deck)


# TODO: discard pile can be a map rather than a list
@attr.s(frozen=True, slots=True)
class CombatCards:
    deck = attr.ib(factory=build_deck)
    discard_pile = attr.ib(factory=pvector)

    def discard(self, card):
        return attr.evolve(self, discard_pile=self.discard_pile.append(card))

    def reshuffle(self):
        assert not self.deck
        deck = thaw(self.discard_pile)
        np.random.shuffle(deck)
        return CombatCards(pvector(deck), pvector())

    def draw(self, amt):
        if amt > len(self.deck):
            to_draw = len(self.deck)
        else:
            to_draw = amt
        drawn = self.deck[:to_draw]
        new_deck = self.deck[to_draw:]
        remaining = amt - to_draw
        if not remaining or not self.discard_pile:
            return attr.evolve(self, deck=new_deck), drawn

        cc = attr.evolve(self, deck=pvector()).reshuffle()
        rest = min(remaining, len(cc.deck))

        drawn = thaw(drawn)
        drawn.extend(cc.deck[:rest])
        return attr.evolve(cc, deck=cc.deck[rest:]), drawn
