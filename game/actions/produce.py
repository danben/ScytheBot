import game.actions.action as a
import game.state_change as sc
from game.types import StructureType, TerrainType, TopActionType

import attr
import logging


@attr.s(frozen=True, slots=True)
class ChooseNumWorkers(a.Choice):
    coords = attr.ib()
    max_workers = attr.ib()

    @classmethod
    def new(cls, space, max_workers):
        return cls('Choose number of workers to receive', space, max_workers)

    def choices(self, game_state):
        return list(range(1, self.max_workers+1))

    def choose(self, agent, game_state):
        c = self.choices(game_state)
        if not c:
            print(f'Max workers: {self.max_workers}')
            assert False
        return agent.choose_numeric(game_state, c)

    def do(self, game_state, amt):
        return sc.push_action(game_state, a.ReceiveWorkers.new(amt, self.coords))


def produce_on_space(coords, game_state):
    space = game_state.board.get_space(coords)
    assert not space.produced_this_turn
    assert coords[0] != -1
    space = attr.evolve(space, produced_this_turn=True)
    game_state = attr.evolve(game_state, board=game_state.board.set_space(space),
                             spaces_produced_this_turn=game_state.spaces_produced_this_turn.add(space.coords))
    num_workers = len(space.worker_keys)
    current_player = sc.get_current_player(game_state)
    if space.has_structure() and space.structure_key.id == StructureType.MILL.value \
            and space.structure_key.faction_name is current_player.faction_name():
        num_workers += 1

    if space.terrain_typ is TerrainType.VILLAGE and current_player.available_workers():
        return sc.push_action(game_state,
                              ChooseNumWorkers.new(space.coords,
                                                   min(num_workers,
                                                       current_player.available_workers()
                                                       )))
    else:
        if space.terrain_typ is TerrainType.VILLAGE:
            return game_state
        else:
            space = space.add_resources(space.terrain_typ.resource_typ(), num_workers)
            return attr.evolve(game_state, board=game_state.board.set_space(space))


@attr.s(frozen=True, slots=True)
class OnOneHex(a.Choice):
    @classmethod
    def new(cls):
        return cls('Produce on a single hex')

    def choices(self, game_state):
        return sc.produceable_space_coords(game_state, sc.get_current_player(game_state))

    def choose(self, agent, game_state):
        coords = self.choices(game_state)
        if coords:
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Choosing from {coords}')
            return agent.choose_board_coords(game_state, coords)
        else:
            return None

    def do(self, game_state, coords):
        if coords:
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f'Coords chosen: {coords}')
            return produce_on_space(coords, game_state)
        else:
            logging.debug('No spaces available for produce')
            return game_state


@attr.s(frozen=True, slots=True)
class OnMillHex(a.StateChange):
    @classmethod
    def new(cls):
        return cls('Produce on mill hex')

    def do(self, game_state):
        space = sc.mill_space(game_state, sc.get_current_player(game_state))
        assert space is not None
        if not space.produced_this_turn:
            return produce_on_space(space.coords, game_state)


@attr.s(frozen=True, slots=True)
class ProduceIfPaid(a.StateChange):
    _on_one_hex = OnOneHex.new()
    _on_one_hex_opt = a.Optional.new(_on_one_hex)
    _on_mill_hex = OnMillHex.new()

    @classmethod
    def new(cls):
        return cls('Produce')

    def do(self, game_state):
        current_player = sc.get_current_player(game_state)
        player_mat = current_player.player_mat
        top_action_cubes_and_structure = \
            player_mat.top_action_cubes_and_structures_by_top_action_typ[TopActionType.PRODUCE]

        if top_action_cubes_and_structure.cubes_upgraded[0]:
            game_state = sc.push_action(game_state, ProduceIfPaid._on_one_hex_opt)

        game_state = sc.push_action(game_state, ProduceIfPaid._on_one_hex)
        game_state = sc.push_action(game_state, ProduceIfPaid._on_one_hex)

        # Put the mill hex on top so we don't have to worry about it getting taken by
        # one of the other produce actions
        if top_action_cubes_and_structure.structure_is_built:
            mill_space = sc.mill_space(game_state, current_player)
            if mill_space.terrain_typ is not TerrainType.FACTORY \
                    and sc.controller(game_state, mill_space) is current_player.faction_name():
                game_state = sc.push_action(game_state, ProduceIfPaid._on_mill_hex)
        return game_state


@attr.s(frozen=True, slots=True)
class Produce(a.MaybePayCost):
    _if_paid = ProduceIfPaid.new()

    @classmethod
    def new(cls):
        return cls('Produce', Produce._if_paid)

    def cost(self, game_state):
        produced_workers = len(sc.get_current_player(game_state).worker_ids) - 2
        power = 1 if produced_workers > 1 else 0
        popularity = 1 if produced_workers > 3 else 0
        coins = 1 if produced_workers > 5 else 0
        return a.Cost.new(power=power, popularity=popularity, coins=coins)

    def top_action(self):
        return self.if_paid.top_action


def action():
    return Produce.new()
