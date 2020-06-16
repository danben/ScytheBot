from game import constants, game_state
from game.actions import Boolean, BottomAction, GetAttackerCombatCards, GetDefenderCombatCards, LoadResources
from game.actions import LoadWorkers,  MaybePayCost, MovePieceOneSpace, Optional
from game.components import piece as gc_piece
from game.encoders import game_state as enc, actions as actions
from game.types import Benefit, BottomActionType, MechType, StarType, StructureType, TopActionType
from collections import defaultdict


def one_hot_to_int(arr, lower, upper):
    x = 0 < lower < len(arr)
    y = 0 < upper < len(arr)
    assert x and y
    for i, val in enumerate(arr[lower:upper]):
        if val == 1:
            return i
    return None


def check_home_bases(gs, encoded_data, indices_by_faction_name):
    for faction_name, index in indices_by_faction_name.items():
        start_plane = enc.EncodedGameState.HOME_BASE_OFFSET \
                      + enc.HOME_BASE_ENCODING_SIZE_PER_PLAYER * index
        character = encoded_data[start_plane + enc.HOME_BASE__CHARACTER_OFFSET]
        workers = int(encoded_data[start_plane + enc.HOME_BASE__WORKER_OFFSET]
                      * constants.NUM_WORKERS)
        mechs = int(encoded_data[start_plane + enc.HOME_BASE__MECH_OFFSET]
                    * constants.NUM_MECHS)
        home_base_space = gs.board.home_base(faction_name)
        assert len(home_base_space.character_keys) == character
        assert len(home_base_space.worker_keys) == workers
        assert len(home_base_space.mech_keys) == mechs


def check_structure_bonus(gs, encoded_data):
    sb = one_hot_to_int(encoded_data, enc.EncodedGameState.STRUCTURE_BONUS_OFFSET,
                        enc.EncodedGameState.STRUCTURE_BONUS_OFFSET
                        + constants.NUM_STRUCTURE_BONUSES)
    assert sb == gs.structure_bonus.value


def check_discard_pile(gs, encoded_data):
    aggregates = defaultdict(int)
    for card in gs.combat_cards.discard_pile:
        aggregates[card] += 1
    for i in range(enc.EncodedGameState.DISCARD_PILE_OFFSET, constants.NUM_COMBAT_CARD_VALUES):
        assert aggregates[i + constants.MIN_COMBAT_CARD] == \
               int(encoded_data[i] * constants.DECK_SIZE)


def check_player_mat(player, encoded_data, start_plane):
    start_plane = start_plane + enc.EncodedPlayer.PLAYER_MAT_OFFSET
    player_mat = player.player_mat
    player_mat_name = one_hot_to_int(encoded_data, start_plane + enc.EncodedPlayerMat.NAME_OFFSET,
                                     start_plane + enc.EncodedPlayerMat.NAME_OFFSET + constants.NUM_PLAYER_MATS)
    assert player_mat_name == player_mat.name.value

    for x in TopActionType:
        top_action_cubes_and_structure = player_mat.top_action_cubes_and_structures_by_top_action_typ[x]
        for i, is_upgraded in enumerate(top_action_cubes_and_structure.cubes_upgraded):
            encoded_value = encoded_data[start_plane + enc.EncodedPlayerMat.TOP_ACTION_CUBES_OFFSET
                                         + enc.EncodedPlayerMat.TOP_ACTION_CUBES_OFFSETS_BY_TOP_ACTION_TYPE[x] + i]
            assert encoded_value == is_upgraded

    for b in BottomActionType:
        bottom_action = player_mat.action_spaces[player_mat.action_spaces_by_bottom_action_typ[b]][1]
        offset = start_plane + enc.EncodedPlayerMat.BOTTOM_ACTION_COSTS_AND_RECRUITS_OFFSET + 2 * b.value
        encoded_cost = encoded_data[offset]
        encoded_has_enlisted = encoded_data[offset + 1]
        assert bottom_action.current_cost == int(encoded_cost * constants.MAX_BOTTOM_ACTION_COST)
        assert player_mat.has_enlisted_by_bottom_action_typ[b] == encoded_has_enlisted

    encoded_last_action_spot = one_hot_to_int(encoded_data,
                                              start_plane + enc.EncodedPlayerMat.LAST_ACTION_SPOT_TAKEN_OFFSET,
                                              start_plane + enc.EncodedPlayerMat.LAST_ACTION_SPOT_TAKEN_OFFSET
                                              + constants.NUM_PLAYER_MAT_ACTION_SPACES)
    assert player_mat.last_action_spot_taken == encoded_last_action_spot


def check_misc_data(player, encoded_data, player_start):
    misc_data_start = player_start + enc.EncodedPlayer.MISC_DATA_OFFSET
    encoded_faction_name = one_hot_to_int(encoded_data, misc_data_start + enc.EncodedPlayer.MISC_DATA__FACTION_OFFSET,
                                          misc_data_start + enc.EncodedPlayer.MISC_DATA__FACTION_OFFSET
                                          + constants.NUM_FACTIONS)
    assert encoded_faction_name == player.faction_name().value
    assert encoded_data[misc_data_start + enc.EncodedPlayer.MISC_DATA__COINS_OFFSET] \
        == player.coins / enc.THEORETICAL_COINS_MAXIMUM
    assert encoded_data[misc_data_start + enc.EncodedPlayer.MISC_DATA__POPULARITY_OFFSET] \
        == player.popularity / constants.MAX_POPULARITY
    assert encoded_data[misc_data_start + enc.EncodedPlayer.MISC_DATA__POWER_OFFSET] \
        == player.power / constants.MAX_POWER
    assert encoded_data[misc_data_start + enc.EncodedPlayer.MISC_DATA__NUM_WORKERS_OFFSET] \
        == len(player.worker_ids) / constants.NUM_WORKERS


def check_player(gs, encoded_data, indices_by_faction_name, index):
    if index == 0:
        player_start = enc.EncodedGameState.CURRENT_PLAYER_OFFSET
    else:
        player_start = enc.EncodedGameState.OTHER_PLAYERS_OFFSET + enc.EncodedPlayer.shape_as_other[0] * (index - 1)
    for f, i in indices_by_faction_name.items():
        if i == index:
            faction_name = f
            break
    player = gs.players_by_idx[gs.player_idx_by_faction_name[faction_name]]
    check_misc_data(player, encoded_data, player_start)
    for b in Benefit:
        encoded_benefit = encoded_data[player_start + enc.EncodedPlayer.ENLIST_REWARDS_OFFSET + b.value]
        if b in player.enlist_rewards:
            assert encoded_benefit == 1
        else:
            assert encoded_benefit == 0
    for m in MechType:
        encoded_mech = encoded_data[player_start + enc.EncodedPlayer.MECHS_OFFSET + m.value]
        if m.value in player.mech_ids:
            assert encoded_mech == 1
        else:
            assert encoded_mech == 0
    for s in StructureType:
        encoded_structure = encoded_data[player_start + enc.EncodedPlayer.STRUCTURES_OFFSET + s.value]
        if s in player.structures:
            assert encoded_structure == 1
        else:
            assert encoded_structure == 0
    assert int(encoded_data[enc.EncodedPlayer.STAR_COUNT_OFFSET] * constants.NUM_STAR_TYPES) == player.stars.count
    for s in StarType:
        encoded_star_type = encoded_data[player_start + enc.EncodedPlayer.STAR_TYPES_OFFSET + s.value]
        if player.stars.achieved[s]:
            assert encoded_star_type == 1
        else:
            assert encoded_star_type == 0

        encoded_second_combat_star = encoded_data[player_start + enc.EncodedPlayer.STAR_TYPES_OFFSET
                                                  + constants.NUM_STAR_TYPES]
        if player.stars.achieved[StarType.COMBAT] > 1:
            assert encoded_second_combat_star == 1
        else:
            assert encoded_second_combat_star == 0

    if index == 0:
        for i in range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1):
            encoded_card_count = int(encoded_data[player_start + enc.EncodedPlayer.COMBAT_CARDS_OFFSET + i
                                                  - constants.MIN_COMBAT_CARD] * constants.DECK_SIZE)
            assert player.combat_cards[i] == encoded_card_count
    else:
        encoded_card_count = encoded_data[player_start + enc.EncodedPlayer.COMBAT_CARDS_OFFSET]
        assert encoded_card_count == sum(player.combat_cards.values()) / constants.DECK_SIZE

    check_player_mat(player, encoded_data, player_start)


def check_other_players(gs, encoded_data, indices_by_faction_name):
    for i in range(1, len(gs.players_by_idx)):
        check_player(gs, encoded_data, indices_by_faction_name, i)


def check_top_action__action_encoding(gs, encoded_data):
    def get_action_val(n):
        return one_hot_to_int(encoded_data, enc.EncodedGameState.TOP_ACTION__ACTION_ENCODING_OFFSET
                              + actions.num_encodable_actions * n,
                              enc.EncodedGameState.TOP_ACTION__ACTION_ENCODING_OFFSET
                              + (n + 1) * actions.num_encodable_actions)
    action_val = get_action_val(0)
    action_2_val = get_action_val(1)
    action_3_val = get_action_val(2)
    top_action = gs.action_stack.first
    assert actions.action_constants[top_action.__class__] == action_val

    if isinstance(top_action, Boolean):
        assert actions.action_constants[top_action.action1.__class__] == action_2_val
        assert actions.action_constants[top_action.action2.__class__] == action_3_val
    elif isinstance(top_action, Optional):
        assert actions.action_constants[top_action.action.__class__] == action_2_val
        assert action_3_val is None
    elif isinstance(top_action, BottomAction):
        assert actions.action_constants[top_action.if_paid.action_benefit.__class__] == action_2_val
        assert action_3_val is None
    elif isinstance(top_action, MaybePayCost):
        assert actions.action_constants[top_action.if_paid.__class__] == action_2_val
        assert action_3_val is None
    else:
        assert action_2_val is action_3_val is None


def check_top_action__space_encoding(gs, encoded_data):
    top_action = gs.action_stack.first
    board_row = one_hot_to_int(encoded_data, enc.EncodedGameState.TOP_ACTION__SPACE_ENCODING_OFFSET,
                               enc.EncodedGameState.TOP_ACTION__SPACE_ENCODING_OFFSET + constants.BOARD_ROWS)
    board_col = one_hot_to_int(encoded_data, enc.EncodedGameState.TOP_ACTION__SPACE_ENCODING_OFFSET
                               + constants.BOARD_ROWS,
                               enc.EncodedGameState.TOP_ACTION__SPACE_ENCODING_OFFSET + constants.BOARD_ROWS
                               + constants.BOARD_COLS)

    if isinstance(top_action, LoadResources) or isinstance(top_action, MovePieceOneSpace):
        piece_coords = gs.pieces_by_key[top_action.piece_key].board_coords
        assert piece_coords == board_row, board_col
    elif isinstance(top_action, LoadWorkers):
        piece_coords = gs.pieces_by_key[top_action.mech_key].board_coords
        assert piece_coords == board_row, board_col
    else:
        assert board_row is board_col is None


def check_top_action__power_encoding(gs, encoded_data):
    top_action = gs.action_stack.first
    encoded_power = int(encoded_data[enc.EncodedGameState.TOP_ACTION__POWER_ENCODING_OFFSET]
                        * enc.THEORETICAL_POWER_MAXIMUM)
    if isinstance(top_action, GetAttackerCombatCards):
        assert encoded_power == top_action.attacker_total_power
    elif isinstance(top_action, GetDefenderCombatCards):
        assert encoded_power == top_action.defender_total_power
    else:
        assert encoded_power == 0


def matching_keys(s, faction_name):
    return len([x for x in s if x.faction_name is faction_name])


def check_space_for_faction(space, encoded_board, start_plane, faction_name):
    board_slice = encoded_board[space.coords[0]][space.coords[1]]
    characters = matching_keys(space.character_keys, faction_name)
    assert board_slice[start_plane + enc.BOARD_ENCODING__CHARACTER_PLANE] == characters
    mechs = matching_keys(space.mech_keys, faction_name)
    assert board_slice[start_plane + enc.BOARD_ENCODING__MECH_PLANE] == mechs / constants.NUM_MECHS
    workers = matching_keys(space.worker_keys, faction_name)
    assert board_slice[start_plane + enc.BOARD_ENCODING__WORKER_PLANE] == workers / constants.NUM_WORKERS
    if (not space.structure_key) or space.structure_key.faction_name is not faction_name:
        assert board_slice[start_plane + enc.BOARD_ENCODING__STRUCTURE_PLANE] == 0
        assert board_slice[start_plane + enc.BOARD_ENCODING__MINE_PLANE] == 0
        assert board_slice[start_plane + enc.BOARD_ENCODING__MILL_PLANE] == 0
    else:
        assert board_slice[start_plane + enc.BOARD_ENCODING__STRUCTURE_PLANE] == 1
        if space.structure_key.id == StructureType.MINE:
            assert board_slice[start_plane + enc.BOARD_ENCODING__MINE_PLANE] == 1
        if space.structure_key.id == StructureType.MILL:
            assert board_slice[start_plane + enc.BOARD_ENCODING__MILL_PLANE] == 1


def check_space(gs, space, encoded_board, factions_by_index):
    row, col = space.coords
    for index in range(constants.MAX_PLAYERS):
        start_plane = index * enc.BOARD_ENCODING__PLANES_PER_PLAYER
        faction_name = None
        if index in factions_by_index:
            faction_name = factions_by_index[index]
        if not faction_name:
            for offset in range(enc.BOARD_ENCODING__PLANES_PER_PLAYER):
                assert encoded_board[row][col][start_plane + offset] == 0
        else:
            check_space_for_faction(space, encoded_board, start_plane, faction_name)
    for resource_typ, amt in space.resources.items():
        plane = enc.BOARD_ENCODING__RESOURCE_PLANES[resource_typ]
        assert encoded_board[row][col][plane] == space.resources[resource_typ] \
            / enc.BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE


def check_board(gs, encoded_board, indices_by_faction_name):
    factions_by_index = {index: faction for faction, index in indices_by_faction_name.items()}
    for space in gs.board.board_spaces_by_coords.values():
        if space.coords[0] >= 0:
            check_space(gs, space, encoded_board, factions_by_index)


def round_trip(gs):
    encoded_game_state = enc.encode(gs)
    encoded_data = encoded_game_state.encoded_data()
    indices_by_faction_name = enc.get_indices_by_faction_name(gs)
    check_board(gs, encoded_game_state.board, indices_by_faction_name)
    check_home_bases(gs, encoded_data, indices_by_faction_name)
    check_structure_bonus(gs, encoded_data)
    check_discard_pile(gs, encoded_data)
    check_player(gs, encoded_data, indices_by_faction_name, 0)
    check_other_players(gs, encoded_data, indices_by_faction_name)
    check_top_action__action_encoding(gs, encoded_data)
    check_top_action__space_encoding(gs, encoded_data)
    check_top_action__power_encoding(gs, encoded_data)


def round_trip_initial_state():
    round_trip(game_state.GameState.from_num_players(2))


def run_tests():
    round_trip_initial_state()


if __name__ == '__main__':
    run_tests()
