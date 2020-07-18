import game.constants as const
import encoders.game_state as gs_enc
import training.decode as decode
from training.constants import Head

from game.actions import *
from game.types import Benefit, BottomActionType, MechType, PieceType, ResourceType, StructureType

import itertools
import numpy as np


def of_boolean(head_ind):
    return np.array([head_ind * 100 + i * 10 for i in [False, True]])


def of_enum(head_ind, cls):
    return np.array([head_ind * 100 + i.value * 10 for i in cls])


def of_range(head_ind, x, y=None):
    low = 0
    if not y:
        high = x + 1
    else:
        low, high = x, y + 1
    return np.array([head_ind * 100 + i * 10 for i in range(low, high)])


def make_board_coords_preds():
    ret = np.zeros(const.BOARD_ROWS * const.BOARD_COLS + const.NUM_FACTIONS)
    for row in range(const.BOARD_ROWS):
        for col in range(const.BOARD_COLS):
            ret[row * const.BOARD_COLS + col] = Head.BOARD_COORDS_HEAD.value * 100 + row * 10 + col
    for i in range(const.NUM_FACTIONS):
        ret[const.BOARD_ROWS * const.BOARD_COLS + i] = Head.BOARD_COORDS_HEAD.value * 100 + const.BOARD_ROWS * 10 + i
    return ret


value_head = np.array([Head.VALUE_HEAD.value * 100 + i * 10 for i in range(const.MAX_PLAYERS)])
optional_head = of_boolean(Head.OPTIONAL_HEAD.value)
boolean_head = np.array([Head.BOOLEAN_HEAD.value * 100 + 4, Head.BOOLEAN_HEAD.value * 100 + 6])
maybe_pay_cost_head = of_boolean(Head.MAYBE_PAY_COST_HEAD.value)
board_coords_head = make_board_coords_preds()
piece_typ_head = of_enum(Head.PIECE_TYP_HEAD.value, PieceType)
resource_typ_head = of_enum(Head.RESOURCE_TYP_HEAD.value, ResourceType)
bottom_action_typ_head = of_enum(Head.BOTTOM_ACTION_TYP_HEAD.value, BottomActionType)
enlist_reward_head = of_enum(Head.ENLIST_REWARD_HEAD.value, Benefit)
mech_typ_head = of_enum(Head.MECH_TYP_HEAD.value, MechType)
structure_typ_head = of_enum(Head.STRUCTURE_TYP_HEAD.value, StructureType)
cube_space_head = of_range(Head.CUBE_SPACE_HEAD.value, const.NUM_UPGRADE_CUBES - 1)
optional_combat_card_head = of_range(Head.OPTIONAL_COMBAT_CARD_HEAD.value, const.MIN_COMBAT_CARD,
                                     const.MAX_COMBAT_CARD + 1)
wheel_power_head = of_range(Head.WHEEL_POWER_HEAD.value, const.MAX_COMBAT_POWER)
num_workers_head = of_range(Head.NUM_WORKERS_HEAD.value, const.NUM_WORKERS)
num_resources_head = of_range(Head.NUM_RESOURCES_HEAD.value, gs_enc.BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE)
choose_action_space_head = of_range(Head.CHOOSE_ACTION_SPACE_HEAD.value, const.NUM_PLAYER_MAT_ACTION_SPACES - 1)


def create_test_preds():
    preds = [None] * len(Head)
    preds[Head.VALUE_HEAD.value] = value_head
    preds[Head.OPTIONAL_HEAD.value] = optional_head
    preds[Head.BOOLEAN_HEAD.value] = boolean_head
    preds[Head.MAYBE_PAY_COST_HEAD.value] = maybe_pay_cost_head
    preds[Head.BOARD_COORDS_HEAD.value] = board_coords_head
    preds[Head.PIECE_TYP_HEAD.value] = piece_typ_head
    preds[Head.RESOURCE_TYP_HEAD.value] = resource_typ_head
    preds[Head.BOTTOM_ACTION_TYP_HEAD.value] = bottom_action_typ_head
    preds[Head.ENLIST_REWARD_HEAD.value] = enlist_reward_head
    preds[Head.MECH_TYP_HEAD.value] = mech_typ_head
    preds[Head.STRUCTURE_TYP_HEAD.value] = structure_typ_head
    preds[Head.CUBE_SPACE_HEAD.value] = cube_space_head
    preds[Head.OPTIONAL_COMBAT_CARD_HEAD.value] = optional_combat_card_head
    preds[Head.WHEEL_POWER_HEAD.value] = wheel_power_head
    preds[Head.NUM_WORKERS_HEAD.value] = num_workers_head
    preds[Head.NUM_RESOURCES_HEAD.value] = num_resources_head
    preds[Head.CHOOSE_ACTION_SPACE_HEAD.value] = choose_action_space_head
    for x in preds:
        assert x is not None
    return preds


def identity_value(v):
    return v * 10


def board_coords_value(coords):
    row, col = coords
    if row >= 0:
        return row * 10 + col
    else:
        return const.BOARD_ROWS * 10 + col


def enum_value(e):
    return e.value * 10


def optional_combat_card_value(c):
    if c is not None:
        return c * 10
    else:
        return const.MAX_COMBAT_CARD * 10


def cube_space_value(c):
    top_action_typ, pos = c
    return (gs_enc.EncodedPlayerMat.TOP_ACTION_CUBES_OFFSETS_BY_TOP_ACTION_TYPE[top_action_typ] + pos) * 10


def choose_between_two_actions_value(b):
    if b:
        return 6
    return 4


to_expected_value = {
    Optional: identity_value,
    Boolean: choose_between_two_actions_value,
    MaybePayCost: identity_value,
    SpendAResource: board_coords_value,
    # TODO: Add this when Crimea joins
    # CrimeaMaybeChooseResource: Head.RESOURCE_TYP_HEAD,
    BottomAction: identity_value,
    Bolster: identity_value,
    ChooseSpaceToBuildOn: board_coords_value,
    ChooseStructureToBuild: enum_value,
    GetDefenderCombatCards: optional_combat_card_value,
    GetAttackerCombatCards: optional_combat_card_value,
    GetDefenderWheelPower: identity_value,
    GetAttackerWheelPower: identity_value,
    NordicMaybeUseCombatPower: identity_value,
    ChooseDeploySpace: board_coords_value,
    DeployMech: enum_value,
    ChooseEnlistReward: enum_value,
    ChooseRecruitToEnlist: enum_value,
    LoadResources: identity_value,
    LoadWorkers: identity_value,
    MovePieceOneSpace: board_coords_value,
    # MoveOnePiece not included, since it combines two heads
    ChooseNumWorkers: identity_value,
    OnOneHex: board_coords_value,
    Produce: identity_value,
    TakeTurn: identity_value,
    ChooseBoardSpaceForResource: board_coords_value,
    ChooseResourceType: enum_value,
    Trade: identity_value,
    RemoveCubeFromAnyTopSpace: cube_space_value,
    PlaceCubeInAnyBottomSpace: enum_value
}


def false_and_true():
    return [False, True]


def all_board_coords():
    return [(row, col) for row in range(const.BOARD_ROWS) for col in range(const.BOARD_COLS)] \
           + [(-1, f) for f in range(const.NUM_FACTIONS)]


def all_board_coords_and_piece_type_combinations():
    return list(itertools.product(all_board_coords(), [x for x in PieceType]))


def all_from_enum(cls):
    return lambda: [x for x in cls]


def from_range(x, y=None):
    if not y:
        return lambda: [v for v in range(x)]
    return lambda: [v for v in range(x, y + 1)]


def all_cube_spaces():
    num_upgrade_cubes_by_top_action_typ = {
        TopActionType.TRADE: 1,
        TopActionType.MOVEGAIN: 2,
        TopActionType.PRODUCE: 1,
        TopActionType.BOLSTER: 2
    }
    return [(top_action_typ, offset) for top_action_typ in TopActionType
            for offset in range(num_upgrade_cubes_by_top_action_typ[top_action_typ])]


make_choices = {
    Optional: false_and_true,
    Boolean: false_and_true,
    MaybePayCost: false_and_true,
    SpendAResource: all_board_coords,
    # TODO: Add this when Crimea joins
    # CrimeaMaybeChooseResource: Head.RESOURCE_TYP_HEAD,
    BottomAction: false_and_true,
    Bolster: false_and_true,
    ChooseSpaceToBuildOn: all_board_coords,
    ChooseStructureToBuild: all_from_enum(StructureType),
    GetDefenderCombatCards: from_range(const.MIN_COMBAT_CARD, const.MAX_COMBAT_CARD + 1),
    GetAttackerCombatCards: from_range(const.MIN_COMBAT_CARD, const.MAX_COMBAT_CARD + 1),
    GetDefenderWheelPower: from_range(const.MAX_COMBAT_POWER + 1),
    GetAttackerWheelPower: from_range(const.MAX_COMBAT_POWER + 1),
    NordicMaybeUseCombatPower: false_and_true,
    ChooseDeploySpace: all_board_coords,
    DeployMech: all_from_enum(MechType),
    ChooseEnlistReward: all_from_enum(Benefit),
    ChooseRecruitToEnlist: all_from_enum(BottomActionType),
    LoadResources: from_range(gs_enc.BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE),
    LoadWorkers: from_range(const.NUM_WORKERS),
    MovePieceOneSpace: all_board_coords,
    MoveOnePiece: all_board_coords_and_piece_type_combinations,
    ChooseNumWorkers: from_range(const.NUM_WORKERS),
    OnOneHex: all_board_coords,
    Produce: false_and_true,
    TakeTurn: from_range(const.NUM_PLAYER_MAT_ACTION_SPACES),
    ChooseBoardSpaceForResource: all_board_coords,
    ChooseResourceType: all_from_enum(ResourceType),
    Trade: false_and_true,
    RemoveCubeFromAnyTopSpace: all_cube_spaces,
    PlaceCubeInAnyBottomSpace: all_from_enum(BottomActionType)
}


def test_decoding(preds, top_action_class, choices):
    if top_action_class is MoveOnePiece:
        priors = decode.get_board_coords_and_piece_typ_priors(choices, preds[Head.BOARD_COORDS_HEAD.value],
                                                              preds[Head.PIECE_TYP_HEAD.value])
        for (board_coords, piece_typ) in choices:
            actual = priors[(board_coords, piece_typ)]
            expected = (Head.BOARD_COORDS_HEAD.value * 100 + board_coords_value(board_coords)) \
                       * (Head.PIECE_TYP_HEAD.value * 100 + enum_value(piece_typ))
            assert expected == actual
    else:
        head = decode.model_head_by_action_class[top_action_class].value
        priors = {choice: preds[head][decode.decoders[top_action_class](choice)] for choice in choices}

        for choice in choices:
            actual = priors[choice]
            expected = decode.model_head_by_action_class[top_action_class].value * 100 \
                       + to_expected_value[top_action_class](choice)
            assert expected == actual


all_choice_action_classes = [
    Optional,
    Boolean,
    MaybePayCost,
    SpendAResource,
    # TODO: Add this when Crimea joins
    # CrimeaMaybeChooseResource,
    BottomAction,
    Bolster,
    ChooseSpaceToBuildOn,
    ChooseStructureToBuild,
    GetDefenderCombatCards,
    GetAttackerCombatCards,
    GetDefenderWheelPower,
    GetAttackerWheelPower,
    NordicMaybeUseCombatPower,
    ChooseDeploySpace,
    DeployMech,
    ChooseEnlistReward,
    ChooseRecruitToEnlist,
    LoadResources,
    LoadWorkers,
    MovePieceOneSpace,
    MoveOnePiece,
    ChooseNumWorkers,
    OnOneHex,
    Produce,
    TakeTurn,
    ChooseBoardSpaceForResource,
    ChooseResourceType,
    Trade,
    RemoveCubeFromAnyTopSpace,
    PlaceCubeInAnyBottomSpace
]

if __name__ == '__main__':
    preds = create_test_preds()
    for action_class in all_choice_action_classes:
        # print(f'Testing {action_class}')
        test_decoding(preds, action_class, make_choices[action_class]())
