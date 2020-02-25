from game import constants
from game.types import Benefit, BottomActionType, FactionName, MechType, PieceType, ResourceType, StarType,\
    TerrainType
from game.components.player_mat import PlayerMat
from game.exceptions import GameOver

import attr
import logging
import numpy as np

from pyrsistent import pmap, pset, thaw


@attr.s(frozen=True, slots=True)
class Stars:
    faction_name = attr.ib()
    limits = attr.ib()
    count = attr.ib(default=0)
    achieved = attr.ib(default=pmap({x: 0 for x in StarType}))

    @classmethod
    def from_faction_name(cls, faction_name):
        limits = {x: 1 for x in StarType}
        if faction_name == FactionName.SAXONY:
            limits[StarType.COMBAT] = 6
            limits[StarType.SECRET_OBJECTIVE] = 6
        else:
            limits[StarType.COMBAT] = 2
        return cls(faction_name, limits)

    def achieve(self, typ):
        if self.achieved[typ] < self.limits[typ]:
            logging.debug(f'Star achieved: {typ!r}')
            assert self.count < 6
            player = attr.evolve(self, count=self.count+1, achieved=self.achieved.set(typ, self.achieved[typ]+1))
            if player.count == 6:
                raise GameOver(player)
            return player

    def __str__(self):
        return self.achieved.__str__()


def combat_cards_dict(combat_cards):
    ret = {i: 0 for i in range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD+1)}
    for card in combat_cards:
        ret[card] += 1
    return pmap(ret)


@attr.s(frozen=True, slots=True)
class Player:
    id = attr.ib()
    faction = attr.ib()
    player_mat = attr.ib()
    coins = attr.ib()
    popularity = attr.ib()
    power = attr.ib()
    combat_cards = attr.ib()
    stars = attr.ib()
    home_base = attr.ib()
    adjacencies = attr.ib()
    workers = attr.ib(default=pset())
    enlist_rewards = attr.ib(default=pmap({benefit: False for benefit in Benefit}))
    mechs = attr.ib(default=pset())
    structures = attr.ib(default=pset())

    @classmethod
    def new(cls, id, faction, player_mat_name, board, starting_combat_cards):
        player_mat = PlayerMat.from_player_mat_name(player_mat_name)
        coins = player_mat.starting_money()
        popularity = player_mat.starting_popularity()
        power = faction.starting_power
        combat_cards = combat_cards_dict(starting_combat_cards)
        stars = Stars.from_faction_name(faction.name)
        home_base = board.home_base(faction.name).coords
        adjacencies = pmap({PieceType.CHARACTER: board.adjacencies_accounting_for_rivers_and_lakes,
                            PieceType.MECH: board.adjacencies_accounting_for_rivers_and_lakes,
                            PieceType.WORKER: board.adjacencies_accounting_for_rivers_and_lakes})
        adjacencies = faction.add_faction_specific_adjacencies(adjacencies, board.base_adjacencies)
        return cls(id, faction, player_mat, coins, popularity, power, combat_cards, stars, home_base,
                   adjacencies)

    def __str__(self):
        return f'{self.faction.name} / {self.player_mat.name}'

    def invariant(self):
        for adj in self.adjacencies[PieceType.WORKER].values():
            for s in adj:
                assert s.terrain_typ is not TerrainType.HOME_BASE

    # def resources_string(self, board):
    #     return ''.join([f'{r} : {self.available_resources(r, board)}; ' for r in ResourceType])

    # TODO: figure out whether I want to pass the board in here or change the representation
    # def to_string(self):
    #     return f'Coins: {self.coins}; Popularity: {self.popularity}; Power: {self.power}\n' \
    #            f'Combat cards: {self.combat_cards}\n' \
    #            f'Workers: {[w.board_coords for w in self.workers]}\n' \
    #            f'Mechs: {[m.board_coords for m in self.deployed_mechs]}\n' \
    #            f'Character at {self.character.board_coords} '
        #      f'Stars: {self.stars}; Score: {self.score()}'
        # f'Controlled spaces: {self.controlled_spaces()}\n'
        # f'Controlled resources: {self.resources_string()}\n'

    def log(self, msg):
        logging.debug(f'{self!r} : {msg}')

    # def score(self, board):
    #     star_score, territory_score, resource_pair_score = 3, 2, 1
    #     if self.popularity > 6:
    #         star_score += 1
    #         territory_score += 1
    #         resource_pair_score += 1
    #     if self.popularity > 12:
    #         star_score += 1
    #         territory_score += 1
    #         resource_pair_score += 1
    #     return star_score * self.stars.count + territory_score * GameState.territory_count(game_state, self) \
    #         + resource_pair_score * self.resource_pair_count(board) + self.coins

    def faction_name(self):
        return self.faction.name

    def add_power(self, power):
        logging.debug(f'{self!r} receives {power} power')
        new_power = min(self.power + power, constants.MAX_POWER)
        ret = attr.evolve(self, power=new_power)
        if new_power == constants.MAX_POWER:
            ret = attr.evolve(ret, stars=ret.stars.achieve(StarType.POWER))
        return ret

    def remove_power(self, power):
        return attr.evolve(self, power=max(self.power - power, 0))

    def add_coins(self, coins):
        logging.debug(f'{self!r} receives {coins} coins')
        return attr.evolve(self, coins=self.coins+coins)

    def remove_coins(self, coins):
        logging.debug(f'{self!r} loses {coins} coins')
        return attr.evolve(self, coins=max(self.coins - coins, 0))

    def add_popularity(self, popularity):
        logging.debug(f'{self!r} receives {popularity} popularity')
        ret = attr.evolve(self, popularity=min(self.popularity + popularity, constants.MAX_POPULARITY))
        if ret.popularity == constants.MAX_POPULARITY:
            ret = attr.evolve(ret, stars=ret.stars.achieve(StarType.POPULARITY))
        return ret

    def remove_popularity(self, popularity):
        logging.debug(f'{self!r} loses {popularity} popularity')
        return attr.evolve(self, popularity=max(self.popularity - popularity, 0))

    def total_combat_cards(self):
        return sum(self.combat_cards.values())

    def available_combat_cards(self):
        return [i for i in range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1) if self.combat_cards[i]]

    def add_combat_cards(self, cards):
        logging.debug(f'{self!r} receives {len(cards)} combat cards')
        combat_cards = thaw(self.combat_cards)
        for card in cards:
            combat_cards[card] += 1
        return attr.evolve(self, combat_cards=pmap(combat_cards))

    def discard_combat_card(self, card_value, combat_card_deck):
        assert self.combat_cards[card_value]
        logging.debug(f'{self!r} discards a combat card with value {card_value}')
        combat_cards = self.combat_cards.set(card_value, self.combat_cards[card_value] - 1)
        return attr.evolve(self, combat_cards=combat_cards), combat_card_deck.discard(card_value)

    # TODO: this is kind of weird. Maybe take care of adding them to the deck in the caller?
    def discard_lowest_combat_cards(self, num_cards, combat_card_deck):
        lowest = constants.MIN_COMBAT_CARD
        ret = self
        for i in range(num_cards):
            while not self.combat_cards[lowest]:
                lowest += 1
            if lowest > constants.MAX_COMBAT_CARD:
                assert False
            ret, combat_card_deck = ret.discard_combat_card(lowest, combat_card_deck)
        return ret, combat_card_deck

    def random_combat_card(self, optional=False):
        total = self.total_combat_cards()
        if not total:
            return None
        if optional:
            total += 1
        all_combat_card_values = list(range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1))
        proportions = [self.combat_cards[card] / total for card in all_combat_card_values]
        if optional:
            all_combat_card_values.append(0)
            proportions.append(1/total)
        return np.random.choice(all_combat_card_values, p=proportions)

    def remove_random_combat_card(self):
        logging.debug(f'{self!r} loses a random combat card')
        card = self.random_combat_card()
        if card:
            attr.evolve(self, combat_cards=self.combat_cards.set(card, self.combat_cards.get(card)-1)), card
        else:
            return self, None

    def available_workers(self):
        return constants.NUM_WORKERS - len(self.workers)

    def _add_worker(self, worker_id):
        assert len(self.workers) < constants.NUM_WORKERS and worker_id not in self.workers
        workers = self.workers.add(worker_id)
        if len(workers) == constants.NUM_WORKERS:
            stars = self.stars.achieve(StarType.WORKER)
        else:
            stars = self.stars
        return attr.evolve(self, workers=workers, stars=stars)

    def add_workers(self, ids):
        ret = self
        for id in ids:
            ret = ret._add_worker(id)
        return ret

    def can_upgrade(self):
        for action_space in self.player_mat.action_spaces:
            bottom_action = action_space[1]
            if bottom_action.is_upgradeable():
                return True
        return False

    def cube_spaces_not_fully_upgraded(self):
        return self.player_mat.cube_spaces_not_fully_upgraded()

    def remove_upgrade_cube(self, top_action_typ, spot):
        assert self.can_upgrade()
        player = attr.evolve(self, player_mat=self.player_mat.remove_upgrade_cube(top_action_typ, spot))
        if not player.can_upgrade():
            player = attr.evolve(player, stars=player.stars.achieve(StarType.UPGRADE))
        return player

    def can_enlist(self):
        return not all(self.enlist_rewards.values())

    def mark_enlist_benefit(self, enlist_benefit):
        logging.debug(f'{self!r} takes enlist benefit {enlist_benefit!r}')
        enlist_rewards = self.enlist_rewards.set(enlist_benefit, True)
        if self.can_enlist():
            stars = self.stars
        else:
            stars = self.stars.achieve(StarType.RECRUIT)
        return attr.evolve(self, enlist_rewards=enlist_rewards, stars=stars)

    def unenlisted_bottom_action_types(self):
        return [b for b, enlisted in self.player_mat.has_enlisted_by_bottom_action_typ.items() if not enlisted]

    def available_enlist_rewards(self):
        return [benefit for (benefit, enlisted) in self.enlist_rewards.items() if not enlisted]

    def has_enlisted(self, bottom_action_typ):
        return self.player_mat.has_enlisted_by_bottom_action_typ[bottom_action_typ]

    def top_action_types_with_unbuilt_structures(self):
        return [t for t, x in self.player_mat.top_action_cubes_and_structures_by_top_action_typ.items()
                if not x.structure_is_built]

    def structure_is_built(self, top_action_typ):
        return self.player_mat.top_action_cubes_and_structures_by_top_action_typ[top_action_typ].structure_is_built

    def can_build(self):
        return len(self.structures) < constants.NUM_STRUCTURES

    def can_deploy(self):
        return len(self.mechs) < constants.NUM_MECHS

    def undeployed_mechs(self):
        return [i for i, key in enumerate(self.mechs) if not key]

    def base_move_for_piece_type(self, piece_typ):
        if piece_typ is PieceType.WORKER:
            return 1
        elif piece_typ is PieceType.CHARACTER or piece_typ is PieceType.MECH:
            return 2 if self.mechs[MechType.SPEED] else 1
        assert False

    def can_legally_receive_action_benefit(self, bottom_action_typ):
        if bottom_action_typ is BottomActionType.ENLIST:
            return self.can_enlist()
        elif bottom_action_typ is BottomActionType.DEPLOY:
            return self.can_deploy()
        elif bottom_action_typ is BottomActionType.BUILD:
            return self.can_build()
        elif bottom_action_typ is BottomActionType.UPGRADE:
            return self.can_upgrade()
        else:
            assert False

    def bottom_action_types_not_fully_upgraded(self):
        return [action_space[1].bottom_action_typ for action_space in self.player_mat.action_spaces
                if action_space[1].is_upgradeable()]

    def upgrade_bottom_action(self, bottom_action_typ):
        return attr.evolve(self, player_mat=self.player_mat.upgrade_bottom_action(bottom_action_typ))
