from game.actions.base import DiscreteChoice, Nothing, Optional, Sequence, StateChange, TopAction
from game.actions.misc import ReceiveBenefit
from game.components import Board
from game.constants import MAX_COMBAT_POWER
from game.faction import Nordic
from game.types import Benefit, FactionName, ResourceType, StarType, StructureType


class MoveGain(TopAction):
    def __init__(self):
        super().__init__(num_cubes=2, structure_typ=StructureType.MINE)

    def choices(self, _game_state):
        move = Sequence.of_list_all_optional([Move(), Move()])
        if self._cubes_upgraded[0]:
            move = Sequence.of_list([Optional(Move()), move, MaybeCombat()])
        coins_to_gain = 2 if self._cubes_upgraded[1] else 1
        gain = ReceiveBenefit(Benefit.COINS, amt=coins_to_gain)
        return [move, gain]


# The outer class represents the entire move action for a single piece. The steps are:
# 1. Choose a piece to move from pieces that haven't moved this turn. Only now do we know how much move we can have.
# 2. For each point of movement you have the option to:
# 2a. Load as much stuff as you want (look at everything in your current square that's carryable by your piece type)
# 2b. Move to an adjacent hex
# 2bi. Update the new and old hexes for the piece being moved as well as each piece being carried.
# 2biii. Mark the piece as having moved this turn.
# 2c. Drop all your stuff
class Move(DiscreteChoice):
    def __init__(self):
        super().__init__()

    @staticmethod
    def load_and_move_piece(piece):
        # This is how we "short-circuit" the move action if a piece walked into an enemy-controlled
        # territory.
        if piece.moved_into_enemy_territory_this_turn:
            return Nothing

        assert piece.not_carrying_anything()
        cur_space = piece.board_space
        load_carryables = [LoadResource(piece, resource_typ)
                           for resource_typ in ResourceType
                           for _ in range(cur_space.amount_of(resource_typ))]
        if piece.is_mech():
            for worker in cur_space.workers:
                load_carryables.append(LoadWorker(piece, worker))
        return Sequence(Sequence.of_list_all_optional(load_carryables), MovePieceOneSpace(piece))

    @staticmethod
    def move_one_piece(piece, game_state):
        num_spaces = game_state.current_player.base_move_for_piece_type(piece.typ())
        return Sequence.of_list_all_optional(Sequence.repeat(Move.load_and_move_piece(piece), num_spaces))

    def choices(self, game_state):
        # Here we don't let someone pick a piece if it happens to be a worker that was dropped into
        # enemy territory this turn. That would get around the [moved_this_turn] check, so we explicitly
        # check to see that we're not starting in enemy territory. There would be no legal way for a mech
        # or character to start in enemy territory anyway.
        return [Move.move_one_piece(piece, game_state)
                for piece in game_state.current_player().movable_pieces()
                if piece.board_space.controller() is game_state.current_player]


class MovePieceOneSpace(DiscreteChoice):
    def __init__(self, piece):
        super().__init__()
        self._piece = piece

    def choices(self, game_state):
        return [MovePieceToSpaceAndDropCarryables(self._piece, board_space)
                for board_space in
                game_state.current_player.effective_adjacent_spaces(self._piece, game_state.board)]


class MovePieceToSpaceAndDropCarryables(StateChange):
    def __init__(self, piece, board_space):
        super().__init__()
        self._piece = piece
        self._board_space = board_space

    def apply(self, game_state):
        controller_of_new_space = self._board_space.controller()
        current_player_faction = game_state.current_player.faction_name()
        if controller_of_new_space and controller_of_new_space is not current_player_faction:
            self._piece.moved_into_enemy_territory_this_turn = True
            if self._piece.is_plastic() and self._board_space.contains_no_enemy_plastic(current_player_faction):
                scared = 0
                for worker in self._board_space.workers():
                    Board.move_piece(worker, game_state.board.home_base(worker.faction_name))
                    scared += 1
                game_state.current_player.remove_popularity(min(scared, game_state.current_player.popularity()))

        for resource_typ in ResourceType:
            self._board_space.add_resources(resource_typ, self._piece.carrying_resources[resource_typ])
            self._piece.board_space.remove_resources(resource_typ, self._piece.carrying_resources[resource_typ])
        if self._piece.is_mech():
            for worker in self._piece.carrying_workers:
                worker.board_space = self._board_space
                self._board_space.workers.add(worker)
                self._piece.board_space.workers.remove(worker)
        Board.move_piece(self._piece, self._board_space)
        self._piece.moved_this_turn = True
        self._piece.drop_everything()


class LoadResource(StateChange):
    def __init__(self, piece, resource_typ):
        super().__init__()
        self._piece = piece
        self._resource_typ = resource_typ

    def apply(self, game_state):
        self._piece.carrying_resources[self._resource_typ] += 1


class LoadWorker(StateChange):
    def __init__(self, mech, worker):
        super().__init__()
        self._mech = mech
        self._worker = worker

    def apply(self, game_state):
        self._mech.carrying_workers.add(self._worker)


class MaybeCombat(StateChange):
    # Rough outline:
    # - for each space, check to see if there should be a combat
    # - if so, note the attacker and defender
    # - have each player choose an amount of power from 0 to min(7, power)
    #   as well as an optional combat card for each of their plastic pieces
    # - send the loser home and give the winner a star.
    def apply(self, game_state):
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
        self._space = space
        self._attacker = attacker
        self._defender = defender

    def get_total_power(self, game_state, player):
        # TODO: implement choose_numeric
        power = player.choose_numeric(0, min(MAX_COMBAT_POWER, player.power()))
        player.remove_power(power)
        for _ in range(self._space.num_combat_cards(player.faction_name())):
            # TODO: implement choose_from
            card = player.choose_from([0] + player.available_combat_cards())
            power += card
            if card:
                player.discard_combat_card(card, game_state.combat_cards)
        return power

    def apply(self, game_state):
        attacking_player = game_state.players_by_faction(self._attacker)
        defending_player = game_state.players_by_faction(self._defender)
        if self._space.has_tunnel(FactionName.SAXONY):
            if self._attacker is FactionName.SAXONY:
                defending_player.remove_power(min(2, defending_player.power()))
            elif self._defender is FactionName.SAXONY:
                attacking_player.remove_power(min(2, attacking_player.power()))
        if self._attacker is FactionName.NORDIC or self._defender is FactionName.NORDIC:
            nordic, not_nordic = (attacking_player, defending_player) \
                if self._attacker is FactionName.NORDIC else (defending_player, attacking_player)
            if nordic.power():
                if nordic.choose[Nordic.DONT_USE_ARTILLERY, Nordic.USE_ARTILLERY]:
                    nordic.remove_power(1)
                    not_nordic.remove_power(min(2, not_nordic.power()))
        if self._attacker is FactionName.CRIMEA or self._defender is FactionName.CRIMEA:
            crimea, not_crimea = (attacking_player, defending_player) \
                if self._attacker is FactionName.CRIMEA else (defending_player, attacking_player)
            card = not_crimea.remove_random_combat_card()
            if card:
                crimea.add_combat_card(card)

        attacker_power = self.get_total_power(game_state, attacking_player)
        defender_power = self.get_total_power(game_state, defending_player)
        winner, loser = (attacking_player, defending_player) \
            if attacker_power >= defender_power \
            else (defending_player, attacking_player)
        for piece in self._space.all_pieces(loser.faction_name()):
            Board.move_piece(piece, loser.home_base)
            if winner is attacking_player and self._attacker is not FactionName.POLANIA \
                    and piece.is_worker() and winner.popularity():
                winner.remove_popularity(1)
        winner.stars.achieve(StarType.COMBAT)
