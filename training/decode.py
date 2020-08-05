from game.actions import *
import encoders.game_state as enc_gs
import game.constants as constants
from training.constants import Head


def decode_boolean(choice):
    return 1 if choice else 0


def decode_enum_value(choice):
    return choice.value


def decode_board_space(choice):
    row, col = choice
    if row >= 0:
        return row * constants.BOARD_COLS + col
    else:
        return constants.BOARD_ROWS * constants.BOARD_COLS + col


def decode_optional_combat_card(choice):
    if not choice:
        return constants.MAX_COMBAT_CARD - constants.MIN_COMBAT_CARD + 1
    return choice - constants.MIN_COMBAT_CARD


def decode_numeric(choice):
    return choice


def decode_top_cube_space(choice):
    top_action_typ, offset = choice
    return enc_gs.EncodedPlayerMat.TOP_ACTION_CUBES_OFFSETS_BY_TOP_ACTION_TYPE[top_action_typ] + offset


# These functions will translate a legal move to an index into the appropriate output head of the model
decoders = {
    Optional: decode_boolean,
    Boolean: decode_boolean,
    MaybePayCost: decode_boolean,
    SpendAResource: decode_board_space,
    BottomAction: decode_boolean,
    Bolster: decode_boolean,
    ChooseSpaceToBuildOn: decode_board_space,
    ChooseStructureToBuild: decode_enum_value,
    GetDefenderCombatCards: decode_optional_combat_card,
    GetAttackerCombatCards: decode_optional_combat_card,
    GetAttackerWheelPower: decode_numeric,
    GetDefenderWheelPower: decode_numeric,
    NordicMaybeUseCombatPower: decode_boolean,
    ChooseDeploySpace: decode_board_space,
    DeployMech: decode_enum_value,
    ChooseEnlistReward: decode_enum_value,
    ChooseRecruitToEnlist: decode_enum_value,
    LoadResources: decode_numeric,
    LoadWorkers: decode_numeric,
    MovePieceOneSpace: decode_board_space,
    ChooseNumWorkers: decode_numeric,
    OnOneHex: decode_board_space,
    Produce: decode_boolean,
    TakeTurn: decode_numeric,
    ChooseBoardSpaceForResource: decode_board_space,
    ChooseResourceType: decode_enum_value,
    Trade: decode_boolean,
    RemoveCubeFromAnyTopSpace: decode_top_cube_space,
    PlaceCubeInAnyBottomSpace: decode_enum_value
}

model_head_by_action_class = {
    Optional: Head.OPTIONAL_HEAD,
    Boolean: Head.BOOLEAN_HEAD,
    MaybePayCost: Head.MAYBE_PAY_COST_HEAD,
    SpendAResource: Head.BOARD_COORDS_HEAD,
    # TODO: Add this when Crimea joins
    # CrimeaMaybeChooseResource: Head.RESOURCE_TYP_HEAD,
    BottomAction: Head.MAYBE_PAY_COST_HEAD,
    Bolster: Head.MAYBE_PAY_COST_HEAD,
    ChooseSpaceToBuildOn: Head.BOARD_COORDS_HEAD,
    ChooseStructureToBuild: Head.STRUCTURE_TYP_HEAD,
    GetDefenderCombatCards: Head.OPTIONAL_COMBAT_CARD_HEAD,
    GetAttackerCombatCards: Head.OPTIONAL_COMBAT_CARD_HEAD,
    GetDefenderWheelPower: Head.WHEEL_POWER_HEAD,
    GetAttackerWheelPower: Head.WHEEL_POWER_HEAD,
    NordicMaybeUseCombatPower: Head.OPTIONAL_HEAD,
    ChooseDeploySpace: Head.BOARD_COORDS_HEAD,
    DeployMech: Head.MECH_TYP_HEAD,
    ChooseEnlistReward: Head.ENLIST_REWARD_HEAD,
    ChooseRecruitToEnlist: Head.BOTTOM_ACTION_TYP_HEAD,
    LoadResources: Head.NUM_RESOURCES_HEAD,
    LoadWorkers: Head.NUM_WORKERS_HEAD,
    MovePieceOneSpace: Head.BOARD_COORDS_HEAD,
    # MoveOnePiece not included, since it combines two heads
    ChooseNumWorkers: Head.NUM_WORKERS_HEAD,
    OnOneHex: Head.BOARD_COORDS_HEAD,
    Produce: Head.MAYBE_PAY_COST_HEAD,
    TakeTurn: Head.CHOOSE_ACTION_SPACE_HEAD,
    ChooseBoardSpaceForResource: Head.BOARD_COORDS_HEAD,
    ChooseResourceType: Head.RESOURCE_TYP_HEAD,
    Trade: Head.MAYBE_PAY_COST_HEAD,
    RemoveCubeFromAnyTopSpace: Head.CUBE_SPACE_HEAD,
    PlaceCubeInAnyBottomSpace: Head.BOTTOM_ACTION_TYP_HEAD
}


def get_board_coords_and_piece_typ_priors(choices, board_coord_preds, piece_typ_preds):
    move_priors = {}
    for board_coords, piece_typ in choices:
        move_priors[(board_coords, piece_typ)] = board_coord_preds[decode_board_space(board_coords)]\
            * piece_typ_preds[piece_typ.value]
    return move_priors


def get_move_priors(preds, top_action_class, choices):
    if top_action_class is MoveOnePiece:
        return get_board_coords_and_piece_typ_priors(choices, preds[Head.BOARD_COORDS_HEAD.value],
                                                     preds[Head.PIECE_TYP_HEAD.value])
    else:
        head = preds[model_head_by_action_class[top_action_class].value]
        decoder = decoders[top_action_class]
        try:
            return {choice: head[decoder(choice)] for choice in choices}
        except IndexError:
            print(f'IndexError from {top_action_class}')
            for choice in choices:
                print(f'Choice: {choice}; Decoded: {decoder(choice)}')
            assert False
