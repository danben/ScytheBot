from game.actions.action import *
from game.types import StructureType, TerrainType


class Produce(MaybePayCost):
    def __init__(self):
        self.if_paid = ProduceIfPaid()
        super().__init__('Produce', self.if_paid)
        self.meeples_produced = 0

    def cost(self):
        power = 1 if self.meeples_produced > 1 else 0
        popularity = 1 if self.meeples_produced > 3 else 0
        coins = 1 if self.meeples_produced > 5 else 0
        return Cost(power=power, popularity=popularity, coins=coins)

    def top_action(self):
        return self.if_paid.top_action


class ProduceIfPaid(StateChange):
    def __init__(self):
        super().__init__()
        self.top_action = TopAction('Produce', num_cubes=1, structure_typ=StructureType.MILL)
        self.on_one_hex = OnOneHex()
        self.on_mill_hex = Optional(OnMillHex())

    def do(self, game_state):

        if self.top_action.cubes_upgraded[0]:
            game_state.action_stack.append(Optional(self.on_one_hex))

        game_state.action_stack.append(Optional(self.on_one_hex))
        game_state.action_stack.append(self.on_one_hex)
        if self.top_action.structure_is_built:
            game_state.action_stack.append(self.on_mill_hex)


def produce_on_space(space, game_state):
    assert not space.produced_this_turn
    game_state.spaces_produced_this_turn.add(space)
    space.produced_this_turn = True
    num_workers = len(space.workers)

    if space.terrain_typ is TerrainType.VILLAGE:
        game_state.action_stack.append(ChooseNumWorkers(space,
                                                        min(num_workers,
                                                            game_state.current_player.available_workers())))
    else:
        space.add_resources(space.terrain_typ.resource_type(), num_workers)


class OnOneHex(Choice):
    def __init__(self):
        super().__init__('Produce on a single hex')

    def choose(self, agent, game_state):
        spaces = game_state.current_player.produceable_spaces()
        if spaces:
            logging.debug(f'Choosing from {spaces}')
            return agent.choose_board_space(game_state, spaces)
        else:
            return None

    def do(self, game_state, space):
        if space:
            logging.debug(f'Space chosen: {space!r}')
            produce_on_space(space, game_state)
        else:
            logging.debug('No spaces available for produce')


class OnMillHex(StateChange):
    def __init__(self):
        super().__init__('Produce on mill hex')

    def do(self, game_state):
        space = game_state.current_player.mill_space()
        assert space is not None
        if not space.produced_this_turn:
            produce_on_space(space, game_state)


class ChooseNumWorkers(Choice):
    def __init__(self, space, max_workers):
        super().__init__('Choose number of workers to receive')
        self.space = space
        self.max_workers = max_workers

    def choose(self, agent, game_state):
        return agent.choose_numeric(game_state, low=1, high=self.max_workers)

    def do(self, game_state, amt):
        game_state.action_stack.append(ReceiveWorkers(amt, self.space))
