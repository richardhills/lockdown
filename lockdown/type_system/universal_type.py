# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from UserDict import DictMixin
from _abcoll import MutableSequence

from lockdown.type_system.composites import Composite, CompositeType, \
    does_value_fit_through_type, unbind_key, bind_key,\
    can_add_composite_type_with_filter
from lockdown.type_system.core_types import merge_types, Const, Type, StringType, \
    IntegerType, OneOfType, AnyType
from lockdown.type_system.exceptions import FatalError, MissingMicroOp, \
    InvalidAssignmentKey, InvalidAssignmentType, InvalidDereferenceKey, \
    raise_if_safe
from lockdown.type_system.managers import get_manager
from lockdown.type_system.micro_ops import MicroOpType
from lockdown.utils import MISSING, default
from __builtin__ import True


SPARSE_ELEMENT = object()


class Universal(Composite):
    def __init__(self, is_sparse, default_factory=None, bind=None, debug_reason=None, initial_wrapped=None, initial_length=0):
        self.wrapped = initial_wrapped or {}

        manager = get_manager(self, "Universal")

        manager.default_factory = default_factory
        manager.is_sparse = is_sparse
        manager.debug_reason = debug_reason

        self._length = initial_length

        if bind:
            manager.add_composite_type(bind)

    def _set(self, key, value):
        manager = get_manager(self)

        if isinstance(key, int) and not manager.is_sparse and not self._is_key_within_range(key):
            raise IndexError()

        self.wrapped[key] = value

        if isinstance(key, int):
            self._length = max(self._length, key + 1)

    def _get(self, key):
        manager = get_manager(self)

        if key in self.wrapped:
            return self.wrapped[key]

        if isinstance(key, int) and manager.is_sparse and self._is_key_within_range(key):
            return SPARSE_ELEMENT

        raise IndexError()

    def _is_key_within_range(self, key, for_insert=False):
        if for_insert:
            return 0 <= key <= self._length
        else:
            return 0 <= key < self._length

    def _delete(self, key):
        manager = get_manager(self)

        if not manager.is_sparse:
            raise FatalError()

        if isinstance(key, int) and not self._is_key_within_range(key):
            raise KeyError()

        del self.wrapped[key]

    def _remove(self, key):
        if not isinstance(key, int):
            raise FatalError()

        if not self._is_key_within_range(key):
            raise KeyError()

        del self.wrapped[key]

        keys_above_key = sorted([k for k in self.wrapped.keys() if isinstance(k, int) and k > key])
        for k in keys_above_key:
            self.wrapped[k - 1] = self.wrapped.pop(k)
        self._length -= 1

    def _insert(self, key, value):
        if not isinstance(key, int):
            raise FatalError()

        manager = get_manager(self)

        if not manager.is_sparse and not self._is_key_within_range(key, for_insert=True):
            raise KeyError()

        keys_above_key = reversed(sorted([k for k in self.wrapped.keys() if isinstance(k, int) and k >= key]))
        for k in keys_above_key:
            self.wrapped[k + 1] = self.wrapped.pop(k)
        self.wrapped[key] = value
        self._length = max(self._length + 1, key + 1)

    def _contains(self, key):
        manager = get_manager(self)

        if isinstance(key, int) and manager.is_sparse:
            return 0 <= key < self._length

        return key in self.wrapped

    def _keys(self):
        manager = get_manager(self)

        if manager.is_sparse:
            for i in self._range():
                yield i

        for k in self.wrapped.keys():
            if not (manager.is_sparse and isinstance(k, int)):
                yield k

    def _values(self):
        for k in self._keys():
            yield self._get(k)

    def _range(self):
        return range(self._length)

    def _to_list(self):
        return [
            self._get(i) for i in self._range()
        ]

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
            if key in ("wrapped", "_length"):
                return super(PythonObject, self).__setattr__(key, value)

            manager = get_manager(self, "PythonObject.__setattr__")

            micro_op_type = manager.get_micro_op_type(("set", key))
            if micro_op_type is not None:
                if not does_value_fit_through_type(value, micro_op_type.value_type):
                    raise TypeError()

                micro_op_type.invoke(manager, value, allow_failure=True)
            else:
                micro_op_type = manager.get_micro_op_type(("set-wildcard",))
    
                if micro_op_type is None:
                    raise MissingMicroOp()

                if not does_value_fit_through_type(value, micro_op_type.value_type):
                    raise TypeError()

                micro_op_type.invoke(manager, key, value, allow_failure=True)
        except (InvalidAssignmentKey, MissingMicroOp):
            raise AttributeError(key)
        except InvalidAssignmentType:
            raise TypeError()

    def __getattribute__(self, key):
        if key in ("__dict__", "__class__", "_contains", "_get", "_set", "_delete", "_keys", "_values", "wrapped", "_length", "_is_key_within_range", "_range"):
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

        micro_op_type = manager.get_micro_op_type(("delete-wildcard",))

        if micro_op_type is None:
            raise MissingMicroOp()

        return micro_op_type.invoke(manager, key)


class PythonList(Universal, MutableSequence):
    def __init__(self, initial_data, is_sparse=False, **kwargs):
        initial_wrapped = {}
        for index, value in enumerate(initial_data):
            initial_wrapped[index] = value
        initial_length = len(initial_data)

        super(PythonList, self).__init__(is_sparse, initial_wrapped=initial_wrapped, initial_length=initial_length, **kwargs)

    def append(self, new_value):
        try:
            manager = get_manager(self)

            micro_op_type = manager.get_micro_op_type(("insert-end",))

            if micro_op_type is not None:
                return micro_op_type.invoke(manager, new_value)

            self.insert(self._length, new_value)
        except MissingMicroOp:
            raise IndexError()
        except InvalidAssignmentType:
            raise TypeError()

    def insert(self, index, element):
        try:
            manager = get_manager(self)

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
                if not does_value_fit_through_type(value, micro_op_type.value_type):
                    raise TypeError()

                micro_op_type.invoke(manager, value, allow_failure=True)
            else:
                micro_op_type = manager.get_micro_op_type(("set-wildcard",))

                if micro_op_type is None:
                    raise MissingMicroOp()

                if not does_value_fit_through_type(value, micro_op_type.value_type):
                    raise TypeError()
    
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
            raise IndexError()
        except MissingMicroOp:
            raise IndexError()

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
        except InvalidDereferenceKey:
            raise IndexError()
        except MissingMicroOp:
            raise IndexError()

    def __len__(self):
        return self._length


class PythonDict(Universal, DictMixin, object):
    def __init__(self, initial_data, **kwargs):
        initial_wrapped = {}
        for key, value in initial_data.items():
            if value is MISSING:
                raise FatalError()
            initial_wrapped[key] = value

        super(PythonDict, self).__init__(True, initial_wrapped=initial_wrapped, *kwargs)

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
        try:
            obj = target_manager.get_obj()
            if self.key in obj._keys():
                value = obj._get(self.key)
            else:
                default_factory = target_manager.default_factory
                value = default_factory(target_manager, self.key)

            return value
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get", self.key))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not self.would_be_bindable_to(manager, self.key):
            return False

        return True

    def would_be_bindable_to(self, manager, key):
        return manager.get_obj()._contains(key) or manager.default_factory

    def conflicts_with(self, our_type, other_type):
        wildcard_insert = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_insert and not wildcard_insert.type_error and not self.value_type.is_copyable_from(wildcard_insert.value_type):
            return True

        insert_first = other_type.get_micro_op_type(("insert-first",))
        if insert_first and not insert_first.type_error and not self.value_type.is_copyable_from(insert_first.value_type):
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
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
        )

    def clone(self, value_type=MISSING):
        return GetterMicroOpType(
            self.key,
            default(value_type, self.value_type)
        )


class SetterMicroOpType(MicroOpType):
    key_error = False
    type_error = False

    def __init__(self, key, value_type):
        self.key = key
        self.value_type = value_type

    def invoke(self, target_manager, value, *args, **kwargs):
        try:
            unbind_key(target_manager, self.key)

            obj = target_manager.get_obj()
            obj._set(self.key, value)

            bind_key(target_manager, self.key)
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set", self.key))
        return (
            other_micro_op_type
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def is_bindable_to(self, our_type, target):
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
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super")
        )

    def clone(self, value_type=MISSING):
        return SetterMicroOpType(
            self.key,
            default(value_type, self.value_type)
        )


class InsertStartMicroOpType(MicroOpType):
    key_error = False

    def __init__(self, value_type, type_error):
        self.value_type = value_type
        self.type_error = type_error

    def invoke(self, target_manager, new_value, *args, **kwargs):
        try:
            obj = target_manager.get_obj()

            if self.type_error:
                target_type = target_manager.get_effective_composite_type()

                if not can_add_composite_type_with_filter(
                    obj, target_type, 0, new_value
                ):
                    raise InvalidAssignmentType()

                for i in obj._range():
                    if not can_add_composite_type_with_filter(
                        obj, target_type, i, obj._get(i - 1)
                    ):
                        raise InvalidAssignmentType()

            for i in obj._range():
                unbind_key(target_manager, i)

            obj = target_manager.get_obj()
            obj._insert(0, new_value)

            for i in obj._range():
                bind_key(target_manager, i)
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert-start",))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        # Check that future left shifts are safe
        for getter in our_type.micro_op_types.values():
            if isinstance(getter, GetterMicroOpType):
                for i in range(getter.key, target._length):
                    if not getter.would_be_bindable_to(manager, i):
                        return False

        return True

    def conflicts_with(self, our_type, other_type):
        if not self.type_error:
            wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
            if wildcard_getter and not wildcard_getter.value_type.is_copyable_from(self.value_type):
                return True

            for tag, possible_detail_getter in other_type.micro_op_types.items():
                if len(tag) == 2 and tag[0] == "get":
                    if not possible_detail_getter.value_type.is_copyable_from(self.value_type):
                        return True

        return False

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
        try:
            if not does_value_fit_through_type(new_value, self.value_type):
                raise InvalidAssignmentType()

            obj = target_manager.get_obj()
            obj._insert(obj._length, new_value)
            bind_key(target_manager, obj._length)
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert-end",))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, our_type, target):
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
        try:
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
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get-wildcard",))
        return (
            other_micro_op_type
            and other_micro_op_type.key_type.is_copyable_from(self.key_type)
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (self.key_error or manager.default_factory):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        # We ignore Deletters and Removers because they either:
        # 1. Throw a KeyError
        # 2. Don't throw a KeyError and have a DefaultFactory
        wildcard_insert = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_insert and not wildcard_insert.type_error and not self.value_type.is_copyable_from(wildcard_insert.value_type):
            return True

        insert_first = other_type.get_micro_op_type(("insert-first",))
        if insert_first and not insert_first.type_error and not self.value_type.is_copyable_from(insert_first.value_type):
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

    def clone(self, value_type=MISSING, key_error=MISSING):
        return GetterWildcardMicroOpType(
            self.key_type,
            default(value_type, self.value_type),
            default(key_error, self.key_error)
        )


class SetterWildcardMicroOpType(MicroOpType):
    def __init__(self, key_type, value_type, key_error, type_error):
        self.key_type = key_type
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, *args, **kwargs):
        try:
            if not does_value_fit_through_type(new_value, self.value_type):
                raise InvalidAssignmentType()

            unbind_key(target_manager, key)

            obj = target_manager.get_obj()
            obj._set(key, new_value)

            bind_key(target_manager, key)
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("set-wildcard",))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error) 
            and (not other_micro_op_type.type_error or self.type_error) 
            and other_micro_op_type.key_type.is_copyable_from(self.key_type)
            and other_micro_op_type.value_type.is_copyable_from(self.value_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        if not self.type_error:
            wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
            if wildcard_getter and not wildcard_getter.value_type.is_copyable_from(self.value_type):
                return True

            for tag, possible_detail_getter in other_type.micro_op_types.items():
                if len(tag) == 2 and tag[0] == "get":
                    if not possible_detail_getter.value_type.is_copyable_from(self.value_type):
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

    def clone(self, value_type=MISSING, key_error=MISSING, type_error=MISSING):
        return SetterWildcardMicroOpType(
            self.key_type,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            default(type_error, self.type_error)
        )


class DeletterWildcardMicroOpType(MicroOpType):
    def __init__(self, key_type, key_error):
        self.key_type = key_type
        self.key_error = key_error

    def invoke(self, target_manager, key, *args, **kwargs):
        try:
            unbind_key(target_manager, key)

            obj = target_manager.get_obj()
            obj._delete(key)
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("delete-wildcard",))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error) 
            and other_micro_op_type.key_type.is_copyable_from(self.key_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (self.key_error or manager.default_factory):
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        # We ignore other Getters because:
        # 1. If we generate KeyErrors, having Getters (which don't throw key errors)
        # 2. If we don't generate KeyErrors, we've got to have a DefaultFactory, so Getters are safe
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
    def __init__(self, key_type, key_error, type_error):
        self.key_type = key_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, *args, **kwargs): 
        try:
            obj = target_manager.get_obj()

            if self.type_error:
                target_type = target_manager.get_effective_composite_type()
                for i in range(key, self._length - 1):
                    if not can_add_composite_type_with_filter(
                        obj, target_type, i, obj._get(i + 1)
                    ):
                        raise InvalidAssignmentType()

            for i in range(key, obj._length):
                unbind_key(target_manager, i)

            obj._remove(key)

            for i in range(key, obj._length):
                bind_key(target_manager, i)
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("remove-wildcard",))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error) 
            and other_micro_op_type.key_type.is_copyable_from(self.key_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        if not (self.key_error or manager.default_factory):
            return False

        # Check that future right shifts are safe
        for getter in our_type.micro_op_types.values():
            if isinstance(getter, GetterMicroOpType):
                for i in range(getter.key, target._length):
                    if not getter.would_be_bindable_to(manager, i):
                        return False

        return True

    def conflicts_with(self, our_type, other_type):
        return False

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return RemoverWildcardMicroOpType(
            merge_types([ self.key_type, other_micro_op_type.key_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def clone(self):
        return RemoverWildcardMicroOpType(self.key_type, self.key_error)


class InserterWildcardMicroOpType(MicroOpType):
    def __init__(self, value_type, key_error, type_error):
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, *args, **kwargs):
        try:
            obj = target_manager.get_obj()

            if self.type_error:
                target_type = target_manager.get_effective_composite_type()

                if not can_add_composite_type_with_filter(
                    obj, target_type, key, new_value
                ):
                    raise InvalidAssignmentType()

                for i in range(key + 1, obj._length):
                    if not can_add_composite_type_with_filter(
                        obj, target_type, i, obj._get(i - 1)
                    ):
                        raise InvalidAssignmentType()

            for i in range(key, obj._length):
                unbind_key(target_manager, i)

            obj._insert(key, new_value)

            for i in range(key, obj._length):
                bind_key(target_manager, i)
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("insert-wildcard",))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error) 
            and (not other_micro_op_type.type_error or self.type_error) 
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        # Check that future right shifts are safe
        for getter in our_type.micro_op_types.values():
            if isinstance(getter, GetterMicroOpType):
                for i in range(0, getter.key):
                    if not getter.would_be_bindable_to(manager, i):
                        return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
        if wildcard_getter and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        if not self.type_error:
            for tag, getter in other_type.micro_op_types.items():
                if len(tag) == 2 and tag[0] == "get":
                    if not getter.value_type.is_copyable_from(self.value_type):
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
        try:
            obj = target_manager.get_obj()
            for v in obj._values():
                yield v
        except KeyError:
            raise FatalError()
        except TypeError:
            raise FatalError()

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("iter",))
        return (
            other_micro_op_type
            and self.value_type.is_copyable_from(other_micro_op_type.value_type)
        )

    def is_bindable_to(self, our_type, target):
        manager = get_manager(target)
        if not isinstance(target, Universal):
            return False
        if not manager:
            return False

        return True

    def conflicts_with(self, our_type, other_type):
        wildcard_insert = other_type.get_micro_op_type(("insert-wildcard",))
        if wildcard_insert and not wildcard_insert.type_error and not self.value_type.is_copyable_from(wildcard_insert.value_type):
            return True

        insert_first = other_type.get_micro_op_type(("insert-first",))
        if insert_first and not insert_first.type_error and not self.value_type.is_copyable_from(insert_first.value_type):
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
    is_const = False

    if isinstance(child_type, Const):
        is_const = True
        child_type = child_type.wrapped

    if not isinstance(child_type, Type):
        raise FatalError()

    micro_ops[("get-wildcard",)] = GetterWildcardMicroOpType(IntegerType(), child_type, True)
    micro_ops[("iter",)] = IterMicroOpType(child_type)

    if not is_const:
        micro_ops[("set-wildcard",)] = SetterWildcardMicroOpType(IntegerType(), child_type, not is_sparse, False)
        micro_ops[("remove-wildcard",)] = RemoverWildcardMicroOpType(IntegerType(), True, False)
        micro_ops[("insert-wildcard",)] = InserterWildcardMicroOpType(IntegerType(), not is_sparse, False)
        micro_ops[("insert-start",)] = InsertStartMicroOpType(child_type, False)
        micro_ops[("insert-end",)] = InsertEndMicroOpType(child_type, False)

    if is_sparse and not is_const:
        micro_ops[("delete-wildcard",)] = DeletterWildcardMicroOpType(IntegerType(), True)

    if name is None:
        name = "UniversalListType"

    return CompositeType(micro_ops, name)

def UniversalLupleType(properties, element_type, is_sparse=False, name=None):
    micro_ops = {}

    if isinstance(element_type, Const):
        const = True
        element_type = element_type.wrapped

    if not isinstance(element_type, Type):
        raise FatalError()

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

    micro_ops[("get-wildcard",)] = GetterWildcardMicroOpType(IntegerType(), element_type, True)
    micro_ops[("set-wildcard",)] = SetterWildcardMicroOpType(IntegerType(), element_type, not is_sparse, True)
    micro_ops[("remove-wildcard",)] = RemoverWildcardMicroOpType(IntegerType(), True, True)
    micro_ops[("insert-wildcard",)] = InserterWildcardMicroOpType(IntegerType(), not is_sparse, True)
    micro_ops[("insert-end",)] = InsertEndMicroOpType(element_type, True)
    micro_ops[("iter",)] = IterMicroOpType(element_type)

    if is_sparse:
        micro_ops[("delete-wildcard",)] = DeletterWildcardMicroOpType(IntegerType(), True)

    if name is None:
        name = "UniversalObjectType"

    return CompositeType(micro_ops, name)


def UniversalDictType(key_type, value_type, name=None):
    micro_ops = {}

    micro_ops[("get-wildcard",)] = GetterWildcardMicroOpType(key_type, value_type, True)
    micro_ops[("set-wildcard",)] = SetterWildcardMicroOpType(key_type, value_type, False, False)
    micro_ops[("delete-wildcard",)] = DeletterWildcardMicroOpType(key_type, True)

    if name is None:
        name = "UniversalDictType"

    return CompositeType(micro_ops, name)

def UniversalDefaultDictType(key_type, value_type, name=None):
    micro_ops = {}

    micro_ops[("get-wildcard",)] = GetterWildcardMicroOpType(key_type, value_type, False)
    micro_ops[("set-wildcard",)] = SetterWildcardMicroOpType(key_type, value_type, False, False)
    micro_ops[("delete-wildcard",)] = DeletterWildcardMicroOpType(key_type, False)

    if name is None:
        name = "UniversalDefaultDictType"

    return CompositeType(micro_ops, name)

EMPTY_COMPOSITE_TYPE = CompositeType({}, "EmptyCompositeType")

DEFAULT_READONLY_COMPOSITE_TYPE = CompositeType({}, "DefaultReadonlyUniversalType")
RICH_READONLY_TYPE = OneOfType([ AnyType(), DEFAULT_READONLY_COMPOSITE_TYPE ])
DEFAULT_READONLY_COMPOSITE_TYPE.micro_op_types[("get-wildcard",)] = GetterWildcardMicroOpType(OneOfType([ StringType(), IntegerType() ]), RICH_READONLY_TYPE, True)

DEFAULT_COMPOSITE_TYPE = CompositeType({}, "DefaultUniversalType")
RICH_TYPE = OneOfType([ AnyType(), DEFAULT_COMPOSITE_TYPE ])
DEFAULT_COMPOSITE_TYPE.micro_op_types[("get-wildcard",)] = GetterWildcardMicroOpType(OneOfType([ StringType(), IntegerType() ]), RICH_TYPE, True)
DEFAULT_COMPOSITE_TYPE.micro_op_types[("set-wildcard",)] = SetterWildcardMicroOpType(OneOfType([ StringType(), IntegerType() ]), RICH_TYPE, True, True)
DEFAULT_COMPOSITE_TYPE.micro_op_types[("delete-wildcard",)] = DeletterWildcardMicroOpType(OneOfType([ StringType(), IntegerType() ]), True)

# A Type that you can always set values on without any errors
# Similar to how a standard unsafe Python Object works
NO_SETTER_ERROR_COMPOSITE_TYPE = CompositeType({}, "NoSetterError")
NO_SETTER_ERROR_TYPE = OneOfType([ AnyType(), NO_SETTER_ERROR_COMPOSITE_TYPE ])
NO_SETTER_ERROR_COMPOSITE_TYPE.micro_op_types[("get-wildcard",)] = GetterWildcardMicroOpType(OneOfType([ StringType(), IntegerType() ]), NO_SETTER_ERROR_TYPE, True)
NO_SETTER_ERROR_COMPOSITE_TYPE.micro_op_types[("set-wildcard",)] = SetterWildcardMicroOpType(OneOfType([ StringType(), IntegerType() ]), NO_SETTER_ERROR_TYPE, False, False)

