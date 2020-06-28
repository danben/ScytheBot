import game.components.piece as gc_piece
import game.components.player_mat as gc_player_mat
import game.state_change as sc
from game import constants
from game.types import Benefit, BottomActionType, FactionName, MechType, PieceType, StarType, TerrainType

import attr
import logging
import numpy as np

from pyrsistent import pmap, pset


@attr.s(frozen=True, slots=True)
class Stars:
    faction_name = attr.ib()
    limits = attr.ib()
    count = attr.ib(default=0)
    achieved = attr.ib(default=pmap({x: 0 for x in StarType}))

    def __str__(self):
        return str([x for lst in [[styp] * self.achieved[styp] for styp in StarType] for x in lst])

    @classmethod
    def from_faction_name(cls, faction_name):
        limits = {x: 1 for x in StarType}
        if faction_name == FactionName.SAXONY:
            limits[StarType.COMBAT] = 6
            limits[StarType.SECRET_OBJECTIVE] = 6
        else:
            limits[StarType.COMBAT] = 2
        return cls(faction_name, limits)


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
    worker_ids = attr.ib(default=pset())
    enlist_rewards = attr.ib(default=pset())
    mech_ids = attr.ib(default=pset())
    structures = attr.ib(default=pset())

    @classmethod
    def new(cls, player_id, faction, player_mat_name, board, starting_combat_cards):
        player_mat = gc_player_mat.PlayerMat.from_player_mat_name(player_mat_name)
        coins = player_mat.starting_money
        popularity = player_mat.starting_popularity
        power = faction.starting_power
        combat_cards = combat_cards_dict(starting_combat_cards)
        stars = Stars.from_faction_name(faction.name)
        home_base = board.home_base(faction.name).coords
        adjacencies = pmap({PieceType.CHARACTER: board.adjacencies_accounting_for_rivers_and_lakes,
                            PieceType.MECH: board.adjacencies_accounting_for_rivers_and_lakes,
                            PieceType.WORKER: board.adjacencies_accounting_for_rivers_and_lakes})
        adjacencies = faction.add_faction_specific_adjacencies(adjacencies, board.base_adjacencies)
        return cls(player_id, faction, player_mat, coins, popularity, power, combat_cards, stars, home_base,
                   adjacencies)

    def __str__(self):
        return f'{self.faction.name} / {self.player_mat.name}'

    def invariant(self, game_state):
        for adj in self.adjacencies[PieceType.WORKER].values():
            for s in adj:
                space = game_state.board.get_space(s)
                assert space.terrain_typ is not TerrainType.HOME_BASE
        for worker_id in self.worker_ids:
            worker_key = gc_piece.worker_key(self.faction_name(), worker_id)
            assert worker_key in game_state.pieces_by_key
        for mech_id in self.mech_ids:
            mech_key = gc_piece.mech_key(self.faction_name(), mech_id)
            assert mech_key in game_state.pieces_by_key
            mech = game_state.pieces_by_key[mech_key]
            assert mech.board_coords
        for structure_typ in self.structures:
            structure_key = gc_piece.structure_key(self.faction_name(), structure_typ)
            assert structure_key in game_state.pieces_by_key
            piece = game_state.pieces_by_key[structure_key]
            assert piece.board_coords
            board_space = game_state.board.get_space(piece.board_coords)
            assert board_space.structure_key == structure_key
        for coords in sc.board_coords_with_mechs(game_state, self):
            assert coords
        for coords in sc.board_coords_with_structures(game_state, self):
            assert coords
        assert len(self.enlist_rewards) == len(self.player_mat.has_enlisted_by_bottom_action_typ)

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

    def score(self, game_state):
        star_score, territory_score, resource_pair_score = 3, 2, 1
        if self.popularity > 6:
            star_score += 1
            territory_score += 1
            resource_pair_score += 1
        if self.popularity > 12:
            star_score += 1
            territory_score += 1
            resource_pair_score += 1
        return star_score * self.stars.count + territory_score * sc.territory_count(game_state, self) \
            + resource_pair_score * sc.resource_pair_count(game_state, self) + self.coins

    def faction_name(self):
        return self.faction.name

    def total_combat_cards(self):
        return sum(self.combat_cards.values())

    def available_combat_cards(self):
        return [i for i in range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1) if self.combat_cards[i]]

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

    ''' This is used when transferring a card from one player to another (Crimea's war power), so we don't discard
        the removed card. '''
    def remove_random_combat_card(self):
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f'{self} loses a random combat card')
        card = self.random_combat_card()
        if card:
            attr.evolve(self, combat_cards=self.combat_cards.set(card, self.combat_cards.get(card)-1)), card
        else:
            return self, None

    def available_workers(self):
        return constants.NUM_WORKERS - len(self.worker_ids)

    def can_upgrade(self):
        for action_space in self.player_mat.action_spaces:
            bottom_action = action_space[1]
            if bottom_action.is_upgradeable():
                return True
        return False

    def cube_spaces_not_fully_upgraded(self):
        return self.player_mat.cube_spaces_not_fully_upgraded()

    def can_enlist(self):
        return len(self.enlist_rewards) < constants.NUM_ENLIST_BENEFITS

    def unenlisted_bottom_action_typs(self):
        return [b for b in BottomActionType if b not in self.player_mat.has_enlisted_by_bottom_action_typ]

    def available_enlist_rewards(self):
        return [benefit for benefit in Benefit if benefit not in self.enlist_rewards]

    def has_enlisted(self, bottom_action_typ):
        return bottom_action_typ in self.player_mat.has_enlisted_by_bottom_action_typ

    def top_action_typs_with_unbuilt_structures(self):
        return [t for t, x in self.player_mat.top_action_cubes_and_structures_by_top_action_typ.items()
                if not x.structure_is_built]

    def structure_is_built(self, top_action_typ):
        return self.player_mat.top_action_cubes_and_structures_by_top_action_typ[top_action_typ].structure_is_built

    def has_unbuilt_structures(self):
        return len(self.structures) < constants.NUM_STRUCTURES

    def undeployed_mech_typs(self):
        return [i for i in MechType if i.value not in self.mech_ids]

    def has_undeployed_mechs(self):
        return len(self.mech_ids) < constants.NUM_MECHS

    def base_move_for_piece_typ(self, piece_typ):
        if piece_typ is PieceType.WORKER:
            return 1
        elif piece_typ is PieceType.CHARACTER or piece_typ is PieceType.MECH:
            return 2 if MechType.SPEED.value in self.mech_ids else 1
        assert False

    def bottom_action_typs_not_fully_upgraded(self):
        return [action_space[1].bottom_action_typ for action_space in self.player_mat.action_spaces
                if action_space[1].is_upgradeable()]

    def upgrade_bottom_action(self, bottom_action_typ):
        return attr.evolve(self, player_mat=self.player_mat.upgrade_bottom_action(bottom_action_typ))
