from enum import Enum
import random


class StructureBonus(Enum):
    NEXT_TO_TUNNELS = 1
    NEXT_TO_LAKES = 2
    NEXT_TO_ENCOUNTERS = 3
    ON_TUNNELS = 4
    LONGEST_ROW_OF_STRUCTURES = 5
    FARMS_OR_TUNDRAS_WITH_STRUCTURES = 6


def choose():
    return StructureBonus(random.randint(1, 6))
