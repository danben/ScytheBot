from game import faction
from game.actions import DiscreteChoice, NumericChoice, StateChange, TakeTurn
from game.agents import RandomAgent
from game.components import Board, CombatCards, PlayerMat, StructureBonus
from game.exceptions import GameOver
from game.player import Player
from game.types import Benefit, FactionName, ResourceType

import game.components.structure_bonus as structure_bonus
import logging
logging.basicConfig(level=logging.DEBUG)

''' TODO list
 - fix BottomAction.apply: enlist benefits happen after the current player finishes their action
 - agents need to be able to specify the amount of workers they take when producing (maybe use choose_numeric for now)
 - make sure all actions have the right level of optionality
 - implement NumericChoice actions
 - redo DiscreteChoice actions to be more specific
 - all of the faction abilities
  - Polania gets 2 encounters per card
 - encounter cards
 - factory cards
 - secret objectives
 - stringify everything
 - logging
 - random agent
 '''


class Game:
    def __init__(self, agents):
        self.action_stack = []
        self.combat_cards = CombatCards()

        num_players = len(agents)
        assert num_players == 2
        self.agents = agents

        factions = faction.choose(num_players)
        self.board = Board(factions)

        player_mat_names = sorted(PlayerMat.choose(num_players), key=lambda x: x.value)
        self.players = [Player(factions[i], player_mat_names[i], self.board, draw_combat_cards=self.combat_cards.draw)
                        for i in range(num_players)]
        self.players_by_faction = {}
        for player in self.players:
            self.players_by_faction[player.faction_name()] = player

        self.current_player_idx = 0
        self.current_player = self.players[self.current_player_idx]

        self.spaces_produced_this_turn = set()
        self.structure_bonus = StructureBonus.random()

    def get_left_player(self):
        new_idx = self.current_player_idx - 1
        if new_idx < 0:
            new_idx = len(self.players) - 1
        return self.players[new_idx]

    def get_right_player(self):
        new_idx = self.current_player_idx + 1
        if new_idx == len(self.players):
            new_idx = 0
        return self.players[new_idx]

    @staticmethod
    def remove_n_resources_from_player(player, n, resource_typ, agent):
        eligible_spaces = player.controlled_spaces_with_resource(resource_typ)
        for _ in range(n):
            # TODO: Separate GameState from Game so Agent doesn't need to depend on Game
            # TODO: Think about how the agent is going to meaningfully choose a board space. Or a resource?
            # Might have to resign myself to forcing the agent to learn the mapping between the available
            # options and the choices being presented. At least use a canonical ordering.
            # Ok, here's an idea - let's feed information about the choices into the neural net. Then we can
            # even get rid of [choose_optional_resource_type].
            space = agent.choose_from(list(eligible_spaces))
            space.remove_resources(resource_typ)
            if not space.has_resource(resource_typ):
                eligible_spaces.remove(space)

    def charge_player(self, player, cost, agent):
        assert player.can_pay_cost(cost)
        player.remove_coins(cost.coins)
        player.remove_power(cost.power)
        player.remove_popularity(cost.popularity)
        player.discard_lowest_combat_cards(cost.combat_cards, self.combat_cards)
        if player.faction_name() is FactionName.CRIMEA and not player.faction.spent_combat_card_as_resource_this_turn:
            choice = agent.choose_optional_resource_type()
            if choice and cost.resource_cost[choice]:
                player.faction.spent_combat_card_as_resource_this_turn = True
                cost.reduce_by_1(choice)
                player.discard_lowest_combat_cards(1, self.combat_cards)

        for resource_typ in ResourceType:
            Game.remove_n_resources_from_player(player, cost.resource_cost[resource_typ], resource_typ, agent)

    def give_reward_to_player(self, player, benefit, amt):
        if benefit is Benefit.POPULARITY:
            player.add_popularity(amt)
        elif benefit is Benefit.COINS:
            player.add_coins(amt)
        elif benefit is Benefit.POWER:
            player.add_power(amt)
        elif benefit is Benefit.COMBAT_CARDS:
            new_cards = self.combat_cards.draw(amt)
            player.add_combat_cards(new_cards)

    def play(self):
        num_turns = 0
        try:
            while True:
                self.current_player = self.players[self.current_player_idx]
                logging.debug(f'Next player: {self.current_player.faction_name()} / '
                              f'{self.current_player.player_mat.name()}')
                logging.debug(f'{self.current_player.to_string()}')
                self.action_stack.append(TakeTurn())
                agent = self.agents[self.current_player_idx]
                while self.action_stack:
                    next_action = self.action_stack.pop()
                    cost = next_action.cost(self)
                    if cost:
                        if not self.current_player.can_pay_cost(cost):
                            logging.debug(f'Cant afford {cost} so skipping')
                            continue
                        self.charge_player(self.current_player, cost, agent)

                    if isinstance(next_action, StateChange):
                        next_action.apply(self)
                    if isinstance(next_action, DiscreteChoice):
                        choices = next_action.choices(self)
                        # We're probably going to need to replace the choosing mechanism altogether.
                        # The agent should know the kind of thing that it's choosing from.
                        if choices:
                            choice = agent.choose_from(choices)
                            logging.debug(f'Chosen: {choice}')
                            self.action_stack.append(choice)
                    if isinstance(next_action, NumericChoice):
                        ''' TODO: Implement this '''
                        pass

                self.current_player.end_turn()

                # TODO: Why is this not a property of the board?
                for space in self.spaces_produced_this_turn:
                    space.produced_this_turn = False
                self.spaces_produced_this_turn.clear()
                self.current_player_idx += 1
                if self.current_player_idx == len(self.players):
                    self.current_player_idx = 0
                num_turns += 1
                if num_turns == 500:
                    logging.debug("500 turns without a winner")
                    raise GameOver()
        except GameOver:
            player_scores = {faction_name: player.score() for faction_name, player in self.players_by_faction.items()}
            structure_bonus_scores = structure_bonus.score(self.structure_bonus, self.board)
            for faction_name, structure_bonus_score in structure_bonus_scores.items():
                player_scores[faction_name] += structure_bonus_score

            for (player, score) in player_scores.items():
                print(f'{player} scored {score} points')


if __name__ == '__main__':
    game = Game([RandomAgent(), RandomAgent()])
    game.play()