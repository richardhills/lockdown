from rdhlang5.executor.flow_control import BreakTypesFactory
from rdhlang5.executor.function_type import ClosedFunctionType
from rdhlang5.type_system.core_types import NoValueType, IntegerType, Const
from rdhlang5.type_system.exceptions import FatalError
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.micro_ops import MicroOpType, MicroOp, \
    raise_micro_op_conflicts


class BuiltInFunctionGetterType(MicroOpType):
    def __init__(self, function_class):
        self.function_class = function_class
        self.type = function_class.get_type()
        self.key_error = False
        self.type_error = False

    def replace_inferred_type(self, other_micro_op_type):
        return self

    def create(self, target_manager):
        return BuiltInFunctionGetter(self.function_class, target_manager)

    def can_be_derived_from(self, other_micro_op_type):
        return True

    def merge(self, other_micro_op_type):
        pass

    def unbind(self, source_type, key, target):
        pass

    def bind(self, source_type, key, target):
        pass

    def raise_on_runtime_micro_op_conflict(self, micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        return False

class BuiltInFunctionGetter(MicroOp):
    def __init__(self, function_class, target_manager):
        self.function_class = function_class
        self.target_manager = target_manager

    def invoke(self, **kwargs):
        raise_micro_op_conflicts(self, [ ], self.target_manager.get_flattened_micro_op_types())
        return self.function_class(self.target_manager)

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
        def get_type(self):
            return function_type

        @property
        def allowed_break_types(self):
            return function_type.break_types

        def invoke(self, argument, frame_manager):
            with frame_manager.get_next_frame(self) as frame:
                our_type = self.get_type()

                argument_manager = get_manager(argument)
                argument_manager.add_composite_type(our_type.argument_type)

#                insert_micro_op_type = self.target_manager.get_micro_op_type(("insert-wildcard",))

                if not insert_micro_op_type:
                    raise FatalError()

                insert_micro_op = insert_micro_op_type.create(self.target_manager)

                return frame.value(insert_micro_op.invoke(*argument))

    return ListInsertFunction
