from _abcoll import MutableSequence
from collections import OrderedDict

from rdhlang5.type_system.builtins import BuiltInFunctionGetterType, \
    ListInsertFunctionType
from rdhlang5.type_system.composites import InferredType, bind_type_to_value, \
    unbind_type_to_value, CompositeType, Composite
from rdhlang5.type_system.core_types import merge_types, Const, NoValueType
from rdhlang5.type_system.exceptions import FatalError, MicroOpTypeConflict, \
    raise_if_safe, InvalidAssignmentType, InvalidDereferenceKey, \
    InvalidDereferenceType, InvalidAssignmentKey, MissingMicroOp
from rdhlang5.type_system.managers import get_manager, get_type_of_value
from rdhlang5.type_system.micro_ops import MicroOpType, MicroOp, \
    raise_micro_op_conflicts
from rdhlang5.utils import MISSING


WILDCARD = object()


def get_key_and_type(micro_op_type):
    if isinstance(micro_op_type, (ListWildcardGetterType, ListWildcardSetterType, ListWildcardDeletterType, ListWildcardInsertType)):
        key = WILDCARD
    elif isinstance(micro_op_type, (ListGetterType, ListSetterType, ListDeletterType, ListInsertType)):
        key = micro_op_type.key
    else:
        raise FatalError()

    if isinstance(micro_op_type, (ListWildcardGetterType, ListGetterType, ListWildcardSetterType, ListSetterType, ListWildcardInsertType, ListInsertType)):
        type = micro_op_type.type
    else:
        type = MISSING

    return key, type


def get_key_and_new_value(micro_op, args):
    if isinstance(micro_op, (ListWildcardGetter, ListWildcardDeletter)):
        key, new_value = MISSING
    elif isinstance(micro_op, (ListGetter, ListDeletter)):
        key = micro_op.key
        new_value = MISSING
    elif isinstance(micro_op, (ListWildcardSetter, ListWildcardInsert)):
        key, new_value = args
    elif isinstance(micro_op, (ListSetter, ListInsert)):
        key = micro_op.key
        new_value = args[0]
    else:
        raise FatalError()
    return key, new_value

class ListMicroOpType(MicroOpType):
    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        if not isinstance(obj, RDHList):
            raise MicroOpTypeConflict()
        return super(ListMicroOpType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_runtime_data_conflict(self, obj):
        if not isinstance(obj, RDHList):
            return True

class ListWildcardGetterType(ListMicroOpType):
    def __init__(self, type, key_error, type_error):
        if isinstance(type, NoValueType):
            raise FatalError()
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ListWildcardGetter(target_manager, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and self.type.is_copyable_from(other_micro_op_type.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ListWildcardGetterType):
            if isinstance(self.type, InferredType):
                raise FatalError()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ListWildcardGetterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target_manager):
        if key is not None:
            keys = [ key ]
        else:
            keys = range(0, len(target_manager.obj.wrapped))
        for k in keys:
            value = target_manager.obj.wrapped[k]
            bind_type_to_value(target_manager, source_type, k, self.type, get_manager(value))

    def unbind(self, source_type, key, target_manager):
        if key is not None:
            if key < 0 or key >= len(target_manager.obj):
                return
            keys = [ key ]
        else:
            keys = range(0, len(target_manager.obj))
        for k in keys:
            unbind_type_to_value(target_manager, source_type, k, self.type, get_manager(target_manager.obj.wrapped[k]))

    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        default_factory = micro_op_types.get(("default-factory",), None)
        has_default_factory = default_factory is not None

        if not self.key_error:
            if not has_default_factory:
                raise MicroOpTypeConflict()
            if not self.type.is_copyable_from(default_factory.type):
                raise MicroOpTypeConflict()

        return super(ListWildcardGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        default_factory = other_micro_op_types.get(("default-factory",), None)
        has_default_factory = default_factory is not None

        if not self.key_error:        
            if not has_default_factory:
                return True

        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            return False
        if isinstance(other_micro_op_type, (ListSetterType, ListWildcardSetterType)):
            if not self.type_error and not self.type.is_copyable_from(other_micro_op_type.type):
                return True
        if isinstance(other_micro_op_type, (ListDeletterType, ListWildcardDeletterType)):
            if not self.key_error and not has_default_factory:
                return True
        if isinstance(other_micro_op_type, (ListInsertType, ListWildcardInsertType)):
            if not self.type_error and not self.type.is_copyable_from(other_micro_op_type.type):
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        if isinstance(other_micro_op, (ListSetter, ListWildcardSetter)):
            _, other_new_value = get_key_and_new_value(other_micro_op, args)
            if not self.type_error and not self.type.is_copyable_from(get_type_of_value(other_new_value)):
                raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
        if isinstance(other_micro_op, (ListInsert, ListWildcardInsert)):
            _, other_new_value = get_key_and_new_value(other_micro_op, args)
            if not self.type_error and not self.type.is_copyable_from(get_type_of_value(other_new_value)):
                raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)

        if isinstance(other_micro_op, (ListDeletter, ListWildcardDeletter)):
            if not self.key_error:
                raise_if_safe(InvalidAssignmentType, other_micro_op.key_error)
        return False

    def check_for_runtime_data_conflict(self, obj):
        if super(ListWildcardGetterType, self).check_for_runtime_data_conflict(obj):
            return True
        if not self.key_error and get_manager(obj).default_factory is None:
            return True

        if not self.type_error:
            for value in obj.wrapped.values(): # Leaking RDHList details...
                get_manager(value)
                if not self.type.is_copyable_from(get_type_of_value(value)):
                    return True

        return False

    def merge(self, other_micro_op_type):
        return ListWildcardGetterType(
            merge_types([ self.type, other_micro_op_type.type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


class ListWildcardGetter(MicroOp):
    def __init__(self, target_manager, type, key_error, type_error):
        self.target_manager = target_manager
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, key, **kwargs):
        raise_micro_op_conflicts(self, [ key ], self.target_manager.get_flattened_micro_op_types())

        if key >= 0 and key < len(self.target_manager.obj):
            value = self.target_manager.obj.__getitem__(key, raw=True)
        else:
            default_factory_op_type = self.target_manager.get_micro_op_type(("default-factory",))

            if not default_factory_op_type:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

            default_factory_op = default_factory_op_type.create(self.target_manager)
            value = default_factory_op.invoke(key)

        if value is not SPARSE_ELEMENT:
            type_of_value = get_type_of_value(value)
            if not self.type.is_copyable_from(type_of_value):
                raise raise_if_safe(InvalidDereferenceType, self.type_error)

        return value


class ListGetterType(ListMicroOpType):
    def __init__(self, key, type, key_error, type_error):
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ListGetter(target_manager, self.key, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and self.type.is_copyable_from(other_micro_op_type.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ListGetterType):
            if isinstance(self.type, InferredType):
                raise FatalError()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ListGetterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target_manager):
        if key is not None and key != self.key:
            return
        value = target_manager.obj.wrapped[self.key]
        bind_type_to_value(target_manager, source_type, key, self.type, get_manager(value))

    def unbind(self, source_type, key, target_manager):
        if key is not None and key != self.key:
            return
        value = target_manager.obj.wrapped[self.key]
        unbind_type_to_value(target_manager, source_type, key, self.type, get_manager(value))

    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        default_factory = micro_op_types.get(("default-factory",), None)
        has_default_factory = default_factory is not None
        has_value_in_place = self.key >= 0 and self.key < len(obj)

        if not self.key_error and not has_value_in_place:
            if not has_default_factory:
                raise MicroOpTypeConflict()
            if not self.type.is_copyable_from(default_factory.type):
                raise MicroOpTypeConflict()

        return super(ListGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListSetterType, ListWildcardSetterType)):
            other_key, other_type = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and self.key != other_key:
                return False
            if not self.type_error and not other_micro_op_type.type_error and not self.type.is_copyable_from(other_type):
                return True
        if isinstance(other_micro_op_type, (ListInsertType, ListWildcardInsertType)):
            other_key, other_type = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD:
                if self.key < other_key:
                    return False
                elif self.key == other_key:
                    if not self.type_error and not other_micro_op_type.type_error and not self.type.is_copyable_from(other_type):
                        return True
                else:
                    prior_micro_op = other_micro_op_types.get(("get", self.key - 1), None)
                    if not prior_micro_op:
                        return True
                    if not self.type_error and not prior_micro_op.type_error and not self.type.is_copyable_from(prior_micro_op.type):
                        return True
            else:
                other_key, other_type = get_key_and_type(other_micro_op_type)
                if not self.type.is_copyable_from(other_type):
                    return True
        if isinstance(other_micro_op_type, (ListDeletterType, ListWildcardDeletterType)):
            other_key, _ = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and self.key < other_key:
                return False
            post_opcode = other_micro_op_types.get(("get", self.key + 1), None)
            if not post_opcode:
                return True
            if not self.type_error and not post_opcode.type_error and not self.type.is_copyable_from(post_opcode.type):
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        if isinstance(other_micro_op, (ListGetter, ListWildcardGetter)):
            return
        if isinstance(other_micro_op, (ListSetter, ListWildcardSetter)):
            other_key, new_value = get_key_and_new_value(other_micro_op, args)
            if self.key != other_key:
                return
            if not self.type_error and not self.type.is_copyable_from(get_type_of_value(new_value)):
                raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
        if isinstance(other_micro_op, (ListInsert, ListWildcardInsert)):
            other_key, new_value = get_key_and_new_value(other_micro_op, args)
            if self.key < other_key:
                return
            elif self.key == other_key:
                if not self.type.is_copyable_from(get_type_of_value(new_value)):
                    raise raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
            elif self.key > other_key:
                new_value = other_micro_op.target_manager.obj[self.key - 1]
                if not self.type.is_copyable_from(get_type_of_value(new_value)):
                    raise raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
        if isinstance(other_micro_op, (ListDeletter, ListWildcardDeletter)):
            other_key, _ = get_key_and_new_value(other_micro_op, args)
            if self.key < other_key:
                return
            else:
                new_value = other_micro_op.target_manager.obj[self.key + 1]
                if not self.key_error and not self.type.is_copyable_from(get_type_of_value(new_value)):
                    raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)

    def check_for_runtime_data_conflict(self, obj):
        if super(ListGetterType, self).check_for_runtime_data_conflict(obj):
            return True

        if self.key < 0 or self.key > len(obj):
            return True
        value = obj.__getitem__(self.key, raw=True)
        type_of_value = get_type_of_value(value)
        return not self.type.is_copyable_from(type_of_value)

    def merge(self, other_micro_op_type):
        return ListGetterType(
            self.key,
            merge_types([ self.type, other_micro_op_type.type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


class ListGetter(MicroOp):
    def __init__(self, target_manager, key, type, key_error, type_error):
        self.target_manager = target_manager
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, **kwargs):
        raise_micro_op_conflicts(self, [], self.target_manager.get_flattened_micro_op_types())

        if self.key >= 0 and self.key < len(self.target_manager.obj):
            value = self.target_manager.obj.__getitem__(self.key, raw=True)
        else:
            default_factory_op = self.target_manager.get_micro_op_type(("default-factory",))

            if default_factory_op:
                value = default_factory_op.invoke(self.key)
            else:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

        type_of_value = get_type_of_value(value)

        if not self.type.is_copyable_from(type_of_value):
            raise_if_safe(InvalidDereferenceKey, self.can_fail)

        return value


class ListWildcardSetterType(ListMicroOpType):
    def __init__(self, type, key_error, type_error):
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ListWildcardSetter(target_manager, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.type.is_copyable_from(self.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ListWildcardSetterType):
            if isinstance(self.type, InferredType):
                raise FatalError()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ListWildcardSetterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            if not self.type_error and not other_micro_op_type.type_error and not other_micro_op_type.type.is_copyable_from(self.type):
                return True

        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if super(ListWildcardSetterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ListWildcardSetterType(
            merge_types([ self.type, other_micro_op_type.type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


class ListWildcardSetter(MicroOp):
    def __init__(self, target_manager, type, key_error, type_error):
        self.target_manager = target_manager
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, key, new_value, **kwargs):
        raise_micro_op_conflicts(self, [ key, new_value ], self.target_manager.get_flattened_micro_op_types())

        new_value_type = get_type_of_value(new_value)
        if not self.type.is_copyable_from(new_value_type):
            raise FatalError()

        if key < 0 or key > len(self.target_manager.obj):
            if self.key_error:
                raise InvalidAssignmentKey()

        self.target_manager.unbind_key(key)

        self.target_manager.obj.__setitem__(key, new_value, raw=True)

        self.target_manager.bind_key(key)

class ListSetterType(ListMicroOpType):
    def __init__(self, key, type, key_error, type_error):
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ListSetter(target_manager, self.key, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.type.is_copyable_from(self.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ListSetterType):
            if isinstance(self.type, InferredType):
                raise FatalError()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ListSetterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            other_key, other_type = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and self.key != other_key:
                return False
            if not self.type_error and not other_micro_op_type.type_error and not other_type.is_copyable_from(self.type):
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if super(ListSetterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ListSetterType(
            self.key,
            merge_types([ self.type, other_micro_op_type.type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


class ListSetter(MicroOp):
    def __init__(self, target_manager, key, type, key_error, type_error):
        self.target_manager = target_manager
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, new_value, **kwargs):
        raise_micro_op_conflicts(self, [ new_value ], self.target_manager.get_flattened_micro_op_types())

        new_value_type = get_type_of_value(new_value)
        if not self.type.is_copyable_from(new_value_type):
            raise FatalError()

        if self.key < 0 or self.key > len(self.target_manager.obj):
            raise_if_safe(InvalidAssignmentKey, self.can_fail)

        self.target_manager.bind_key(self.key)

        self.target_manager.obj.__setitem__(self.key, new_value, raw=True)

        self.target_manager.unbind_key(self.key)


class ListWildcardDeletterType(ListMicroOpType):
    def __init__(self, key_error):
        self.key_error = key_error

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def create(self, target_manager):
        return ListWildcardDeletter(target_manager, self.key_error)

    def can_be_derived_from(self, other_micro_op_type):
        return not other_micro_op_type.key_error or self.key_error

    def replace_inferred_type(self, other_micro_op_type):
        return self

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            default_factory = other_micro_op_types.get(("default-factory",), None)
            has_default_factory = default_factory is not None

            if not other_micro_op_type.key_error and not self.key_error and not has_default_factory:
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        return False

    def check_for_runtime_data_conflict(self, obj):
        if super(ListWildcardDeletterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ListWildcardDeletterType(
            self.key_error or other_micro_op_type.key_error
        )


class ListWildcardDeletter(MicroOp):
    def __init__(self, target_manager, key_error):
        self.target_manager = target_manager
        self.key_error = key_error

    def invoke(self, key, **kwargs):
        raise_micro_op_conflicts(self, [ key ], self.target_manager.get_flattened_micro_op_types())

        self.target_manager.unbind_key(self.key)

        self.target_manager.obj.__delitem__(raw=True)


class ListDeletterType(ListMicroOpType):
    def __init__(self, key, key_error):
        self.key = key
        self.key_error = key_error

    def create(self, target_manager):
        return ListDeletter(target_manager, self.key, self.key_error)

    def can_be_derived_from(self, other_micro_op_type):
        return not other_micro_op_type.key_error or self.key_error

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ListDeletterType):
            if isinstance(self.type, InferredType):
                raise FatalError()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ListDeletterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            other_key, _ = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and self.key > other_key:
                return False
            if not self.key_error and not other_micro_op_type.key_error:
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if super(ListDeletterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ListDeletter(self.key, self.can_fail or other_micro_op_type.can_fail)


class ListDeletter(MicroOp):
    def __init__(self, target_manager, key):
        self.target_manager = target_manager
        self.key = key

    def invoke(self, **kwargs):
        raise_micro_op_conflicts(self, [ ], self.target_manager.get_flattened_micro_op_types())

        self.target_manager.unbind_key(self.key)

        self.target_manager.obj.__delitem__(self.key, raw=True)


class ListWildcardInsertType(ListMicroOpType):
    def __init__(self, type, key_error, type_error):
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ListWildcardInsert(target_manager, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.type.is_copyable_from(self.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ListWildcardInsertType):
            if isinstance(self.type, InferredType):
                raise FatalError()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ListDeletterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            _, other_type = get_key_and_type(other_micro_op_type)
            return not other_type.is_copyable_from(self.type)

        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        return False

    def check_for_runtime_data_conflict(self, obj):
        if super(ListWildcardInsertType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ListWildcardInsertType(
            merge_types([ self.type, other_micro_op_type.type ], "sub"),
            self.key_error or other_micro_op_type.key_error, self.type_error or other_micro_op_type.type_error
        )


class ListWildcardInsert(MicroOp):
    def __init__(self, target_manager, type, key_error, type_error):
        self.target_manager = target_manager
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, key, new_value, **kwargs):
        raise_micro_op_conflicts(self, [ key, new_value ], self.target_manager.get_flattened_micro_op_types())

        new_value_type = get_type_of_value(new_value)
        if not self.type.is_copyable_from(new_value_type):
            raise FatalError()

        for after_key in range(key, len(self.target_manager.obj)):
            self.target_manager.unbind_key(after_key)

        self.target_manager.obj.insert(key, new_value, raw=True)

        for after_key in range(key, len(self.target_manager.obj)):
            self.target_manager.unbind_key(after_key)


class ListInsertType(ListMicroOpType):
    def __init__(self, type, key, key_error, type_error):
        self.type = type
        self.key = key
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ListInsert(target_manager, self.key, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.type.is_copyable_from(self.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ListInsertType):
            if isinstance(self.type, InferredType):
                raise FatalError()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ListInsertType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            other_key, other_type = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD:
                if self.key > other_key:
                    return False
                elif self.key == other_key:
                    return not other_type.is_copyable_from(self.type)
                elif self.key < other_key:
                    prior_micro_op = other_micro_op_types.get(("get", other_key - 1), None)
                    if prior_micro_op is None:
                        return True
                    if not self.type_error and not prior_micro_op.type_error and not other_micro_op_type.type.is_copyable_from(prior_micro_op.type):
                        return True
            else:
                return not other_type.is_copyable_from(self.type)
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        return False

    def check_for_runtime_data_conflict(self, obj):
        if super(ListInsertType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ListInsertType(
            merge_types([ self.type, other_micro_op_type.type ], "sub"),
            self.key,
            self.key_error or other_micro_op_type.key_error, self.type_error or other_micro_op_type.type_error
        )

class ListInsert(MicroOp):
    def __init__(self, target_manager, key, type, key_error, type_error):
        self.target_manager = target_manager
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, new_value, **kwargs):
        raise_micro_op_conflicts(self, [ new_value ], self.target_manager.get_flattened_micro_op_types())

        new_value_type = get_type_of_value(new_value)
        if not self.type.is_copyable_from(new_value_type):
            raise FatalError()

        for after_key in range(self.key, len(self.target_manager.obj)):
            self.target_manager.unbind_key(after_key)

        self.target_manager.obj.insert(self.key, new_value, raw=True)

        for after_key in range(self.key, len(self.target_manager.obj)):
            self.target_manager.bind_key(after_key)


def RDHListType(element_types, wildcard_type, allow_push=True, allow_wildcard_insert=True, allow_delete=True, is_sparse=False):
    micro_ops = OrderedDict() #  Ordered so that dependencies from i+1 element on i are preserved

    for index, element_type in enumerate(element_types):
        const = False
        if isinstance(element_type, Const):
            const = True
            element_type = element_type.wrapped

        micro_ops[("get", index)] = ListGetterType(index, element_type, False, False)
        if not const:
            micro_ops[("set", index)] = ListSetterType(index, element_type, False, False)

    if wildcard_type:
        const = False
        if isinstance(wildcard_type, Const):
            const = True
            wildcard_type = wildcard_type.wrapped

        micro_ops[("get-wildcard",)] = ListWildcardGetterType(wildcard_type, True, False)
        if not const:
            micro_ops[("set-wildcard",)] = ListWildcardSetterType(wildcard_type, not is_sparse, True)
        if allow_push:
            micro_ops[("insert", 0)] = ListInsertType(wildcard_type, 0, False, False)
        if allow_delete:
            micro_ops[("delete-wildcard",)] = ListWildcardDeletterType(True)
        if allow_wildcard_insert:
            micro_ops[("insert-wildcard",)] = ListWildcardInsertType(wildcard_type, not is_sparse, False)
            micro_ops[("get", "insert")] = BuiltInFunctionGetterType(ListInsertFunctionType(wildcard_type))

    return CompositeType(micro_ops)

SPARSE_ELEMENT = object()

class RDHList(Composite, MutableSequence, object):
    def __init__(self, initial_data, bind=None):
        self.wrapped = {
            index: value for index, value in enumerate(initial_data)
        }
        self.length = len(initial_data)
        if bind:
            get_manager(self).add_composite_type(bind)

    def __len__(self):
        return self.length

    def insert(self, index, element, raw=False):
        if raw:
            for i in reversed(range(index, self.length)):
                self.wrapped[i + 1] = self.wrapped[i]
            self.wrapped[index] = element
            self.length = max(index + 1, self.length + 1)
            return

        manager = get_manager(self)

        micro_op_type = manager.get_micro_op_type(("insert", index))

        if micro_op_type is not None:
            micro_op = micro_op_type.create(manager)
            return micro_op.invoke(element)
        else:
            micro_op_type = manager.get_micro_op_type(("insert-wildcard",))

            if micro_op_type is None:
                raise MissingMicroOp()

            micro_op = micro_op_type.create(manager)
            micro_op.invoke(index, element)

    def __setitem__(self, key, value, raw=False):
        if raw:
            self.wrapped[key] = value
            self.length = max(self.length, key + 1)
            return

        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("set", key))
            if micro_op_type is not None:
                micro_op = micro_op_type.create(manager)
                micro_op.invoke(value)
            else:
                micro_op_type = manager.get_micro_op_type(("set-wildcard",))
    
                if micro_op_type is None:
                    raise MissingMicroOp()
    
                micro_op = micro_op_type.create(manager)
                micro_op.invoke(key, value)
        except (InvalidAssignmentKey, MissingMicroOp):
            raise IndexError()

    def __getitem__(self, key, raw=False):
        if raw:
            if key < 0 or key >= self.length:
                raise FatalError()
            return self.wrapped.get(key, SPARSE_ELEMENT)

        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("get", key))
            if micro_op_type is not None:
                micro_op = micro_op_type.create(manager)
                return micro_op.invoke()
            else:
                micro_op_type = manager.get_micro_op_type(("get-wildcard",))

                if micro_op_type is None:
                    raise MissingMicroOp(key)

                micro_op = micro_op_type.create(manager)
                return micro_op.invoke(key)
        except InvalidDereferenceKey:
            if key >= 0 and key < self.length:
                return None
            raise IndexError()
        except MissingMicroOp:
            raise IndexError()

    def __delitem__(self, key, raw=False):
        if raw:
            for i in reversed(range(key, self.length)):
                self.wrapped[i - 1] = self.wrapped[i]
            self.length -= 1
            return

        manager = get_manager(self)

        micro_op_type = manager.get_micro_op_type(("delete", key))
        if micro_op_type is not None:
            micro_op = micro_op_type.create(manager)
            return micro_op.invoke()
        else:
            micro_op_type = manager.get_micro_op_type(("delete-wildcard",))

            if micro_op_type is None:
                raise MissingMicroOp()

            micro_op = micro_op_type.create(manager)
            return micro_op.invoke(key)

    def __str__(self):
        return str(list(self))

    def __repr__(self):
        return repr(list(self))
