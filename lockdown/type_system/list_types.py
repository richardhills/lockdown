from _abcoll import MutableSequence
from collections import OrderedDict

from lockdown.type_system.composites import CompositeType, \
    Composite, unbind_key, bind_key, can_add_composite_type_with_filter,\
    does_value_fit_through_type
from lockdown.type_system.core_types import merge_types, Const, NoValueType, \
    IntegerType, Type
from lockdown.type_system.exceptions import FatalError, raise_if_safe, \
    InvalidDereferenceKey, InvalidDereferenceType, InvalidAssignmentKey, \
    InvalidAssignmentType, MissingMicroOp
from lockdown.type_system.managers import get_manager, get_type_of_value
from lockdown.type_system.micro_ops import MicroOpType
from lockdown.utils import MISSING, is_debug, micro_op_repr, default


class ListMicroOpType(MicroOpType):
    key_type = IntegerType()


class ListWildcardGetterType(ListMicroOpType):
    def __init__(self, value_type, key_error, type_error):
        if isinstance(type, NoValueType):
            raise FatalError()
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, allow_failure)
 
        obj = target_manager.get_obj()
 
        if obj._contains(key):
            value = obj._get(key)
        else:
            default_factory = target_manager.default_factory
 
            if not default_factory:
                raise_if_safe(InvalidDereferenceKey, self.key_error)
 
            value = default_factory(target_manager, key)
 
        if value is not SPARSE_ELEMENT:
            if is_debug() or self.type_error:
                if not does_value_fit_through_type(value, self.value_type):
                    raise raise_if_safe(InvalidDereferenceType, self.type_error)
 
        return value

    def raise_micro_op_invocation_conflicts(self, target_manager, key, allow_failure):
        pass

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get-wildcard",))

        if other_micro_op_type:
            return (
                (not other_micro_op_type.key_error or self.key_error)
                and (not other_micro_op_type.type_error or self.type_error)
                and self.value_type.is_copyable_from(other_micro_op_type.value_type)
            )

        return False

    def conflicts_with(self, our_type, other_type):
        wildcard_setter = other_type.get_micro_op_type(("set-wildcard",))
        if wildcard_setter and not self.type_error and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
            return True

        wildcard_inserter = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_inserter and not self.type_error and not wildcard_inserter.type_error and not self.value_type.is_copyable_from(wildcard_inserter.value_type):
            return True

        for tag, other in other_type.micro_op_types.items():
            if tag[0] == "set" and not self.type_error and not other.type_error and not self.value_type.is_copyable_from(other.value_type):
                return True
            if tag[0] == "insert" and not self.type_error and not other.type_error and not self.value_type.is_copyable_from(other.value_type):
                return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        if not (manager.default_factory or self.key_error):
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        if key_filter is not None:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if key_filter in target.wrapped:
                return ([ target.wrapped[key_filter] ], self.value_type)
            return ([], None)
        return (target.wrapped.values(), self.value_type)

    def clone(self, value_type=MISSING, key_error=MISSING, type_error=MISSING):
        return ListWildcardGetterType(
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            default(type_error, self.type_error)
        )

    def merge(self, other_micro_op_type):
        return ListWildcardGetterType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("getL", "*", self.key_error, self.value_type, self.type_error)

class ListGetterType(ListMicroOpType):
    def __init__(self, key, type, key_error, type_error):
        if not isinstance(key, int):
            raise FatalError()
        if not isinstance(type, Type):
            raise FatalError()

        self.key = key
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, allow_failure)

        obj = target_manager.get_obj()

        if obj._contains(self.key):
            value = obj._get(self.key)
        else:
            default_factory = target_manager.default_factory

            if default_factory:
                value = default_factory(self.key)
            else:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

        type_of_value = get_type_of_value(value)

        if not self.value_type.is_copyable_from(type_of_value):
            raise_if_safe(InvalidDereferenceKey, self.can_fail)

        return value

    def raise_micro_op_invocation_conflicts(self, target_manager, allow_failure):
        pass

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get", self.key))

        if other_micro_op_type:
            return (
                (not other_micro_op_type.key_error or self.key_error)
                and (not other_micro_op_type.type_error or self.type_error)
                and self.value_type.is_copyable_from(other_micro_op_type.value_type)
            )

        return False
            
    def conflicts_with(self, our_type, other_type):
        wildcard_setter = other_type.get_micro_op_type(("set-wildcard",))
        if wildcard_setter and not self.type_error and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
            return True

        wildcard_inserter = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_inserter and self.key > 0 and not wildcard_inserter.type_error and not wildcard_inserter.type.is_copyable_from(self.value_type):
            return True

        detail_setter = other_type.get_micro_op_type(("set", self.key))
        if detail_setter and not self.type_error and not detail_setter.type_error and not self.value_type.is_copyable_from(detail_setter.value_type):
            return True

        detail_inserter = other_type.get_micro_op_type(("insert", self.key))
        if detail_inserter and not self.type_error and not detail_inserter.type_error and not self.value_type.is_copyable_from(detail_inserter.value_type):
            return True

        for tag, other in other_type.micro_op_types.items():
            # Need to work out if deletes work this way...
            if tag[0] == "delete" and tag[1] < self.key and not other.key_error and not self.key_error:
                return True
            if tag[0] == "insert" and tag[1] < self.key and not other.type_error and not self.type_error and not self.value_type.is_copyable_from(other.value_type):
                return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        if not (self.key < len(target) or manager.default_factory or self.key_error):
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        if key_filter is None or key_filter == self.key:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(self.key):
                return ([ target._get(self.key) ], self.value_type)
        return ([], None)

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListGetterType(
            self.key,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

    def merge(self, other_micro_op_type):
        return ListGetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("getL", self.key, self.key_error, self.value_type, self.type_error)


class ListWildcardSetterType(ListMicroOpType):
    def __init__(self, type, key_error, type_error):
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, new_value, allow_failure)

        if key < 0 or key > target_manager.get_obj()._length:
            if self.key_error:
                raise InvalidAssignmentKey()

        unbind_key(target_manager, key)

        target_manager.get_obj()._set(key, new_value)

        bind_key(target_manager, key)

    def raise_micro_op_invocation_conflicts(self, target_manager, key, new_value, allow_failure):
        target_type = target_manager.get_effective_composite_type()
        if not can_add_composite_type_with_filter(target_manager.get_obj(), target_type, key, new_value):
            raise_if_safe(InvalidAssignmentType, self.type_error or allow_failure)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set-wildcard",))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        for tag, other_getter in other_type.micro_op_types.items():
            if tag[0] == "get" and not self.type_error and not other_getter.type_error and not other_getter.value_type.is_copyable_from(self.value_type):
                return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        if not self.key_error and not target.is_sparse:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)


    def clone(self, value_type=MISSING, key_error=MISSING, type_error=MISSING):
        return ListWildcardSetterType(
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            default(type_error, self.type_error)
        )

    def merge(self, other_micro_op_type):
        return ListWildcardSetterType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("setL", "*", self.key_error, self.value_type, self.type_error)

class ListSetterType(ListMicroOpType):
    def __init__(self, key, type, key_error, type_error):
        self.key = key
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, new_value, allow_failure)

        if self.key < 0 or self.key > len(target_manager.get_obj()):
            raise_if_safe(InvalidAssignmentKey, self.key_error)

        unbind_key(target_manager, self.key)

        target_manager.get_obj()._set(self.key, new_value)

        bind_key(target_manager, self.key)

    def raise_micro_op_invocation_conflicts(self, target_manager, new_value, allow_failure):
        target_type = target_manager.get_effective_composite_type()
        if not can_add_composite_type_with_filter(target_manager.get_obj(), target_type, self.key, new_value):
            raise_if_safe(InvalidAssignmentType, self.type_error or allow_failure)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set", self.key))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        other_getter = other_type.get_micro_op_type(("get", self.key))
        if other_getter and not self.type_error and not other_getter.type_error and not other_getter.value_type.is_copyable_from(self.value_type):
            return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        if not target._contains(self.key) and not self.key_error and not target.is_sparse:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def clone(self, value_type):
        return ListSetterType(self.key, value_type, self.key_error, self.type_error)

    def merge(self, other_micro_op_type):
        return ListSetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("setL", self.key, self.key_error, self.value_type, self.type_error)


class ListWildcardDeletterType(ListMicroOpType):
    def __init__(self, key_error):
        self.key_error = key_error

    def invoke(self, target_manager, key, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, allow_failure)

        for after_key in range(key, len(target_manager.get_obj())):
            unbind_key(target_manager, after_key)

        target_manager.get_obj().__delitem__(key, raw=True)

        for after_key in range(key, len(target_manager.get_obj())):
            bind_key(target_manager, after_key)

    def raise_micro_op_invocation_conflicts(self, target_manager, key, allow_failure):
        target_type = target_manager.get_effective_composite_type()

        wildcard_getter = target_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not wildcard_getter.key_error:
            raise_if_safe(InvalidAssignmentType, self.key_error)

        detail_getter = target_type.get_micro_op_type(("get", self.key))
        if detail_getter and not detail_getter.key_error:
            raise_if_safe(InvalidAssignmentType, self.key_error)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("delete-wildcard",))
        return (other_micro_op_type and not other_micro_op_type.key_error) or self.key_error

    def conflicts_with(self, our_type, other_type):
        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return ListWildcardDeletterType(
            self.key_error or other_micro_op_type.key_error
        )

    def __repr__(self):
        return micro_op_repr("deleteL", "*", self.key_error)

class ListDeletterType(ListMicroOpType):
    def __init__(self, key, key_error):
        self.key = key
        self.key_error = key_error

    def invoke(self, target_manager, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, allow_failure)

        for after_key in range(self.key, len(target_manager.get_obj())):
            unbind_key(target_manager, after_key)

        target_manager.get_obj().__delitem__(self.key, raw=True)

        for after_key in range(self.key, len(target_manager.get_obj())):
            bind_key(target_manager, after_key)

    def raise_micro_op_invocation_conflicts(self, target_manager, allow_failure):
        target_type = target_manager.get_effective_composite_type()

        wildcard_getter = target_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not wildcard_getter.key_error:
            raise_if_safe(InvalidDereferenceKey, self.type_error)

        detail_getter = target_type.get_micro_op_type(("get", self.key))
        if detail_getter and not detail_getter.key_error:
            raise_if_safe(InvalidDereferenceKey, self.type_error)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("delete", self.key))

        return other_micro_op_type and not other_micro_op_type.key_error or self.key_error

    def conflicts_with(self, our_type, other_type):
        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return ListDeletterType(self.key, self.can_fail or other_micro_op_type.can_fail)

    def __repr__(self):
        return micro_op_repr("deleteL", self.key, self.key_error)


class ListWildcardInsertType(ListMicroOpType):
    def __init__(self, type, key_error, type_error):
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, new_value, allow_failure)
 
        for after_key in range(key, len(target_manager.get_obj())):
            unbind_key(target_manager, after_key)

        target_manager.get_obj()._insert(key, new_value)
 
        for after_key in range(key, len(target_manager.get_obj())):
            bind_key(target_manager, after_key)

    def raise_micro_op_invocation_conflicts(self, target_manager, key, new_value, allow_failure):
        target_type = target_manager.get_effective_composite_type()
        target = target_manager.get_obj()

        if not can_add_composite_type_with_filter(target, target_type, key, new_value):
            raise_if_safe(InvalidAssignmentType, self.type_error or allow_failure)

        for after_key in range(key + 1, len(target_manager.get_obj()) + 1):            
            if not can_add_composite_type_with_filter(target_manager.get_obj(), target_type, after_key, target_manager.get_obj().wrapped[after_key - 1]):
                raise_if_safe(InvalidAssignmentType, self.type_error or allow_failure)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert-wildcard",))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        for tag, other_getter in other_type.micro_op_types.items():
            if tag[0] == "get" and not self.type_error and not other_getter.type_error and not other_getter.value_type.is_copyable_from(self.value_type):
                return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListWildcardInsertType(
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

    def merge(self, other_micro_op_type):
        return ListWildcardInsertType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error, self.type_error or other_micro_op_type.type_error
        )

class ListInsertType(ListMicroOpType):
    def __init__(self, key, type, key_error, type_error):
        if not isinstance(type, Type):
            raise FatalError()
        if not isinstance(key, int):
            raise FatalError()
        self.value_type = type
        self.key = key
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, new_value, allow_failure)

        for after_key in range(self.key, len(target_manager.get_obj())):
            unbind_key(target_manager, after_key)

        target_manager.get_obj()._insert(self.key, new_value)

        for after_key in range(self.key, len(target_manager.get_obj())):
            bind_key(target_manager, after_key)

    def raise_micro_op_invocation_conflicts(self, target_manager, new_value, allow_failure):
        target_type = target_manager.get_effective_composite_type()
        for after_key in range(self.key + 1, len(target_manager.get_obj())):            
            if not can_add_composite_type_with_filter(target_manager.get_obj(), target_type, after_key, target_manager.get_obj().wrapped[after_key - 1]):
                raise_if_safe(InvalidAssignmentType, self.type_error)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert", self.key))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        for tag, other_getter in other_type.micro_op_types.items():
            if tag[0] == "get" and tag[1] >= self.key and not self.type_error and not other_getter.type_error and not other_getter.value_type.is_copyable_from(self.value_type):
                return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListInsertType(
            self.key,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

    def merge(self, other_micro_op_type):
        return ListInsertType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key,
            self.key_error or other_micro_op_type.key_error, self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("insertL", self.key, self.key_error, self.value_type, self.type_error)

class ListRangeGetterType(ListMicroOpType):
    def __init__(self, range, value_type, key_error, type_error):
        self.range = range
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key):
        if key < 0 or key >= self.range:
            raise FatalError()

        obj = target_manager.get_obj()

        if obj._contains(key):
            value = obj._get(key)
        else:
            default_factory = target_manager.default_factory

            if default_factory:
                value = default_factory(key)
            else:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

        if not does_value_fit_through_type(value, self.value_type):
            raise_if_safe(InvalidDereferenceKey, self.type_error)

        return value

    def is_derivable_from(self, other_type):
        for tag, micro_op in other_type.micro_op_types:
            tags_match = tag[0] == "get-range" and tag[1] > self.range
            if not tags_match:
                continue
            micro_op_match = self.value_type.is_copyable_from(micro_op.value_type)
            if micro_op_match:
                return True
        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        if not (self.range < target._length or manager.default_factory or self.key_error):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_setter = other_type.get_micro_op_type(("set-wildcard",))
        if wildcard_setter and not self.type_error and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
            return True

        wildcard_inserter = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_inserter and not self.type_error and not wildcard_setter.type_error and not wildcard_inserter.type.is_copyable_from(self.value_type):
            return True

        for tag, other in other_type.micro_op_types.items():
            if tag[0] == "set" and tag[1] < self.range and not self.value_type.is_copyable_from(other.value_type):
                return True
            if tag[0] == "insert" and tag[1] < self.range and not self.value_type.is_copyable_from(other.value_type):
                return True

        # There's a lot more to do here...

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        if key_filter is not None or key_filter < self.range:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(key_filter):
                return ([ target._get(key_filter) ], self.value_type)
        return ([], None)

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListRangeGetterType(
            self.range,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

    def merge(self, other_micro_op_type):
        return ListRangeGetterType(
            self.range,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("getrangeL", self.key, self.key_error, self.value_type, self.type_error)

class ListRangeSetterType(ListMicroOpType):
    def __init__(self, range, value_type, key_error, type_error):
        self.range = range
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value):
        if key < 0 or key >= self.range:
            if self.key_error:
                raise InvalidAssignmentKey()

        obj = target_manager.get_obj()

        unbind_key(target_manager, key)

        target_manager.get_obj()._set(key, new_value)

        bind_key(target_manager, key)

    def is_derivable_from(self, other_type):
        for tag, micro_op in other_type.micro_op_types:
            tags_match = tag[0] == "set-range" and tag[1] > self.range
            if not tags_match:
                continue
            micro_op_match = self.value_type.is_copyable_from(micro_op.value_type)
            if micro_op_match:
                return True
        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        if not self.key_error and not target.is_sparse:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        for tag, other in other_type.micro_op_types.items():
            pass #...

        # There's a lot more to do here...

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListRangeSetterType(
            self.range,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

    def merge(self, other_micro_op_type):
        return ListRangeSetterType(
            self.range,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("setrangeL", self.key, self.key_error, self.value_type, self.type_error)


def RDHListType(element_types, wildcard_type, allow_push=True, allow_wildcard_insert=True, allow_delete=True, is_sparse=False):
    micro_ops = OrderedDict()  #  Ordered so that dependencies from i+1 element on i are preserved

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

        if not isinstance(wildcard_type, Type):
            raise ValueError()

        micro_ops[("get-wildcard",)] = ListWildcardGetterType(wildcard_type, True, False)
        if not const:
            micro_ops[("set-wildcard",)] = ListWildcardSetterType(wildcard_type, not is_sparse, True)
        if allow_push:
            micro_ops[("insert", 0)] = ListInsertType(0, wildcard_type, False, False)
        if allow_delete:
            micro_ops[("delete-wildcard",)] = ListWildcardDeletterType(True)
        if allow_wildcard_insert:
            micro_ops[("insert-wildcard",)] = ListWildcardInsertType(wildcard_type, not is_sparse, False)
#            micro_ops[("get", "insert")] = BuiltInFunctionGetterType(ListInsertFunctionType(micro_ops[("insert-wildcard",)], wildcard_type))

    return CompositeType(micro_ops, "RDHListType")


SPARSE_ELEMENT = object()


class RDHList(Composite, MutableSequence, object):
    def __init__(self, initial_data, is_sparse=False, bind=None, debug_reason=None):
        self.wrapped = {
            index: value for index, value in enumerate(initial_data)
        }
        manager = get_manager(self, "RDHList")
        self.length = len(initial_data)
        self.is_sparse = is_sparse
        manager.debug_reason = debug_reason
        if bind:
            get_manager(self).add_composite_type(bind)

    def _set(self, key, value):
        if key not in self.wrapped and not self.is_sparse:
            raise IndexError()

        self.wrapped[key] = value
        self.length = max(self.length, key + 1)

    def _get(self, key):
        if key in self.wrapped:
            return self.wrapped[key]
        if self.is_sparse and key >= 0 and key < self.length:
            return SPARSE_ELEMENT
        raise IndexError()

    def _delete(self, key):
        del self.wrapped[key]
        keys_above_key = sorted([k for k in self.wrapped.keys() if k > key])
        for k in keys_above_key:
            self.wrapped[k - 1] = self.wrapped[k]
            del self.wrapped[k]
        self.length -= 1

    def _contains(self, key):
        return key >= 0 and key < self.length

    def _keys(self):
        return list(range(self.length))

    def _values(self):
        return [self._get(k) for k in self._keys()]

    def _insert(self, key, value):
        # <= because  we  allow inserts after the last element in the list
        if not (key >= 0 and key <= self.length) and not self.is_sparse:
            raise IndexError()

        keys_above_key = reversed(sorted([k for k in self.wrapped.keys() if k >= key]))
        for k in keys_above_key:
            self.wrapped[k + 1] = self.wrapped[k]
            del self.wrapped[k]
        self.wrapped[key] = value
        self.length = max(self.length + 1, key + 1)

    @property
    def _length(self):
        return self.length

    def _to_list(self):
        return self._values()

    def __len__(self):
        return self.length

    def insert(self, index, element):
        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("insert", index))

            if micro_op_type is not None:
                return micro_op_type.invoke(manager, element, allow_failure=True)
            else:
                micro_op_type = manager.get_micro_op_type(("insert-wildcard",))

                if micro_op_type is None:
                    raise MissingMicroOp()

                micro_op_type.invoke(manager, index, element, allow_failure=True)
        except MissingMicroOp:
            raise IndexError()
        except InvalidAssignmentType:
            raise TypeError()

    def __setitem__(self, key, value):
        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("set", key))
            if micro_op_type is not None:
                micro_op_type.invoke(manager, value, allow_failure=True)
            else:
                micro_op_type = manager.get_micro_op_type(("set-wildcard",))
    
                if micro_op_type is None:
                    raise MissingMicroOp()
    
                micro_op_type.invoke(manager, key, value, allow_failure=True)
        except (InvalidAssignmentKey, MissingMicroOp):
            raise IndexError()
        except InvalidAssignmentType:
            raise TypeError()

    def __getitem__(self, key):
        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("get", key))
            if micro_op_type is not None:
                return micro_op_type.invoke(manager)
            else:
                micro_op_type = manager.get_micro_op_type(("get-wildcard",))

                if micro_op_type is None:
                    raise MissingMicroOp(key)

                return micro_op_type.invoke(manager, key)
        except InvalidDereferenceKey:
            if key >= 0 and key < self.length:
                return None
            raise IndexError()
        except MissingMicroOp:
            raise IndexError()

    def __delitem__(self, key):
        manager = get_manager(self)

        micro_op_type = manager.get_micro_op_type(("delete", key))
        if micro_op_type is not None:
            return micro_op_type.invoke(manager)
        else:
            micro_op_type = manager.get_micro_op_type(("delete-wildcard",))

            if micro_op_type is None:
                raise MissingMicroOp()

            return micro_op_type.invoke(manager, key)

    def __str__(self):
        return str(list(self))

    def __repr__(self):
        return repr(list(self))
