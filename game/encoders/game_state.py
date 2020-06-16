from game import constants
from game.actions import Boolean, BottomAction, GetAttackerCombatCards, GetDefenderCombatCards, LoadResources
from game.actions import LoadWorkers,  MaybePayCost, MovePieceOneSpace, Optional
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

    shape = (constants.NUM_PLAYER_MATS + constants.NUM_UPGRADE_CUBES + 2 * constants.NUM_PLAYER_MAT_ACTION_SPACES
             + constants.NUM_PLAYER_MAT_ACTION_SPACES,)

    NAME_OFFSET = 0
    TOP_ACTION_CUBES_OFFSET = NAME_OFFSET + constants.NUM_PLAYER_MATS
    BOTTOM_ACTION_COSTS_AND_RECRUITS_OFFSET = TOP_ACTION_CUBES_OFFSET + constants.NUM_UPGRADE_CUBES
    LAST_ACTION_SPOT_TAKEN_OFFSET = BOTTOM_ACTION_COSTS_AND_RECRUITS_OFFSET + 2 * constants.NUM_PLAYER_MAT_ACTION_SPACES

    TOP_ACTION_CUBES_OFFSETS_BY_TOP_ACTION_TYPE = {
        TopActionType.BOLSTER: 0,
        TopActionType.PRODUCE: 2,
        TopActionType.MOVEGAIN: 3,
        TopActionType.TRADE: 5
    }

    def encoded_data(self):
        return np.concatenate([self.name, self.top_action_cubes, self.bottom_action_costs_and_recruits,
                              self.last_action_spot_taken])


def encode_top_action_cubes(top_action_cubes_and_structures_by_top_action_typ):
    ret = np.zeros(constants.NUM_UPGRADE_CUBES)
    for x in TopActionType:
        top_action_cubes_and_structure = top_action_cubes_and_structures_by_top_action_typ[x]
        for i, upgraded in enumerate(top_action_cubes_and_structure.cubes_upgraded):
            if upgraded:
                ret[EncodedPlayerMat.TOP_ACTION_CUBES_OFFSETS_BY_TOP_ACTION_TYPE[x] + i] = 1
    return ret


def encode_bottom_action_costs_and_recruits(has_enlisted_by_bottom_action_typ, action_spaces_by_bottom_action_typ,
                                            action_spaces):
    ret = np.zeros(2 * constants.NUM_PLAYER_MAT_ACTION_SPACES)
    for b in BottomActionType:
        # encode cost and whether or not this recruit is enlisted
        bottom_action = action_spaces[action_spaces_by_bottom_action_typ[b]][1]
        ret[2 * b.value] = bottom_action.current_cost / constants.MAX_BOTTOM_ACTION_COST
        if has_enlisted_by_bottom_action_typ[b]:
            ret[2 * b.value + 1] = 1
    return ret


def encode_last_action_spot_taken(last_action_spot_taken):
    ret = np.zeros(constants.NUM_PLAYER_MAT_ACTION_SPACES)
    if last_action_spot_taken is not None:
        ret[last_action_spot_taken] = 1
    return ret


def encode_player_mat(player_mat):
    name_encoding = np.zeros(constants.NUM_PLAYER_MATS)
    name_encoding[player_mat.name.value] = 1
    return EncodedPlayerMat(name_encoding,
                            encode_top_action_cubes(player_mat.top_action_cubes_and_structures_by_top_action_typ),
                            encode_bottom_action_costs_and_recruits(player_mat.has_enlisted_by_bottom_action_typ,
                                                                    player_mat.action_spaces_by_bottom_action_typ,
                                                                    player_mat.action_spaces),
                            encode_last_action_spot_taken(player_mat.last_action_spot_taken))


@attr.s(frozen=True, slots=True)
class EncodedPlayer:
    player_mat = attr.ib()
    combat_cards = attr.ib()
    star_count = attr.ib()
    star_types = attr.ib()
    enlist_rewards = attr.ib()
    mechs = attr.ib()
    structures = attr.ib()
    misc_data = attr.ib()

    misc_data_size = constants.NUM_FACTIONS + 4  # coins + popularity + power + num_workers

    # The first 1 is for the total number of stars that the player has.
    # The second 1 is for the extra spot we reserve for a second combat star.
    shape_as_self = (EncodedPlayerMat.shape[0] + constants.NUM_COMBAT_CARD_VALUES + 1 + constants.NUM_STAR_TYPES + 1 +
                     constants.NUM_ENLIST_BENEFITS + constants.NUM_MECHS + constants.NUM_STRUCTURES + misc_data_size,)

    shape_as_other = (shape_as_self[0] - constants.NUM_COMBAT_CARD_VALUES + 1,)

    PLAYER_MAT_OFFSET = 0
    STAR_COUNT_OFFSET = EncodedPlayerMat.shape[0]
    STAR_TYPES_OFFSET = STAR_COUNT_OFFSET + 1
    ENLIST_REWARDS_OFFSET = STAR_TYPES_OFFSET + 1 + constants.NUM_STAR_TYPES
    MECHS_OFFSET = ENLIST_REWARDS_OFFSET + constants.NUM_ENLIST_BENEFITS
    STRUCTURES_OFFSET = MECHS_OFFSET + constants.NUM_MECHS
    MISC_DATA_OFFSET = STRUCTURES_OFFSET + constants.NUM_STRUCTURES
    MISC_DATA__FACTION_OFFSET = 0
    MISC_DATA__COINS_OFFSET = MISC_DATA__FACTION_OFFSET + constants.NUM_FACTIONS
    MISC_DATA__POPULARITY_OFFSET = MISC_DATA__COINS_OFFSET + 1
    MISC_DATA__POWER_OFFSET = MISC_DATA__POPULARITY_OFFSET + 1
    MISC_DATA__NUM_WORKERS_OFFSET = MISC_DATA__POWER_OFFSET + 1
    COMBAT_CARDS_OFFSET = MISC_DATA_OFFSET + misc_data_size

    def encoded_data(self):
        combat_cards = [self.combat_cards] if isinstance(self.combat_cards, float) else self.combat_cards
        return np.concatenate([self.player_mat.encoded_data(), [self.star_count], self.star_types, self.enlist_rewards,
                               self.mechs, self.structures, self.misc_data, combat_cards])


def encode_combat_cards(aggregates):
    ret = np.zeros(constants.NUM_COMBAT_CARD_VALUES)
    for i in range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1):
        ret[i - constants.MIN_COMBAT_CARD] = aggregates[i] / constants.DECK_SIZE
    return ret


def encode_stars(stars):
    ret = np.zeros(1 + constants.NUM_STAR_TYPES)
    for x in StarType:
        if stars.achieved[x]:
            ret[x.value] = 1

    if stars.achieved[StarType.COMBAT] > 1:
        ret[constants.NUM_STAR_TYPES] = 1

    return ret


def encode_enlist_rewards(enlist_rewards):
    ret = np.zeros(constants.NUM_ENLIST_BENEFITS)
    for x in Benefit:
        if x in enlist_rewards:
            ret[x.value] = 1
    return ret


def encode_mechs(mech_ids):
    ret = np.zeros(constants.NUM_MECHS)
    for x in mech_ids:
        ret[x] = 1
    return ret


def encode_structures(structure_typs):
    ret = np.zeros(constants.NUM_STRUCTURES)
    for x in structure_typs:
        ret[x.value] = 1
    return ret


def encode_player(player, as_self):
    misc_data = np.zeros(EncodedPlayer.misc_data_size)
    misc_data[EncodedPlayer.MISC_DATA__FACTION_OFFSET + player.faction_name().value] = 1
    misc_data[EncodedPlayer.MISC_DATA__COINS_OFFSET] = player.coins / 100
    misc_data[EncodedPlayer.MISC_DATA__POPULARITY_OFFSET] = player.popularity / constants.MAX_POPULARITY
    misc_data[EncodedPlayer.MISC_DATA__POWER_OFFSET] = player.power / constants.MAX_POWER
    misc_data[EncodedPlayer.MISC_DATA__NUM_WORKERS_OFFSET] = len(player.worker_ids) / constants.NUM_WORKERS
    combat_cards = encode_combat_cards(player.combat_cards) if as_self else sum(player.combat_cards.values()) \
        / constants.DECK_SIZE
    return EncodedPlayer(encode_player_mat(player.player_mat), combat_cards,
                         player.stars.count / constants.MAX_STARS, encode_stars(player.stars),
                         encode_enlist_rewards(player.enlist_rewards), encode_mechs(player.mech_ids),
                         encode_structures(player.structures), misc_data)


def encode_other_players(game_state, index_by_faction_name):
    num_players = len(index_by_faction_name)
    ret = [None] * (num_players - 1)
    current_player_faction_name = sc.get_current_player(game_state).faction_name()
    for faction_name, index in index_by_faction_name.items():
        if faction_name is not current_player_faction_name:
            ret[index-1] = encode_player(game_state.players_by_idx[game_state.player_idx_by_faction_name[faction_name]],
                                         as_self=False)

    assert all(ret)
    return ret


BOARD_ENCODING__PLANES_PER_PLAYER = 6
BOARD_ENCODING__CHARACTER_PLANE = 0
BOARD_ENCODING__MECH_PLANE = 1
BOARD_ENCODING__WORKER_PLANE = 2
BOARD_ENCODING__MILL_PLANE = 3
BOARD_ENCODING__STRUCTURE_PLANE = 4
BOARD_ENCODING__MINE_PLANE = 5
BOARD_ENCODING__OIL_PLANE = BOARD_ENCODING__PLANES_PER_PLAYER * constants.MAX_PLAYERS
BOARD_ENCODING__WOOD_PLANE = BOARD_ENCODING__OIL_PLANE + 1
BOARD_ENCODING__METAL_PLANE = BOARD_ENCODING__OIL_PLANE + 2
BOARD_ENCODING__FOOD_PLANE = BOARD_ENCODING__OIL_PLANE + 3
BOARD_ENCODING__EXTRA_PLANES = 4
BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE = 20
BOARD_ENCODING__TOTAL_PLANES = BOARD_ENCODING__PLANES_PER_PLAYER * constants.MAX_PLAYERS + BOARD_ENCODING__EXTRA_PLANES

BOARD_ENCODING__RESOURCE_PLANES = {
    ResourceType.OIL: BOARD_ENCODING__OIL_PLANE,
    ResourceType.METAL: BOARD_ENCODING__METAL_PLANE,
    ResourceType.WOOD: BOARD_ENCODING__WOOD_PLANE,
    ResourceType.FOOD: BOARD_ENCODING__FOOD_PLANE
}

HOME_BASE_ENCODING_SIZE_PER_PLAYER = 3
HOME_BASE__CHARACTER_OFFSET = 0
HOME_BASE__MECH_OFFSET = 1
HOME_BASE__WORKER_OFFSET = 2
TOP_ACTION__ACTION_ENCODING_SIZE = 3 * encode_actions.num_encodable_actions
TOP_ACTION__SPACE_ENCODING_SIZE = constants.BOARD_ROWS + constants.BOARD_COLS
TOP_ACTION__POWER_ENCODING_SIZE = 1
TOP_ACTION_ENCODING_SIZE = TOP_ACTION__ACTION_ENCODING_SIZE + TOP_ACTION__POWER_ENCODING_SIZE \
                           + TOP_ACTION__SPACE_ENCODING_SIZE


@attr.s(frozen=True, slots=True)
class EncodedGameState:
    board = attr.ib()
    home_bases = attr.ib()
    structure_bonus = attr.ib()
    discard_pile = attr.ib()
    current_player = attr.ib()
    other_players = attr.ib()
    top_action__action_encoding = attr.ib()
    top_action__space_encoding = attr.ib()
    top_action__power_encoding = attr.ib()

    board_shape = (BOARD_ENCODING__TOTAL_PLANES, constants.BOARD_ROWS, constants.BOARD_COLS)
    data_shape = (HOME_BASE_ENCODING_SIZE_PER_PLAYER + constants.NUM_STRUCTURE_BONUSES
                  + constants.NUM_COMBAT_CARD_VALUES + EncodedPlayer.shape_as_self[0]
                  + EncodedPlayer.shape_as_other[0] * (constants.MAX_PLAYERS - 1)
                  + TOP_ACTION_ENCODING_SIZE,)

    HOME_BASE_OFFSET = 0
    STRUCTURE_BONUS_OFFSET = HOME_BASE_OFFSET + HOME_BASE_ENCODING_SIZE_PER_PLAYER * constants.MAX_PLAYERS
    DISCARD_PILE_OFFSET = STRUCTURE_BONUS_OFFSET + constants.NUM_STRUCTURE_BONUSES
    TOP_ACTION__ACTION_ENCODING_OFFSET = DISCARD_PILE_OFFSET + constants.NUM_COMBAT_CARD_VALUES
    TOP_ACTION__SPACE_ENCODING_OFFSET = TOP_ACTION__ACTION_ENCODING_OFFSET + TOP_ACTION__ACTION_ENCODING_SIZE
    TOP_ACTION__POWER_ENCODING_OFFSET = TOP_ACTION__SPACE_ENCODING_OFFSET + TOP_ACTION__SPACE_ENCODING_SIZE
    CURRENT_PLAYER_OFFSET = TOP_ACTION__POWER_ENCODING_OFFSET + TOP_ACTION__POWER_ENCODING_SIZE
    OTHER_PLAYERS_OFFSET = CURRENT_PLAYER_OFFSET + EncodedPlayer.shape_as_self[0]

    def encoded_data(self):
        return np.concatenate([self.home_bases, self.structure_bonus, self.discard_pile,
                               self.top_action__action_encoding, self.top_action__space_encoding,
                               self.top_action__power_encoding, self.current_player.encoded_data()]
                              + list(map(lambda x: x.encoded_data(), self.other_players)))


def encode_discard_pile(combat_cards):
    aggregates = defaultdict(int)
    for card in combat_cards.discard_pile:
        aggregates[card] += 1
    return encode_combat_cards(aggregates)


def encode_space(board, index_by_faction_name, space):
    row, col = space.coords
    # if space.has_encounter and not space.encounter_used:
    #     board[BOARD_ENCODING__ENCOUNTERS_PLANE][row][col] = 1
    if space.structure_key:
        start_plane = index_by_faction_name[space.structure_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[row][col][start_plane + BOARD_ENCODING__STRUCTURE_PLANE] = 1
        if space.structure_key.id == StructureType.MINE:
            board[row][col][start_plane + BOARD_ENCODING__MINE_PLANE] = 1
        elif space.structure_key.id == StructureType.MILL:
            board[row][col][start_plane + BOARD_ENCODING__MILL_PLANE] = 1
    for character_key in space.character_keys:
        start_plane = index_by_faction_name[character_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[row][col][start_plane + BOARD_ENCODING__CHARACTER_PLANE] = 1
    for mech_key in space.mech_keys:
        start_plane = index_by_faction_name[mech_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[row][col][start_plane + BOARD_ENCODING__MECH_PLANE] += 1 / constants.NUM_MECHS
    for worker_key in space.worker_keys:
        start_plane = index_by_faction_name[worker_key.faction_name] * BOARD_ENCODING__PLANES_PER_PLAYER
        board[row][col][start_plane + BOARD_ENCODING__WORKER_PLANE] += 1 / constants.NUM_WORKERS
    for resource_typ, amt in space.resources.items():
        board[row][col][BOARD_ENCODING__RESOURCE_PLANES[resource_typ]] = \
            amt / BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE


def encode_home_base(home_bases, index_by_faction_name, space):
    faction_name = FactionName(space.coords[1])
    if faction_name in index_by_faction_name:
        start_plane = index_by_faction_name[faction_name] * HOME_BASE_ENCODING_SIZE_PER_PLAYER
        if space.character_keys:
            home_bases[start_plane + HOME_BASE__CHARACTER_OFFSET] = 1
        home_bases[start_plane + HOME_BASE__MECH_OFFSET] = len(space.mech_keys) / constants.NUM_MECHS
        home_bases[start_plane + HOME_BASE__WORKER_OFFSET] = len(space.worker_keys) / constants.NUM_WORKERS


def encode_board(game_state, index_by_faction_name):
    player_planes = constants.MAX_PLAYERS * BOARD_ENCODING__PLANES_PER_PLAYER
    num_planes = player_planes + BOARD_ENCODING__EXTRA_PLANES
    board = np.zeros((constants.BOARD_ROWS, constants.BOARD_COLS, num_planes))
    home_bases = np.zeros(HOME_BASE_ENCODING_SIZE_PER_PLAYER * constants.MAX_PLAYERS)
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


# def encode_piece_key(piece_encoding, piece_key):
#     piece_encoding[piece_key.faction_name.value] = 1
#     piece_encoding[constants.NUM_FACTIONS + piece_key.piece_typ.value] = 1
#     piece_encoding[constants.NUM_FACTIONS + constants.NUM_PIECE_TYPES + piece_key.id] = 1

def encode_piece_coords(space_encoding, game_state, piece_key):
    coords = game_state.pieces_by_key[piece_key].board_coords
    space_encoding[coords[0]] = 1
    space_encoding[constants.BOARD_ROWS + coords[1]] = 1


THEORETICAL_COINS_MAXIMUM = 100
THEORETICAL_POWER_MAXIMUM = 22


def encode_context(game_state, actions_encoding, space_encoding, power_encoding):
    top_action = game_state.action_stack.first
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
        encode_piece_coords(space_encoding, game_state, top_action.piece_key)
    elif isinstance(top_action, LoadWorkers):
        encode_piece_coords(space_encoding, game_state, top_action.mech_key)
    elif isinstance(top_action, MovePieceOneSpace):
        encode_piece_coords(space_encoding, game_state, top_action.piece_key)
    elif isinstance(top_action, GetAttackerCombatCards):
        power_encoding[0] = top_action.attacker_total_power / THEORETICAL_POWER_MAXIMUM
    elif isinstance(top_action, GetDefenderCombatCards):
        power_encoding[0] = top_action.defender_total_power / THEORETICAL_POWER_MAXIMUM
    else:
        assert False


def encode_top_action(game_state):
    actions_encoding = np.zeros(3 * encode_actions.num_encodable_actions)
    space_encoding = np.zeros(constants.BOARD_ROWS + constants.BOARD_COLS)
    power_encoding = np.zeros(1)
    top_action = game_state.action_stack.first
    top_action_typ = type(top_action)
    actions_encoding[encode_actions.action_constants[top_action_typ]] = 1
    if top_action_typ in encode_actions.choices_that_need_context:
        encode_context(top_action, actions_encoding, space_encoding, power_encoding)
    return actions_encoding, space_encoding, power_encoding


# Encode players in the following order: self, player to my right, player to my left,
# everyone else in player order
def get_indices_by_faction_name(game_state):
    ret = {sc.get_current_player(game_state).faction_name(): 0}
    num_players = len(game_state.players_by_idx)
    right_player_idx = (game_state.current_player_idx + 1) % num_players
    ret[game_state.players_by_idx[right_player_idx].faction_name()] = 1
    if num_players > 2:
        left_player_idx = (game_state.current_player_idx - 1) % num_players
        ret[game_state.players_by_idx[left_player_idx].faction_name()] = 2

        ctr = 3
        for idx in range(game_state.current_player_idx + 2, game_state.current_player_idx + num_players - 1):
            ret[game_state.players_by_idx[idx % num_players].faction_name()] = ctr
            ctr += 1

    assert len(ret) == num_players
    return ret


def encode_structure_bonus(structure_bonus_value):
    ret = np.zeros(constants.NUM_STRUCTURE_BONUSES)
    ret[structure_bonus_value] = 1
    return ret


def encode(game_state):
    indices_by_faction_name = get_indices_by_faction_name(game_state)
    board, home_bases = encode_board(game_state, indices_by_faction_name)
    return EncodedGameState(board,
                            home_bases,
                            encode_structure_bonus(game_state.structure_bonus.value),
                            encode_discard_pile(game_state.combat_cards),
                            encode_player(sc.get_current_player(game_state), as_self=True),
                            encode_other_players(game_state, indices_by_faction_name),
                            *encode_top_action(game_state))
