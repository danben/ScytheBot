from game.actions import *
import encoders.game_state as enc_gs
import game.constants as constants
import training.constants as c


def decode_based_on_ordering(choices, head):
    return {choice: head[0][i] for i, choice in enumerate(choices)}


def decode_based_on_enum_values(choices, head):
    return {choice: head[0][choice.value] for choice in choices}


def decode_board_space(head, row, col):
    if row >= 0:
        return head[0][row * constants.BOARD_COLS + col]
    else:
        return head[0][constants.BOARD_ROWS * constants.BOARD_COLS + col]


def decode_board_spaces(choices, head):
    ret = {}
    for choice in choices:
        ret[choice] = decode_board_space(head, *choice)
    return ret


def decode_optional_combat_cards(choices, head):
    ret = {choice: head[0][choice - constants.MIN_COMBAT_CARD] for choice in choices}
    ret[None] = head[0][constants.MAX_COMBAT_CARD - 1]
    return ret


def decode_numeric(choices, head):
    return {choice: head[0][choice] for choice in choices}


def decode_top_cube_spaces(choices, head):
    ret = {}
    for choice in choices:
        top_action_typ, offset = choice
        ret[choice] = head[0][enc_gs.EncodedPlayerMat.TOP_ACTION_CUBES_OFFSETS_BY_TOP_ACTION_TYPE[top_action_typ] + offset]
    return ret


_decoders = {
    Optional: decode_based_on_ordering,
    Boolean: decode_based_on_ordering,
    MaybePayCost: decode_based_on_ordering,
    SpendAResource: decode_board_spaces,
    BottomAction: decode_based_on_ordering,
    Bolster: decode_based_on_ordering,
    ChooseSpaceToBuildOn: decode_board_spaces,
    ChooseStructureToBuild: decode_based_on_enum_values,
    GetDefenderCombatCards: decode_optional_combat_cards,
    GetAttackerCombatCards: decode_optional_combat_cards,
    GetAttackerWheelPower: decode_numeric,
    GetDefenderWheelPower: decode_numeric,
    NordicMaybeUseCombatPower: decode_based_on_ordering,
    ChooseDeploySpace: decode_board_spaces,
    DeployMech: decode_based_on_enum_values,
    ChooseEnlistReward: decode_based_on_enum_values,
    ChooseRecruitToEnlist: decode_based_on_enum_values,
    LoadResources: decode_numeric,
    LoadWorkers: decode_numeric,
    MovePieceOneSpace: decode_board_spaces,
    ChooseNumWorkers: decode_numeric,
    OnOneHex: decode_board_spaces,
    Produce: decode_based_on_ordering,
    TakeTurn: decode_numeric,
    ChooseBoardSpaceForResource: decode_board_spaces,
    ChooseResourceType: decode_based_on_enum_values,
    Trade: decode_based_on_ordering,
    RemoveCubeFromAnyTopSpace: decode_top_cube_spaces,
    PlaceCubeInAnyBottomSpace: decode_based_on_enum_values
}

_model_head_by_action_class = {
    Optional: c.OPTIONAL_HEAD,
    Boolean: c.BOOLEAN_HEAD,
    MaybePayCost: c.MAYBE_PAY_COST_HEAD,
    SpendAResource: c.BOARD_COORDS_HEAD,
    # TODO: Add this when Crimea joins
    # CrimeaMaybeChooseResource: c.RESOURCE_TYP_HEAD,
    BottomAction: c.MAYBE_PAY_COST_HEAD,
    Bolster: c.MAYBE_PAY_COST_HEAD,
    ChooseSpaceToBuildOn: c.BOARD_COORDS_HEAD,
    ChooseStructureToBuild: c.STRUCTURE_TYP_HEAD,
    GetDefenderCombatCards: c.OPTIONAL_COMBAT_CARD_HEAD,
    GetAttackerCombatCards: c.OPTIONAL_COMBAT_CARD_HEAD,
    GetDefenderWheelPower: c.WHEEL_POWER_HEAD,
    GetAttackerWheelPower: c.WHEEL_POWER_HEAD,
    NordicMaybeUseCombatPower: c.OPTIONAL_HEAD,
    ChooseDeploySpace: c.BOARD_COORDS_HEAD,
    DeployMech: c.MECH_TYP_HEAD,
    ChooseEnlistReward: c.ENLIST_REWARD_HEAD,
    ChooseRecruitToEnlist: c.BOTTOM_ACTION_TYP_HEAD,
    LoadResources: c.NUM_RESOURCES_HEAD,
    LoadWorkers: c.NUM_WORKERS_HEAD,
    MovePieceOneSpace: c.BOARD_COORDS_HEAD,
    # MoveOnePiece not included, since it combines two heads
    ChooseNumWorkers: c.NUM_WORKERS_HEAD,
    OnOneHex: c.BOARD_COORDS_HEAD,
    Produce: c.MAYBE_PAY_COST_HEAD,
    TakeTurn: c.CHOOSE_ACTION_SPACE_HEAD,
    ChooseBoardSpaceForResource: c.BOARD_COORDS_HEAD,
    ChooseResourceType: c.RESOURCE_TYP_HEAD,
    Trade: c.MAYBE_PAY_COST_HEAD,
    RemoveCubeFromAnyTopSpace: c.CUBE_SPACE_HEAD,
    PlaceCubeInAnyBottomSpace: c.BOTTOM_ACTION_TYP_HEAD
}


def get_board_coords_and_piece_typ_priors(choices, board_coord_preds, piece_typ_preds):
    move_priors = {}
    for board_coords, piece_typ in choices:
        move_priors[(board_coords, piece_typ)] = decode_board_space(board_coord_preds, *board_coords)\
            * piece_typ_preds[0][piece_typ.value]
    return move_priors


def get_move_priors(preds, top_action_class, choices):
    if top_action_class is MoveOnePiece:
        return get_board_coords_and_piece_typ_priors(choices, preds[c.BOARD_COORDS_HEAD], preds[c.PIECE_TYP_HEAD])
    else:
        return _decoders[top_action_class](choices, preds[_model_head_by_action_class[top_action_class]])
