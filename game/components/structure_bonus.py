import game.components.board as bd
import game.constants as constants
from game.types import TerrainType

from collections import defaultdict
from enum import Enum

import random


def score_adjacent(board, coords, num_spaces_to_coins):
    scores = defaultdict(int)
    for c in coords:
        marked = defaultdict(bool)
        for other_coords in board.base_adjacencies[c]:
            other_space = board.get_space(other_coords)
            if other_space.structure_key and not marked[other_space.structure_key.faction_name]:
                scores[other_space.structure_key.faction_name] += 1
                marked[other_space.structure_key.faction_name] = True

    return {faction: num_spaces_to_coins(num_spaces) for faction, num_spaces in scores.items()}


def score_on_top_of(spaces, num_spaces_to_coins):
    scores = defaultdict(int)
    for space in spaces:
        if space.structure_key:
            scores[space.structure_key.faction_name] += 1

    return {faction: num_spaces_to_coins(num_spaces) for faction, num_spaces in scores.items()}


def score_next_to_tunnels(board):
    def num_spaces_to_coins(num_spaces):
        if num_spaces >= 6:
            return 9
        elif num_spaces >= 4:
            return 6
        elif num_spaces >= 2:
            return 4
        elif num_spaces == 1:
            return 2
        else:
            return 0

    tunnel_spaces = []
    for coords in board.base_adjacencies.keys():
        space = board.get_space(coords)
        if space.has_tunnel():
            tunnel_spaces.append(coords)

    return score_adjacent(board, tunnel_spaces, num_spaces_to_coins)


def score_next_to_lakes(board):
    def num_spaces_to_coins(num_spaces):
        if num_spaces >= 6:
            return 9
        elif num_spaces >= 4:
            return 6
        elif num_spaces >= 2:
            return 4
        elif num_spaces == 1:
            return 2
        else:
            return 0

    lake_spaces = []
    for coords in board.base_adjacencies.keys():
        space = board.get_space(coords)
        if space.terrain_typ is TerrainType.LAKE:
            lake_spaces.append(coords)
    return score_adjacent(board, lake_spaces, num_spaces_to_coins)


def score_next_to_encounters(board):
    def num_spaces_to_coins(num_spaces):
        if num_spaces >= 6:
            return 9
        elif num_spaces >= 4:
            return 6
        elif num_spaces >= 2:
            return 4
        elif num_spaces == 1:
            return 2
        else:
            return 0

    encounter_spaces = [coords for coords in board.base_adjacencies.keys() if board.get_space(coords).has_encounter]
    return score_adjacent(board, encounter_spaces, num_spaces_to_coins)


def score_on_tunnels(board):
    def num_spaces_to_coins(num_spaces):
        if num_spaces >= 3:
            return 6
        elif num_spaces == 2:
            return 4
        elif num_spaces == 1:
            return 2
        else:
            return 0

    tunnel_spaces = []
    for coords in board.base_adjacencies.keys():
        space = board.get_space(coords)
        if space._has_tunnel:
            tunnel_spaces.append(space)
    return score_on_top_of(tunnel_spaces, num_spaces_to_coins)


def score_longest_row_of_structures(board):
    player_scores = defaultdict(int)

    def count_in_a_line(space, faction, move):
        count = 0
        while space and space.structure_key and space.structure_key.faction_name is faction:
            count += 1
            next_r, next_c = move(*space.coords)
            if bd.on_the_board(next_r, next_c) and (next_r, next_c) in board.board_spaces_by_coords:
                space = board.board_spaces_by_coords[(next_r, next_c)]
            else:
                space = None
        return count

    for coords in board.base_adjacencies.keys():
        space = board.get_space(coords)
        if space and space.structure_key and space.terrain_typ is not TerrainType.HOME_BASE:
            faction = space.structure_key.faction_name
            count_down_right = count_in_a_line(space, faction, bd.move_down_and_right)
            count_up_right = count_in_a_line(space, faction, bd.move_up_and_right)
            player_scores[faction] = max(player_scores[faction], count_down_right)
            player_scores[faction] = max(player_scores[faction], count_up_right)

    def length_to_coins(length):
        assert 0 <= length <= 4
        scores = {1: 2, 2: 4, 3: 6, 4: 9}
        return scores[length]

    return {faction: length_to_coins(length) for faction, length in player_scores.items()}


def score_farms_or_tundras_with_structures(board):
    def num_spaces_to_coins(num_spaces):
        if num_spaces >= 4:
            return 9
        elif num_spaces == 3:
            return 6
        elif num_spaces == 2:
            return 4
        elif num_spaces == 1:
            return 2
        else:
            return 0

    farms_and_tundras = []
    for coords in board.base_adjacencies.keys():
        space = board.get_space(coords)
        if space.terrain_typ is TerrainType.FARM or space.terrain_typ is TerrainType.TUNDRA:
            farms_and_tundras.append(space)

    return score_on_top_of(farms_and_tundras, num_spaces_to_coins)


class StructureBonus(Enum):
    NEXT_TO_TUNNELS = 0
    NEXT_TO_LAKES = 1
    NEXT_TO_ENCOUNTERS = 2
    ON_TUNNELS = 3
    LONGEST_ROW_OF_STRUCTURES = 4
    FARMS_OR_TUNDRAS_WITH_STRUCTURES = 5

    @staticmethod
    def random():
        return StructureBonus(random.randint(0, constants.NUM_STRUCTURE_BONUSES - 1))


score_functions = {StructureBonus.NEXT_TO_TUNNELS: score_next_to_tunnels,
                   StructureBonus.NEXT_TO_LAKES: score_next_to_lakes,
                   StructureBonus.NEXT_TO_ENCOUNTERS: score_next_to_encounters,
                   StructureBonus.ON_TUNNELS: score_on_tunnels,
                   StructureBonus.LONGEST_ROW_OF_STRUCTURES: score_longest_row_of_structures,
                   StructureBonus.FARMS_OR_TUNDRAS_WITH_STRUCTURES: score_farms_or_tundras_with_structures}


def score(structure_bonus, board):
    return score_functions[structure_bonus](board)
