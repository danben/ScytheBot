from tensorflow.keras.activations import relu
from tensorflow.keras.layers import Activation, Add, BatchNormalization, Conv2D, Dense
from tensorflow.keras.regularizers import l2

REGULARIZATION_FACTOR = 0.01


def hidden_layer(n):
    return Dense(n, activation='relu', kernel_regularizer=l2(REGULARIZATION_FACTOR))


def conv_block(X):
    X = Conv2D(256, 3, padding='same', kernel_regularizer=l2(REGULARIZATION_FACTOR))(X)
    X = BatchNormalization()(X)
    X = Activation(relu)(X)
    return X


def res_block(X):
    X_skip = X
    X = conv_block(X)
    X = Conv2D(256, 3, padding='same', kernel_regularizer=l2(REGULARIZATION_FACTOR))(X)
    X = BatchNormalization()(X)
    X = Add()([X, X_skip])
    X = Activation(relu)(X)
    return X
