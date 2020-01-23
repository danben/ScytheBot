from game import faction
from game.actions import SpendAResource
from game.components import Board, CombatCards, PlayerMat, StructureBonus
from game.player import Player
from game.types import Benefit, ResourceType

import attr
import logging


class GameState:
    def __init__(self, agents):
        self.action_stack = []
        self.combat_cards = CombatCards()
        num_players = len(agents)
        self.agents_by_player = {}

        factions = faction.choose(num_players)
        self.board = Board(factions)

        player_mat_names = sorted(PlayerMat.choose(num_players), key=lambda x: x.value)
        self.players = [Player(factions[i], player_mat_names[i], self.board, draw_combat_cards=self.combat_cards.draw)
                        for i in range(num_players)]
        self.players_by_faction = {}
        for player, agent in zip(self.players, agents):
            self.players_by_faction[player.faction_name()] = player
            self.agents_by_player[player] = agent

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
        logging.debug(f'Remove {n} {resource_typ!r}')
        eligible_spaces = player.controlled_spaces_with_resource(resource_typ)
        for _ in range(n):
            # TODO: Separate GameState from Game so Agent doesn't need to depend on Game
            # TODO: Think about how the agent is going to meaningfully choose a board space. Or a resource?
            # Might have to resign myself to forcing the agent to learn the mapping between the available
            # options and the choices being presented. At least use a canonical ordering.
            # Ok, here's an idea - let's feed information about the choices into the neural net. Then we can
            # even get rid of [choose_optional_resource_type].
            space = agent.choose_from(list(eligible_spaces))
            logging.debug(f'1 from {space!r}')
            space.remove_resources(resource_typ)
            if not space.has_resource(resource_typ):
                eligible_spaces.remove(space)

    def charge_player(self, player, cost):
        assert player.can_pay_cost(cost)
        logging.debug(f'Pay {cost!r}')
        if cost.coins:
            player.remove_coins(cost.coins)

        if cost.power:
            player.remove_power(cost.power)

        if cost.popularity:
            player.remove_popularity(cost.popularity)

        if cost.combat_cards:
            player.discard_lowest_combat_cards(cost.combat_cards, self.combat_cards)

        for resource_typ in ResourceType:
            amount_owned = player.available_resources(resource_typ)
            amount_owed = cost.resource_cost[resource_typ]
            if amount_owned > amount_owed:
                for _ in range(amount_owed):
                    self.action_stack.append(SpendAResource(resource_typ))
            else:
                assert amount_owned == cost.resource_cost[resource_typ]
                player.remove_all_of_this_resource(resource_typ)

    def give_reward_to_player(self, player, benefit, amt):
        logging.debug(f'Receive {amt} {benefit!r}')
        if benefit is Benefit.POPULARITY:
            player.add_popularity(amt)
        elif benefit is Benefit.COINS:
            player.add_coins(amt)
        elif benefit is Benefit.POWER:
            player.add_power(amt)
        elif benefit is Benefit.COMBAT_CARDS:
            new_cards = self.combat_cards.draw(amt)
            player.add_combat_cards(new_cards)
