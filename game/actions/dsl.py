class Action:
    def __init__(self):
        pass

    def to_string(self):
        pass

    def cost(self, game_state):
        pass


class DiscreteChoice(Action):
    def __init__(self):
        super().__init__()

    def choices(self, game_state):
        pass


class NumericChoice(Action):
    def __init__(self):
        super().__init__()


class StateChange(Action):
    def __init__(self):
        super().__init__()

    def apply(self, game_state):
        pass


class Nothing(Action):
    pass


class Optional(Action):
    def __init__(self, action):
        super().__init__()
        self._action = action

    def choices(self, game_state):
        return [Nothing(), self._action]


class Sequence(Action):
    def __init__(self, action1, action2):
        super().__init__()
        self._action1 = action1
        self._action2 = action2

    def apply(self, game_state):
        game_state.action_stack.append(self._action2)
        game_state.action_stack.append(self._action1)

    @staticmethod
    def of_list(actions):
        assert len(actions) > 1
        if len(actions) == 2:
            return Sequence(actions[0], actions[1])
        return Sequence(actions[0], Sequence.of_list(actions[1:]))

    @staticmethod
    def of_list_all_optional(actions):
        actions = [Optional(action) for action in actions]
        return Sequence.of_list(actions)

    @staticmethod
    def repeat(action, num_iterations):
        return Sequence.of_list([action] * num_iterations)
