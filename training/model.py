from tensorflow.keras.activations import relu
from tensorflow.keras.layers import Activation, BatchNormalization, Concatenate, Conv2D, Dense, Flatten, Input
from tensorflow.keras.models import Model
from tensorflow.keras.regularizers import l2

from game import constants, game_state as gs
from encoders import game_state as gs_enc
from training import decode, utils
from training.constants import Head

import numpy as np
import time

NUM_RESIDUAL_BLOCKS = 5

head_sizes = {
    Head.VALUE_HEAD: constants.MAX_PLAYERS,
    Head.OPTIONAL_HEAD: 2,
    Head.BOOLEAN_HEAD: 2,
    Head.MAYBE_PAY_COST_HEAD: 2,
    Head.BOARD_COORDS_HEAD: constants.BOARD_ROWS * constants.BOARD_COLS + constants.NUM_FACTIONS,
    Head.PIECE_TYP_HEAD: 3,  # Structures are not represented, so we don't use len(PieceType)
    Head.RESOURCE_TYP_HEAD: constants.NUM_RESOURCE_TYPES,
    Head.BOTTOM_ACTION_TYP_HEAD: constants.NUM_PLAYER_MAT_ACTION_SPACES,
    Head.ENLIST_REWARD_HEAD: constants.NUM_ENLIST_BENEFITS,
    Head.MECH_TYP_HEAD: constants.NUM_MECHS,
    Head.STRUCTURE_TYP_HEAD: constants.NUM_STRUCTURES,
    Head.CUBE_SPACE_HEAD: constants.NUM_UPGRADE_CUBES,
    Head.OPTIONAL_COMBAT_CARD_HEAD: constants.NUM_COMBAT_CARD_VALUES + 1,
    Head.WHEEL_POWER_HEAD: constants.MAX_COMBAT_POWER + 1,
    Head.NUM_WORKERS_HEAD: constants.NUM_WORKERS,
    Head.NUM_RESOURCES_HEAD: gs_enc.BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE,
    Head.CHOOSE_ACTION_SPACE_HEAD: constants.NUM_PLAYER_MAT_ACTION_SPACES
}


def resnet(board, num_residual_blocks):
    base = utils.conv_block(board)
    for _ in range(num_residual_blocks):
        base = utils.res_block(base)
    return base


def head(x, num_choices):
    # x = utils.hidden_layer(128)(x)
    # x = utils.hidden_layer(64)(x)
    x = Dense(num_choices, activation='softmax', kernel_regularizer=l2(utils.REGULARIZATION_FACTOR))(x)
    return x


def network():
    board_input = Input(gs_enc.BOARD_SHAPE, name="board")
    data_input = Input(gs_enc.EncodedGameState.data_shape, name="data")

    board = resnet(board_input, NUM_RESIDUAL_BLOCKS)
    board = Conv2D(2, 1, kernel_regularizer=l2(utils.REGULARIZATION_FACTOR))(board)
    board = BatchNormalization()(board)
    board = Activation(relu)(board)
    board = Flatten()(board)

    data = utils.hidden_layer(2048)(data_input)
    # data = utils.hidden_layer(2048)(data)
    data = utils.hidden_layer(1024)(data)
    # data = utils.hidden_layer(1024)(data)
    data = utils.hidden_layer(512)(data)
    # data = utils.hidden_layer(512)(data)
    data = utils.hidden_layer(256)(data)
    # data = utils.hidden_layer(256)(data)

    concat = Concatenate()([board, data])

    outputs = [None] * len(Head)
    outputs[Head.VALUE_HEAD.value] = Dense(head_sizes[Head.VALUE_HEAD], activation="softmax",
                                            kernel_regularizer=l2(utils.REGULARIZATION_FACTOR))(concat)
    outputs[Head.OPTIONAL_HEAD.value] = head(concat, head_sizes[Head.OPTIONAL_HEAD])
    outputs[Head.BOOLEAN_HEAD.value] = head(concat, head_sizes[Head.BOOLEAN_HEAD])
    outputs[Head.MAYBE_PAY_COST_HEAD.value] = head(concat, head_sizes[Head.MAYBE_PAY_COST_HEAD])
    outputs[Head.BOARD_COORDS_HEAD.value] = head(concat, head_sizes[Head.BOARD_COORDS_HEAD])
    # This will combine with [board_coords_head] to choose a piece
    outputs[Head.PIECE_TYP_HEAD.value] = head(concat, head_sizes[Head.PIECE_TYP_HEAD])
    outputs[Head.RESOURCE_TYP_HEAD.value] = head(concat, head_sizes[Head.RESOURCE_TYP_HEAD])
    outputs[Head.BOTTOM_ACTION_TYP_HEAD.value] = head(concat, head_sizes[Head.BOTTOM_ACTION_TYP_HEAD])
    outputs[Head.ENLIST_REWARD_HEAD.value] = head(concat, head_sizes[Head.ENLIST_REWARD_HEAD])
    outputs[Head.MECH_TYP_HEAD.value] = head(concat, head_sizes[Head.MECH_TYP_HEAD])
    outputs[Head.STRUCTURE_TYP_HEAD.value] = head(concat, head_sizes[Head.STRUCTURE_TYP_HEAD])
    outputs[Head.CUBE_SPACE_HEAD.value] = head(concat, head_sizes[Head.CUBE_SPACE_HEAD])
    outputs[Head.OPTIONAL_COMBAT_CARD_HEAD.value] = head(concat, head_sizes[Head.OPTIONAL_COMBAT_CARD_HEAD])
    outputs[Head.WHEEL_POWER_HEAD.value] = head(concat, head_sizes[Head.WHEEL_POWER_HEAD])
    outputs[Head.NUM_WORKERS_HEAD.value] = head(concat, head_sizes[Head.NUM_WORKERS_HEAD])
    outputs[Head.NUM_RESOURCES_HEAD.value] = head(concat, head_sizes[Head.NUM_RESOURCES_HEAD])
    outputs[Head.CHOOSE_ACTION_SPACE_HEAD.value] = head(concat, head_sizes[Head.CHOOSE_ACTION_SPACE_HEAD])

    for output in outputs:
        assert output is not None
    model = Model([board_input, data_input], outputs)
    return model


def map_factions_to_values(game_state, values):
    indices_by_faction_name = gs_enc.get_indices_by_faction_name(game_state)
    return {f: values[i] for (f, i) in indices_by_faction_name.items()}


# Even though [choices] is implied by [game_state], we pass it in here to avoid recomputing it
# since we needed to compute it in the initial call to [select_move] in order to shortcut in the
# event that there are 0 or 1 choices.
def evaluate(model, game_states, choices):
    encoded = [gs_enc.encode(game_state) for game_state in game_states]
    encoded_data = np.array([e.encoded_data() for e in encoded])
    boards = np.array([e.board for e in encoded])
    # This will give us a list of [len(game_states)] predictions for each head
    inverted_preds = model.predict([boards, encoded_data], batch_size=len(game_states), use_multiprocessing=False)
    # inverted_preds = model([boards, encoded_data], training=False)

    # What we really want is a list of samples, where each sample contains a single prediction for each head
    preds = []
    for i in range(len(game_states)):
        preds.append([inverted_preds[head][i] for head in range(len(Head))])
    values = [map_factions_to_values(game_states[i], preds[i][Head.VALUE_HEAD.value]) for i in range(len(game_states))]
    move_priors = [decode.get_move_priors(preds[i], game_states[i].action_stack.first.__class__, choices[i])
                   for i in range(len(game_states))]
    return values, move_priors


def empty_heads(len):
    return [np.zeros((len, head_sizes[h])) for h in Head]


if __name__ == '__main__':
    import tensorflow as tf
    # import keras.backend as K
    # tf.config.set_visible_devices([], 'GPU')
    # tf.debugging.set_log_device_placement(True)
    import os
    # K.set_floatx('float16')
    # K.set_epsilon(1e-4)
    # K.set_learning_phase(0)

    # V1
    # physical_devices = tf.config.experimental.list_physical_devices('GPU')
    # tf.config.experimental.set_memory_growth(physical_devices[0], True)
    # tf.compat.v1.config.optimizer.set_experimental_options({'layout_optimizer':True})

    # V2
    #physical_devices = tf.config.list_physical_devices('GPU')
    #tf.config.experimental.set_memory_growth(physical_devices[0], True)
    gs = gs.GameState.from_num_players(constants.MAX_PLAYERS)
    m = network()
    from game import play
    for i in range(10):
        encoded = gs_enc.encode(gs)
        encoded_data = encoded.encoded_data()
        s = time.time()
        preds = m.predict([[encoded.board], [encoded_data]])
        print(f'Time to predict: {time.time() - s}')
        gs = play.apply_move(gs, gs.legal_moves()[0])
