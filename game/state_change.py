import game.actions.action as action
from game.types import Benefit, BottomActionType, FactionName, MechType, PieceType, ResourceType, StarType, \
    StructureType, TerrainType
import game.components.piece as gc_piece
import game.constants as constants

import attr
import logging

from pyrsistent import plist, pmap


def push_action(game_state, to_push):
    if not isinstance(to_push, action.Action):
        raise Exception("bad")
    return attr.evolve(game_state, action_stack=game_state.action_stack.cons(to_push))


def pop_action(game_state):
    top_action = game_state.action_stack.first
    if top_action:
        game_state = attr.evolve(game_state, action_stack=game_state.action_stack.rest)
        if isinstance(game_state, tuple):
            raise Exception("very bad")
        return game_state, top_action
    else:
        if isinstance(game_state, tuple):
            raise Exception("almost as bad")
        return game_state, None


def get_current_player(game_state):
    return game_state.players_by_idx[game_state.current_player_idx]


def get_player_by_idx(game_state, i):
    return game_state.players_by_idx[i]


def get_player_by_faction_name(game_state, faction_name):
    return game_state.players_by_idx[game_state.player_idx_by_faction_name[faction_name]]


def get_left_player(game_state):
    new_idx = game_state.current_player_idx - 1
    if new_idx < 0:
        new_idx = len(game_state.players_by_idx) - 1
    return game_state.players_by_idx[new_idx]


def get_right_player(game_state):
    new_idx = game_state.current_player_idx + 1
    if new_idx == len(game_state.players_by_idx):
        new_idx = 0
    return game_state.players_by_idx[new_idx]


def get_board_coords_for_piece_key(game_state, piece_key):
    return game_state.pieces_by_key[piece_key].board_coords


def change_turn(game_state, faction_name):
    return attr.evolve(game_state, current_player_idx=game_state.player_idx_by_faction_name[faction_name])


def set_player(game_state, player):
    return attr.evolve(game_state, players_by_idx=game_state.players_by_idx.set(player.id, player))


def set_piece(game_state, piece):
    return attr.evolve(game_state, pieces_by_key=game_state.pieces_by_key.set(piece.key(), piece))


def _board_coords_with_piece_typ(game_state, player, piece_typ):
    if piece_typ is PieceType.WORKER:
        id_set = player.worker_ids
    elif piece_typ is PieceType.MECH:
        id_set = player.mech_ids
    else:
        assert False

    pieces = [game_state.pieces_by_key[gc_piece.PieceKey(piece_typ, player.faction_name(), piece_id)]
              for piece_id in id_set]

    ret = set([piece.board_coords for piece in pieces])
    ret.discard(player.home_base)
    return ret


def board_coords_with_workers(game_state, player):
    return _board_coords_with_piece_typ(game_state, player, PieceType.WORKER)


def board_coords_with_mechs(game_state, player):
    return _board_coords_with_piece_typ(game_state, player, PieceType.MECH)


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
    if board_space.structure:
        return board_space.structure.faction_name
    return None


def controlled_spaces(game_state, player):
    s = board_coords_with_workers(game_state, player) | \
        board_coords_with_mechs(game_state, player)
    s.add(game_state.pieces_by_key[gc_piece.character_key(player.faction_name())].board_coords)
    s.discard(player.home_base)
    s = set(map(game_state.board.get_space, s))
    to_remove = []
    for space in s:
        if controller(game_state, space) is not player.faction_name():
            to_remove.append(space)
    for space in to_remove:
        s.remove(space)
    to_add = []
    for coords in board_coords_with_structures(game_state, player):
        space = game_state.board.get_space(coords)
        if controller(game_state, space) is player.faction_name():
            to_add.append(space)
    for space in to_add:
        s.add(space)
    return s


def territory_count(game_state, player):
    s = controlled_spaces(game_state, player)
    ret = len(s)
    for space in s:
        if space.coords == (3, 3):
            return ret + 2
    return ret


def controlled_spaces_with_resource(game_state, player, resource_typ):
    return [space for space in controlled_spaces(game_state, player)
            if space.has_resource(resource_typ)]


def board_coords_with_structures(game_state, player):
    ret = set()
    for structure_typ in StructureType:
        if structure_typ in player.structures:
            ret.add(get_board_coords_for_piece_key(game_state,
                                                   gc_piece.PieceKey(PieceType.STRUCTURE,
                                                                     player.faction_name(),
                                                                     structure_typ.value)))
    return ret


def legal_building_spots(game_state, player):
    ret = []
    for coords in board_coords_with_workers(game_state, player):
        space = game_state.board.get_space(coords)
        if not (space.has_structure() or space.terrain_typ is TerrainType.LAKE):
            assert space.terrain_typ is not TerrainType.HOME_BASE
            ret.append(coords)
    return ret


def can_build(game_state, player):
    return player.has_unbuilt_structures() and legal_building_spots(game_state, player)


def can_deploy(game_state, player):
    return player.has_undeployed_mechs() and board_coords_with_workers(game_state, player)


def can_legally_receive_action_benefit(game_state, player, bottom_action_typ):
    if bottom_action_typ is BottomActionType.ENLIST:
        return player.can_enlist()
    elif bottom_action_typ is BottomActionType.DEPLOY:
        return can_deploy(game_state, player)
    elif bottom_action_typ is BottomActionType.BUILD:
        return can_build(game_state, player)
    elif bottom_action_typ is BottomActionType.UPGRADE:
        return player.can_upgrade()
    else:
        assert False


def add_resources_to_space(game_state, coords, resource_typ, amt):
    board = game_state.board
    board_space = board.board_spaces_by_coords[coords].add_resources(resource_typ, amt)
    assert board_space.terrain_typ is not TerrainType.HOME_BASE
    board = attr.evolve(board, board_spaces_by_coords=board.board_spaces_by_coords.set(coords, board_space))
    return attr.evolve(game_state, board=board)


def remove_all_of_this_resource(game_state, player, resource_typ):
    board = game_state.board
    for space in controlled_spaces_with_resource(game_state, player, resource_typ):
        board_spaces_by_coords = \
            board.board_spaces_by_coords.set(space.coords,
                                             space.remove_resources(resource_typ,
                                                                    space.amount_of(resource_typ)))
        board = attr.evolve(board, board_spaces_by_coords=board_spaces_by_coords)
    return attr.evolve(game_state, board=board)


def charge_player(game_state, player, cost):
    assert can_pay_cost(game_state, player, cost)
    logging.debug(f'Pay {cost}')
    if cost.coins:
        player = player.remove_coins(cost.coins)
    if cost.power:
        player = player.remove_power(cost.power)
    if cost.popularity:
        player = player.remove_popularity(cost.popularity)
    if cost.combat_cards:
        player = player.discard_lowest_combat_cards(cost.combat_cards, game_state.combat_cards)
    for resource_typ in ResourceType:
        amount_owned = available_resources(game_state, player, resource_typ)
        amount_owed = cost.resource_cost[resource_typ]
        if amount_owned > amount_owed:
            for _ in range(amount_owed):
                game_state = push_action(game_state, action.SpendAResource.new(player.id, resource_typ))
        else:
            assert amount_owned == cost.resource_cost[resource_typ]
            game_state = remove_all_of_this_resource(game_state, player, resource_typ)

    return set_player(game_state, player)


def give_reward_to_player(game_state, player, benefit, amt):
    logging.debug(f'Receive {amt} {benefit}')
    if benefit is Benefit.POPULARITY:
        player = player.add_popularity(amt)
    elif benefit is Benefit.COINS:
        player = player.add_coins(amt)
    elif benefit is Benefit.POWER:
        player = player.add_power(amt)
    elif benefit is Benefit.COMBAT_CARDS:
        combat_cards, new_cards = game_state.combat_cards.draw(amt)
        game_state = attr.evolve(game_state, combat_cards=combat_cards)
        player = player.add_combat_cards(new_cards)

    return set_player(game_state, player)


def add_workers(game_state, player, coords, amt):
    max_worker_id = max(player.worker_ids)
    assert max_worker_id + amt < constants.NUM_WORKERS
    ids = list(range(max_worker_id+1, max_worker_id+amt+1))
    game_state = set_player(game_state, player.add_workers(ids))
    space = game_state.board.get_space(coords)
    for i in ids:
        piece_key = gc_piece.PieceKey(PieceType.WORKER, player.faction_name(), i)
        space = space.add_piece(piece_key)
        piece = attr.evolve(game_state.pieces_by_key[piece_key], board_coords=coords)
        game_state = attr.evolve(game_state, pieces_by_key=game_state.pieces_by_key.set(piece_key, piece))
    board = game_state.board.set_space(space)
    return attr.evolve(game_state, board=board)


def build_structure(game_state, player, board_coords, structure_typ):
    assert structure_typ not in player.structures
    board_space = game_state.board.get_space(board_coords)
    assert not board_space.has_structure()
    structure_key = gc_piece.PieceKey(PieceType.STRUCTURE, player.faction_name(), structure_typ.value)
    board_space = attr.evolve(board_space, structure=structure_key)
    game_state = attr.evolve(game_state, board=game_state.board.set_space(board_space))
    structure = attr.evolve(game_state.pieces_by_key[structure_key], board_coords=board_coords)
    game_state = attr.evolve(game_state, pieces_by_key=game_state.pieces_by_key.set(structure_key, structure))
    player_mat = player.player_mat
    top_action_typ = structure_typ.to_top_action_typ()
    top_action_cubes_and_structures =\
        player_mat.top_action_cubes_and_structures_by_top_action_typ[top_action_typ].build_structure()
    player_mat =\
        attr.evolve(player_mat,
                    top_action_cubes_and_structures_by_top_action_typ=player_mat.
                    top_action_cubes_and_structures_by_top_action_typ.set(top_action_typ,
                                                                          top_action_cubes_and_structures
                                                                          ))
    player = attr.evolve(player, structures=player.structures.add(structure_typ), player_mat=player_mat)
    if not player.has_unbuilt_structures():
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
            adjacent_to_current_space = piece_adjacencies[board_coords]
            # By iterating over every space on the board...
            for coords, adjacent_coords in piece_adjacencies.items():
                # And if it isn't the spot we're building on...
                if coords != board_coords:
                    other_space = game_state.board.board_spaces_by_coords[coords]
                    # Check if it has a tunnel...
                    if other_space.has_tunnel(player.faction_name()):
                        # If so, add the current spot to its adjacency list...
                        if board_coords not in adjacent_coords:
                            adjacent_coords = adjacent_coords.cons(board_coords)
                        # And add it to the current spot's adjacency list...
                        if coords not in adjacent_to_current_space:
                            adjacent_to_current_space = adjacent_to_current_space.cons(coords)
                    # We're done with this space, so replace its adjacency list in [new_piece_adjacencies]...
                    new_piece_adjacencies[coords] = adjacent_coords
            # After we're done with all other spaces, we can replace the current space's adjacency list as well...
            new_piece_adjacencies[board_coords] = adjacent_to_current_space
            # [new_piece_adjacencies] is done, so we can replace the adjacency mapping for [piece_typ]...
            new_adjacencies[piece_typ] = pmap(new_piece_adjacencies)
        # And finally replace the player's piece-adjacencies mapping.
        player = attr.evolve(player, adjacencies=pmap(new_adjacencies))
    return set_player(game_state, player)


def deploy_mech(game_state, player, mech_type, board_coords):
    assert mech_type.value not in player.mech_ids
    mk = gc_piece.mech_key(player.faction_name(), mech_type.value)
    logging.debug(f'{player} deploys {mech_type} mech to {board_coords} with key {mk}')
    board = game_state.board.add_piece(mk, board_coords)
    game_state = attr.evolve(game_state, board=board)
    mech = attr.evolve(game_state.pieces_by_key[mk], board_coords=board_coords)
    game_state = attr.evolve(game_state, pieces_by_key=game_state.pieces_by_key.set(mk, mech))
    if mech_type == MechType.RIVERWALK:
        adjacencies = player.faction.add_riverwalk_adjacencies(player.adjacencies, game_state.board)
    elif mech_type == MechType.TELEPORT:
        adjacencies = player.faction.add_teleport_adjacencies(player.adjacencies, game_state.board)
    else:
        adjacencies = player.adjacencies
    player = attr.evolve(player, mech_ids=player.mech_ids.add(mech_type.value), adjacencies=adjacencies)

    if not player.has_undeployed_mechs():
        stars = player.stars.achieve(StarType.MECH)
        player = attr.evolve(player, stars=stars)
        player = attr.evolve(player, stars=stars)
    return set_player(game_state, player)


def available_resources(game_state, player, resource_typ):
    return sum([game_state.board.get_space(space.coords).amount_of(resource_typ)
                for space in controlled_spaces(game_state, player)])


def has_no_resources(game_state, player):
    for r in ResourceType:
        if available_resources(game_state, player, r):
            return False
    return True


def resource_pair_count(game_state, player):
    num_resources = sum([available_resources(game_state, player, r) for r in ResourceType])
    return int(num_resources / 2)


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
        num_missing_resources = sum([available_resources(game_state, player, resource_typ)
                                     - cost.resource_cost[resource_typ]
                                     for resource_typ in ResourceType])
        return has_extra_combat_cards and num_missing_resources <= 1
    else:
        return all([available_resources(game_state, player, resource_typ)
                    >= cost.resource_cost[resource_typ]
                    for resource_typ in ResourceType])


def mill_space(game_state, player):
    if StructureType.MILL in player.structures:
        mill = game_state.pieces_by_key[gc_piece.structure_key(player.faction_name(), StructureType.MILL)]
        return game_state.board.get_space(mill.board_coords)
    return None


def produceable_space_coords(game_state, player):
    coords = board_coords_with_workers(game_state, player)
    spaces = set(map(game_state.board.get_space, coords))
    player_mill_space = mill_space(game_state, player)
    if player_mill_space:
        spaces.add(player_mill_space)
    to_remove = []
    for space in spaces:
        if space.produced_this_turn \
                or space.terrain_typ is TerrainType.LAKE \
                or space.terrain_typ is TerrainType.FACTORY \
                or space.terrain_typ is TerrainType.VILLAGE and not player.available_workers():
            to_remove.append(space)
    for space in to_remove:
        spaces.remove(space)
    return list(map(lambda x: x.coords, list(spaces)))


def adjacent_space_coords_without_enemies(game_state, piece):
    player = get_player_by_faction_name(game_state, piece.faction_name)
    adjacent_space_coords = player.adjacencies[PieceType.WORKER][piece.board_coords]
    ret = []
    for adjacent_coords in adjacent_space_coords:
        adjacent_space = game_state.board.get_space(adjacent_coords)
        space_controller = controller(game_state, adjacent_space)
        if space_controller is None or space_controller is player.faction_name():
            ret.append(adjacent_coords)
    return ret


def movable_pieces(game_state, player):
    s = set()
    for worker_id in player.worker_ids:
        worker = game_state.pieces_by_key[gc_piece.worker_key(player.faction_name(), worker_id)]
        if game_state.board.get_space(worker.board_coords).terrain_typ is not TerrainType.LAKE \
                and adjacent_space_coords_without_enemies(game_state, worker):
            s.add(worker)
    for mech_id in player.mech_ids:
        s.add(game_state.pieces_by_key[gc_piece.mech_key(player.faction_name(), mech_id)])
    s.add(game_state.pieces_by_key[gc_piece.character_key(player.faction_name())])
    return [piece for piece in s if not piece.moved_this_turn]


def effective_adjacent_space_coords(game_state, piece_key):
    piece = game_state.pieces_by_key[piece_key]
    player = game_state.players_by_idx[game_state.player_idx_by_faction_name[piece.faction_name]]
    adjacent_space_coords = player.adjacencies[piece.typ][piece.board_coords]
    assert piece.board_coords not in adjacent_space_coords
    if MechType.TELEPORT.value in player.mech_ids and piece.is_plastic():
        extra_adjacent_space_coords = player.faction.extra_adjacent_space_coords(piece, game_state)
        assert piece.board_coords not in extra_adjacent_space_coords
        for coords in extra_adjacent_space_coords:
            if coords not in adjacent_space_coords:
                adjacent_space_coords = adjacent_space_coords.cons(coords)
        return adjacent_space_coords
    elif piece.is_worker():
        return plist(adjacent_space_coords_without_enemies(game_state, piece))
    else:
        return adjacent_space_coords


def end_turn(game_state, player):
    logging.debug(f'{player} ends their turn')
    pieces_by_key = game_state.pieces_by_key
    faction_name = player.faction_name()
    ck = gc_piece.character_key(faction_name)
    character = pieces_by_key[ck]
    if character.moved_this_turn:
        character = attr.evolve(character, moved_this_turn=False, moved_into_enemy_territory_this_turn=False)
        pieces_by_key = pieces_by_key.set(ck, character)
    for worker_id in player.worker_ids:
        wk = gc_piece.worker_key(faction_name, worker_id)
        worker = pieces_by_key[wk]
        if worker.moved_this_turn:
            worker = attr.evolve(worker, moved_this_turn=False, moved_into_enemy_territory_this_turn=False)
            pieces_by_key = pieces_by_key.set(wk, worker)
    for mech_id in player.mech_ids:
        mk = gc_piece.mech_key(faction_name, mech_id)
        mech = pieces_by_key[mk]
        if mech.moved_this_turn:
            mech = attr.evolve(mech, moved_this_turn=False, moved_into_enemy_territory_this_turn=False)
            pieces_by_key = pieces_by_key.set(mk, mech)
    if faction_name is FactionName.CRIMEA:
        faction = attr.evolve(player.faction, spent_combat_card_as_resource_this_turn=False)
        player = attr.evolve(player, faction=faction)
        game_state = set_player(game_state, player)

    return attr.evolve(game_state, pieces_by_key=pieces_by_key)


def move_piece(game_state, piece_key, to_coords):
    board = game_state.board
    piece = game_state.pieces_by_key[piece_key]
    logging.debug(f'{piece_key} moves from {piece.board_coords} to {to_coords}')
    old_space = board.get_space(piece.board_coords).remove_piece(piece_key)
    new_space = board.get_space(to_coords).add_piece(piece_key)
    piece = attr.evolve(piece, board_coords=to_coords)
    board = board.set_space(old_space).set_space(new_space)
    pieces_by_key = game_state.pieces_by_key.set(piece_key, piece)
    game_state = attr.evolve(game_state, board=board, pieces_by_key=pieces_by_key)
    return game_state
