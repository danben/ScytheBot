from game.actions.action import *
from game.constants import NUM_WORKERS
from game.game_state import GameState
from game.types import TerrainType, TopActionType

import attr


@attr.s(frozen=True, slots=True)
class ChooseNumWorkers(Choice):
    space = attr.ib()
    max_workers = attr.ib()

    @classmethod
    def new(cls, space, max_workers):
        return cls('Choose number of workers to receive', space, max_workers)

    def choose(self, agent, game_state):
        high = self.max_workers
        low = min(1, high)
        return agent.choose_numeric(game_state, low, high)

    def do(self, game_state, amt):
        return GameState.push_action(game_state, ReceiveWorkers.new(amt, self.space))


def produce_on_space(space, game_state):
    assert not space.produced_this_turn
    space = attr.evolve(space, produced_this_turn=True)
    game_state = attr.evolve(game_state, board=game_state.board.set_space(space),
                             spaces_produced_this_turn=game_state.spaces_produced_this_turn.add(space))
    num_workers = len(space.workers)

    if space.terrain_typ is TerrainType.VILLAGE:
        return GameState.push_action(game_state, ChooseNumWorkers.new(space,
                                                                      min(num_workers,
                                                                          game_state.current_player.available_workers()
                                                                          )))
    else:
        space = space.add_resources(space.terrain_typ.resource_type(), num_workers)
        return attr.evolve(game_state, board=game_state.board.set_space(space))


@attr.s(frozen=True, slots=True)
class OnOneHex(Choice):
    @classmethod
    def new(cls):
        return cls('Produce on a single hex')

    def choose(self, agent, game_state):
        spaces = GameState.produceable_spaces(game_state, GameState.get_current_player(game_state))
        if spaces:
            logging.debug(f'Choosing from {spaces}')
            return agent.choose_board_space(game_state, spaces)
        else:
            return None

    def do(self, game_state, space):
        if space:
            logging.debug(f'Space chosen: {space!r}')
            return produce_on_space(space, game_state)
        else:
            logging.debug('No spaces available for produce')


@attr.s(frozen=True, slots=True)
class OnMillHex(StateChange):
    @classmethod
    def new(cls):
        return cls('Produce on mill hex')

    def do(self, game_state):
        space = GameState.mill_space(game_state, game_state.current_player())
        assert space is not None
        if not space.produced_this_turn:
            produce_on_space(space, game_state)


@attr.s(frozen=True, slots=True)
class ProduceIfPaid(StateChange):
    _on_one_hex = OnOneHex.new()
    _on_one_hex_opt = Optional.new(_on_one_hex)
    _on_mill_hex = OnMillHex.new()

    @classmethod
    def new(cls):
        return cls('Produce')

    def do(self, game_state):
        current_player = GameState.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.PRODUCE]

        if top_action_cubes_and_structure.cubes_upgraded[0]:
            game_state = GameState.push_action(game_state, ProduceIfPaid._on_one_hex_opt)

        game_state = GameState.push_action(game_state, ProduceIfPaid._on_one_hex)
        game_state = GameState.push_action(game_state, ProduceIfPaid._on_one_hex)

        # Put the mill hex on top so we don't have to worry about it getting taken by
        # one of the other produce actions
        if top_action_cubes_and_structure.structure_is_built:
            game_state = GameState.push_action(game_state, ProduceIfPaid._on_mill_hex)
        return game_state


@attr.s(frozen=True, slots=True)
class Produce(MaybePayCost):
    _if_paid = ProduceIfPaid.new()

    @classmethod
    def new(cls):
        return cls('Produce', Produce._if_paid)

    def cost(self, game_state):
        produced_workers = len(GameState.get_current_player(game_state).workers) - 2
        power = 1 if produced_workers > 1 else 0
        popularity = 1 if produced_workers > 3 else 0
        coins = 1 if produced_workers > 5 else 0
        return Cost.new(power=power, popularity=popularity, coins=coins)

    def top_action(self):
        return self.if_paid.top_action
