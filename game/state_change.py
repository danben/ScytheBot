import game.actions.action as action
import game.components.piece as gc_piece
import game.constants as constants
from game.exceptions import GameOver
from game.types import Benefit, BottomActionType, FactionName, MechType, PieceType, ResourceType, StarType, \
    StructureType, TerrainType

import attr
import logging

from pyrsistent import pmap, pset, thaw, PVector


def push_action(game_state, to_push):
    if not isinstance(to_push, action.Action):
        raise Exception("bad")
    return attr.evolve(game_state, action_stack=game_state.action_stack.cons(to_push))


def pop_action(game_state):
    top_action = game_state.action_stack.first
    if top_action:
        game_state = attr.evolve(game_state, action_stack=game_state.action_stack.rest)
        return game_state, top_action
    else:
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

    faction_name = player.faction_name()
    ret = set()
    for piece_id in id_set:
        piece = game_state.pieces_by_key[gc_piece.PieceKey(piece_typ, faction_name, piece_id)]
        ret.add(piece.board_coords)
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
    if len(candidates) > 2:
        logging.error(f'Multiple controller candidates on space {board_space}: {candidates}')
        assert False
    if len(candidates) == 2:
        candidates.discard(get_current_player(game_state).faction_name())
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


# TODO: optimize this. Possibly cache the controller on spaces, though that doesn't
# seem to be the main slowness culprit.
def controlled_spaces(game_state, player):
    player_faction = player.faction_name()
    s = board_coords_with_workers(game_state, player) | \
        board_coords_with_mechs(game_state, player)
    s.add(game_state.pieces_by_key[gc_piece.character_key(player_faction)].board_coords)
    s.discard(player.home_base)
    s = set(map(game_state.board.get_space, s))
    to_remove = []
    for space in s:
        if controller(game_state, space) is not player_faction:
            to_remove.append(space)
    for space in to_remove:
        s.remove(space)
    to_add = []
    for coords in board_coords_with_structures(game_state, player):
        space = game_state.board.get_space(coords)
        if controller(game_state, space) is player_faction:
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
                                                   gc_piece.structure_key(player.faction_name(), structure_typ)))
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


def add_popularity(game_state, player, popularity):
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} receives {popularity} popularity')
    player = attr.evolve(player, popularity=min(player.popularity + popularity, constants.MAX_POPULARITY))
    game_state = set_player(game_state, player)
    if player.popularity == constants.MAX_POPULARITY:
        game_state = achieve(game_state, player, StarType.POPULARITY)
    return game_state


def remove_popularity(game_state, player, popularity):
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} loses {popularity} popularity')
    player = attr.evolve(player, popularity=max(player.popularity - popularity, 0))
    return set_player(game_state, player)


def add_coins(game_state, player, coins):
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} receives {coins} coins')
    player = attr.evolve(player, coins=player.coins+coins)
    return set_player(game_state, player)


def remove_coins(game_state, player, coins):
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} loses {coins} coins')
    player = attr.evolve(player, coins=max(player.coins - coins, 0))
    return set_player(game_state, player)


def add_power(game_state, player, power):
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} receives {power} power')
    new_power = min(player.power + power, constants.MAX_POWER)
    player = attr.evolve(player, power=new_power)
    game_state = set_player(game_state, player)
    if new_power == constants.MAX_POWER:
        game_state = achieve(game_state, player, StarType.POWER)
    return game_state


def remove_power(game_state, player, power):
    player = attr.evolve(player, power=max(player.power - power, 0))
    return set_player(game_state, player)


def add_combat_cards(game_state, player, cards):
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} receives {len(cards)} combat cards')
    combat_cards = thaw(player.combat_cards)
    for card in cards:
        combat_cards[card] += 1
    player = attr.evolve(player, combat_cards=pmap(combat_cards))
    return set_player(game_state, player)


def discard_combat_card(game_state, player, card_value):
    assert player.combat_cards[card_value]
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} discards a combat card with value {card_value}')
    combat_cards = player.combat_cards.set(card_value, player.combat_cards[card_value] - 1)
    player = attr.evolve(player, combat_cards=combat_cards)
    combat_cards = game_state.combat_cards.discard(card_value)
    game_state = set_player(game_state, player)
    return attr.evolve(game_state, combat_cards=combat_cards)


def discard_lowest_combat_cards(game_state, player, num_cards):
    lowest = constants.MIN_COMBAT_CARD
    for i in range(num_cards):
        while not player.combat_cards[lowest]:
            lowest += 1
        if lowest > constants.MAX_COMBAT_CARD:
            assert False
        game_state = game_state.discard_combat_card(game_state, player, lowest)
    return game_state


def give_reward_to_player(game_state, player, benefit, amt):
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'Receive {amt} {benefit}')
    if benefit is Benefit.POPULARITY:
        return add_popularity(game_state, player, amt)
    elif benefit is Benefit.COINS:
        return add_coins(game_state, player, amt)
    elif benefit is Benefit.POWER:
        return add_power(game_state, player, amt)
    elif benefit is Benefit.COMBAT_CARDS:
        combat_cards, new_cards = game_state.combat_cards.draw(amt)
        game_state = attr.evolve(game_state, combat_cards=combat_cards)
        return add_combat_cards(game_state, player, new_cards)

    assert False


def charge_player(game_state, player, cost):
    assert can_pay_cost(game_state, player, cost)
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'Pay {cost}')
    if cost.coins:
        game_state = remove_coins(game_state, player, cost.coins)
    if cost.power:
        game_state = remove_power(game_state, player, cost.power)
    if cost.popularity:
        game_state = remove_popularity(game_state, player, cost.popularity)
    if cost.combat_cards:
        game_state = discard_lowest_combat_cards(game_state, player, cost.combat_cards)
    for resource_typ in ResourceType:
        amount_owned = available_resources(game_state, player, resource_typ)
        amount_owed = cost.resource_cost[resource_typ]
        if amount_owned > amount_owed:
            for _ in range(amount_owed):
                game_state = push_action(game_state, action.SpendAResource.new(player.id, resource_typ))
        else:
            assert amount_owned == cost.resource_cost[resource_typ]
            game_state = remove_all_of_this_resource(game_state, player, resource_typ)

    return game_state


def achieve(game_state, player, star_typ):
    stars = player.stars
    if stars.achieved[star_typ] < stars.limits[star_typ]:
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'Star achieved: {star_typ}')
        assert stars.count <= constants.MAX_STARS
        stars = attr.evolve(stars, count=stars.count+1,
                            achieved=stars.achieved.set(star_typ, stars.achieved[star_typ]+1))
        player = attr.evolve(player, stars=stars)
        game_state = set_player(game_state, player)
        if stars.count == constants.MAX_STARS:
            raise GameOver(game_state)
        return game_state
    else:
        return game_state


def add_workers(game_state, player, coords, amt):
    max_worker_id = max(player.worker_ids) if player.worker_ids else -1
    if max_worker_id is None:
        assert False
    if amt is None:
        assert False
    ids = list(range(max_worker_id+1, max_worker_id+amt+1))
    space = game_state.board.get_space(coords)
    for worker_id in ids:
        assert len(player.worker_ids) < constants.NUM_WORKERS and worker_id not in player.worker_ids
        worker_ids = player.worker_ids.add(worker_id)
        player = attr.evolve(player, worker_ids=worker_ids)
        game_state = set_player(game_state, player)
        piece_key = gc_piece.worker_key(player.faction_name(), worker_id)
        space = space.add_piece(piece_key)
        piece = attr.evolve(game_state.pieces_by_key[piece_key], board_coords=coords)
        game_state = attr.evolve(game_state, pieces_by_key=game_state.pieces_by_key.set(piece_key, piece))
    board = game_state.board.set_space(space)
    game_state = attr.evolve(game_state, board=board)
    if len(player.worker_ids) == constants.NUM_WORKERS:
        game_state = achieve(game_state, player, StarType.WORKER)
    return game_state


def build_structure(game_state, player, board_coords, structure_typ):
    assert structure_typ not in player.structures
    board_space = game_state.board.get_space(board_coords)
    assert not board_space.has_structure()
    structure_key = gc_piece.structure_key(player.faction_name(), structure_typ)
    board_space = attr.evolve(board_space, structure_key=structure_key)
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
                            adjacent_coords = adjacent_coords.append(board_coords)
                        # And add it to the current spot's adjacency list...
                        if coords not in adjacent_to_current_space:
                            adjacent_to_current_space = adjacent_to_current_space.append(coords)
                    # We're done with this space, so replace its adjacency list in [new_piece_adjacencies]...
                    new_piece_adjacencies[coords] = adjacent_coords
            # After we're done with all other spaces, we can replace the current space's adjacency list as well...
            new_piece_adjacencies[board_coords] = adjacent_to_current_space
            # [new_piece_adjacencies] is done, so we can replace the adjacency mapping for [piece_typ]...
            new_adjacencies[piece_typ] = pmap(new_piece_adjacencies)
        # And finally replace the player's piece-adjacencies mapping.
        player = attr.evolve(player, adjacencies=pmap(new_adjacencies))
    game_state = set_player(game_state, player)
    if not player.has_unbuilt_structures():
        game_state = achieve(game_state, player, StarType.STRUCTURE)
    return game_state


def deploy_mech(game_state, player, mech_typ, board_coords):
    assert mech_typ.value not in player.mech_ids
    mk = gc_piece.mech_key(player.faction_name(), mech_typ.value)
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} deploys {mech_typ} mech to {board_coords} with key {mk}')
    board = game_state.board.add_piece(mk, board_coords)
    game_state = attr.evolve(game_state, board=board)
    try:
        mech = attr.evolve(game_state.pieces_by_key[mk], board_coords=board_coords)
    except KeyError:
        print(game_state.pieces_by_key.keys())
        assert False
    game_state = attr.evolve(game_state, pieces_by_key=game_state.pieces_by_key.set(mk, mech))
    if mech_typ == MechType.RIVERWALK:
        adjacencies = player.faction.add_riverwalk_adjacencies(player.adjacencies, game_state.board)
    elif mech_typ == MechType.TELEPORT:
        adjacencies = player.faction.add_teleport_adjacencies(player.adjacencies, game_state.board)
    else:
        adjacencies = player.adjacencies
    player = attr.evolve(player, mech_ids=player.mech_ids.add(mech_typ.value), adjacencies=adjacencies)
    game_state = set_player(game_state, player)
    if not player.has_undeployed_mechs():
        game_state = achieve(game_state, player, StarType.MECH)
    return game_state


def remove_upgrade_cube(game_state, player, top_action_typ, spot):
    assert player.can_upgrade()
    player = attr.evolve(player, player_mat=player.player_mat.remove_upgrade_cube(top_action_typ, spot))
    game_state = set_player(game_state, player)
    if not player.can_upgrade():
        game_state = achieve(game_state, player, StarType.UPGRADE)
    return game_state


def mark_enlist_benefit(game_state, player, enlist_benefit):
    assert enlist_benefit not in player.enlist_rewards
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{player} takes enlist benefit {enlist_benefit}')
    enlist_rewards = player.enlist_rewards.add(enlist_benefit)
    player = attr.evolve(player, enlist_rewards=enlist_rewards)
    game_state = set_player(game_state, player)
    if not player.can_enlist():
        game_state = achieve(game_state, player, StarType.RECRUIT)
    return game_state


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
    to_remove = []
    for space in spaces:
        if space.produced_this_turn \
                or space.terrain_typ is TerrainType.LAKE \
                or space.terrain_typ is TerrainType.FACTORY \
                or space.terrain_typ is TerrainType.VILLAGE and not player.available_workers()\
                or space.has_structure() and space.structure_key.id is StructureType.MILL.value:
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
        if adjacent_space.contains_no_enemy_plastic(piece.faction_name) \
                and adjacent_space.contains_no_enemy_workers(piece.faction_name):
            ret.append(adjacent_coords)
    return ret


def movable_pieces_debug(game_state, player):
    for worker_id in player.worker_ids:
        worker = game_state.pieces_by_key[gc_piece.worker_key(player.faction_name(), worker_id)]
        if game_state.board.get_space(worker.board_coords).terrain_typ is TerrainType.LAKE:
            print(f'{worker} is on a LAKE so can\'t move')
        if not adjacent_space_coords_without_enemies(game_state, worker):
            print(f'{worker} has no adjacent spaces without enemies')
        if worker.moved_this_turn:
            print(f'{worker} moved this turn')
    for mech_id in player.mech_ids:
        mech = game_state.pieces_by_key[gc_piece.mech_key(player.faction_name(), mech_id)]
        if mech.moved_this_turn:
            print(f'{mech} moved this turn')


def movable_pieces(game_state, player):
    s = set()
    for worker_id in player.worker_ids:
        worker = game_state.pieces_by_key[gc_piece.worker_key(player.faction_name(), worker_id)]
        if (not worker.moved_this_turn) \
                and game_state.board.get_space(worker.board_coords).terrain_typ is not TerrainType.LAKE \
                and adjacent_space_coords_without_enemies(game_state, worker):
            s.add((worker.board_coords, PieceType.WORKER))
    for mech_id in player.mech_ids:
        mech = game_state.pieces_by_key[gc_piece.mech_key(player.faction_name(), mech_id)]
        if not mech.moved_this_turn:
            s.add((mech.board_coords, PieceType.MECH))

    character = game_state.pieces_by_key[gc_piece.character_key(player.faction_name())]
    if not character.moved_this_turn:
        s.add((character.board_coords, PieceType.CHARACTER))
    return s


def effective_adjacent_space_coords(game_state, piece_key):
    piece = game_state.pieces_by_key[piece_key]
    player = game_state.players_by_idx[game_state.player_idx_by_faction_name[piece.faction_name]]
    adjacent_space_coords = player.adjacencies[piece.typ][piece.board_coords]
    assert piece.board_coords not in adjacent_space_coords
    assert isinstance(adjacent_space_coords, PVector)
    if MechType.TELEPORT.value in player.mech_ids and piece.is_plastic():
        extra_adjacent_space_coords = player.faction.extra_adjacent_space_coords(piece, game_state)
        assert piece.board_coords not in extra_adjacent_space_coords
        for coords in extra_adjacent_space_coords:
            if coords not in adjacent_space_coords:
                adjacent_space_coords = adjacent_space_coords.append(coords)
        return thaw(adjacent_space_coords)
    elif piece.is_worker():
        return adjacent_space_coords_without_enemies(game_state, piece)
    else:
        return thaw(adjacent_space_coords)


def end_turn(game_state):
    player = get_current_player(game_state)
    if logging.getLogger().isEnabledFor(logging.DEBUG):
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

    game_state = attr.evolve(game_state, pieces_by_key=pieces_by_key)
    board = game_state.board
    for space_coords in game_state.spaces_produced_this_turn:
        space = attr.evolve(board.get_space(space_coords), produced_this_turn=False)
        board = board.set_space(space)
    next_player_idx = game_state.current_player_idx + 1
    if next_player_idx == len(game_state.players_by_idx):
        next_player_idx = 0
    game_state = attr.evolve(game_state, board=board, current_player_idx=next_player_idx,
                             spaces_produced_this_turn=pset(), num_turns=game_state.num_turns+1)
    return game_state


def move_piece(game_state, piece_key, to_coords):
    board = game_state.board
    piece = game_state.pieces_by_key[piece_key]
    if logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f'{piece_key} moves from {piece.board_coords} to {to_coords}')
    old_space = board.get_space(piece.board_coords).remove_piece(piece_key)
    new_space = board.get_space(to_coords).add_piece(piece_key)
    piece = attr.evolve(piece, board_coords=to_coords)
    board = board.set_space(old_space).set_space(new_space)
    game_state = set_piece(game_state, piece)
    game_state = attr.evolve(game_state, board=board)
    return game_state


def get_piece_by_board_coords_and_piece_typ(game_state, board_coords, piece_typ):
    space = game_state.board.get_space(board_coords)
    faction_name = get_current_player(game_state).faction_name()
    key_set = space.character_keys
    if piece_typ is PieceType.MECH:
        key_set = space.mech_keys
    elif piece_typ is PieceType.WORKER:
        key_set = space.worker_keys
    elif piece_typ is PieceType.STRUCTURE:
        assert False
    for key in key_set:
        if key.faction_name is faction_name:
            return key
    assert False
