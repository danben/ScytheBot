from game.actions import SpendAResource
from game.components import Board, CombatCards, PlayerMat, StructureBonus
from game.components.piece import character_key, worker_key, mech_key, PieceKey, Structure
from game.constants import NUM_WORKERS
from game.faction import choose as choose_faction
from game.player import Player
from game.types import Benefit, FactionName, MechType, PieceType, ResourceType, StarType, StructureType, TerrainType, \
    TopActionType

import attr
import logging
from pyrsistent import plist, pmap, pset, thaw


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
        player_mat_names = sorted(PlayerMat.choose(num_players), key=lambda x: x.value)
        board = Board.from_active_factions(factions)
        combat_cards = CombatCards()

        pieces_by_key = {}
        for piece_typ in PieceType:
            if piece_typ is PieceType.STRUCTURE:
                continue
            ctor = piece_typ.ctor()
            for faction in factions:
                for i in range(piece_typ.num_pieces()):
                    new_piece = ctor(None, faction.name, i)
                    pieces_by_key[new_piece.key()] = new_piece

        for faction in factions:
            for typ in StructureType:
                new_piece = Structure.of_typ(None, faction.name, typ)
                pieces_by_key[new_piece.key()] = new_piece

        def add_piece_for_player(player, board, piece_typ, id, coords):
            key = PieceKey(piece_typ, player.faction_name(), id)
            piece = pieces_by_key[key]
            pieces_by_key[key] = attr.evolve(piece, board_coords=coords)
            board = board.add_piece(key, coords)
            return board

        players_by_idx = {}
        player_idx_by_faction_name = {}
        for i in range(num_players):
            faction = factions[i]
            player = Player.new(i, faction, player_mat_names[i], board,
                                combat_cards.draw(faction.starting_combat_cards))
            player_idx_by_faction_name[faction.name] = i
            spaces_adjacent_to_home_base = board.adjacencies_accounting_for_rivers_and_lakes[player.home_base]
            assert len(spaces_adjacent_to_home_base) == 2
            player = player.add_workers([0, 1])
            for j, coords in enumerate(spaces_adjacent_to_home_base):
                board = add_piece_for_player(player, board, PieceType.WORKER, j, coords)
            board = add_piece_for_player(player, board, PieceType.CHARACTER, 0, player.home_base)
            players_by_idx[i] = player
        players_by_idx = pmap(players_by_idx)
        structure_bonus = StructureBonus.random()
        return cls(board, structure_bonus, combat_cards, players_by_idx, player_idx_by_faction_name, pieces_by_key)

    @staticmethod
    def push_action(game_state, action):
        return attr.evolve(game_state, action_stack=game_state.action_stack.cons(action))

    @staticmethod
    def pop_action(game_state):
        action = game_state.action_stack.first
        if action:
            return attr.evolve(game_state, action_stack=game_state.action_stack.rest), action
        else:
            return game_state, None

    @staticmethod
    def get_current_player(game_state):
        return game_state.players_by_idx[game_state.current_player_idx]

    @staticmethod
    def get_player(game_state, faction_name):
        return game_state.players_by_idx[game_state.player_idx_by_faction_name[faction_name]]

    @staticmethod
    def get_left_player(game_state):
        new_idx = game_state.current_player_idx - 1
        if new_idx < 0:
            new_idx = len(game_state.players_by_idx) - 1
        return game_state.players_by_idx[new_idx]

    @staticmethod
    def get_right_player(game_state):
        new_idx = game_state.current_player_idx + 1
        if new_idx == len(game_state.players_by_idx):
            new_idx = 0
        return game_state.players_by_idx[new_idx]

    @staticmethod
    def get_board_coords_for_piece_key(game_state, piece_key):
        return game_state.pieces_by_key[piece_key].board_coords

    @staticmethod
    def change_turn(game_state, faction_name):
        return attr.evolve(game_state, current_player_idx=game_state.player_idx_by_faction_name[faction_name])

    @staticmethod
    def set_player(game_state, player):
        return attr.evolve(game_state, players_by_idx=game_state.players_by_idx.set(player.id, player))

    @staticmethod
    def set_piece(game_state, piece):
        return attr.evolve(game_state, pieces_by_key=game_state.pieces_by_key.set(piece.key(), piece))

    @staticmethod
    def _board_coords_with_piece_typ(game_state, player, piece_typ):
        if piece_typ is PieceType.WORKER:
            id_set = player.workers()
        elif piece_typ is PieceType.MECH:
            id_set = player.mechs()
        else:
            assert False

        pieces = [game_state.pieces_by_key[(piece_typ, player.faction_name(), id)] for id in id_set]
        ret = set([piece.board_coords for piece in pieces])
        ret.discard(player.home_base)
        return ret

    @staticmethod
    def board_coords_with_workers(game_state, player):
        return GameState._board_coords_with_piece_typ(game_state, player, PieceType.WORKER)

    @staticmethod
    def board_coords_with_mechs(game_state, player):
        return GameState._board_coords_with_piece_typ(game_state, player, PieceType.MECH)

    @staticmethod
    def controller(game_state, board_space):
        candidates = set()
        for character_key in board_space.character_keys:
            character = game_state.pieces_by_key[character_key]
            if not character.moved_into_enemy_territory_this_turn:
                candidates.add(character.faction_name)
        for mech_key in board_space.mech_keys:
            mech = game_state.pieces_by_key[mech_key]
            if not mech.moved_into_enemy_territory_this_turn:
                candidates.add(mech_key.faction_name)
        if len(candidates) > 1:
            logging.error(f'Multiple controller candidates on space {board_space}: {candidates}')
            assert False
        if len(candidates) == 1:
            return candidates.pop()
        for worker_key in board_space.worker_keys:
            candidates.add(worker_key.faction_name)
        if len(candidates) > 1:
            assert False
        if len(candidates) == 1:
            return candidates.pop()
        if board_space.structure_key:
            return board_space.structure_key.faction_name
        return None

    @staticmethod
    def controlled_spaces(game_state, player):
        s = GameState.board_coords_with_workers(game_state, player) | GameState.board_coords_with_mechs(game_state, player)
        s.add(game_state.pieces_by_key[character_key(player.faction_name())].coords)
        s.discard(player.home_base)
        s = set(map(game_state.board.get_space, s))
        to_remove = []
        for space in s:
            if GameState.controller(game_state, space) is not player.faction_name():
                to_remove.append(space)
        for space in to_remove:
            s.remove(space)
        to_add = []
        for coords in GameState.board_coords_with_structures(game_state, player):
            space = game_state.board.get_space(coords)
            if GameState.controller(game_state, space) is player.faction_name():
                to_add.append(space)
        for space in to_add:
            s.add(space)
        return s

    @staticmethod
    def territory_count(game_state, player):
        s = GameState.controlled_spaces(game_state, player)
        ret = len(s)
        for space in s:
            if space.coords == (3, 3):
                return ret + 2
        return ret

    @staticmethod
    def controlled_spaces_with_resource(game_state, player, resource_typ):
        return [space for space in GameState.controlled_spaces(game_state, player)
                if space.has_resource(resource_typ)]

    @staticmethod
    def board_coords_with_structures(game_state, player):
        ret = set()
        for structure_typ in StructureType:
            if structure_typ in player.structures:
                ret.add(GameState.get_board_coords_for_piece_key(game_state,
                                                                 PieceKey(PieceType.STRUCTURE, player.faction_name(),
                                                                          structure_typ.value)))
        return ret

    @staticmethod
    def legal_building_spots(game_state, player):
        ret = []
        for coords in GameState.board_coords_with_workers(game_state, player):
            space = game_state.board.get_space(coords)
            if not (space.has_structure() or space.terrain_typ is TerrainType.LAKE):
                ret.append(coords)
        return ret

    @staticmethod
    def remove_all_of_this_resource(game_state, player, resource_typ):
        board = game_state.board
        for space in GameState.controlled_spaces_with_resource(game_state, player, resource_typ):
            board_spaces_by_coords = \
                board.board_spaces_by_coords.set(space.coords,
                                                 space.remove_resources(resource_typ,
                                                                        space.amount_of(resource_typ)))
            board = attr.evolve(game_state.board, board_spaces_by_coords=board_spaces_by_coords)
        return attr.evolve(game_state, board=board)

    @staticmethod
    def charge_player(game_state, player, cost):
        assert player.can_pay_cost(cost)
        logging.debug(f'Pay {cost!r}')
        if cost.coins:
            player = player.remove_coins(cost.coins)
        if cost.power:
            player = player.remove_power(cost.power)
        if cost.popularity:
            player = player.remove_popularity(cost.popularity)
        if cost.combat_cards:
            player = player.discard_lowest_combat_cards(cost.combat_cards, game_state.combat_cards)
        for resource_typ in ResourceType:
            amount_owned = player.available_resources(resource_typ)
            amount_owed = cost.resource_cost[resource_typ]
            if amount_owned > amount_owed:
                for _ in range(amount_owed):
                    game_state = game_state.push_action(SpendAResource.new(player.id, resource_typ))
            else:
                assert amount_owned == cost.resource_cost[resource_typ]
                game_state = game_state.remove_all_of_this_resource(game_state, player, resource_typ)

        return game_state.set_player(player)

    @staticmethod
    def give_reward_to_player(game_state, player, benefit, amt):
        logging.debug(f'Receive {amt} {benefit!r}')
        if benefit is Benefit.POPULARITY:
            player = player.add_popularity(amt)
        elif benefit is Benefit.COINS:
            player = player.add_coins(amt)
        elif benefit is Benefit.POWER:
            player = player.add_power(amt)
        elif benefit is Benefit.COMBAT_CARDS:
            new_cards, combat_cards = game_state.combat_cards.draw(amt)
            game_state = attr.evolve(game_state, combat_cards=combat_cards)
            player = player.add_combat_cards(new_cards)

        return game_state.set_player(player)

    @staticmethod
    def add_workers(game_state, player, coords, amt):
        max_worker_id = max(player.workers)
        assert max_worker_id + amt < NUM_WORKERS
        ids = list(range(max_worker_id+1, max_worker_id+amt+1))
        game_state = game_state.set_player(player.id, player.add_workers(ids))
        return attr.evolve(game_state, board=game_state.board.add_workers(coords, player.faction_name, ids))

    @staticmethod
    def add_riverwalk_adjacencies(game_state, player):
        player = attr.evolve(player,
                             adjacencies=player.faction.add_riverwalk_adjacencies(player.adjacencies, game_state.board))
        return game_state.set_player(player)

    @staticmethod
    def add_teleport_adjacencies(game_state, player):
        player = attr.evolve(player,
                             adjacencies=player.faction.add_teleport_adjacencies(player.adjacencies, game_state.board))
        return game_state.set_player(player)

    @staticmethod
    def build_structure(game_state, player, board_coords, structure_typ):
        assert structure_typ not in player.structures
        board_space = game_state.board.get_space(board_coords)
        assert not board_space.has_structure()
        structure_key = PieceKey(PieceType.STRUCTURE, player.faction_name(), structure_typ.value)
        board_space = attr.evolve(board_space, structure=structure_key)
        game_state = attr.evolve(game_state, board=game_state.board.set_space(board_space))
        player_mat = player.player_mat
        top_action_typ = TopActionType.of_structure_type(structure_typ)
        top_action_cubes_and_structure =\
            player_mat.top_action_cubes_and_structure_by_top_action_typ[top_action_typ].build_structure()
        player_mat =\
            attr.evolve(player_mat,
                        top_action_cubes_and_structure_by_top_action_typ=
                          player_mat.top_action_cubes_and_structure_by_top_action_typ.set(top_action_typ,
                                                                                          top_action_cubes_and_structure
                                                                                          ))
        player = attr.evolve(player, structures=player.structures.add(structure_typ), player_mat=player_mat)
        if not player.can_build():
            player = attr.evolve(player, stars=player.stars.achieve(StarType.STRUCTURE))
        if structure_typ is StructureType.MINE:
            # For every tunnel space on the board, add it to the current space's
            # adjacency list and add the current space to its adjacency list.
            new_adjacencies = {}
            for piece_typ in [PieceType.CHARACTER, PieceType.MECH, PieceType.WORKER]:
                # player.adjacencies is a doubly-nested pmap: piece type -> board coords -> coord plist
                # We get the adjacency map for the current piece type...
                piece_adjacencies = player.adjacencies[piece_typ]
                # And build a new adjacency map for this piece type...
                new_piece_adjacencies = {}
                adjacent_to_current_space = thaw(piece_adjacencies[board_space])
                # By iterating over every space on the board...
                for coords, adjacent_coords in piece_adjacencies.items():
                    # And if it isn't the spot we're building on...
                    if coords != board_space.coords:
                        # Thaw out its adjacency list...
                        adjacent_coords = thaw(adjacent_coords)
                        other_space = game_state.board.board_spaces_by_coords[coords]
                        # Check if it has a tunnel...
                        if other_space.has_tunnel(player.faction_name()):
                            # If so, add the current spot to its adjacency list...
                            if board_space.coords not in adjacent_coords:
                                adjacent_coords.append(board_space.coords)
                            # And add it to the current spot's adjacency list...
                            if coords not in adjacent_to_current_space:
                                adjacent_to_current_space.append(coords)
                        # We're done with this space, so replace its adjacency list in [new_piece_adjacencies]...
                        new_piece_adjacencies[coords] = plist(adjacent_coords)
                # After we're done with all other spaces, we can replace the current space's adjacency list as well...
                new_piece_adjacencies[board_space.coords] = plist(adjacent_to_current_space)
                # [new_piece_adjacencies] is done, so we can replace the adjacency mapping for [piece_typ]...
                new_adjacencies[piece_typ] = pmap(new_piece_adjacencies)
            # And finally replace the player's piece-adjacencies mapping.
            player = attr.evolve(player, adjacencies=pmap(new_adjacencies))
        return game_state.set_player(player)

    @staticmethod
    def deploy_mech(game_state, player, mech_type, board_coords):
        assert mech_type.value not in player.mechs
        logging.debug(f'{player} deploys {mech_type} mech to {board_coords}')
        mk = mech_key(player.faction_name(), mech_type)
        board_space = game_state.board.get_space(board_coords)
        board = game_state.board.set_space(board_space.add_mech(mech_key))
        if mech_type == MechType.RIVERWALK:
            adjacencies = GameState.add_riverwalk_adjacencies(game_state, player)
        elif mech_type == MechType.TELEPORT:
            adjacencies = GameState.add_teleport_adjacencies(game_state, player)
        else:
            adjacencies = player.adjacencies
        player = attr.evolve(player, mechs=player.mechs.add(mech_type.value), adjacencies=adjacencies)

        if not player.can_deploy():
            stars = player.stars.achieve(StarType.MECH)
            player = attr.evolve(player, stars=stars)

        return attr.evolve(game_state.set_player(player), board=board)

    @staticmethod
    def available_resources(game_state, player, resource_typ):
        return sum([game_state.board.get_space(coords).amount_of(resource_typ)
                    for coords in GameState.controlled_spaces(game_state, player)])

    @staticmethod
    def has_no_resources(game_state, player):
        for r in ResourceType:
            if GameState.available_resources(game_state, player, r):
                return False
        return True

    @staticmethod
    def resource_pair_count(game_state, player):
        num_resources = sum([GameState.available_resources(game_state, player, r) for r in ResourceType])
        return int(num_resources / 2)

    @staticmethod
    def can_pay_cost(game_state, player, cost):
        if not cost:
            return True
        total_combat_cards = player.total_combat_cards()
        if not (player.power >= cost.power
                and player.popularity >= cost.popularity
                and player.coins >= cost.coins
                and total_combat_cards >= cost.combat_cards):
            return False
        if player.faction_name() is FactionName.CRIMEA:
            has_extra_combat_cards = total_combat_cards - cost.combat_cards > 0
            num_missing_resources = sum([GameState.available_resources(game_state, player, resource_typ)
                                         - cost.resource_cost[resource_typ]
                                         for resource_typ in ResourceType])
            return has_extra_combat_cards and num_missing_resources <= 1
        else:
            return all([GameState.available_resources(game_state, player, resource_typ)
                        >= cost.resource_cost[resource_typ]
                        for resource_typ in ResourceType])

    @staticmethod
    def mill_space(game_state, player):
        if StructureType.MILL in player.structures:
            return game_state.board.get_space(game_state.pieces_by_key[(PieceType.STRUCTURE,
                                                                        player.faction_name(),
                                                                        StructureType.MILL.value)].board_coords)
        return None

    @staticmethod
    def produceable_spaces(game_state, player):
        coords = GameState.board_coords_with_workers(game_state, player)
        spaces = set(map(game_state.board.get_space, coords))
        mill_space = player.mill_space()
        if mill_space:
            spaces.add(mill_space)
        to_remove = []
        for space in spaces:
            if space.produced_this_turn \
                    or space.terrain_typ is TerrainType.LAKE \
                    or space.terrain_typ is TerrainType.VILLAGE and not player.available_workers():
                to_remove.append(space)
        for space in to_remove:
            spaces.remove(space)
        return list(spaces)

    @staticmethod
    def movable_pieces(game_state, player):
        s = set()
        for worker_id in player.workers:
            worker = game_state.pieces_by_key[worker_key(player.faction_name(), worker_id)]
            if game_state.board.get_space(worker.board_coords).terrain_typ is not TerrainType.LAKE:
                s.add(worker)
        for mech_id in player.mechs:
            s.add(game_state.pieces_by_key[mech_key(player.faction_name(), mech_id)])
        s.add(game_state.pieces_by_key[character_key(player.faction_name())])
        return [piece for piece in s if not piece.moved_this_turn]

    @staticmethod
    def effective_adjacent_space_coords(game_state, piece_key):
        piece = game_state.pieces_by_key[piece_key]
        player = game_state.players_by_idx[game_state.player_idx_by_faction_name[piece.faction_name]]
        adjacent_space_coords = player.adjacencies[piece.typ][piece.board_coords]
        assert piece.board_space.coords not in adjacent_space_coords
        if MechType.TELEPORT.value in player.mechs and piece.is_plastic():
            extra_adjacent_space_coords = player.faction.extra_adjacent_space_coords(piece, game_state.board)
            assert piece.board_space.coords not in extra_adjacent_space_coords
            for coords in extra_adjacent_space_coords:
                if coords not in adjacent_space_coords:
                    adjacent_space_coords = adjacent_space_coords.cons(coords)
            return adjacent_space_coords
        elif piece.is_worker():
            adjacent_space_coords_without_enemies = []
            for coords in adjacent_space_coords:
                space = game_state.board.get_space(coords)
                controller = space.controller()
                if controller is None or controller is player.faction_name():
                    adjacent_space_coords_without_enemies.append(space)
            return plist(adjacent_space_coords_without_enemies)
        else:
            return adjacent_space_coords

    @staticmethod
    def end_turn(game_state, player):
        logging.debug(f'{player} ends their turn')
        pieces_by_key = game_state.pieces_by_key
        faction_name = player.faction_name()
        ck = character_key(faction_name)
        character = pieces_by_key[ck]
        if character.moved_this_turn:
            character = attr.evolve(character, moved_this_turn=False, moved_into_enemy_territory_this_turn=False)
            pieces_by_key = pieces_by_key.set(ck, character)
        for worker in player.workers:
            wk = worker_key(faction_name, worker)
            worker = pieces_by_key[wk]
            if worker.moved_this_turn:
                worker = attr.evolve(worker, moved_this_turn=False, moved_into_enemy_territory_this_turn=False)
                pieces_by_key = pieces_by_key.set(wk, worker)
        for mech in player.mechs:
            mk = mech_key(faction_name, mech)
            mech = pieces_by_key[mk]
            if mech.moved_this_turn:
                mech = attr.evolve(mech, moved_this_turn=False, moved_into_enemy_territory_this_turn=False)
                pieces_by_key = pieces_by_key.set(mk, mech)
        if faction_name is FactionName.CRIMEA:
            faction = attr.evolve(player.faction, spent_combat_card_as_resource_this_turn=False)
            player = attr.evolve(player, faction=faction)
            game_state = game_state.set_player(player)

        return attr.evolve(game_state, pieces_by_key=pieces_by_key)

    @staticmethod
    def move_piece(game_state, piece, to_coords):
        board = game_state.board
        logging.debug(f'{piece} moves from {piece.board_coords} to {to_coords}')
        piece_key = piece.key()
        old_space = board.get_space(piece.board_coords).remove_piece(piece_key)
        new_space = board.get_space(to_coords).add_piece(piece_key)
        piece = attr.evolve(piece, board_coords=to_coords)
        board = board.set_space(old_space).set_space(new_space)
        pieces_by_key = game_state.pieces_by_key.set(piece_key, piece)
        return attr.evolve(game_state, board=board, pieces_by_key=pieces_by_key)