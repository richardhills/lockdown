from rdhlang5.executor.flow_control import BreakTypesFactory
from rdhlang5.executor.function_type import ClosedFunctionType
from rdhlang5.type_system.core_types import NoValueType, IntegerType, Const, \
    UnitType, OneOfType
from rdhlang5.type_system.exceptions import FatalError, InvalidDereferenceKey
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.micro_ops import MicroOpType, \
    raise_micro_op_conflicts
from rdhlang5.utils import NOTHING


class BuiltInFunctionGetterType(MicroOpType):
    def __init__(self, function_class):
        self.function_class = function_class
        self.value_type = function_class.get_type()
        self.key_error = False
        self.type_error = False

    def replace_inferred_type(self, other_micro_op_type):
        return self

    def invoke(self, target_manager, **kwargs):
        return self.function_class(target_manager)

    def is_derivable_from(self, type, data):
        return True

    def conflicts_with(self, our_type, other_type):
        return False

    def merge(self, other_micro_op_type):
        return self

    def unbind(self, source_type, key, target):
        pass

    def bind(self, source_type, key, target):
        pass

def ObjectGetFunctionType(object_wildcard_getter_opcode_type):
    from rdhlang5.executor.function import RDHFunction
    from rdhlang5.type_system.list_types import RDHListType
    break_types = BreakTypesFactory(None)
    argument_type = RDHListType([ object_wildcard_getter_opcode_type.key_type ], None, allow_push=False, allow_wildcard_insert=False, allow_delete=False, is_sparse=False)
    break_types.add("value", OneOfType([
        object_wildcard_getter_opcode_type.value_type,
        UnitType(NOTHING)
    ]))
    function_type = ClosedFunctionType(argument_type, break_types.build())

    class ObjectGetFunction(RDHFunction):
        def __init__(self, target_manager):
            self.target_manager = target_manager

        @classmethod
        def get_type(cls):
            return function_type

        @property
        def break_types(self):
            return function_type.break_types

        def invoke(self, argument, frame_manager):
            with frame_manager.get_next_frame(self) as frame:
                our_type = self.get_type()
                argument_manager = get_manager(argument)
                argument_manager.add_composite_type(our_type.argument_type)

                try:
                    frame.value(object_wildcard_getter_opcode_type.invoke(self.target_manager, *argument))
                except InvalidDereferenceKey:
                    frame.value(NOTHING)

    return ObjectGetFunction

def ListInsertFunctionType(insert_micro_op_type, wildcard_type):
    from rdhlang5.executor.function import RDHFunction
    from rdhlang5.type_system.list_types import RDHListType
    break_types = BreakTypesFactory(None)
    argument_type = RDHListType([ Const(IntegerType()), Const(wildcard_type) ], None, allow_push=False, allow_wildcard_insert=False, allow_delete=False, is_sparse=False)
    break_types.add("value", NoValueType())
    function_type = ClosedFunctionType(argument_type, break_types.build())

    class ListInsertFunction(RDHFunction):
        def __init__(self, target_manager):
            self.target_manager = target_manager

        @classmethod
        def get_type(cls):
            return function_type

        @property
        def break_types(self):
            return function_type.break_types

        def invoke(self, argument, frame_manager):
            with frame_manager.get_next_frame(self) as frame:
                our_type = self.get_type()
                argument_manager = get_manager(argument)
                argument_manager.add_composite_type(our_type.argument_type)

                if not insert_micro_op_type:
                    raise FatalError()

                return frame.value(insert_micro_op_type.invoke(self.target_manager, *argument))

    return ListInsertFunction
