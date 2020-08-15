from abc import abstractmethod

from rdhlang5.executor.ast_utils import compile_expression
from rdhlang5.type_system.core_types import Type
from rdhlang5.type_system.exceptions import FatalError, MicroOpTypeConflict
from rdhlang5.utils import is_debug


class MicroOpType(object):
#    __metaclass__ = ABCMeta

    @abstractmethod
    def replace_inferred_type(self, other_micro_op_type):
        raise NotImplementedError(self)

    def reify_revconst_types(self, other_micro_op_types):
        return self

    @abstractmethod
    def create(self, target_manager):
        raise NotImplementedError(self)

    def invoke(self, target_manager, *args, **kwargs):
        return self.create(target_manager).invoke(*args, **kwargs)

    @abstractmethod
    def can_be_derived_from(self, other_micro_op_type):
        raise NotImplementedError(self)

    @abstractmethod
    def merge(self, other_micro_op_type):
        raise NotImplementedError(self)

    @abstractmethod
    def unbind(self, source_type, key, target_manager):
        raise NotImplementedError(self)

    @abstractmethod
    def bind(self, source_type, key, target_manager):
        raise NotImplementedError(self)

    @abstractmethod
    def raise_on_runtime_micro_op_conflict(self, micro_op, args):
        # Invoked on all MicroOpTypes on a class before any MicroOp is executed to check
        # for run time conflicts
        raise NotImplementedError(self)

    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        for other_micro_op_type in micro_op_types.values():
            first_check = other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
            if is_debug():
                second_check = self.check_for_new_micro_op_type_conflict(other_micro_op_type, micro_op_types)
                other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
                if first_check != second_check:
                    other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
                    self.check_for_new_micro_op_type_conflict(other_micro_op_type, micro_op_types)
                    raise FatalError("Type check conflict between {} and {}".format(self, other_micro_op_type))
            if first_check:
                other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
                raise MicroOpTypeConflict(self, other_micro_op_type)

    @abstractmethod
    def check_for_runtime_data_conflict(self, obj):
        raise NotImplementedError(self)     

    @abstractmethod
    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        raise NotImplementedError(self)

    def to_ast(self, dependency_builder, target, *args):
        args_parameters = { "arg{}".format(i): a for i, a in enumerate(args) }
        args_string = ", {" + "},{".join(args_parameters.keys()) + "}" if len(args_parameters) > 0 else ""

        return compile_expression(
            "{invoke}(get_manager({target})" + args_string + ")",
            None, dependency_builder,
            invoke=self.invoke, target=target, **args_parameters
        )

class MicroOp(object):
    def invoke(self, *args, **kwargs):
        raise NotImplementedError(self)


def raise_micro_op_conflicts(micro_op, args, other_micro_op_types):
    for other_micro_op_type in other_micro_op_types:
        other_micro_op_type.raise_on_runtime_micro_op_conflict(micro_op, args)


def merge_composite_types(types, initial_data, name=None):
    from rdhlang5.type_system.composites import CompositeType

    for t in types:
        if not isinstance(t, Type):
            raise FatalError()

    if len(types) == 1:
        return CompositeType(types[0].micro_op_types, types[0].python_object_type_checker, initial_data=initial_data, name=name) 

    result = {}
    python_object_type_checker = None
    for type in types:
        if python_object_type_checker and python_object_type_checker != type.python_object_type_checker:
            raise FatalError()
        python_object_type_checker = type.python_object_type_checker
        for tag, micro_op_type in type.micro_op_types.items():
            if tag in result:
                result[tag] = result[tag].merge(micro_op_type)
            else:
                result[tag] = micro_op_type

    return CompositeType(result, python_object_type_checker, initial_data=initial_data, name=name, is_revconst=len(types) == 0)

