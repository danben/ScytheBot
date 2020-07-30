import logging

import game.play as gp
import game.state_change as sc


async def play_game(game_state, agents):
    logging.debug('\nNEW GAME\n')
    while not game_state.is_over():
        # logging.debug(f'Board: {game_state.board}')
        agent = agents[game_state.current_player_idx]
        chosen = await agent.select_move(game_state)
        if logging.getLogger().isEnabledFor(logging.INFO):
            next_action = game_state.action_stack.first
            logging.info(f'{sc.get_current_player(game_state)} chooses {chosen} for {next_action}')
        game_state = gp.apply_move(game_state, chosen)
        # game_state.board.invariant(game_state)
        # sc.get_current_player(game_state).invariant(game_state)

    if logging.getLogger().isEnabledFor(logging.INFO):
        logging.info(f'Game ended in {game_state.num_turns} turns')
        for (faction_name, score) in game_state.player_scores.items():
            player = sc.get_player_by_faction_name(game_state, faction_name)
            logging.info(f'\n{faction_name} scored {score} points!\n'
                         f'Popularity: {player.popularity}\n'
                         f'Stars: {player.stars.count} ({player.stars.__str__()})\n'
                         f'Territories: {len(sc.controlled_spaces(game_state, player))}\n'
                         f'Resource pairs: {sc.resource_pair_count(game_state, player)}\n'
                         f'Coins: {player.coins}\n')
            logging.info(f'Winner is {game_state.winner}')
    return game_state
