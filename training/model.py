from keras.activations import relu
from keras.layers import Activation, BatchNormalization, Concatenate, Conv2D, Dense, Flatten, Input
from keras.models import Model
from keras.regularizers import l2

from game import constants, game_state as gs
from encoders import game_state as gs_enc
from training import constants as model_const, decode, utils

NUM_RESIDUAL_BLOCKS = 10


def resnet(board, num_residual_blocks):
    base = utils.conv_block(board)
    for _ in range(num_residual_blocks):
        base = utils.res_block(base)
    return base


def head(X, num_choices):
    X = utils.hidden_layer(128)(X)
    X = utils.hidden_layer(64)(X)
    X = Dense(num_choices, activation='softmax', kernel_regularizer=l2(utils.REGULARIZATION_FACTOR))(X)
    return X


def network():
    board_input = Input(gs_enc.BOARD_SHAPE, name="board")
    data_input = Input(gs_enc.EncodedGameState.data_shape, name="data")

    board = resnet(board_input, NUM_RESIDUAL_BLOCKS)
    board = Conv2D(2, 1, kernel_regularizer=l2(utils.REGULARIZATION_FACTOR))(board)
    board = BatchNormalization()(board)
    board = Activation(relu)(board)
    board = Flatten()(board)

    data = utils.hidden_layer(2048)(data_input)
    data = utils.hidden_layer(2048)(data)
    data = utils.hidden_layer(1024)(data)
    data = utils.hidden_layer(1024)(data)
    data = utils.hidden_layer(512)(data)
    data = utils.hidden_layer(512)(data)
    data = utils.hidden_layer(256)(data)
    data = utils.hidden_layer(256)(data)

    concat = Concatenate()([board, data])

    value_head = Dense(constants.MAX_PLAYERS, activation="softmax", kernel_regularizer=l2(utils.REGULARIZATION_FACTOR))(concat)
    optional_head = head(concat, 2)
    boolean_head = head(concat, 2)
    maybe_pay_cost_head = head(concat, 2)
    board_coords_head = head(concat, constants.BOARD_ROWS * constants.BOARD_COLS + constants.NUM_FACTIONS)
    piece_typ_head = head(concat, 3) # This will combine with [board_coords_head] to choose a piece
    resource_typ_head = head(concat, constants.NUM_RESOURCE_TYPES)
    bottom_action_typ_head = head(concat, constants.NUM_PLAYER_MAT_ACTION_SPACES)
    enlist_reward_head = head(concat, constants.NUM_ENLIST_BENEFITS)
    mech_typ_head = head(concat, constants.NUM_MECHS)
    structure_typ_head = head(concat, constants.NUM_STRUCTURES)
    cube_space_head = head(concat, constants.NUM_UPGRADE_CUBES)
    optional_combat_card_head = head(concat, constants.NUM_COMBAT_CARD_VALUES + 1)
    wheel_power_head = head(concat, constants.MAX_COMBAT_POWER + 1)
    num_workers_head = head(concat, constants.NUM_WORKERS)
    num_resources_head = head(concat, gs_enc.BOARD_ENCODING__THEORETICAL_MAX_RESOURCES_PER_SPACE)
    choose_action_space_head = head(concat, constants.NUM_PLAYER_MAT_ACTION_SPACES)

    outputs = [None] * model_const.NUM_HEADS
    outputs[model_const.VALUE_HEAD] = value_head
    outputs[model_const.OPTIONAL_HEAD] = optional_head
    outputs[model_const.BOOLEAN_HEAD] = boolean_head
    outputs[model_const.MAYBE_PAY_COST_HEAD] = maybe_pay_cost_head
    outputs[model_const.BOARD_COORDS_HEAD] = board_coords_head
    outputs[model_const.PIECE_TYP_HEAD] = piece_typ_head
    outputs[model_const.RESOURCE_TYP_HEAD] = resource_typ_head
    outputs[model_const.BOTTOM_ACTION_TYP_HEAD] = bottom_action_typ_head
    outputs[model_const.ENLIST_REWARD_HEAD] = enlist_reward_head
    outputs[model_const.MECH_TYP_HEAD] = mech_typ_head
    outputs[model_const.STRUCTURE_TYP_HEAD] = structure_typ_head
    outputs[model_const.CUBE_SPACE_HEAD] = cube_space_head
    outputs[model_const.OPTIONAL_COMBAT_CARD_HEAD] = optional_combat_card_head
    outputs[model_const.WHEEL_POWER_HEAD] = wheel_power_head
    outputs[model_const.NUM_RESOURCES_HEAD] = num_resources_head
    outputs[model_const.NUM_WORKERS_HEAD] = num_workers_head
    outputs[model_const.CHOOSE_ACTION_SPACE_HEAD] = choose_action_space_head

    assert(all(outputs))
    model = Model([board_input, data_input], outputs)
    return model


def evaluate(model, game_state):
    encoded = gs_enc.encode(game_state)
    encoded_data = encoded.encoded_data()
    preds = model.predict([[encoded.board], [encoded_data]])
    values = preds[0][0]
    move_priors = decode.get_move_priors(preds, game_state)
    return values, move_priors


if __name__ == '__main__':
    import tensorflow as tf
    from keras.backend.tensorflow_backend import set_session

    config = tf.ConfigProto(
        gpu_options=tf.GPUOptions(per_process_gpu_memory_fraction=0.8)
        # device_count = {'GPU': 1}
    )
    config.gpu_options.allow_growth = True
    session = tf.Session(config=config)
    set_session(session)
    gs = gs.GameState.from_num_players(constants.MAX_PLAYERS)
    encoded = gs_enc.encode(gs)
    encoded_data = encoded.encoded_data()
    m = network()
    preds = m.predict([[encoded.board], [encoded_data]])
    for pred in preds:
        print(pred)