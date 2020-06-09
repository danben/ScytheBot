from game import constants
from game.actions import Boolean, BottomAction, LoadResources, LoadWorkers,  MaybePayCost, MovePieceOneSpace, Optional
from game.types import Benefit, BottomActionType, FactionName, ResourceType, StarType, StructureType, TopActionType
import game.state_change as sc
import game.encoders.actions as encode_actions

from collections import defaultdict
import attr
import numpy as np


@attr.s(frozen=True, slots=True)
class EncodedPlayerMat:
    name = attr.ib()
    top_action_cubes = attr.ib()
    bottom_action_costs_and_recruits = attr.ib()
    last_action_spot_taken = attr.ib(default=None)


def encode_top_action_cubes(top_action_cubes_and_structures_by_top_action_typ):
    ret = np.zeros(constants.NUM_UPGRADE_CUBES)
    for x in TopActionType:
        top_action_cubes_and_structure = top_action_cubes_and_structures_by_top_action_typ[x]
        for i, c in enumerate(range(top_action_cubes_and_structure.num_cubes)):
            if top_action_cubes_and_structure.cubes_upgraded[c]:
                ret[i] = 1
    return ret


def encode_bottom_action_costs_and_recruits(has_enlisted_by_bottom_action_typ, bottom_spaces_by_bottom_action_typ,
                                            action_spaces):
    ret = np.zeros(8)  # 2 * number of action spaces on the board
    for b in BottomActionType:
        # encode cost and whether or not this recruit is enlisted
        bottom_action = action_spaces[bottom_spaces_by_bottom_action_typ[b]][1]
        ret[2 * (b.value - 1)] = bottom_action.current_cost / constants.MAX_BOTTOM_ACTION_COST
        if has_enlisted_by_bottom_action_typ[b]:
            ret[(2 * (b.value - 1)) + 1] = 1
    return ret


def encode_player_mat(player_mat):
    name_encoding = np.zeros(constants.NUM_PLAYER_MATS)
    name_encoding[player_mat.name.value - 1] = 1
    return EncodedPlayerMat(name_encoding,
                            encode_top_action_cubes(player_mat.top_action_cubes_and_structures_by_top_action_typ),
                            encode_bottom_action_costs_and_recruits(player_mat.has_enlisted_by_bottom_action_typ,
                                                                    player_mat.bottom_spaces_by_bottom_action_typ,
                                                                    player_mat.action_spaces),
                            player_mat.last_action_spot_taken)


@attr.s(frozen=True, slots=True)
class EncodedPlayer:
    player_mat = attr.ib()
    combat_cards = attr.ib()
    stars = attr.ib()
    enlist_rewards = attr.ib()
    mechs = attr.ib()
    structures = attr.ib()
    misc_data = attr.ib()

    misc_data_size = constants.NUM_FACTIONS + 4  # coins + popularity + power + num_workers


def encode_combat_cards(aggregates):
    ret = np.zeros(constants.MAX_COMBAT_CARD - constants.MIN_COMBAT_CARD + 1)
    for i in range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1):
        ret[i - constants.MIN_COMBAT_CARD] = aggregates[i] / constants.DECK_SIZE
    return ret


# TODO: need to redo stars so that the encoding knows when a player has 2 combat stars
def encode_stars(stars):
    ret = np.zeros(1 + constants.NUM_STAR_TYPES)
    ret[0] = stars.count / 6
    for x in StarType:
        if stars.achieved[x]:
            ret[x.value] = 1
    return ret


def encode_enlist_rewards(enlist_rewards):
    ret = np.zeros(constants.NUM_ENLIST_BENEFITS)
    for x in Benefit:
        if enlist_rewards[x]:
            ret[x.value - 1] = 1
    return ret


def encode_mechs(mech_ids):
    ret = np.zeros(constants.NUM_MECHS)
    for x in mech_ids:
        ret[x-1] = 1
    return ret


def encode_structures(structure_typs):
    ret = np.zeros(constants.NUM_STRUCTURES)
    for x in structure_typs:
        ret[x.value-1] = 1
    return ret


def encode_player(player, as_self):
    num_factions = constants.NUM_FACTIONS
    misc_data = np.zeros(EncodedPlayer.misc_data_size)
    misc_data[player.faction_name().value - 1] = 1
    misc_data[num_factions] = player.coins / 100
    misc_data[num_factions + 1] = player.popularity / constants.MAX_POPULARITY
    misc_data[num_factions + 2] = player.power / constants.MAX_POWER
    misc_data[num_factions + 3] = len(player.worker_ids) / constants.NUM_WORKERS
    combat_cards = encode_combat_cards(player.combat_cards) if as_self else len(player.combat_cards)
    return EncodedPlayer(encode_player_mat(player.player_mat), combat_cards,
                         encode_stars(player.stars), encode_enlist_rewards(player.enlist_rewards),
                         encode_mechs(player.mech_ids), encode_structures(player.structures), misc_data)


def encode_other_players(game_state, index_by_faction_name):
    num_players = len(index_by_faction_name)
    ret = [None] * (num_players - 1)
    current_player_faction_name = game_state.get_current_player().faction_name
    for faction_name, index in index_by_faction_name.values():
        if faction_name is not current_player_faction_name:
            ret[index-1] = encode_player(game_state.players_by_idx[game_state.player_idx_by_faction_name[faction_name]],
                                         as_self=False)

    assert all(ret)
    return ret


@attr.s(frozen=True, slots=True)
class EncodedGameState:
    board = attr.ib()
    home_bases = attr.ib()
    structure_bonus = attr.ib()
    discard_pile = attr.ib()
    current_player = attr.ib()
    other_players = attr.ib()
    top_action = attr.ib()


def encode_discard_pile(combat_cards):
    aggregates = defaultdict(int)
    for card in combat_cards.discard_pile:
        aggregates[card] += 1
    return encode_combat_cards(aggregates)


BOARD_ENCODING__PLANES_PER_PLAYER = 3 + constants.NUM_WORKERS + constants.NUM_MECHS
BOARD_ENCODING__CHARACTER_PLANE = 0
BOARD_ENCODING__STRUCTURE_PLANE = 1
BOARD_ENCODING__MILL_PLANE = 2
BOARD_ENCODING__WORKER_PLANE__START = 3
BOARD_ENCODING__MECH_PLANE__START = BOARD_ENCODING__WORKER_PLANE__START + constants.NUM_WORKERS
BOARD_ENCODING__TUNNELS_PLANE = BOARD_ENCODING__PLANES_PER_PLAYER * constants.MAX_PLAYERS
BOARD_ENCODING__ENCOUNTERS_PLANE = BOARD_ENCODING__TUNNELS_PLANE + 1
BOARD_ENCODING__OIL_PLANE = BOARD_ENCODING__TUNNELS_PLANE + 2
BOARD_ENCODING__WOOD_PLANE = BOARD_ENCODING__TUNNELS_PLANE + 3
BOARD_ENCODING__METAL_PLANE = BOARD_ENCODING__TUNNELS_PLANE + 4
BOARD_ENCODING__FOOD_PLANE = BOARD_ENCODING__TUNNELS_PLANE + 5
BOARD_ENCODING__EXTRA_PLANES = 6 # tunnels, encounters and each of the four resource types
BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE = 20

BOARD_ENCODING__RESOURCE_PLANES = {
    ResourceType.OIL: BOARD_ENCODING__OIL_PLANE,
    ResourceType.METAL: BOARD_ENCODING__METAL_PLANE,
    ResourceType.WOOD: BOARD_ENCODING__WOOD_PLANE,
    ResourceType.FOOD: BOARD_ENCODING__FOOD_PLANE
}


def encode_space(board, index_by_faction_name, space):
    row, col = space.coords
    if space._has_tunnel:
        board[BOARD_ENCODING__TUNNELS_PLANE][row][col] = 1
    if space.has_encounter and not space.encounter_used:
        board[BOARD_ENCODING__ENCOUNTERS_PLANE][row][col] = 1
    if space.structure_key:
        start_plane = index_by_faction_name[space.structure_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[start_plane + BOARD_ENCODING__STRUCTURE_PLANE][row][col] = 1
        if space.structure_key.id == StructureType.MINE:
            board[BOARD_ENCODING__TUNNELS_PLANE][row][col] = 1
    for character_key in space.character_keys:
        start_plane = index_by_faction_name[character_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[start_plane + BOARD_ENCODING__CHARACTER_PLANE][row][col] = 1
    for mech_key in space.mech_keys:
        start_plane = index_by_faction_name[mech_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[start_plane + BOARD_ENCODING__MECH_PLANE__START + mech_key.id - 1][row][col] = 1
    for worker_key in space.worker_keys:
        start_plane = index_by_faction_name[worker_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[start_plane + BOARD_ENCODING__WORKER_PLANE__START + worker_key.id - 1][row][col] = 1
    for resource_typ, amt in space.resources.items():
        board[BOARD_ENCODING__RESOURCE_PLANES[resource_typ]] = amt / BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE


def encode_home_base(home_bases, index_by_faction_name, space):
    start_plane = index_by_faction_name[FactionName(space.coords[1])] * BOARD_ENCODING__PLANES_PER_PLAYER
    if space.character_keys:
        home_bases[start_plane + BOARD_ENCODING__CHARACTER_PLANE] = 1
    for mech_key in space.mech_keys:
        home_bases[start_plane + BOARD_ENCODING__MECH_PLANE__START + mech_key.id - 1] = 1
    for worker_key in space.worker_keys:
        home_bases[start_plane + BOARD_ENCODING__WORKER_PLANE__START + worker_key.id - 1] = 1


def encode_board(game_state, index_by_faction_name):
    player_planes = constants.MAX_PLAYERS * BOARD_ENCODING__PLANES_PER_PLAYER
    num_planes = player_planes + BOARD_ENCODING__EXTRA_PLANES
    board = np.zeros((num_planes, constants.BOARD_ROWS, constants.BOARD_COLS))
    home_bases = np.zeros(player_planes)
    for space in game_state.board.board_spaces_by_coords.values():
        row, col = space.coords
        if row == -1:
            # This is a home base
            encode_home_base(home_bases, index_by_faction_name, space)
        else:
            encode_space(board, index_by_faction_name, space)
    return board, home_bases


def action_num(action):
    return encode_actions.action_constants[type(action)]


def encode_piece_key(piece_encoding, piece_key):
    piece_encoding[piece_key.faction_name.value - 1] = 1
    piece_encoding[constants.NUM_FACTIONS + piece_key.piece_typ.value - 1] = 1
    piece_encoding[constants.NUM_FACTIONS + constants.NUM_PIECE_TYPES + piece_key.id - 1] = 1


def encode_context(top_action, actions_encoding, piece_encoding):
    if isinstance(top_action, Boolean):
        choice_1 = action_num(top_action.action1)
        choice_2 = action_num(top_action.action2)
        actions_encoding[encode_actions.num_encodable_actions + choice_1] = 1
        actions_encoding[encode_actions.num_encodable_actions * 2 + choice_2] = 1
    elif isinstance(top_action, Optional):
        maybe_action = action_num(top_action.action)
        actions_encoding[encode_actions.num_encodable_actions + maybe_action] = 1
    elif isinstance(top_action, BottomAction):
        maybe_action = action_num(top_action.if_paid.action_benefit)
        actions_encoding[encode_actions.num_encodable_actions + maybe_action] = 1
    elif isinstance(top_action, MaybePayCost):
        if_paid_action = action_num(top_action.if_paid)
        actions_encoding[encode_actions.num_encodable_actions + if_paid_action] = 1
    elif isinstance(top_action, LoadResources):
        encode_piece_key(piece_encoding, top_action.piece_key)
    elif isinstance(top_action, LoadWorkers):
        encode_piece_key(piece_encoding, top_action.mech_key)
    elif isinstance(top_action, MovePieceOneSpace):
        encode_piece_key(piece_encoding, top_action.piece_key)
    else:
        assert False


def encode_top_action(top_action):
    actions_encoding = np.zeros(3 * encode_actions.num_encodable_actions)
    piece_encoding = np.zeros(constants.NUM_FACTIONS + constants.NUM_PIECE_TYPES + constants.NUM_WORKERS)
    top_action_typ = type(top_action)
    actions_encoding[encode_actions.action_constants[top_action_typ]] = 1
    if top_action_typ in encode_actions.choices_that_need_context:
        encode_context(top_action, actions_encoding, piece_encoding)
    return actions_encoding, piece_encoding


# Encode players in the following order: self, player to my right, player to my left,
# everyone else in player order
def get_indices_by_faction_name(game_state):
    ret = {game_state.get_current_player().faction_name: 0}
    num_players = len(game_state.players_by_idx)
    right_player_idx = (game_state.current_player_idx + 1) % num_players
    ret[game_state.players_by_idx[right_player_idx].faction_name] = 1
    if num_players > 2:
        left_player_idx = (game_state.current_player_idx - 1) % num_players
        ret[game_state.players_by_idx[left_player_idx].faction_name] = 2

        ctr = 3
        for idx in range(game_state.current_player_idx + 2, game_state.current_player_idx + num_players - 1):
            ret[game_state.players_by_idx[idx % num_players].faction_name] = ctr
            ctr += 1

    assert len(ret) == num_players - 1
    return ret


def encode(game_state):
    indices_by_faction_name = get_indices_by_faction_name(game_state)
    board, home_bases = encode_board(game_state, indices_by_faction_name)
    return EncodedGameState(board,
                            home_bases,
                            game_state.structure_bonus.value,
                            encode_discard_pile(game_state.combat_cards),
                            encode_player(sc.get_current_player(game_state), as_self=True),
                            encode_other_players(game_state, indices_by_faction_name),
                            encode_top_action(game_state.action_stack.first))