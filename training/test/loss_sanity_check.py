from agents.mcts_zero import MCTSZeroAgent
from game.game_state import GameState
from play import play
from training import model

from tensorflow.keras.losses import categorical_crossentropy

import logging
logging.getLogger().setLevel(logging.DEBUG)


def do_it():
    # play one game
    # get samples and distributions
    # run samples through model
    # compare output with distributions
    # sanity check loss
    game_state = GameState.from_num_players(2)
    nn = model.network()
    agents = [MCTSZeroAgent(simulations_per_choice=10, c=0.8, evaluator_network=nn) for _ in range(2)]
    game_state = play.play_game(game_state, agents)
    assert game_state.winner is not None
    for agent in agents:
        agent.complete_episode(game_state.winner)

    experience_collector = agents[0].experience_collector
    encoded_boards, encoded_data, values_and_move_probs = experience_collector.to_numpy()

    preds = nn([encoded_boards, encoded_data])
    print(f'{len(experience_collector.game_states)} game states')
    # print(f'{len(predicted_priors)} predicted priors')
    print(f'{len(values_and_move_probs[0])} samples')
    for i in range(len(values_and_move_probs[0])):
        y_true = [head[i] for head in values_and_move_probs]
        y_pred = [head[i].numpy() for head in preds]
        print(f'Actual: {y_true}')
        print(f'Predicted: {y_pred}')
        loss = [categorical_crossentropy(y_true[i], y_pred[i]).numpy() for i in range(len(y_true))]
        print(f'Loss: {loss}')


if __name__ == '__main__':
    do_it()