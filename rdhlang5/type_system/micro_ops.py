from abc import ABCMeta, abstractmethod

from rdhlang5.type_system.core_types import Type
from rdhlang5.type_system.exceptions import FatalError, MicroOpTypeConflict


class MicroOpType(object):
#    __metaclass__ = ABCMeta

    @abstractmethod
    def replace_inferred_type(self, other_micro_op_type):
        raise NotImplementedError(self)

    def reify_revconst_types(self, other_micro_op_types):
        return self

    @abstractmethod
    def create(self, target):
        raise NotImplementedError(self)

    @abstractmethod
    def can_be_derived_from(self, other_micro_op_type):
        raise NotImplementedError(self)

    @abstractmethod
    def merge(self, other_micro_op_type):
        raise NotImplementedError(self)

    @abstractmethod
    def unbind(self, key, target):
        raise NotImplementedError(self)

    @abstractmethod
    def bind(self, key, target):
        raise NotImplementedError(self)

    @abstractmethod
    def raise_on_runtime_micro_op_conflict(self, micro_op, args):
        # Invoked on all MicroOpTypes on a class before any MicroOp is executed to check
        # for run time conflicts
        raise NotImplementedError(self)

    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        for other_micro_op_type in micro_op_types.values():
            first_check = other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
            # These functions should be symmetrical so this second call shouldn't be necessary
            # Remove for performance when confident about this!
            second_check = self.check_for_new_micro_op_type_conflict(other_micro_op_type, micro_op_types)
            if first_check != second_check:
                other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
                self.check_for_new_micro_op_type_conflict(other_micro_op_type, micro_op_types)
                raise FatalError()
            if first_check:
                other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
                raise MicroOpTypeConflict()

    @abstractmethod
    def check_for_runtime_data_conflict(self, obj):
        raise NotImplementedError(self)     

    @abstractmethod
    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        raise NotImplementedError(self)


class MicroOp(object):
    def invoke(self, *args):
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
        return CompositeType(types[0].micro_op_types, initial_data=initial_data, name=name) 

    result = {}
    for type in types:
        for tag, micro_op_type in type.micro_op_types.items():
            if tag in result:
                result[tag] = result[tag].merge(micro_op_type)
            else:
                result[tag] = micro_op_type

    return CompositeType(result, initial_data=initial_data, name=name)

