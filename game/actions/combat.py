from game.actions.action import *
from game.components import Board
from game.constants import MAX_COMBAT_POWER
from game.faction import Nordic
from game.types import FactionName, StarType


class MaybeCombat(StateChange):
    # Rough outline:
    # - for each space, check to see if there should be a combat
    # - if so, note the attacker and defender
    # - have each player choose an amount of power from 0 to min(7, power)
    #   as well as an optional combat card for each of their plastic pieces
    # - send the loser home and give the winner a star.
    def do(self, game_state):
        for space in game_state.board.base_adjacencies.keys():
            combat_factions = space.combat_factions()
            if combat_factions:
                faction1, faction2 = combat_factions
                current_player_faction = game_state.current_player.faction_name()
                assert current_player_faction is faction1 or current_player_faction is faction2
                attacker, defender = (faction1, faction2) \
                    if current_player_faction is faction1 else (faction2, faction1)
                game_state.action_stack.append(Combat(space, attacker, defender))


class Combat(StateChange):
    def __init__(self, space, attacker, defender):
        super().__init__()
        self.space = space
        self.attacker = attacker
        self.defender = defender

    def do(self, game_state):
        attacking_player = game_state.players_by_faction[self.attacker]
        defending_player = game_state.players_by_faction[self.defender]
        if self.space.has_tunnel(FactionName.SAXONY):
            if self.attacker is FactionName.SAXONY:
                defending_player.remove_power(min(2, defending_player.power()))
            elif self.defender is FactionName.SAXONY:
                attacking_player.remove_power(min(2, attacking_player.power()))
        if self.attacker is FactionName.NORDIC or self.defender is FactionName.NORDIC:
            nordic, not_nordic = (attacking_player, defending_player) \
                if self.attacker is FactionName.NORDIC else (defending_player, attacking_player)
            if nordic.power():
                if nordic.choose[Nordic.DONT_USE_ARTILLERY, Nordic.USE_ARTILLERY]:
                    nordic.remove_power(1)
                    not_nordic.remove_power(min(2, not_nordic.power()))
        if self.attacker is FactionName.CRIMEA or self.defender is FactionName.CRIMEA:
            crimea, not_crimea = (attacking_player, defending_player) \
                if self.attacker is FactionName.CRIMEA else (defending_player, attacking_player)
            card = not_crimea.remove_random_combat_card()
            if card:
                crimea.add_combat_card(card)

        game_state.action_stack.append(GetAttackerWheelPower(self.space, attacking_player, defending_player))


class GetAttackerWheelPower(Choice):
    def __init__(self, space, attacking_player, defending_player):
        super().__init__('Attacker commits wheel power')
        self.space = space
        self.attacking_player = attacking_player
        self.defending_player = defending_player

    def choose(self, agent, game_state):
        return agent.choose_numeric(game_state, 0, min(MAX_COMBAT_POWER, self.attacking_player.power()))

    def do(self, game_state, power):
        self.attacking_player.remove_power(power)
        num_combat_cards = self.space.num_combat_cards(self.attacking_player.faction_name())
        if num_combat_cards:
            game_state.action_stack.append(
                GetAttackerCombatCards(self.space, self.attacking_player, self.defending_player,
                                       attacker_total_power=power,
                                       num_combat_cards=num_combat_cards))
        else:
            game_state.current_player = self.defending_player
            game_state.action_stack.append(GetDefenderWheelPower(self.space, self.attacking_player,
                                                                 self.defending_player,
                                                                 attacker_total_power=power))


class GetAttackerCombatCards(Choice):
    def __init__(self, space, attacking_player, defending_player, attacker_total_power, num_combat_cards):
        super().__init__('Attacker commits combat cards')
        self.space = space
        self.attacking_player = attacking_player
        self.defending_player = defending_player
        self.attacker_total_power = attacker_total_power
        self.num_combat_cards = num_combat_cards

    def choose(self, agent, game_state):
        return agent.choose_optional_combat_card(game_state)

    def do(self, game_state, card):
        if card:
            self.attacker_total_power += card
            self.attacking_player.discard_combat_card(card, game_state.combat_cards)
        self.num_combat_cards -= 1
        if self.num_combat_cards:
            game_state.action_stack.append(self)
        else:
            game_state.current_player = self.defending_player
            game_state.action_stack.append(GetDefenderWheelPower(self.space, self.attacking_player,
                                                                 self.defending_player,
                                                                 attacker_total_power=self.attacker_total_power))


class GetDefenderWheelPower(Choice):
    def __init__(self, space, attacking_player, defending_player, attacker_total_power):
        super().__init__('Defender commits wheel power')
        self.space = space
        self.attacking_player = attacking_player
        self.defending_player = defending_player
        self.attacker_total_power = attacker_total_power

    def choose(self, agent, game_state):
        return agent.choose_numeric(game_state, 0, min(MAX_COMBAT_POWER, self.defending_player.power()))

    def do(self, game_state, power):
        self.defending_player.remove_power(power)
        num_combat_cards = self.space.num_combat_cards(self.defending_player.faction_name())
        if num_combat_cards:
            game_state.action_stack.append(
                GetDefenderCombatCards(self.space, self.attacking_player, self.defending_player,
                                       attacker_total_power=self.attacker_total_power,
                                       defender_total_power=power,
                                       num_combat_cards=num_combat_cards))
        else:
            game_state.action_stack.append(ResolveCombat(self.space, self.attacking_player, self.defending_player,
                                                         attacker_total_power=self.attacker_total_power,
                                                         defender_total_power=power))


class GetDefenderCombatCards(Choice):
    def __init__(self, space, attacking_player, defending_player, attacker_total_power, defender_total_power,
                 num_combat_cards):
        super().__init__('Defender commits combat cards')
        self.space = space
        self.attacking_player = attacking_player
        self.defending_player = defending_player
        self.attacker_total_power = attacker_total_power
        self.defender_total_power = defender_total_power
        self.num_combat_cards = num_combat_cards

    def choose(self, agent, game_state):
        return agent.choose_optional_combat_card(game_state)

    def do(self, game_state, card):
        if card:
            self.defender_total_power += card
            self.defending_player.discard_combat_card(card, game_state.combat_cards)
        self.num_combat_cards -= 1
        if self.num_combat_cards:
            game_state.action_stack.append(self)
        else:
            game_state.action_stack.append(ResolveCombat(self.space, self.attacking_player, self.defending_player,
                                                         attacker_total_power=self.attacker_total_power,
                                                         defender_total_power=self.defender_total_power))


class ResolveCombat(StateChange):
    def __init__(self, space, attacking_player, defending_player, attacker_total_power, defender_total_power):
        super().__init__('Resolve combat')
        self.space = space
        self.attacking_player = attacking_player
        self.defending_player = defending_player
        self.attacker_total_power = attacker_total_power
        self.defender_total_power = defender_total_power

    def do(self, game_state):
        game_state.current_player = self.attacking_player
        winner, loser = (self.attacking_player, self.defending_player) \
            if self.attacker_total_power >= self.defender_total_power \
            else (self.defending_player, self.attacking_player)
        for piece in self.space.all_pieces(loser.faction_name()):
            Board.move_piece(piece, loser.home_base)
            if winner is self.attacking_player and self.attacking_player.faction_name() is not FactionName.POLANIA \
                    and piece.is_worker() and winner.popularity():
                winner.remove_popularity(1)
        winner.stars.achieve(StarType.COMBAT)
