from UserDict import DictMixin

from rdhlang5.type_system.composites import InferredType, CompositeType, \
    Composite, unbind_key, bind_key
from rdhlang5.type_system.core_types import Type, merge_types
from rdhlang5.type_system.exceptions import FatalError, raise_if_safe, \
    InvalidDereferenceKey, InvalidDereferenceType, InvalidAssignmentType, \
    InvalidAssignmentKey, MissingMicroOp
from rdhlang5.type_system.managers import get_manager, get_type_of_value
from rdhlang5.type_system.micro_ops import MicroOpType
from rdhlang5.utils import MISSING, is_debug


WILDCARD = object()


def get_key_and_type(micro_op_type):
    if isinstance(micro_op_type, (DictWildcardGetterType, DictWildcardSetterType, DictWildcardDeletterType)):
        key = WILDCARD
    elif isinstance(micro_op_type, (DictGetterType, DictSetterType, DictDeletterType)):
        key = micro_op_type.key
    else:
        raise FatalError()

    if isinstance(micro_op_type, (DictWildcardGetterType, DictGetterType, DictWildcardSetterType, DictSetterType)):
        type = micro_op_type.type
    else:
        type = MISSING

    return key, type


def get_key_and_new_value(micro_op, args):
    if isinstance(micro_op, (DictWildcardGetter, DictWildcardDeletter)):
        key, = args
        new_value = MISSING
    elif isinstance(micro_op, (DictGetter, DictDeletter)):
        key = micro_op.key
        new_value = MISSING
    elif isinstance(micro_op, DictWildcardSetter):
        key, new_value = args
    elif isinstance(micro_op, DictSetter):
        key = micro_op.key
        new_value = args[0]
    else:
        raise FatalError()
    if new_value is not None:
        get_manager(new_value)
    return key, new_value


class DictMicroOpType(MicroOpType):
    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        if not isinstance(obj, RDHDict):
            raise IncorrectObjectTypeForMicroOp()
        return super(DictMicroOpType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_runtime_data_conflict(self, obj):
        if not isinstance(obj, RDHDict):
            return True


class DictWildcardGetterType(DictMicroOpType):
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
            type_of_value = get_type_of_value(value)
            if not self.value_type.is_copyable_from(type_of_value):
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

        # TODO: work out if the get-wildcard and delete-wildcard checks are necessary.
        # Another type with get-wildcard no key errors with a delete-wildcard with no key errors would be inconsistent
#         wildcard_getter = other_type.get_micro_op_type(("get-wildcard", ))
#         other_type_has_default_factory = wildcard_getter and not wildcard_getter.key_error
# 
#         wildcard_deletter = other_type.get_micro_op_type(("delete-wildcard", ))
#         if wildcard_deletter and not self.key_error and not wildcard_deletter.key_error and not other_type_has_default_factory:
#             return True

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
        if key_filter:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if target._contains(key_filter):
                return ([ target._get(key_filter) ], self.value_type)
            return ([], self.value_type)

        return (target._values(), self.value_type)

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, DictWildcardGetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return DictWildcardGetterType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

#     def bind(self, source_type, key, target_manager):
#         if key is not None:
#             keys = [ key ]
#         else:
#             keys = target_manager.get_obj().keys()
#         for k in keys:
#             bind_type_to_manager(target_manager, source_type, k, "key", self.key_type, get_manager(k))
#             value = target_manager.get_obj().wrapped[k]
#             bind_type_to_manager(target_manager, source_type, k, "value", self.value_type, get_manager(value))
# 
#     def unbind(self, source_type, key, target_manager):
#         if key is not None:
#             keys = [ key ]
#         else:
#             keys = target_manager.get_obj().wrapped.keys()
#         for k in keys:
#             unbind_type_to_manager(target_manager, source_type, k, "key", self.key_type, get_manager(k))
#             unbind_type_to_manager(target_manager, source_type, k, "value", get_manager(target_manager.get_obj().wrapped[k]))

#     def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
#         default_factory = micro_op_types.get(("default-factory",), None)
#         has_default_factory = default_factory is not None
# 
#         if not self.key_error:
#             if not has_default_factory:
#                 raise MicroOpTypeConflict()
#             if not self.value_type.is_copyable_from(default_factory.value_type):
#                 raise MicroOpTypeConflict()
# 
#         return super(DictWildcardGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)
# 
#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         has_default_factory = ("default-factory",) in other_micro_op_types
#         if not self.key_error:
#             if not has_default_factory:
#                 return True
# 
#         if isinstance(other_micro_op_type, (DictGetterType, DictWildcardGetterType)):
#             return False
#         if isinstance(other_micro_op_type, (DictSetterType, DictWildcardSetterType)):
#             if not self.type_error and not self.value_type.is_copyable_from(other_micro_op_type.value_type):
#                 return True
#         if isinstance(other_micro_op_type, (DictDeletterType, DictWildcardDeletterType)):
#             if not self.key_error and not has_default_factory:
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         if isinstance(other_micro_op, (DictSetter, DictWildcardSetter)):
#             _, new_value = get_key_and_new_value(other_micro_op, args)
#             if not self.type_error and not self.value_type.is_copyable_from(get_type_of_value(new_value)):
#                 raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
# 
#         if isinstance(other_micro_op, (DictDeletter, DictWildcardDeletter)):
#             if not self.key_error:
#                 raise_if_safe(InvalidAssignmentType, other_micro_op.key_error)
#         return False
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(DictWildcardGetterType, self).check_for_runtime_data_conflict(obj):
#             return True
#         if not self.key_error and get_manager(obj).default_factory is None:
#             return True
# 
#         if not self.type_error:
#             for value in obj.wrapped.values():
#                 get_manager(value)
#                 if isinstance(self.value_type, dict):
#                     pass
#                 if not self.value_type.is_copyable_from(get_type_of_value(value)):
#                     return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return DictWildcardGetterType(
            self.key_type,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


# class DictWildcardGetter(MicroOp):
# 
#     def __init__(self, target_manager, key_type, value_type, key_error, type_error):
#         target_manager = target_manager
#         self.key_type = key_type
#         self.value_type = value_type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, key, **kwargs):
#         raise_micro_op_conflicts(self, [ key ], target_manager.get_flattened_micro_op_types())
# 
#         if is_debug() and not self.key_type.is_copyable_from(get_type_of_value(key)):
#             raise FatalError()
# 
#         if key in target_manager.get_obj().wrapped:
#             value = target_manager.get_obj().__getitem__(key, raw=True)
#         else:
#             default_factory_op_type = target_manager.get_micro_op_type(("default-factory",))
# 
#             if not default_factory_op_type:
#                 raise_if_safe(InvalidDereferenceKey, self.key_error)
# 
#             default_factory_op = default_factory_op_type.create(target_manager)
#             value = default_factory_op.invoke(key)
# 
#         get_manager(value)
# 
#         type_of_value = get_type_of_value(value)
#         if not self.value_type.is_copyable_from(type_of_value):
#             raise raise_if_safe(InvalidDereferenceType, self.type_error)
#         return value


class DictGetterType(DictMicroOpType):
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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, DictGetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return DictGetterType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

#     def bind(self, source_type, key, target_manager):
#         if key is not None and key != self.key:
#             return
#         bind_type_to_manager(target_manager, source_type, self.key, "key", self.key_type, get_manager(key, "DictWildcardGetterType.bind"))
#         value = target_manager.get_obj().wrapped[self.key]
#         bind_type_to_manager(target_manager, source_type, self.key, "value", self.value_type, get_manager(value, "DictWildcardGetterType.bind"))
# 
#     def unbind(self, source_type, key, target_manager):
#         if key is not None and key != self.key:
#             return
#         unbind_type_to_manager(target_manager, source_type, self.key, "key", get_manager(key, "DictWildcardGetterType.bind"))
#         value = target_manager.get_obj().wrapped[key]
#         unbind_type_to_manager(target_manager, source_type, self.key, "value", get_manager(value))

#     def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
#         default_factory = micro_op_types.get(("default-factory",), None)
#         has_default_factory = default_factory is not None
#         has_value_in_place = self.key in obj.wrapped
# 
#         if not self.key_error and not has_value_in_place:
#             if not has_default_factory:
#                 raise MicroOpTypeConflict()
#             if not self.value_type.is_copyable_from(default_factory.value_type):
#                 raise MicroOpTypeConflict()
# 
#         return super(DictGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)
# 
#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (DictGetterType, DictWildcardGetterType)):
#             return False
#         if isinstance(other_micro_op_type, (DictSetterType, DictWildcardSetterType)):
#             other_key, other_type = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and other_key != self.key:
#                 return False
#             if not self.type_error and not other_micro_op_type.type_error and not self.value_type.is_copyable_from(other_type):
#                 return True
#         if isinstance(other_micro_op_type, (DictDeletterType, DictWildcardDeletterType)):
#             other_key, _ = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and other_key != self.key:
#                 return False
# 
#             default_factory = other_micro_op_types.get(("default-factory",), None)
#             has_default_factory = default_factory is not None
# 
#             if not self.key_error and not has_default_factory:
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         if isinstance(other_micro_op, (DictGetter, DictWildcardGetter)):
#             return
#         if isinstance(other_micro_op, (DictSetter, DictWildcardSetter)):
#             other_key, other_new_value = get_key_and_new_value(other_micro_op, args)
#             if other_key != self.key:
#                 return
#             if not self.type_error and not self.value_type.is_copyable_from(get_type_of_value(other_new_value)):
#                 raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
#         if isinstance(other_micro_op, (DictDeletter, DictWildcardDeletter)):
#             other_key, _ = get_key_and_new_value(other_micro_op, args)
#             if not self.key_error and other_key == self.key:
#                 raise raise_if_safe(InvalidDereferenceKey, other_micro_op.key_error)
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(DictGetterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         value_in_place = obj.wrapped[self.key]
#         get_manager(value_in_place)
#         type_of_value = get_type_of_value(value_in_place)
#         if not self.value_type.is_copyable_from(type_of_value):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return DictGetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


# class DictGetter(MicroOp):
#     def __init__(self, target_manager, key, type, key_error, type_error):
#         target_manager = target_manager
#         self.key = key
#         self.value_type = type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, **kwargs):
#         raise_micro_op_conflicts(self, [], target_manager.get_flattened_micro_op_types())
# 
#         if self.key in target_manager.get_obj().wrapped:
#             value = target_manager.get_obj().wrapped[self.key]
#         else:
#             default_factory_op = target_manager.get_micro_op_type(("default-factory",))
# 
#             if default_factory_op:
#                 value = default_factory_op.invoke(self.key)
#             else:
#                 raise_if_safe(InvalidDereferenceKey, self.key_error)
# 
#         get_manager(value)
# 
#         type_of_value = get_type_of_value(value)
# 
#         if not self.value_type.is_copyable_from(type_of_value):
#             raise raise_if_safe(InvalidDereferenceType, self.type_error)
# 
#         return value


class DictWildcardSetterType(DictMicroOpType):
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

        unbind_key(target_manager.get_obj(), key)

        target_manager.get_obj()._get(key, new_value)

        bind_key(target_manager.get_obj(), key)

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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, DictWildcardSetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return DictWildcardSetterType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (DictGetterType, DictWildcardGetterType)):
#             if not self.type_error and not other_micro_op_type.type_error and not other_micro_op_type.value_type.is_copyable_from(self.value_type):
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         pass
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(DictWildcardSetterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return DictWildcardSetterType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


# class DictWildcardSetter(MicroOp):
#     def __init__(self, target_manager, value_type, key_error, type_error):
#         target_manager = target_manager
#         self.value_type = value_type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, key, new_value, **kwargs):
#         get_manager(new_value)
#         target_manager = target_manager
#         raise_micro_op_conflicts(self, [ key, new_value ], target_manager.get_flattened_micro_op_types())
# 
#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
# 
#         target_manager.unbind_key(key)
# 
#         target_manager.get_obj().wrapped[key] = new_value
# 
#         target_manager.bind_key(key)


class DictSetterType(DictMicroOpType):
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

        unbind_key(target_manager.get_obj(), key)

        target_manager.get_obj()._set(self.key, new_value)

        bind_key(target_manager.get_obj(), key)

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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, DictSetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return DictSetterType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (DictGetterType, DictWildcardGetterType)):
#             other_key, other_type = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and other_key != self.key:
#                 return False
#             if not self.type_error and not other_micro_op_type.type_error and not other_type.is_copyable_from(self.value_type):
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         pass
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(DictSetterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return DictSetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )


# class DictSetter(MicroOp):
# 
#     def __init__(self, target_manager, key, type, key_error, type_error):
#         target_manager = target_manager
#         self.key = key
#         self.value_type = type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, new_value, **kwargs):
#         get_manager(new_value)
#         target_manager = target_manager
#         raise_micro_op_conflicts(self, [ new_value ], target_manager.get_flattened_micro_op_types())
# 
#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
# 
#         target_manager.unbind_key(self.key)
# 
#         target_manager.get_obj().wrapped[self.key] = new_value
# 
#         target_manager.bind_key(self.key)


class InvalidDeletion(Exception):
    pass


class DictWildcardDeletterType(DictMicroOpType):

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
#         wildcard_getter = other_type.get_micro_op_type(("get-wildcard", ))
#         if wildcard_getter and not self.key_error and not wildcard_getter.key_error:
#             return True
# 
#         for key, other_getter in other_type.micro_op_types.items():
#             if key[0] == "get":
#                 if not self.key_error and not other_getter.key_error:
#                     return True

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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (DictGetterType, DictWildcardGetterType)):
#             default_factory = other_micro_op_types.get(("default-factory",), None)
#             has_default_factory = default_factory is not None
# 
#             if not other_micro_op_type.key_error and not has_default_factory:
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         return False
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(DictWildcardDeletterType, self).check_for_runtime_data_conflict(obj):
#             return True
#         return False

    def merge(self, other_micro_op_type):
        return DictWildcardDeletterType(
            self.key_error or other_micro_op_type.key_error
        )


# class DictWildcardDeletter(MicroOp):
#     def __init__(self, target_manager, key_error):
#         target_manager = target_manager
#         self.key_error = key_error
# 
#     def invoke(self, key, **kwargs):
#         target_manager = target_manager
#         raise_micro_op_conflicts(self, [ key ], target_manager.get_flattened_micro_op_types())
# 
#         target_manager.unbind_key(key)
# 
#         del target_manager.get_obj().wrapped[key]


class DictDeletterType(DictMicroOpType):
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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         return self

#     def bind(self, key, target):
#         pass
# 
#     def unbind(self, key, target):
#         pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (DictGetterType, DictWildcardGetterType)):
#             other_key, _ = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and other_key != self.key:
#                 return False
#             if not other_micro_op_type.key_error:
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         pass
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(DictDeletterType, self).check_for_runtime_data_conflict(obj):
#             return True
#         return False

    def merge(self, other_micro_op_type):
        return DictDeletterType(self.key, self.key_error or other_micro_op_type.key_error)


# class DictDeletter(MicroOp):
#     def __init__(self, target_manager, key, key_error):
#         target_manager = target_manager
#         self.key = key
#         self.key_error = key_error
# 
#     def invoke(self, **kwargs):
#         target_manager = target_manager
#         raise_micro_op_conflicts(self, [ ], target_manager.get_flattened_micro_op_types())
# 
#         target_manager.unbind_key(self.key)
# 
#         del target_manager.get_obj().wrapped[self.key]

# def is_dict_checker(obj):
#     return isinstance(obj, RDHDict)

class RDHDictType(CompositeType):
    def __init__(self, wildcard_type=None):
        micro_ops = {}

        if wildcard_type:
            micro_ops[("get-wildcard",)] = DictWildcardGetterType(wildcard_type, True, False)
            micro_ops[("set-wildcard",)] = DictWildcardSetterType(wildcard_type, True, True)
            micro_ops[("delete-wildcard",)] = DictWildcardDeletterType(True)

        super(RDHDictType, self).__init__(micro_ops)


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
