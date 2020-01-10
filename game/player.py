from game import constants
from game.types import Benefit, FactionName, PieceType, ResourceType, StarType, StructureType, TerrainType
from game.components.board import THE_FACTORY
from game.components.piece import Character, Mech, Structure, Worker
from game.components.player_mat import PlayerMat
from game.exceptions import GameOver
from collections import defaultdict

import numpy as np


class Stars:
    def __init__(self, faction_name):
        self.count = 0
        self._achieved = defaultdict(int)
        self._limits = defaultdict(lambda: 1)
        if faction_name == FactionName.SAXONY:
            self._limits[StarType.COMBAT] = 6
            self._limits[StarType.SECRET_OBJECTIVE] = 6
        else:
            self._limits[StarType.COMBAT] = 2

    def achieve(self, typ):
        if self._achieved[typ] < self._limits[typ]:
            self._achieved[typ] += 1
            self.count += 1
            assert self.count < 7
            if self.count == 6:
                raise GameOver()


def combat_cards_dict(combat_cards):
    ret = defaultdict(int)
    for card in combat_cards:
        ret[card] += 1
    return ret


class Player:
    def __init__(self, faction, player_mat_name, board, draw_combat_cards):
        self.faction = faction
        self.player_mat = PlayerMat(player_mat_name)
        self._coins = self.player_mat.starting_money()
        self._popularity = self.player_mat.starting_popularity()
        self._power = faction.starting_power
        self._combat_cards = combat_cards_dict(draw_combat_cards(faction.starting_combat_cards))
        self.stars = Stars(faction.name)
        self._workers = set()
        self.home_base = board.home_base(faction.name)
        spaces_adjacent_to_home_base = board.adjacencies_accounting_for_rivers_and_lakes[self.home_base]
        assert len(spaces_adjacent_to_home_base) == 2
        for space in spaces_adjacent_to_home_base:
            new_worker = Worker(space, self.faction_name)
            self._workers.add(new_worker)
            space.workers.add(new_worker)
        self._deployed_mechs = set()
        self._character = Character(self.home_base, faction.name)
        self.home_base.characters.add(self._character)
        self._enlist_rewards = {benefit: False for benefit in Benefit}
        self.mech_slots = [False] * constants.NUM_MECHS
        self._structures = defaultdict()
        self._adjacencies = {PieceType.CHARACTER: board.adjacencies_accounting_for_rivers_and_lakes.copy(),
                             PieceType.MECH: board.adjacencies_accounting_for_rivers_and_lakes.copy(),
                             PieceType.WORKER: board.adjacencies_accounting_for_rivers_and_lakes.copy()}

        self.faction.add_faction_specific_adjacencies(self._adjacencies, board.base_adjacencies)

    def score(self):
        star_score, territory_score, resource_pair_score = 3, 2, 1
        if self.popularity() > 6:
            star_score += 1
            territory_score += 1
            resource_pair_score += 1
        if self.popularity() > 12:
            star_score += 1
            territory_score += 1
            resource_pair_score += 1
        return star_score * self.stars.count + territory_score * self.territory_count() \
            + resource_pair_score * self.resource_pair_count()

    def faction_name(self):
        return self.faction.name

    def build_structure(self, board_space, structure_typ):
        assert not self._structures[structure_typ()]
        assert not board_space.has_structure
        structure = Structure(board_space, structure_typ, self.faction_name())
        board_space.set_structure(structure)
        self._structures[structure_typ()] = structure
        if not self.can_build():
            self.stars.achieve(StarType.STRUCTURE)
        if structure_typ() is StructureType.MINE:
            for piece_typ in [PieceType.CHARACTER, PieceType.MECH, PieceType.WORKER]:
                adjacencies = self._adjacencies[piece_typ]
                for space, adjacent in adjacencies.items():
                    if space is not board_space and space.has_tunnel(self.faction_name()):
                        if board_space not in adjacent:
                            adjacent.append(board_space)
                        my_adjacencies = adjacencies[board_space]
                        if space not in my_adjacencies:
                            my_adjacencies.append(space)

    def add_power(self, power):
        self._power = min(self._power + power, constants.MAX_POWER)
        if self._power == constants.MAX_POWER:
            self.stars.achieve(StarType.POWER)

    def remove_power(self, power):
        self._power = max(self._power - power, 0)

    def power(self):
        return self._power

    def add_coins(self, coins):
        self._coins += coins

    def remove_coins(self, coins):
        self._coins = max(self._coins - coins, 0)

    def add_popularity(self, popularity):
        self._popularity = min(self._popularity + popularity, constants.MAX_POPULARITY)
        if self._popularity == constants.MAX_POPULARITY:
            self.stars.achieve(StarType.POPULARITY)

    def remove_popularity(self, popularity):
        self._popularity = max(self._popularity - popularity, 0)

    def popularity(self):
        return self._popularity

    def total_combat_cards(self):
        return sum(self._combat_cards.values())

    def available_combat_cards(self):
        return [i for i in range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1) if self._combat_cards[i]]

    def add_combat_cards(self, cards):
        for card in cards:
            self._combat_cards[card] += 1

    def discard_combat_card(self, card_value, combat_card_deck):
        assert self._combat_cards[card_value]
        self._combat_cards[card_value] -= 1
        combat_card_deck.discard(card_value)

    def discard_lowest_combat_cards(self, num_cards, combat_card_deck):
        lowest = constants.MIN_COMBAT_CARD
        for i in range(num_cards):
            while not self._combat_cards[lowest]:
                lowest += 1
            if lowest > constants.MAX_COMBAT_CARD:
                assert False
            self.discard_combat_card(lowest, combat_card_deck)

    def remove_random_combat_card(self):
        total = self.total_combat_cards()
        if not total:
            return None
        all_combat_card_values = range(constants.MIN_COMBAT_CARD, constants.MAX_COMBAT_CARD + 1)
        proportions = [self._combat_cards[card] / total for card in all_combat_card_values]
        card = np.random.choice(all_combat_card_values, p=proportions)
        self._combat_cards[card] -= 1
        return card

    def add_worker(self, board_space):
        assert len(self._workers) < constants.NUM_WORKERS
        new_worker = Worker(board_space, self.faction_name)
        self._workers.add(new_worker)
        board_space.workers.add(new_worker)
        if len(self._workers) == constants.NUM_WORKERS:
            self.stars.achieve(StarType.WORKER)

    def can_upgrade(self):
        for action_space in self.player_mat.action_spaces():
            bottom_action = action_space[1]
            if bottom_action.is_upgradeable():
                return True
        return False

    def maybe_get_upgrade_star(self):
        if not self.can_upgrade():
            self.stars.achieve(StarType.UPGRADE)

    def cube_spaces_not_fully_upgraded(self):
        ret = []
        for action_space in self.player_mat.action_spaces():
            top_action = action_space[0]
            for i in top_action.upgradeable_cubes():
                ret.append((top_action, i))

        return ret

    def spaces_with_workers(self):
        ret = set([worker.board_space for worker in self._workers
                   if worker.board_space.terrain_typ is not TerrainType.LAKE])
        ret.remove(self.home_base)
        return ret

    def spaces_with_mechs(self):
        ret = set([mech.board_space for mech in self._deployed_mechs])
        ret.remove(self.home_base)
        return ret

    def spaces_with_structures(self):
        ret = set()
        for structure in self._structures.values():
            if structure:
                ret.add(structure.board_space)
        return ret

    def controlled_spaces(self):
        s = self.spaces_with_workers() | self.spaces_with_mechs()
        s.add(self._character.board_space)
        s.remove(self.home_base)
        for space in s:
            if space.controller is not self:
                s.remove(space)
        for space in self.spaces_with_structures():
            if space.controller() is self:
                s.add(space)
        return s

    def territory_count(self):
        s = self.controlled_spaces()
        ret = len(s)
        if THE_FACTORY in s:
            ret += 2
        return ret

    def controlled_spaces_with_resource(self, resource_typ):
        return [space for space in self.controlled_spaces() if space.has_resource(resource_typ)]

    def legal_building_spots(self):
        return [space for space in self.spaces_with_workers() if not space.has_structure()]

    def end_turn(self):
        self._character.moved_this_turn = False
        self._character.moved_into_enemy_territory_this_turn = False
        for worker in self._workers:
            worker.moved_this_turn = False
            worker.moved_into_enemy_territory_this_turn = False
        for mech in self._deployed_mechs:
            mech.moved_this_turn = False
            mech.moved_into_enemy_territory_this_turn = False
        if self.faction_name() is FactionName.CRIMEA:
            self.faction.spent_combat_card_as_resource_this_turn = False

    def can_enlist(self):
        return not all(self._enlist_rewards.values())

    def mark_enlist_benefit(self, enlist_benefit):
        self._enlist_rewards[enlist_benefit] = True
        if not self.can_enlist():
            self.stars.achieve(StarType.RECRUIT)

    def unenlisted_bottom_actions(self):
        ret = []
        for action_space in self.player_mat.action_spaces():
            bottom_action = action_space[1]
            if not bottom_action.enlisted:
                ret.append(bottom_action)
        return ret

    def available_enlist_rewards(self):
        return [benefit for (benefit, enlisted) in self._enlist_rewards.items() if not enlisted]

    def top_actions_with_unbuilt_structures(self):
        ret = []
        for action_space in self.player_mat.action_spaces():
            top_action = action_space[0]
            if not top_action.structure_is_built():
                ret.append(top_action)
        return ret

    def can_build(self):
        return not all(self._structures.values())

    def can_deploy(self):
        return not all(self.mech_slots)

    def undeployed_mechs(self):
        ret = []
        for i, deployed in enumerate(self.mech_slots):
            if not deployed:
                ret.append(i)
        return ret

    def deploy_mech(self, mech, space, board):
        self.mech_slots[mech] = True
        new_mech = Mech(space, self)
        self._deployed_mechs.add(new_mech)
        space.mechs.add(new_mech)
        if mech == constants.RIVERWALK_MECH:
            self.add_riverwalk_adjacencies(board)
        elif mech == constants.TELEPORT_MECH:
            self.add_teleport_adjacencies(board)
        if len(self._deployed_mechs) == constants.NUM_MECHS:
            self.stars.achieve(StarType.MECH)

    def add_riverwalk_adjacencies(self, board):
        self.faction.add_riverwalk_adjacencies(self._adjacencies, board)

    def add_teleport_adjacencies(self, board):
        self.faction.add_teleport_adjacencies(self._adjacencies, board)

    def available_resources(self, resource_typ):
        return sum([space.amount_of(resource_typ) for space in self.controlled_spaces()])

    def resource_pair_count(self):
        num_resources = sum([self.available_resources(r) for r in ResourceType])
        return int(num_resources / 2)

    def can_pay_cost(self, cost):
        return (self._power >= cost.power
                and self._popularity >= cost.popularity
                and self._coins >= cost.coins
                and self.available_resources(ResourceType.WOOD) >= cost.wood
                and self.available_resources(ResourceType.OIL) >= cost.oil
                and self.available_resources(ResourceType.METAL) >= cost.metal
                and self.available_resources(ResourceType.FOOD) >= cost.food
                and self.total_combat_cards >= cost.combat_cards)

    def mill_space(self):
        return self._structures[StructureType.MILL]

    def produceable_spaces(self):
        spaces = self.spaces_with_workers()
        mill_space = self.mill_space()
        if mill_space:
            spaces.add(mill_space)
        for space in spaces:
            if space.produced_on_this_turn:
                spaces.remove(space)
        return spaces

    def movable_pieces(self):
        s = self._workers | self._deployed_mechs
        s.add(self._character)
        for worker in self._workers:
            if worker.board_space.terrain_typ is TerrainType.LAKE:
                s.remove(worker)
        return [piece for piece in s if not piece.moved_this_turn]

    def base_move_for_piece_type(self, piece_typ):
        if piece_typ is PieceType.WORKER:
            return 1
        elif piece_typ is PieceType.CHARACTER or piece_typ is PieceType.MECH:
            return 2 if self.mech_slots[constants.SPEED_MECH] else 1
        assert False

    def effective_adjacent_spaces(self, piece, board):
        assert piece.faction_name is self.faction.name
        adjacent_spaces = self._adjacencies[piece.typ()][piece.board_space]
        if self.mech_slots[constants.TELEPORT_MECH] and piece.is_plastic():
            extra_adjacent_spaces = self.faction.extra_adjacent_spaces(piece, board)
            adjacent_spaces = adjacent_spaces.copy()
            for space in extra_adjacent_spaces:
                if space not in adjacent_spaces:
                    adjacent_spaces.append(space)
            return adjacent_spaces
        elif piece.is_worker():
            adjacent_spaces_without_enemies = []
            for space in adjacent_spaces:
                controller = space.controller()
                if controller is None or controller is self.faction_name():
                    adjacent_spaces_without_enemies.append(space)
                elif not (space.characters or space.mechs or space.workers):
                    adjacent_spaces_without_enemies.append(space)
            return adjacent_spaces_without_enemies
        else:
            return adjacent_spaces
