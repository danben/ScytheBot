from enum import Enum


class Benefit(Enum):
    POWER = 1
    POPULARITY = 2
    COMBAT_CARDS = 3
    COINS = 4

    def __repr__(self):
        if self is Benefit.POWER:
            return "power"
        elif self is Benefit.POPULARITY:
            return "popularity"
        elif self is Benefit.COMBAT_CARDS:
            return "combat cards"
        elif self is Benefit.COINS:
            return "coins"


class BottomActionType(Enum):
    UPGRADE = 1
    DEPLOY = 2
    BUILD = 3
    ENLIST = 4

    def __repr__(self):
        if self is BottomActionType.UPGRADE:
            return "Upgrade"
        elif self is BottomActionType.DEPLOY:
            return "Deploy"
        elif self is BottomActionType.BUILD:
            return "Build"
        elif self is BottomActionType.ENLIST:
            return "Enlist"


class FactionName(Enum):
    RUSVIET = 1
    CRIMEA = 2
    NORDIC = 3
    POLANIA = 4
    SAXONY = 5

    def __repr__(self):
        if self is FactionName.RUSVIET:
            return "Rusviet"
        elif self is FactionName.CRIMEA:
            return "Crimea"
        elif self is FactionName.NORDIC:
            return "Nordic"
        elif self is FactionName.POLANIA:
            return "Polania"
        elif self is FactionName.SAXONY:
            return "Saxony"


class PieceType(Enum):
    WORKER = 1
    MECH = 2
    CHARACTER = 3
    STRUCTURE = 4

    def __repr__(self):
        if self is PieceType.WORKER:
            return "worker"
        elif self is PieceType.MECH:
            return "mech"
        elif self is PieceType.CHARACTER:
            return "character"
        elif self is PieceType.STRUCTURE:
            return "structure"


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

    def __repr__(self):
        if self is PlayerMatName.INDUSTRIAL:
            return "Industrial"
        elif self is PlayerMatName.ENGINEERING:
            return "Engineering"
        elif self is PlayerMatName.PATRIOTIC:
            return "Patriotic"
        elif self is PlayerMatName.MECHANICAL:
            return "Mechanical"
        elif self is PlayerMatName.AGRICULTURAL:
            return "Agricultural"


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
        if self is TerrainType.MOUNTAIN:
            return ResourceType.METAL
        elif self is TerrainType.TUNDRA:
            return ResourceType.OIL
        elif self is TerrainType.FARM:
            return ResourceType.FOOD
        elif self is TerrainType.FOREST:
            return ResourceType.WOOD

    def __repr__(self):
        if self is TerrainType.MOUNTAIN:
            return "mountain"
        elif self is TerrainType.TUNDRA:
            return "tundra"
        elif self is TerrainType.FARM:
            return "farm"
        elif self is TerrainType.FOREST:
            return "forest"
        elif self is TerrainType.VILLAGE:
            return "village"
        elif self is TerrainType.FACTORY:
            return "factory"
        elif self is TerrainType.LAKE:
            return "lake"
        elif self is TerrainType.HOME_BASE:
            return "home base"
