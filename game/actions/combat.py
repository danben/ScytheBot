import game.actions.action as a
import game.state_change as sc
from game.constants import MAX_COMBAT_POWER
from game.types import FactionName, StarType

import attr


@attr.s(frozen=True, slots=True)
class ResolveCombat(a.StateChange):
    board_coords = attr.ib()
    attacking_faction_name = attr.ib()
    defending_faction_name = attr.ib()
    attacker_total_power = attr.ib()
    defender_total_power = attr.ib()

    @classmethod
    def new(cls, board_coords, attacking_faction_name, defending_faction_name, attacker_total_power,
            defender_total_power):
        return cls('Resolve combat', board_coords, attacking_faction_name, defending_faction_name, attacker_total_power,
                   defender_total_power)

    def do(self, game_state):
        sc.change_turn(game_state, self.attacking_faction_name)
        winner, loser = (self.attacking_faction_name, self.defending_faction_name) \
            if self.attacker_total_power >= self.defender_total_power \
            else (self.defending_faction_name, self.attacking_faction_name)
        space = game_state.board.get_space(self.board_coords)
        loser_home_base_coords = game_state.board.home_base(loser).coords
        winning_player = sc.get_player_by_faction_name(game_state, winner)
        for piece_key in space.all_piece_keys(loser):
            game_state = sc.move_piece(game_state, piece_key, loser_home_base_coords)
            piece = game_state.pieces_by_key[piece_key]
            if winner is self.attacking_faction_name and self.attacking_faction_name is not FactionName.POLANIA \
                    and piece.is_worker() and winning_player.popularity:
                winning_player = winning_player.remove_popularity(1)
        winning_player = attr.evolve(winning_player, stars=winning_player.stars.achieve(StarType.COMBAT))
        return sc.set_player(game_state, winning_player)


@attr.s(frozen=True, slots=True)
class GetDefenderCombatCards(a.Choice):
    board_coords = attr.ib()
    attacking_faction_name = attr.ib()
    defending_faction_name = attr.ib()
    attacker_total_power = attr.ib()
    defender_total_power = attr.ib()
    num_combat_cards = attr.ib()

    @classmethod
    def new(cls, board_coords, attacking_faction_name, defending_faction_name, attacker_total_power,
            defender_total_power, num_combat_cards):
        return cls('Defender commits combat cards', board_coords, attacking_faction_name, defending_faction_name,
                   attacker_total_power, defender_total_power, num_combat_cards)

    def choose(self, agent, game_state):
        return agent.choose_optional_combat_card(game_state)

    def do(self, game_state, card):
        if card:
            self = attr.evolve(self, defender_total_power=(self.defender_total_power + card))
            defending_player = sc.get_player_by_faction_name(game_state, self.defending_faction_name)
            defending_player, combat_cards = defending_player.discard_combat_card(card, game_state.combat_cards)
            game_state = attr.evolve(sc.set_player(game_state, defending_player), combat_cards=combat_cards)
        self = attr.evolve(self, num_combat_cards=(self.num_combat_cards - 1))
        if self.num_combat_cards:
            return sc.push_action(game_state, self)
        else:
            return sc.push_action(game_state,
                                  ResolveCombat.new(self.board_coords, self.attacking_faction_name,
                                                    self.defending_faction_name,
                                                    attacker_total_power=self.attacker_total_power,
                                                    defender_total_power=self.defender_total_power))


@attr.s(frozen=True, slots=True)
class GetDefenderWheelPower(a.Choice):
    board_coords = attr.ib()
    attacking_faction_name = attr.ib()
    defending_faction_name = attr.ib()
    attacker_total_power = attr.ib()

    @classmethod
    def new(cls, board_coords, attacking_faction_name, defending_faction_name, attacker_total_power):
        return cls('Defender commits wheel power', board_coords, attacking_faction_name, defending_faction_name,
                   attacker_total_power)

    def choose(self, agent, game_state):
        defending_player = sc.get_player_by_faction_name(game_state, self.defending_faction_name)
        return agent.choose_numeric(game_state, 0, min(MAX_COMBAT_POWER, defending_player.power))

    def do(self, game_state, power):
        defending_player = sc.get_player_by_faction_name(game_state, self.defending_faction_name).remove_power(power)
        game_state = sc.set_player(game_state, defending_player)
        space = game_state.board.get_space(self.board_coords)
        num_combat_cards = space.num_combat_cards(self.defending_faction_name)
        if num_combat_cards:
            game_state = sc.push_action(game_state,
                                        GetDefenderCombatCards.new(self.board_coords,
                                                                   self.attacking_faction_name,
                                                                   self.defending_faction_name,
                                                                   self.attacker_total_power,
                                                                   defender_total_power=power,
                                                                   num_combat_cards=num_combat_cards))
        else:
            game_state = sc.push_action(game_state,
                                        ResolveCombat.new(self.board_coords, self.attacking_faction_name,
                                                          self.defending_faction_name,
                                                          self.attacker_total_power,
                                                          defender_total_power=power))
        return game_state


@attr.s(frozen=True, slots=True)
class GetAttackerCombatCards(a.Choice):
    board_coords = attr.ib()
    attacking_faction_name = attr.ib()
    defending_faction_name = attr.ib()
    attacker_total_power = attr.ib()
    num_combat_cards = attr.ib()

    @classmethod
    def new(cls, board_coords, attacking_faction_name, defending_faction_name, attacker_total_power,
            num_combat_cards):
        return cls('Attacker commits combat cards', board_coords, attacking_faction_name, defending_faction_name,
                   attacker_total_power, num_combat_cards)

    def choose(self, agent, game_state):
        return agent.choose_optional_combat_card(game_state)

    def do(self, game_state, card):
        if card:
            self = attr.evolve(self, attacker_total_power=(self.attacker_total_power + card))
            attacking_player = sc.get_player_by_faction_name(game_state, self.attacking_faction_name)
            attacking_player, combat_cards = attacking_player.discard_combat_card(card, game_state.combat_cards)
            game_state = attr.evolve(sc.set_player(game_state, attacking_player), combat_cards=combat_cards)
        self = attr.evolve(self, num_combat_cards=self.num_combat_cards - 1)
        if self.num_combat_cards:
            return sc.push_action(game_state, self)
        else:
            game_state = sc.change_turn(game_state, self.defending_faction_name)
            return sc.push_action(game_state,
                                  GetDefenderWheelPower.new(self.board_coords, self.attacking_faction_name,
                                                            self.defending_faction_name,
                                                            attacker_total_power=self.attacker_total_power))


@attr.s(frozen=True, slots=True)
class GetAttackerWheelPower(a.Choice):
    board_coords = attr.ib()
    attacking_faction_name = attr.ib()
    defending_faction_name = attr.ib()

    @classmethod
    def new(cls, board_coords, attacking_faction_name, defending_faction_name):
        return cls('Attacker commits wheel power', board_coords, attacking_faction_name, defending_faction_name)

    def choose(self, agent, game_state):
        attacking_player = sc.get_player_by_faction_name(game_state, self.attacking_faction_name)
        return agent.choose_numeric(game_state, 0, min(MAX_COMBAT_POWER, attacking_player.power))

    def do(self, game_state, power):
        attacking_player = sc.get_player_by_faction_name(game_state, self.attacking_faction_name)
        attacking_player = attacking_player.remove_power(power)
        game_state = sc.set_player(game_state, attacking_player)
        space = game_state.board.get_space(self.board_coords)
        num_combat_cards = space.num_combat_cards(self.attacking_faction_name)
        if num_combat_cards:
            game_state = sc.push_action(game_state,
                                        GetAttackerCombatCards.new(self.board_coords,
                                                                   self.attacking_faction_name,
                                                                   self.defending_faction_name,
                                                                   attacker_total_power=power,
                                                                   num_combat_cards=num_combat_cards))
        else:
            game_state = sc.change_turn(game_state, self.defending_faction_name)
            game_state = sc.push_action(game_state, GetDefenderWheelPower.new(self.board_coords,
                                                                              self.attacking_faction_name,
                                                                              self.defending_faction_name,
                                                                              attacker_total_power=power))
        return game_state


@attr.s(frozen=True, slots=True)
class NordicMaybeUseCombatPower(a.Choice):
    nordic_faction_name = attr.ib()
    not_nordic_faction_name = attr.ib()
    attacking_faction_name = attr.ib()

    @classmethod
    def new(cls, nordic_faction_name, not_nordic_faction_name, attacking_faction_name):
        return cls('Nordic decides whether to use its combat power', attacking_faction_name, nordic_faction_name,
                   not_nordic_faction_name)

    def choose(self, agent, game_state):
        return agent.choose_boolean(game_state)

    def do(self, game_state, chosen):
        if chosen:
            nordic_player = sc.get_player_by_faction_name(game_state, self.nordic_faction_name).remove_power(1)
            not_nordic_player = sc.get_player_by_faction_name(game_state, self.not_nordic_faction_name).remove_power(2)
            game_state = sc.set_player(game_state, nordic_player)
            game_state = sc.set_player(game_state, not_nordic_player)
            game_state = sc.change_turn(game_state, self.attacking_faction_name)
        return game_state


@attr.s(frozen=True, slots=True)
class Combat(a.StateChange):
    board_coords = attr.ib()
    attacking_faction_name = attr.ib()
    defending_faction_name = attr.ib()

    @classmethod
    def new(cls, board_coords, attacking_faction_name, defending_faction_name):
        return cls(f'Combat between {attacking_faction_name} and {defending_faction_name}', board_coords,
                   attacking_faction_name, defending_faction_name)

    def do(self, game_state):
        attacking_player = sc.get_player_by_faction_name(game_state, self.attacking_faction_name)
        defending_player = sc.get_player_by_faction_name(game_state, self.defending_faction_name)
        space = game_state.board.get_space(self.board_coords)
        if space.has_tunnel(FactionName.SAXONY):
            if self.attacking_faction_name is FactionName.SAXONY:
                defending_player = defending_player.remove_power(2)
                game_state = sc.set_player(game_state, defending_player)
            elif self.defending_faction_name is FactionName.SAXONY:
                attacking_player = attacking_player.remove_power(2)
                game_state = sc.set_player(game_state, attacking_player)

        if self.attacking_faction_name is FactionName.CRIMEA or self.defending_faction_name is FactionName.CRIMEA:
            crimea, not_crimea = (attacking_player, defending_player) \
                if self.attacking_faction_name is FactionName.CRIMEA else (defending_player, attacking_player)
            not_crimea, card = not_crimea.remove_random_combat_card()
            if card:
                crimea = crimea.add_combat_cards([card])
                game_state = sc.set_player(game_state, crimea)
                game_state = sc.set_player(game_state, not_crimea)

        game_state = sc.push_action(game_state, GetAttackerWheelPower.new(self.board_coords,
                                                                          self.attacking_faction_name,
                                                                          self.defending_faction_name))

        if self.attacking_faction_name is FactionName.NORDIC or self.defending_faction_name is FactionName.NORDIC:
            nordic, not_nordic = (attacking_player, defending_player) \
                if self.attacking_faction_name is FactionName.NORDIC else (defending_player, attacking_player)
            if nordic.power():
                game_state = sc.push_action(game_state,
                                            NordicMaybeUseCombatPower.new(nordic.faction_name(),
                                                                          not_nordic.faction_name(),
                                                                          self.attacking_faction_name))
        return game_state


@attr.s(frozen=True, slots=True)
class MaybeCombat(a.StateChange):
    @classmethod
    def new(cls):
        return cls('Check for combat')

    # Rough outline:
    # - for each space, check to see if there should be a combat
    # - if so, note the attacker and defender
    # - have each player choose an amount of power from 0 to min(7, power)
    #   as well as an optional combat card for each of their plastic pieces
    # - send the loser home and give the winner a star.
    def do(self, game_state):
        for board_coords in game_state.board.base_adjacencies.keys():
            space = game_state.board.get_space(board_coords)
            combat_factions = space.combat_factions()
            if combat_factions:
                faction1, faction2 = combat_factions
                current_player_faction = sc.get_current_player(game_state).faction_name()
                assert current_player_faction is faction1 or current_player_faction is faction2
                attacker, defender = (faction1, faction2) \
                    if current_player_faction is faction1 else (faction2, faction1)
                game_state = sc.push_action(game_state, Combat.new(board_coords, attacker, defender))
        return game_state
