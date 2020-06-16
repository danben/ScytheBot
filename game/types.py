import game.constants as constants

from enum import Enum


class Benefit(Enum):
    POWER = 0
    POPULARITY = 1
    COMBAT_CARDS = 2
    COINS = 3

    def __str__(self):
        if self is Benefit.POWER:
            return "power"
        elif self is Benefit.POPULARITY:
            return "popularity"
        elif self is Benefit.COMBAT_CARDS:
            return "combat cards"
        elif self is Benefit.COINS:
            return "coins"

        assert False


class BottomActionType(Enum):
    UPGRADE = 0
    DEPLOY = 1
    BUILD = 2
    ENLIST = 3

    def __str__(self):
        if self is BottomActionType.UPGRADE:
            return "Upgrade"
        elif self is BottomActionType.DEPLOY:
            return "Deploy"
        elif self is BottomActionType.BUILD:
            return "Build"
        elif self is BottomActionType.ENLIST:
            return "Enlist"

        assert False


class TopActionType(Enum):
    MOVEGAIN = 0
    BOLSTER = 1
    PRODUCE = 2
    TRADE = 3


class FactionName(Enum):
    RUSVIET = 0
    CRIMEA = 1
    NORDIC = 2
    POLANIA = 3
    SAXONY = 4

    def __str__(self):
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

        assert False


class PieceType(Enum):
    WORKER = 0
    MECH = 1
    CHARACTER = 2
    STRUCTURE = 3

    def __str__(self):
        if self is PieceType.WORKER:
            return "worker"
        elif self is PieceType.MECH:
            return "mech"
        elif self is PieceType.CHARACTER:
            return "character"
        elif self is PieceType.STRUCTURE:
            return "structure"

        assert False

    def num_pieces(self):
        if self is PieceType.WORKER:
            return constants.NUM_WORKERS
        elif self is PieceType.MECH:
            return constants.NUM_MECHS
        elif self is PieceType.STRUCTURE:
            return constants.NUM_STRUCTURES
        elif self is PieceType.CHARACTER:
            return 1

        assert False


class MechType(Enum):
    RIVERWALK = 0
    TELEPORT = 1
    COMBAT = 2
    SPEED = 3


class StructureType(Enum):
    MILL = 0
    MONUMENT = 1
    MINE = 2
    ARMORY = 3

    def __str__(self):
        if self is StructureType.MILL:
            return "mill"
        elif self is StructureType.MONUMENT:
            return "monument"
        elif self is StructureType.MINE:
            return "mine"
        elif self is StructureType.ARMORY:
            return "armory"

        assert False

    @staticmethod
    def of_top_action_typ(top_action_typ):
        if top_action_typ is TopActionType.MOVEGAIN:
            return StructureType.MINE
        elif top_action_typ is TopActionType.PRODUCE:
            return StructureType.MILL
        elif top_action_typ is TopActionType.BOLSTER:
            return StructureType.MONUMENT
        elif top_action_typ is TopActionType.TRADE:
            return StructureType.ARMORY

        assert False

    def to_top_action_typ(self):
        if self is StructureType.MINE:
            return TopActionType.MOVEGAIN
        elif self is StructureType.MILL:
            return TopActionType.PRODUCE
        elif self is StructureType.MONUMENT:
            return TopActionType.BOLSTER
        elif self is StructureType.ARMORY:
            return TopActionType.TRADE

        assert False


class PlayerMatName(Enum):
    INDUSTRIAL = 0
    ENGINEERING = 1
    PATRIOTIC = 2
    MECHANICAL = 3
    AGRICULTURAL = 4

    def __str__(self):
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

        assert False


class ResourceType(Enum):
    WOOD = 0
    METAL = 1
    OIL = 2
    FOOD = 3

    def __str__(self):
        if self is ResourceType.WOOD:
            return "wood"
        elif self is ResourceType.METAL:
            return "metal"
        elif self is ResourceType.OIL:
            return "oil"
        elif self is ResourceType.FOOD:
            return "food"

        assert False


class StarType(Enum):
    UPGRADE = 0
    MECH = 1
    STRUCTURE = 2
    RECRUIT = 3
    WORKER = 4
    SECRET_OBJECTIVE = 5
    COMBAT = 6
    POPULARITY = 7
    POWER = 8

    def __str__(self):
        if self is StarType.UPGRADE:
            return "upgrade"
        elif self is StarType.MECH:
            return "mech"
        elif self is StarType.STRUCTURE:
            return "structure"
        elif self is StarType.RECRUIT:
            return "recruit"
        elif self is StarType.WORKER:
            return "worker"
        elif self is StarType.SECRET_OBJECTIVE:
            return "secret objective"
        elif self is StarType.COMBAT:
            return "combat"
        elif self is StarType.POPULARITY:
            return "popularity"
        elif self is StarType.POWER:
            return "power"

        assert False

    def __repr__(self):
        return self.__str__()


class TerrainType(Enum):
    MOUNTAIN = 0
    TUNDRA = 1
    FARM = 2
    FOREST = 3
    VILLAGE = 4
    FACTORY = 5
    LAKE = 6
    HOME_BASE = 7

    def resource_typ(self):
        if self is TerrainType.MOUNTAIN:
            return ResourceType.METAL
        elif self is TerrainType.TUNDRA:
            return ResourceType.OIL
        elif self is TerrainType.FARM:
            return ResourceType.FOOD
        elif self is TerrainType.FOREST:
            return ResourceType.WOOD

        else:
            raise Exception(f'Illegal: asking for resource type of {self}')

    def __str__(self):
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

        assert False
