# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from UserDict import DictMixin

from lockdown.type_system.composites import CompositeType, \
    Composite, unbind_key, bind_key, does_value_fit_through_type
from lockdown.type_system.core_types import Type, merge_types, StringType
from lockdown.type_system.exceptions import FatalError, raise_if_safe, \
    InvalidDereferenceKey, InvalidDereferenceType, InvalidAssignmentType, \
    InvalidAssignmentKey, MissingMicroOp
from lockdown.type_system.managers import get_manager, get_type_of_value
from lockdown.type_system.micro_ops import MicroOpType
from lockdown.utils import MISSING, is_debug


class DictWildcardGetterType(MicroOpType):
    def __init__(self, key_type, value_type, key_error, type_error):
        if not isinstance(key_type, Type) or not isinstance(value_type, Type):
            raise FatalError()
        self.key_type = key_type
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, shortcut_checks=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key)

        if is_debug() and not self.key_type.is_copyable_from(get_type_of_value(key)):
            raise FatalError()

        obj = target_manager.get_obj()

        if obj._contains(key):
            value = obj._get(key)
        else:
            default_factory = target_manager.default_factory

            if not default_factory:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

            value = default_factory(key)

        if is_debug() or self.type_error:
            if not does_value_fit_through_type(value, self.value_type):
                raise raise_if_safe(InvalidDereferenceType, self.type_error)

        return value

    def raise_micro_op_invocation_conflicts(self, target_manager, key):
        pass

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get-wildcard", ))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.key_type.is_copyable_from(self.key_type)
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_setter = other_type.get_micro_op_type(("set-wildcard", ))
        if wildcard_setter and not self.type_error and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
                return True

        for key, other_setter_or_deleter in other_type.micro_op_types.items():
            if key[0] == "set":
                if not self.type_error and not other_setter_or_deleter.type_error and not self.value_type.is_copyable_from(other_setter_or_deleter.value_type):
                    return True
            if key[0] == "delete":
                if not self.key_error and not other_setter_or_deleter.key_error:
                    return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not bool(isinstance(target, RDHDict)):
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
            if target._contains(key_filter):
                return ([ target._get(key_filter) ], self.value_type)
            return ([], self.value_type)

        return (target._values(), self.value_type)

    def merge(self, other_micro_op_type):
        return DictWildcardGetterType(
            self.key_type,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


class DictGetterType(MicroOpType):
    def __init__(self, key, type, key_error, type_error):
        self.key = key
        self.key_type = get_type_of_value(key)
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, **kwargs):
        self.raise_micro_op_invocation_conflicts(target_manager)
 
        obj = target_manager.get_obj()
 
        if obj._contains(self.key):
            value = obj._get(self.key)
        else:
            default_factory = target_manager.default_factory
 
            if default_factory:
                value = default_factory(self.key)
            else:
                raise_if_safe(InvalidDereferenceKey, self.key_error)
 
        get_manager(value)
 
        type_of_value = get_type_of_value(value)
 
        if not self.value_type.is_copyable_from(type_of_value):
            raise raise_if_safe(InvalidDereferenceType, self.type_error)
 
        return value

    def raise_micro_op_invocation_conflicts(self, target_manager):
        pass

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get", self.key))
        return (
            other_micro_op_type,
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.value_type_error)
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_setter = other_type.get_micro_op_type(("set-wildcard", ))
        if wildcard_setter and not self.type_error and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
            return True

        wildcard_deletter = other_type.get_micro_op_type(("delete-wildcard", ))
        if wildcard_deletter and not self.key_error and not wildcard_deletter.key_error:
            return True

        detail_setter = other_type.get_micro_op_type(("set", self.key))
        if detail_setter and not self.type_error and not detail_setter.type_error and not self.value_type.is_copyable_from(detail_setter.value_type):
            return True

        detail_deleter = other_type.get_micro_op_type(("delete", self.key))
        if detail_deleter and not self.key_error and not detail_deleter.key_error:
            return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHDict):
            return False
        if not manager:
            return False

        if not (target._contains(self.key) or manager.default_factory or self.key_error):
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        if not key_filter or key_filter == self.key:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(self.key):
                return ([ target._get(self.key) ], self.value_type)
        return ([], None)

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return DictGetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

class DictWildcardSetterType(MicroOpType):
    def __init__(self, key_type, value_type, key_error, type_error):
        self.key_type = key_type
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, **kwargs):
        self.raise_micro_op_invocation_conflicts(target_manager, key, new_value)

        new_value_type = get_type_of_value(new_value)
        if not self.value_type.is_copyable_from(new_value_type):
            raise FatalError()

        unbind_key(target_manager, key)

        target_manager.get_obj()._get(key, new_value)

        bind_key(target_manager, key)

    def raise_micro_op_invocation_conflicts(self, target_manager, key, new_value):
        target_type = target_manager.get_effective_composite_type()

        wildcard_getter = target_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
            raise_if_safe(InvalidAssignmentType, self.type_error)

        detail_getter = target_type.get_micro_op_type(("get", key))
        if detail_getter and not detail_getter.type_error and not detail_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
            raise_if_safe(InvalidAssignmentType, self.type_error)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set-wildcard", ))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        for key, other_getter in other_type.micro_op_types.items():
            if key[0] == "get":
                if not self.type_error and not other_getter.type_error and not other_getter.value_type.is_copyable_from(self.value_type):
                    return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not bool(isinstance(target, RDHDict)):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return DictWildcardSetterType(
            self.key_type,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


class DictSetterType(MicroOpType):
    def __init__(self, key, type, key_error, type_error):
        self.key = key
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, new_value, **kwargs):
        self.raise_micro_op_invocation_conflicts(target_manager, new_value)

        new_value_type = get_type_of_value(new_value)
        if not self.value_type.is_copyable_from(new_value_type):
            raise FatalError()

        unbind_key(target_manager, self.key)

        target_manager.get_obj()._set(self.key, new_value)

        bind_key(target_manager, self.key)

    def raise_micro_op_invocation_conflicts(self, target_manager, new_value):
        target_type = target_manager.get_effective_composite_type()

        wildcard_getter = target_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
            raise_if_safe(InvalidAssignmentType, self.type_error)

        detail_getter = target_type.get_micro_op_type(("get", self.key))
        if detail_getter and not detail_getter.type_error and not detail_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
            raise_if_safe(InvalidAssignmentType, self.type_error)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set", self.key))
        return (
            other_micro_op_type,
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter and not self.type_error and not detail_getter.type_error and not detail_getter.value_type.is_copyable_from(self.value_type):
            return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not bool(isinstance(target, RDHDict)):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return DictSetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


class DictWildcardDeletterType(MicroOpType):

    def __init__(self, key_error):
        self.key_error = key_error

    def invoke(self, target_manager, key, **kwargs):
        self.raise_micro_op_invocation_conflicts(target_manager, key)

        unbind_key(target_manager.get_obj(), key)

        target_manager.get_obj()._delete(key)

    def raise_micro_op_invocation_conflicts(self, target_manager, key):
        target_type = target_manager.get_effective_composite_type()

        wildcard_getter = target_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not wildcard_getter.key_error:
            raise_if_safe(InvalidDereferenceKey, self.type_error)

        detail_getter = target_type.get_micro_op_type(("get", key))
        if detail_getter and not detail_getter.key_error:
            raise_if_safe(InvalidDereferenceKey, self.type_error)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("delete-wildcard", ))
        return other_micro_op_type and not other_micro_op_type.key_error or self.key_error

    def conflicts_with(self, our_type, other_type):
        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not bool(isinstance(target, RDHDict)):
            return False
        if not manager:
            return False

        if not (manager.default_factory or self.key_error):
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return DictWildcardDeletterType(
            self.key_error or other_micro_op_type.key_error
        )

class DictDeletterType(MicroOpType):
    def __init__(self, key, key_error):
        self.key = key
        self.key_error = key_error

    def invoke(self, target_manager, **kwargs):
        self.raise_micro_op_invocation_conflicts(target_manager)

        unbind_key(target_manager.get_obj(), self.key)

        target_manager.get_obj()._delete(self.key)

    def raise_micro_op_invocation_conflicts(self, target_manager):
        target_type = target_manager.get_effective_composite_type()

        wildcard_getter = target_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not wildcard_getter.key_error:
            raise_if_safe(InvalidDereferenceKey, self.type_error)

        detail_getter = target_type.get_micro_op_type(("get", self.key))
        if detail_getter and not detail_getter.key_error:
            raise_if_safe(InvalidDereferenceKey, self.type_error)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("delete", self.key))
        return other_micro_op_type and not other_micro_op_type.key_error or self.key_error

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not self.key_error and not wildcard_getter.key_error:
            return True

        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter and not self.key_error and not detail_getter.key_error:
            return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not bool(isinstance(target, RDHDict)):
            return False
        if not manager:
            return False

        if not (manager.default_factory or self.key_error):
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return DictDeletterType(self.key, self.key_error or other_micro_op_type.key_error)


class RDHDictType(CompositeType):
    def __init__(self, wildcard_type=None):
        micro_ops = {}

        if wildcard_type:
            micro_ops[("get-wildcard",)] = DictWildcardGetterType(StringType(), wildcard_type, True, False)
            micro_ops[("set-wildcard",)] = DictWildcardSetterType(StringType(), wildcard_type, True, True)
            micro_ops[("delete-wildcard",)] = DictWildcardDeletterType(True)

        super(RDHDictType, self).__init__(micro_ops, "RDHDictType")


class RDHDict(Composite, DictMixin, object):
    def __init__(self, initial_data, bind=None, debug_reason=None):
        self.wrapped = dict(initial_data)
        get_manager(self).debug_reason = debug_reason
        if isinstance(self.wrapped, RDHDict):
            raise FatalError()
        if bind:
            get_manager(self).add_composite_type(bind)

    def _get(self, key):
        if key in self.wrapped:
            return self.wrapped[key]
        raise AttributeError()

    def _set(self, key, value):
        self.wrapped[key] = value

    def _delete(self, key):
        del self.wrapped[key]

    def _contains(self, key):
        return key in self.wrapped

    def _keys(self):
        return self.wrapped.keys()

    def _values(self):
        return self.wrapped.values()

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
            raise KeyError()

    def __setitem__(self, key, value):
        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("set", key))
            if micro_op_type is not None:
                micro_op_type.invoke(manager, value)
            else:
                micro_op_type = manager.get_micro_op_type(("set-wildcard",))

                if micro_op_type is None:
                    raise MissingMicroOp()

                micro_op_type.invoke(manager, key, value)
        except InvalidAssignmentKey:
            raise KeyError()

    def __delitem__(self, key):
        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("delete", key))
            if micro_op_type is not None:
                return micro_op_type.invoke(manager)
            else:
                micro_op_type = manager.get_micro_op_type(("delete-wildcard",))
    
                if micro_op_type is None:
                    raise MissingMicroOp()

                return micro_op_type.invoke(manager, key)
        except MissingMicroOp:
            raise KeyError()

    def keys(self):
        if self is self.wrapped:
            raise FatalError()
        return self._keys()
