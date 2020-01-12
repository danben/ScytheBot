from collections import defaultdict
from enum import Enum

import logging


class Benefit(Enum):
    POWER = 1
    POPULARITY = 2
    COMBAT_CARDS = 3
    COINS = 4


class FactionName(Enum):
    RUSVIET = 1
    CRIMEA = 2
    NORDIC = 3
    POLANIA = 4
    SAXONY = 5


class PieceType(Enum):
    WORKER = 1
    MECH = 2
    CHARACTER = 3
    STRUCTURE = 4


class StructureType(Enum):
    MILL = 1
    MONUMENT = 2
    MINE = 3
    ARMORY = 4


class PlayerMatName(Enum):
    INDUSTRIAL = 1
    ENGINEERING = 2
    PATRIOTIC = 3
    MECHANICAL = 4
    AGRICULTURAL = 5


class ResourceType(Enum):
    WOOD = 1
    METAL = 2
    OIL = 3
    FOOD = 4

    def __repr__(self):
        if self is ResourceType.WOOD:
            return "wood"
        elif self is ResourceType.METAL:
            return "metal"
        elif self is ResourceType.OIL:
            return "oil"
        elif self is ResourceType.FOOD:
            return "food"


class StarType(Enum):
    UPGRADE = 1
    MECH = 2
    STRUCTURE = 3
    RECRUIT = 4
    WORKER = 5
    SECRET_OBJECTIVE = 6
    COMBAT = 7
    POPULARITY = 8
    POWER = 9


class TerrainType(Enum):
    MOUNTAIN = 1
    TUNDRA = 2
    FARM = 3
    FOREST = 4
    VILLAGE = 5
    FACTORY = 6
    LAKE = 7
    HOME_BASE = 8

    def resource_type(self):
        if self is TerrainType.MOUNTAIN: return ResourceType.METAL
        elif self is TerrainType.TUNDRA: return ResourceType.OIL
        elif self is TerrainType.FARM: return ResourceType.FOOD
        elif self is TerrainType.FOREST: return ResourceType.WOOD

    def __repr__(self):
        if self is TerrainType.MOUNTAIN: return "mountain"
        elif self is TerrainType.TUNDRA: return "tundra"
        elif self is TerrainType.FARM: return "farm"
        elif self is TerrainType.FOREST: return "forest"
        elif self is TerrainType.VILLAGE: return "village"
        elif self is TerrainType.FACTORY: return "factory"
        elif self is TerrainType.LAKE: return "lake"
        elif self is TerrainType.HOME_BASE: return "home base"
