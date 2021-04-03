from lockdown.type_system.exceptions import FatalError

class Reasoner(object):
    def __init__(self):
        self.stack = []

    def push_micro_op_conflicts_with_type(self, micro_op, other_type):
        self.stack.insert(0, ("micro-op-type-conflict", micro_op, other_type))

    def push_micro_op_conflicts_with_micro_op(self, original, conflict):
        self.stack.insert(0, ("micro-op-micro-op-conflict", original, conflict))

    def push_not_copyable_type(self, target, source):
        self.stack.insert(0, ("not-copyable", target, source))

    def push_inconsistent_type(self, type):
        self.stack.insert(0, ("inconsistent", type))

    def attach_child_reasoners(self, reasoners):
        self.stack.insert(0, ("child-reasoners", reasoners))

    def to_message(self):
        return "\n\nBecause: ".join([
            str(m) for m in self.stack
        ])

class DummyReasoner(object):
    def push_micro_op_conflicts_with_type(self, micro_op, other_type):
        pass

    def push_micro_op_conflicts_with_micro_op(self, original, conflict):
        pass

    def push_not_copyable_type(self, target, source):
        pass

    def push_inconsistent_type(self, type):
        pass

    def attach_child_reasoners(self, reasoners):
        pass

    def to_message(self):
        raise FatalError()

DUMMY_REASONER = DummyReasoner()
