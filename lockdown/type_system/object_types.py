# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from lockdown.executor.ast_utils import compile_statement, compile_expression
from lockdown.type_system.composites import CompositeType, \
    Composite, unbind_key, bind_key, can_add_composite_type_with_filter, \
    does_value_fit_through_type
from lockdown.type_system.core_types import merge_types, Type, Const, OneOfType, \
    AnyType, StringType, NoValueType
from lockdown.type_system.exceptions import FatalError, raise_if_safe, \
    InvalidDereferenceKey, InvalidDereferenceType, \
    InvalidAssignmentType, MissingMicroOp, InvalidAssignmentKey
from lockdown.type_system.managers import get_manager, get_type_of_value
from lockdown.type_system.micro_ops import MicroOpType
from lockdown.utils import is_debug, MISSING, micro_op_repr, \
    runtime_type_information, default


class ObjectWildcardGetterType(MicroOpType):
    __slots__ = [ "key_type", "value_type", "key_error", "type_error" ]

    def __init__(self, key_type, value_type, key_error, type_error):
        if value_type is None:
            raise FatalError()
        if isinstance(value_type, NoValueType):
            raise FatalError()
        if not runtime_type_information() and type_error:
            raise FatalError()
        self.key_type = key_type
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, allow_failure)

        if is_debug() and not self.key_type.is_copyable_from(get_type_of_value(key)):
            raise FatalError()

        obj = target_manager.get_obj()

        if obj._contains(key):
            value = obj._get(key)
        else:
            default_factory = target_manager.default_factory

            if not default_factory:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

            value = default_factory(target_manager, key)

        if is_debug() or self.type_error:
            if not does_value_fit_through_type(value, self.value_type):
                raise raise_if_safe(InvalidDereferenceType, self.type_error)

        return value

    def raise_micro_op_invocation_conflicts(self, target_manager, key, allow_failure):
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
        if not isinstance(target, RDHObject):
            return False
        if not manager:
            return False

        if not (manager.default_factory or self.key_error):
            return False

        for key in target._keys():
            if not self.key_type.is_copyable_from(get_type_of_value(key)):
                return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        if key_filter is not None:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(key_filter):
                return ([ target._get(key_filter) ], self.value_type)
            return ([], None)
        return (target._values(), self.value_type)

    def clone(self, value_type=MISSING, key_error=MISSING, type_error=MISSING):
        return ObjectWildcardGetterType(
            self.key_type,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            default(type_error, self.type_error)
        )

    def merge(self, other_micro_op_type):
        return ObjectWildcardGetterType(
            self.key_type,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("getO", "*", self.key_error, self.value_type, self.type_error)

class ObjectGetterType(MicroOpType):
    __slots__ = [ "key", "value_type", "key_error", "type_error" ]

    def __init__(self, key, value_type, key_error, type_error):
        if value_type is None or not isinstance(value_type, Type):
            raise FatalError()
        if isinstance(value_type, NoValueType):
            raise FatalError()
        if not isinstance(key, (basestring, int)):
            raise FatalError()
        if not runtime_type_information() and type_error:
            raise FatalError()
        self.key = key
        self.key_type = get_type_of_value(key)
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, **kwargs):
        if is_debug() or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager)

        if self.key in target_manager.get_obj()._keys():
            value = target_manager.get_obj()._get(self.key)
        else:
            default_factory = target_manager.default_factory

            if not default_factory:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

            value = default_factory(target_manager, self.key)

        if is_debug() or self.type_error:
            if not does_value_fit_through_type(value, self.value_type):
                raise raise_if_safe(InvalidDereferenceType, self.type_error)

        return value

    def raise_micro_op_invocation_conflicts(self, target_manager):
        pass

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("get", self.key))
        return (
            other_micro_op_type
            and (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
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
        if not isinstance(target, RDHObject):
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

    def clone(self, value_type=None):
        return ObjectGetterType(self.key, value_type, self.key_error, self.type_error)

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return ObjectGetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def to_ast(self, dependency_builder, target):
        if runtime_type_information() or self.type_error or self.key_error:
            return super(ObjectGetterType, self).to_ast(dependency_builder, target)
        return compile_expression(
            "{target}.__dict__[\"{key}\"]",
            None, dependency_builder, target=target, key=self.key
        )

    def __repr__(self):
        return micro_op_repr("getO", self.key, self.key_error, self.value_type, self.type_error)

class ObjectWildcardSetterType(MicroOpType):
    __slots__ = [ "key_type", "value_type", "key_error", "type_error" ]

    def __init__(self, key_type, value_type, key_error, type_error):
        if isinstance(value_type, NoValueType):
            raise FatalError()
        if not runtime_type_information() and type_error:
            raise FatalError()
        self.key_type = key_type
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, new_value, allow_failure)

        unbind_key(target_manager, key)

        target_manager.get_obj()._set(key, new_value)

        bind_key(target_manager, key)

    def raise_micro_op_invocation_conflicts(self, target_manager, key, new_value, allow_failure):
        target_type = target_manager.get_effective_composite_type()
        if not can_add_composite_type_with_filter(target_manager.get_obj(), target_type, key, new_value):
            raise_if_safe(InvalidAssignmentType, self.type_error or allow_failure)

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
        if not isinstance(target, RDHObject):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def clone(self, value_type=MISSING, key_error=MISSING, type_error=MISSING):
        return ObjectWildcardSetterType(
            self.key_type,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            default(type_error, self.type_error)
        )

    def merge(self, other_micro_op_type):
        return ObjectWildcardSetterType(
            self.key_error,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("setO", "*", self.key_error, self.value_type, self.type_error)

class ObjectSetterType(MicroOpType):
    __slots__ = [ "key", "value_type", "key_error", "type_error" ]

    def __init__(self, key, value_type, key_error, type_error):
        if value_type is None or not isinstance(value_type, Type):
            raise FatalError()
        if isinstance(value_type, NoValueType):
            raise FatalError()
        if not isinstance(key, (basestring, int)):
            raise FatalError()
        if not runtime_type_information() and type_error:
            raise FatalError()
        self.key = key
        self.value_type = value_type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, new_value, allow_failure)

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
        wildcard_getter = other_type.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter and not self.type_error and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(self.value_type):
            return True

        detail_getter = other_type.get_micro_op_type(("get", self.key))
        if detail_getter and not self.type_error and not detail_getter.type_error and not detail_getter.value_type.is_copyable_from(self.value_type):
            return True

        return False

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHObject):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def clone(self, value_type=None):
        return ObjectSetterType(self.key, value_type, self.key_error, self.type_error)

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return ObjectSetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def to_ast(self, dependency_builder, target, new_value):
        if runtime_type_information() or self.type_error or self.key_error:
            return super(ObjectSetterType, self).to_ast(dependency_builder, target, new_value)
        return compile_statement(
            "{target}.__dict__[\"{key}\"] = {rvalue}",
            None, dependency_builder,
            target=target, key=self.key, rvalue=new_value
        )

    def __repr__(self):
        return micro_op_repr("setO", self.key, self.key_error, self.value_type, self.type_error)


class InvalidDeletion(Exception):
    pass


class ObjectWildcardDeletterType(MicroOpType):
    __slots__ = [ "key_error" ]

    def __init__(self, key_error):
        self.key_error = key_error

    def invoke(self, target_manager, key, **kwargs):
        if is_debug() or self.key_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key)

        unbind_key(target_manager, key)

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
        if not isinstance(target, RDHObject):
            return False
        if not manager:
            return False

        if not (manager.default_factory or self.key_error):
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return ObjectWildcardDeletterType(
            self.key_error or other_micro_op_type.key_error
        )

class ObjectDeletterType(MicroOpType):
    __slots__ = [ "key", "key_error" ]

    def __init__(self, key, key_error):
        self.key = key
        self.key_error = key_error

    def invoke(self, target_manager, **kwargs):
        if self.key_error:
            self.raise_micro_op_invocation_conflicts(target_manager)

        unbind_key(target_manager, self.key)

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
        if not isinstance(target, RDHObject):
            return False
        if not manager:
            return False

        if not (manager.default_factory or self.key_error):
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

    def merge(self, other_micro_op_type):
        return ObjectDeletterType(self.key, self.key_error or other_micro_op_type.key_error)

def RDHObjectType(properties=None, wildcard_key_type=None, wildcard_value_type=None, **kwargs):
    raise ValueError()
    if not properties:
        properties = {}
    if not wildcard_key_type:
        wildcard_key_type = StringType()
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

        if not isinstance(type, NoValueType):
            micro_ops[("get", name)] = ObjectGetterType(name, type, False, False)
            if not const:
                micro_ops[("set", name)] = ObjectSetterType(name, type, False, False)

    if wildcard_value_type:
        micro_ops[("get-wildcard",)] = ObjectWildcardGetterType(wildcard_key_type, wildcard_value_type, True, False)
        micro_ops[("set-wildcard",)] = ObjectWildcardSetterType(wildcard_key_type, wildcard_value_type, True, True)

#        micro_ops[("get", "get")] = BuiltInFunctionGetterType(ObjectGetFunctionType(micro_ops[("get-wildcard",)]))

    if "name" not in kwargs:
        kwargs["name"] = "RDHObjectType"

    return CompositeType(micro_ops, **kwargs)

class PythonObjectType(CompositeType):
    def __init__(self, **kwargs):
        micro_ops = {}

        micro_ops[("get-wildcard",)] = ObjectWildcardGetterType(StringType(), OneOfType([ self, AnyType() ]), True, False)
        micro_ops[("set-wildcard",)] = ObjectWildcardSetterType(StringType(), OneOfType([ self, AnyType() ]), False, False)
        micro_ops[("delete-wildcard",)] = ObjectWildcardDeletterType(True)

        super(PythonObjectType, self).__init__(micro_ops, **kwargs)

class DefaultDictType(CompositeType):
    def __init__(self, type, **kwargs):
        micro_ops = {}

        micro_ops[("get-wildcard",)] = ObjectWildcardGetterType(StringType(), type, False, False)
        micro_ops[("set-wildcard",)] = ObjectWildcardSetterType(StringType(), type, False, False)
        micro_ops[("delete-wildcard",)] = ObjectWildcardDeletterType(False)

        super(DefaultDictType, self).__init__(micro_ops, **kwargs)

class RDHObject(Composite, object):
    def __init__(self, initial_data=None, default_factory=None, is_sparse=True, bind=None, debug_reason=None):
        raise ValueError()
        if initial_data is None:
            initial_data = {}
        for key, value in initial_data.items():
            if value is MISSING:
                raise FatalError()
            self.__dict__[key] = value
        manager = get_manager(self, "RDHObject")
        manager.default_factory = default_factory
        manager.debug_reason = debug_reason
        if bind:
            manager.add_composite_type(bind)

    def _get(self, key):
        if key in self.__dict__:
            return self.__dict__[key]
        raise AttributeError()

    def _set(self, key, value):
        self.__dict__[key] = value

    def _delete(self, key):
        del self.__dict__[key]

    def _contains(self, key):
        return key in self.__dict__

    def _keys(self):
        return self.__dict__.keys()

    def _values(self):
        return self.__dict__.values()

    def __setattr__(self, key, value):
        try:
            manager = get_manager(self, "RDHObject.__setattr__")

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
        if key in ("__dict__", "__class__", "_contains", "_get", "_set", "_delete", "_keys", "_values"):
            return super(RDHObject, self).__getattribute__(key)

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

    def __repr__(self):
        return repr(self.__dict__)

    def __str__(self):
        return str(self.__dict__)
