# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from UserDict import DictMixin
from _abcoll import MutableSequence

from lockdown.type_system.composites import Composite, CompositeType
from lockdown.type_system.core_types import merge_types, Const, Type, StringType, \
    IntegerType, OneOfType, AnyType
from lockdown.type_system.exceptions import FatalError, MissingMicroOp, \
    InvalidAssignmentKey, InvalidAssignmentType, InvalidDereferenceKey, \
    raise_if_safe
from lockdown.type_system.managers import get_manager
from lockdown.type_system.micro_ops import MicroOpType
from lockdown.utils import MISSING

SPARSE_ELEMENT = object()


class Universal(Composite):
    def __init__(self, is_sparse, default_factory=None, bind=None, debug_reason=None, initial_wrapped=None, initial_length=0):
        self.wrapped = initial_wrapped or {}

        manager = get_manager(self, "Universal")

        manager.default_factory = default_factory
        manager.is_sparse = is_sparse
        manager.debug_reason = debug_reason

        self.length = initial_length

        if bind:
            manager.add_composite_type(bind)

    def _set(self, key, value):
        manager = get_manager(self)

        if isinstance(key, int) and not manager.is_sparse and not self._is_key_within_range(key):
            raise IndexError()

        self.wrapped[key] = value

        if isinstance(key, int):
            self.length = max(self.length, key + 1)

    def _get(self, key):
        manager = get_manager(self)

        if key in self.wrapped:
            return self.wrapped[key]

        if isinstance(key, int) and manager.is_sparse and self._is_key_within_range(key):
            return SPARSE_ELEMENT

        raise IndexError()

    def _is_key_within_range(self, key):
        return 0 <= key < self.length

    def _delete(self, key):
        manager = get_manager(self)

        if not manager.is_sparse:
            raise FatalError()

        if not self._is_key_within_range(key):
            if manager.default_factory:
                return
            raise KeyError()

        del self.wrapped[key]

    def _remove(self, key):
        if not isinstance(key, int):
            raise FatalError()

        manager = get_manager(self)

        if not self._is_key_within_range(key):
            if manager.default_factory:
                return
            raise KeyError()

        del self.wrapped[key]

        keys_above_key = sorted([k for k in self.wrapped.keys() if isinstance(k, int) and k > key])
        for k in keys_above_key:
            self.wrapped[k - 1] = self.wrapped.pop(k)
        self.length -= 1

    def _insert(self, key, value):
        if not isinstance(key, int):
            raise FatalError()

        manager = get_manager(self)

        if not manager.is_sparse and not self.self._is_key_within_range(key):
            raise KeyError()

        keys_above_key = reversed(sorted([k for k in self.wrapped.keys() if isinstance(k, int) and k >= key]))
        for k in keys_above_key:
            self.wrapped[k + 1] = self.wrapped.pop(k)
        self.wrapped[key] = value
        self.length = max(self.length + 1, key + 1)

    def _contains(self, key):
        manager = get_manager(self)

        if isinstance(key, int) and manager.is_sparse:
            return 0 <= key < self.length

        return key in self.wrapped

    def _keys(self):
        manager = get_manager(self)

        if manager.is_sparse:
            for i in range(self.length):
                yield i

        for k in self.wrapped.keys():
            if not (manager.is_sparse and isinstance(k, int)):
                yield k

    def _values(self):
        for k in self._keys():
            yield self._get(k)

    @property
    def _length(self):
        return self.length

    def __repr__(self):
        return repr(self.__dict__)

    def __str__(self):
        return str(self.__dict__)


class PythonObject(Universal):
    def __init__(self, initial_data, **kwargs):
        initial_wrapped = {}
        for key, value in initial_data.items():
            if value is MISSING:
                raise FatalError()
            initial_wrapped[key] = value

        super(PythonObject, self).__init__(True, initial_wrapped=initial_wrapped, **kwargs)

    def __setattr__(self, key, value):
        try:
            if key in ("wrapped", "length"):
                return super(PythonObject, self).__setattr__(key, value)

            manager = get_manager(self, "PythonObject.__setattr__")

            micro_op_type = manager.get_micro_op_type(("set", key))
            if micro_op_type is not None:
                micro_op_type.invoke(manager, value, allow_failure=True)
            else:
                micro_op_type = manager.get_micro_op_type(("set-wildcard",))
    
                if micro_op_type is None:
                    raise MissingMicroOp()

                micro_op_type.invoke(manager, key, value, allow_failure=True)
        except (InvalidAssignmentKey, MissingMicroOp):
            raise AttributeError(key)
        except InvalidAssignmentType:
            raise TypeError()

    def __getattribute__(self, key):
        if key in ("__dict__", "__class__", "_contains", "_get", "_set", "_delete", "_keys", "_values", "wrapped", "length"):
            return super(PythonObject, self).__getattribute__(key)

        try:
            manager = get_manager(self, "RDHObject.__getattr__")

            micro_op_type = manager.get_micro_op_type(("get", key))
            if micro_op_type is not None:
                return micro_op_type.invoke(manager)
            else:
                micro_op_type = manager.get_micro_op_type(("get-wildcard",))

                if micro_op_type is None:
                    raise MissingMicroOp(key)

                return micro_op_type.invoke(manager, key)
        except InvalidDereferenceKey:
            raise AttributeError(key)
        except MissingMicroOp:
            raise AttributeError(key)

    def __delattr__(self, key):
        manager = get_manager(self)

        micro_op_type = manager.get_micro_op_type(("delete", key))
        if micro_op_type is not None:
            return micro_op_type.invoke(manager)
        else:
            micro_op_type = manager.get_micro_op_type(("delete-wildcard",))

            if micro_op_type is None:
                raise MissingMicroOp()

            return micro_op_type.invoke(manager, key)


class PythonList(Universal, MutableSequence):
    def __init__(self, initial_data, **kwargs):
        initial_wrapped = {}
        for index, value in enumerate(initial_data):
            initial_wrapped[index] = value
        initial_length = len(initial_data)

        super(PythonList, self).__init__(False, initial_wrapped=initial_wrapped, initial_length=initial_length, **kwargs)

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

    def __len__(self):
        return self.length


class PythonDict(Universal, DictMixin, object):
    def __init__(self, initial_data, **kwargs):
        initial_wrapped = {}
        for key, value in initial_data.items():
            if value is MISSING:
                raise FatalError()
            initial_wrapped[key] = value

        super(PythonDict, self).__init__(initial_wrapped=initial_wrapped, *kwargs)

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


class GetterMicroOpType(MicroOpType):
    key_error = False
    type_error = False

    def __init__(self, key, value_type):
        self.key = key
        self.value_type = value_type

    def invoke(self, target_manager, *args, **kwargs):
        obj = target_manager.get_obj()
        if self.key in obj._keys():
            value = obj._get(self.key)
        else:
            default_factory = target_manager.default_factory
            value = default_factory(target_manager, self.key)

        return value

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get", self.key))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (target._contains(self.key) or manager.default_factory):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_deletter = other_type.get_micro_op_type(("delete-wildcard",))
        if wildcard_deletter:
            return True

        wildcard_remove = other_type.get_micro_op_type(("remove-wildcard",))
        if wildcard_remove:
            return True

        wildcard_insert = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_insert:
            return True

        insert_first = other_type.get_micro_op_type(("insert-first",))
        if insert_first:
            return True

        wildcard_setter = other_type.get_micro_op_type(("set-wildcard",))
        if wildcard_setter and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
            return True

        detail_setter = other_type.get_micro_op_type(("set", self.key))
        if detail_setter and not self.value_type.is_copyable_from(detail_setter.value_type):
            return True

    def prepare_bind(self, target, key_filter, substitute_value):
        if key_filter is None or key_filter == self.key:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(self.key):
                return ([ target._get(self.key) ], self.value_type)
        return ([], None)

    def merge(self, other_micro_op_type):
        return GetterMicroOpType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
        )

    def clone(self):
        return GetterMicroOpType(self.key, self.value_type)


class SetterMicroOpType(MicroOpType):
    key_error = False
    type_error = False

    def __init__(self, key, value_type):
        self.key = key
        self.value_type = value_type

    def invoke(self, target_manager, *args, **kwargs):
        obj = target_manager.get_obj()
        if self.key in obj._keys():
            value = obj._get(self.key)
        else:
            default_factory = target_manager.default_factory
            value = default_factory(target_manager, self.key)

        return value

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set", self.key))
        return (
            other_micro_op_type
            and (not other_type.key_error or self.key_error)
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (target._contains(self.key) or manager.default_factory):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter and not detail_getter.value_type.is_copyable_from(self.value_type):
            return True

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return SetterMicroOpType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.type_error or other_micro_op_type.type_error
        )

    def clone(self):
        return SetterMicroOpType(self.key, self.value_type, self.type_error)


class InsertStartMicroOpType(MicroOpType):
    key_error = False

    def __init__(self, value_type, type_error):
        self.value_type = value_type
        self.type_error = type_error

    def invoke(self, target_manager, new_value, *args, **kwargs):
        obj = target_manager.get_obj()
        obj._insert(0, new_value)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert-start",))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter and not self.value_type.is_copyable_from(detail_getter.value_type):
            return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return InsertStartMicroOpType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.type_error or other_micro_op_type.type_error
        )

    def clone(self):
        return InsertStartMicroOpType(self.value_type, self.type_error)


class InsertEndMicroOpType(MicroOpType):
    key_error = False

    def __init__(self, value_type, type_error):
        self.value_type = value_type
        self.type_error = type_error

    def invoke(self, target_manager, new_value, *args, **kwargs):
        obj = target_manager.get_obj()
        obj._insert(obj._length, new_value)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert-end",))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return InsertEndMicroOpType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.type_error or other_micro_op_type.type_error
        )

    def clone(self):
        return InsertEndMicroOpType(self.value_type, self.type_error)


class GetterWildcardMicroOpType(MicroOpType):
    type_error = False

    def __init__(self, key_type, value_type, key_error):
        self.key_type = key_type
        self.value_type = value_type
        self.key_error = key_error

    def invoke(self, target_manager, key, *args, **kwargs):
        obj = target_manager.get_obj()
        default_factory = target_manager.default_factory

        value = MISSING

        if obj._contains(key):
            value = obj._get(key)
        elif default_factory:
            value = default_factory(target_manager, key)

        if value is MISSING:
            raise_if_safe(InvalidDereferenceKey, self.key_error)

        return value

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get-wildcard",))
        return (
            other_micro_op_type
            and other_type.key_type.is_copyable_from(self.key_type)
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (self.key_error or manager.default_factory):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_deletter = other_type.get_micro_op_type(("delete-wildcard",))
        if wildcard_deletter:
            return True

        wildcard_remove = other_type.get_micro_op_type(("remove-wildcard",))
        if wildcard_remove:
            return True

        wildcard_insert = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_insert:
            return True

        insert_first = other_type.get_micro_op_type(("insert-first",))
        if insert_first:
            return True

        wildcard_setter = other_type.get_micro_op_type(("set-wildcard",))
        if wildcard_setter and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
            return True

        for tag in other_type.micro_op_types.keys():
            if len(tag) == 2 and tag[0] == "set":
                detail_setter = other_type.get_micro_op_type(("set", tag[1]))
                if detail_setter and not self.value_type.is_copyable_from(detail_setter.value_type):
                    return True

    def prepare_bind(self, target, key_filter, substitute_value):
        if key_filter is not None:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(key_filter):
                return ([ target._get(key_filter) ], self.value_type)
            return ([], None)
        return (target._values(), self.value_type)

    def merge(self, other_micro_op_type):
        return GetterMicroOpType(
            self.key,
            merge_types([ self.key_type, other_micro_op_type.key_type ], "sub"),
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
        )

    def clone(self):
        return GetterWildcardMicroOpType(self.key_type, self.value_type)


class SetterWildcardMicroOpType(MicroOpType):
    def __init__(self, key_type, value_type, key_error, type_error):
        self.key_type = key_type
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, *args, **kwargs):
        obj = target_manager.get_obj()
        obj._set(key, new_value)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set-wildcard",))
        return (
            other_micro_op_type
            and (not other_type.key_error or self.key_error) 
            and (not other_type.type_error or self.type_error) 
            and other_type.key_type.is_copyable_from(self.key_type)
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        for tag, possible_detail_getter in other_type.micro_op_types.items():
            if len(tag) == 2 and tag[0] == "get":
                if not self.value_type.is_copyable_from(possible_detail_getter.value_type):
                    return True

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return SetterWildcardMicroOpType(
            merge_types([ self.key_type, other_micro_op_type.key_type ], "sub"),
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def clone(self):
        return SetterWildcardMicroOpType(self.key_type, self.value_type, self.key_error, self.type_error)


class DeletterWildcardMicroOpType(MicroOpType):
    def __init__(self, key_type, key_error):
        self.key_type = key_type
        self.key_error = key_error

    def invoke(self, target_manager, key, *args, **kwargs):
        obj = target_manager.get_obj()
        obj._delete(key)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("delete-wildcard",))
        return (
            other_micro_op_type
            and (not other_type.key_error or self.key_error) 
            and other_type.key_type.is_copyable_from(self.key_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (self.key_error or manager.default_factory):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter:
            return True

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return DeletterWildcardMicroOpType(
            merge_types([ self.key_type, other_micro_op_type.key_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
        )

    def clone(self):
        return DeletterWildcardMicroOpType(self.key_type, self.key_error)


class RemoverWildcardMicroOpType(MicroOpType):
    def __init__(self, key_type, key_error):
        self.key_type = key_type
        self.key_error = key_error

    def invoke(self, target_manager, key, *args, **kwargs):
        obj = target_manager.get_obj()
        obj._remove(key)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("remove-wildcard",))
        return (
            other_micro_op_type
            and (not other_type.key_error or self.key_error) 
            and other_type.key_type.is_copyable_from(self.key_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (self.key_error or manager.default_factory):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter:
            return True

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return RemoverWildcardMicroOpType(
            merge_types([ self.key_type, other_micro_op_type.key_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
        )

    def clone(self):
        return RemoverWildcardMicroOpType(self.key_type, self.key_error)


class InserterWildcardMicroOpType(MicroOpType):
    def __init__(self, value_type, key_error, type_error):
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, *args, **kwargs):
        obj = target_manager.get_obj()
        obj._insert(key, new_value)

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert-wildcard",))
        return (
            other_micro_op_type
            and (not other_type.key_error or self.key_error) 
            and (not other_type.type_error or self.type_error) 
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter:
            return True

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return InserterWildcardMicroOpType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error,
        )

    def clone(self):
        return InserterWildcardMicroOpType(self.value_type, self.key_type, self.key_error)


class IterMicroOpType(MicroOpType):
    key_error = False
    type_error = False

    def __init__(self, value_type):
        self.value_type = value_type

    def invoke(self, target_manager, key, new_value, *args, **kwargs):
        obj = target_manager.get_obj()
        for v in obj._values():
            yield v

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("iter",))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_deletter = other_type.get_micro_op_type(("delete-wildcard",))
        if wildcard_deletter:
            return True

        wildcard_remove = other_type.get_micro_op_type(("remove-wildcard",))
        if wildcard_remove:
            return True

        wildcard_insert = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_insert:
            return True

        insert_first = other_type.get_micro_op_type(("insert-first",))
        if insert_first:
            return True

        wildcard_setter = other_type.get_micro_op_type(("set-wildcard",))
        if wildcard_setter and not wildcard_setter.type_error and not self.value_type.is_copyable_from(wildcard_setter.value_type):
            return True

        for tag in other_type.micro_op_types.keys():
            if len(tag) == 2 and tag[0] == "set":
                detail_setter = other_type.get_micro_op_type(("set", tag[1]))
                if detail_setter and not self.value_type.is_copyable_from(detail_setter.value_type):
                    return True

        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        if key_filter is not None:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(key_filter):
                return ([ target._get(key_filter) ], self.value_type)
            return ([], None)
        return (target._values(), self.value_type)

    def merge(self, other_micro_op_type):
        return IterMicroOpType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub")
        )

    def clone(self):
        return IterMicroOpType(self.value_type, self.key_type, self.key_error)


def UniversalObjectType(properties, wildcard_type=None, has_default_factory=False, name=None):
    micro_ops = {}

    for name, type in properties.items():
        const = False
        if isinstance(type, Const):
            const = True
            type = type.wrapped

        if not isinstance(name, basestring):
            raise FatalError()
        if not isinstance(type, Type):
            raise FatalError()

        micro_ops[("get", name)] = GetterMicroOpType(name, type)
        if not const:
            micro_ops[("set", name)] = SetterMicroOpType(name, type)

    if wildcard_type:
        micro_ops[("get-wildcard",)] = GetterWildcardMicroOpType(StringType(), wildcard_type, not has_default_factory)
        micro_ops[("set-wildcard",)] = SetterWildcardMicroOpType(StringType(), wildcard_type, False, True)

    if name is None:
        name = "UniversalObjectType"

    return CompositeType(micro_ops, name)


def UniversalTupleType(properties, name=None):
    micro_ops = {}

    for index, type in enumerate(properties):
        const = False
        if isinstance(type, Const):
            const = True
            type = type.wrapped

        if not isinstance(index, int):
            raise FatalError()
        if not isinstance(type, Type):
            raise FatalError()

        micro_ops[("get", index)] = GetterMicroOpType(index, type)
        if not const:
            micro_ops[("set", index)] = SetterMicroOpType(index, type)

    if name is None:
        name = "UniversalObjectType"

    return CompositeType(micro_ops, name)


def UniversalListType(child_type, is_sparse=False, name=None):
    micro_ops = {}

    micro_ops[("get-wildcard",)] = GetterWildcardMicroOpType(IntegerType(), child_type, True)
    micro_ops[("set-wildcard",)] = SetterWildcardMicroOpType(IntegerType(), child_type, not is_sparse, False)
    micro_ops[("remove-wildcard",)] = RemoverWildcardMicroOpType(IntegerType(), True)
    micro_ops[("insert-wildcard",)] = InserterWildcardMicroOpType(IntegerType(), not is_sparse, False)
    micro_ops[("insert-start",)] = InsertStartMicroOpType(child_type, False)
    micro_ops[("insert-end",)] = InsertEndMicroOpType(child_type, False)
    micro_ops[("iter",)] = IterMicroOpType(child_type)

    if is_sparse:
        micro_ops[("delete-wildcard",)] = DeletterWildcardMicroOpType(IntegerType(), True)

    if name is None:
        name = "UniversalListType"

    return CompositeType(micro_ops, name)


def UniversalDictType(key_type, value_type, name=None):
    micro_ops = {}

    micro_ops[("get-wildcard",)] = GetterWildcardMicroOpType(key_type, value_type, True)
    micro_ops[("set-wildcard",)] = SetterWildcardMicroOpType(key_type, value_type, False, False)
    micro_ops[("delete-wildcard",)] = DeletterWildcardMicroOpType(key_type, True)

    if name is None:
        name = "UniversalDictType"

    return CompositeType(micro_ops, name)


DEFAULT_READONLY_COMPOSITE_TYPE = CompositeType({}, "DefaultReadonlyUniversalType")

RICH_TYPE = OneOfType([ AnyType(), DEFAULT_READONLY_COMPOSITE_TYPE ])

DEFAULT_READONLY_COMPOSITE_TYPE.micro_op_types[("get-wildcard",)] = GetterWildcardMicroOpType(OneOfType([ StringType(), IntegerType() ]), RICH_TYPE, True)

EMPTY_COMPOSITE_TYPE = CompositeType({}, "EmptyCompositeType")
