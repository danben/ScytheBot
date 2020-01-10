import game.components.board as bd
from game.types import TerrainType

from collections import defaultdict
from enum import Enum
import random as rnd


class StructureBonus(Enum):
    NEXT_TO_TUNNELS = 1
    NEXT_TO_LAKES = 2
    NEXT_TO_ENCOUNTERS = 3
    ON_TUNNELS = 4
    LONGEST_ROW_OF_STRUCTURES = 5
    FARMS_OR_TUNDRAS_WITH_STRUCTURES = 6

    @staticmethod
    def random():
        return StructureBonus(rnd.randint(1, 6))


def score_adjacent(board, spaces, num_spaces_to_coins):
    scores = defaultdict(int)
    for space in spaces:
        marked = defaultdict(bool)
        for other_space in board.base_adjacencies[space]:
            if other_space.structure and not marked[other_space.structure.faction_name]:
                scores[other_space.structure.faction_name] += 1
                marked[other_space.structure.faction_name] = True
                
    return {faction: num_spaces_to_coins(num_spaces) for faction, num_spaces in scores.items()}


def score_on_top_of(spaces, num_spaces_to_coins):
    scores = defaultdict(int)
    for space in spaces:
        if space.structure:
            scores[space.structure.faction_name] += 1
            
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
    
    return score_adjacent(board, bd.tunnel_spaces, num_spaces_to_coins)


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

    return score_adjacent(board, bd.lake_spaces, num_spaces_to_coins)


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

    return score_adjacent(board, bd.encounter_spaces, num_spaces_to_coins)


def score_on_tunnels(_board):
    def num_spaces_to_coins(num_spaces):
        if num_spaces >= 3:
            return 6
        elif num_spaces == 2:
            return 4
        elif num_spaces == 1:
            return 2
        else:
            return 0

    return score_on_top_of(bd.tunnel_spaces, num_spaces_to_coins)


def score_longest_row_of_structures(board):
    player_scores = defaultdict(int)

    def count_in_a_line(space, faction, move):
        count = 0
        while space and space.structure and space.structure.faction_name is faction:
            count += 1
            next_r, next_c = move(r, c)
            space = board.all_spaces_except_home_bases[next_r][next_c] if bd.on_the_board(next_r, next_c) else None
        return count

    for r, row in enumerate(board.all_spaces_except_home_bases):
        for c, space in enumerate(row):
            if space and space.structure:
                faction = space.structure.faction_name
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

    farms_and_tundras = [space for space in board.base_adjacencies.keys()
                         if space.terrain_typ is TerrainType.FARM or space.terrain_typ is TerrainType.TUNDRA]
    return score_on_top_of(farms_and_tundras, num_spaces_to_coins)


score_functions = {StructureBonus.NEXT_TO_TUNNELS: score_next_to_tunnels,
                   StructureBonus.NEXT_TO_LAKES: score_next_to_lakes,
                   StructureBonus.NEXT_TO_ENCOUNTERS: score_next_to_encounters,
                   StructureBonus.ON_TUNNELS: score_on_tunnels,
                   StructureBonus.LONGEST_ROW_OF_STRUCTURES: score_longest_row_of_structures,
                   StructureBonus.FARMS_OR_TUNDRAS_WITH_STRUCTURES: score_farms_or_tundras_with_structures}


def score(self, board):
    return score_functions[self](board)
