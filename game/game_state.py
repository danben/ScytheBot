import game.components.board as gc_board
import game.components.combat_cards as gc_combat_cards
import game.components.player_mat as gc_player_mat
import game.components.piece as gc_piece
import game.components.structure_bonus as gc_structure_bonus
import game.state_change as sc
from game.faction import choose as choose_faction
from game.player import Player
from game.types import PieceType, StructureType

import attr
from pyrsistent import plist, pmap, pset


@attr.s(slots=True, frozen=True)
class GameState:
    board = attr.ib()
    structure_bonus = attr.ib()
    combat_cards = attr.ib()
    players_by_idx = attr.ib()
    player_idx_by_faction_name = attr.ib()
    pieces_by_key = attr.ib()
    action_stack = attr.ib(default=plist())
    current_player_idx = attr.ib(default=0)
    spaces_produced_this_turn = attr.ib(default=pset())

    @classmethod
    def from_num_players(cls, num_players):
        factions = choose_faction(num_players)
        player_mat_names = sorted(gc_player_mat.PlayerMat.choose(num_players), key=lambda x: x.value)
        board = gc_board.Board.from_active_factions(factions)
        combat_cards = gc_combat_cards.CombatCards()

        pieces_by_key = {}
        for piece_typ in PieceType:
            if piece_typ is PieceType.STRUCTURE:
                continue
            elif piece_typ is PieceType.WORKER:
                ctor = gc_piece.Worker
            elif piece_typ is PieceType.MECH:
                ctor = gc_piece.Mech
            elif piece_typ is PieceType.CHARACTER:
                ctor = gc_piece.Character
            for faction in factions:
                for i in range(piece_typ.num_pieces()):
                    new_piece = ctor(None, faction.name, i)
                    pieces_by_key[new_piece.key()] = new_piece

        for faction in factions:
            for typ in StructureType:
                new_piece = gc_piece.Structure.of_typ(None, faction.name, typ)
                pieces_by_key[new_piece.key()] = new_piece

        def add_piece_for_player(player, board, piece_typ, piece_id, coords):
            key = gc_piece.PieceKey(piece_typ, player.faction_name(), piece_id)
            piece = pieces_by_key[key]
            pieces_by_key[key] = attr.evolve(piece, board_coords=coords)
            board = board.add_piece(key, coords)
            return board

        players_by_idx = {}
        player_idx_by_faction_name = {}
        for i in range(num_players):
            faction = factions[i]
            combat_cards, starting_combat_cards = combat_cards.draw(faction.starting_combat_cards)
            player = Player.new(i, faction, player_mat_names[i], board, starting_combat_cards)
            player_idx_by_faction_name[faction.name] = i
            board = add_piece_for_player(player, board, PieceType.CHARACTER, 0, player.home_base)
            players_by_idx[i] = player

        players_by_idx = pmap(players_by_idx)
        pieces_by_key = pmap(pieces_by_key)
        structure_bonus = gc_structure_bonus.StructureBonus.random()
        game_state = cls(board, structure_bonus, combat_cards, players_by_idx, player_idx_by_faction_name, pieces_by_key)
        for i in range(num_players):
            player = game_state.players_by_idx[i]
            spaces_adjacent_to_home_base = board.adjacencies_accounting_for_rivers_and_lakes[player.home_base]
            assert len(spaces_adjacent_to_home_base) == 2
            for coords in spaces_adjacent_to_home_base:
                game_state = sc.add_workers(game_state, player, coords, 1)
                player = game_state.players_by_idx[i]
        return game_state


