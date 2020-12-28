from __builtin__ import True
from _abcoll import MutableSequence
from _collections import defaultdict
from collections import OrderedDict

from rdhlang5.type_system.composites import InferredType, CompositeType, \
    Composite, unbind_key, bind_key, can_add_composite_type_with_filter,\
    does_value_fit_through_type
from rdhlang5.type_system.core_types import merge_types, Const, NoValueType, \
    IntegerType, Type
from rdhlang5.type_system.exceptions import FatalError, raise_if_safe, \
    InvalidDereferenceKey, InvalidDereferenceType, InvalidAssignmentKey, \
    InvalidAssignmentType, MissingMicroOp
from rdhlang5.type_system.managers import get_manager, get_type_of_value
from rdhlang5.type_system.micro_ops import MicroOpType, \
    raise_micro_op_conflicts
from rdhlang5.utils import MISSING, is_debug, micro_op_repr, default


WILDCARD = object()


def get_key_and_type(micro_op_type):
    if isinstance(micro_op_type, (ListWildcardGetterType, ListWildcardSetterType, ListWildcardDeletterType, ListWildcardInsertType)):
        key = WILDCARD
    elif isinstance(micro_op_type, (ListGetterType, ListSetterType, ListDeletterType, ListInsertType)):
        key = micro_op_type.key
    else:
        raise FatalError()

    if isinstance(micro_op_type, (ListWildcardGetterType, ListGetterType, ListWildcardSetterType, ListSetterType, ListWildcardInsertType, ListInsertType)):
        type = micro_op_type.value_type
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
    key_type = IntegerType()

    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        if not isinstance(obj, RDHList):
            raise IncorrectObjectTypeForMicroOp()
        return super(ListMicroOpType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_runtime_data_conflict(self, obj):
        if not isinstance(obj, RDHList):
            return True


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

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListWildcardGetterType(
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

#     def apply_consistency_heuristic(self, other_micro_op_types):
#         reified_type_to_use = self.value_type.apply_consistency_heuristic(other_micro_op_types)
#         if reified_type_to_use != self.value_type:
#             return ListWildcardGetterType(reified_type_to_use, self.key_error, self.type_error)
#         return self

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, ListWildcardGetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return ListWildcardGetterType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

#     def bind(self, source_type, key, target_manager):
#         if key is not None:
#             keys = [ key ]
#         else:
#             keys = range(0, len(target_manager.get_obj().wrapped))
#         for k in keys:
#             value = target_manager.get_obj().wrapped[k]
#             bind_type_to_manager(target_manager, source_type, k, "value", self.value_type, get_manager(value))
# 
#     def unbind(self, source_type, key, target_manager):
#         if key is not None:
#             if key < 0 or key >= len(target_manager.get_obj()):
#                 return
#             keys = [ key ]
#         else:
#             keys = range(0, len(target_manager.get_obj()))
#         for k in keys:
#             unbind_type_to_manager(target_manager, source_type, k, "value", get_manager(target_manager.get_obj().wrapped[k]))

#     def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
#         default_factory = micro_op_types.get(("default-factory",), None)
#         has_default_factory = default_factory is not None
# 
#         if not self.key_error:
#             if not has_default_factory:
#                 raise MicroOpTypeConflict()
#             if not self.value_type.is_copyable_from(default_factory.type):
#                 raise MicroOpTypeConflict()
# 
#         return super(ListWildcardGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)
# 
#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         default_factory = other_micro_op_types.get(("default-factory",), None)
#         has_default_factory = default_factory is not None
# 
#         if not self.key_error:        
#             if not has_default_factory:
#                 return True
# 
#         if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
#             return False
#         if isinstance(other_micro_op_type, (ListSetterType, ListWildcardSetterType)):
#             if not self.type_error and not self.value_type.is_copyable_from(other_micro_op_type.value_type):
#                 return True
#         if isinstance(other_micro_op_type, (ListDeletterType, ListWildcardDeletterType)):
#             if not self.key_error and not has_default_factory:
#                 return True
#         if isinstance(other_micro_op_type, (ListInsertType, ListWildcardInsertType)):
#             if not self.type_error and not self.value_type.is_copyable_from(other_micro_op_type.value_type):
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         if isinstance(other_micro_op, (ListSetter, ListWildcardSetter)):
#             _, other_new_value = get_key_and_new_value(other_micro_op, args)
#             if not self.type_error and not self.value_type.is_copyable_from(get_type_of_value(other_new_value)):
#                 raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
#         if isinstance(other_micro_op, (ListInsert, ListWildcardInsert)):
#             _, other_new_value = get_key_and_new_value(other_micro_op, args)
#             if not self.type_error and not self.value_type.is_copyable_from(get_type_of_value(other_new_value)):
#                 raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
# 
#         if isinstance(other_micro_op, (ListDeletter, ListWildcardDeletter)):
#             if not self.key_error:
#                 raise_if_safe(InvalidAssignmentType, other_micro_op.key_error)
#         return False
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(ListWildcardGetterType, self).check_for_runtime_data_conflict(obj):
#             return True
#         if not self.key_error and get_manager(obj).default_factory is None:
#             return True
# 
#         if not self.type_error:
#             for value in obj.wrapped.values():  # Leaking RDHList details...
#                 get_manager(value)
#                 if not self.value_type.is_copyable_from(get_type_of_value(value)):
#                     return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return ListWildcardGetterType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("getL", "*", self.key_error, self.value_type, self.type_error)

# class ListWildcardGetter(MicroOp):
#     def __init__(self, target_manager, type, key_error, type_error):
#         target_manager = target_manager
#         self.value_type = type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, key, **kwargs):
#         raise_micro_op_conflicts(self, [ key ], target_manager.get_flattened_micro_op_types())
# 
#         if key >= 0 and key < len(target_manager.get_obj()):
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
#         if value is not SPARSE_ELEMENT:
#             type_of_value = get_type_of_value(value)
#             if not self.value_type.is_copyable_from(type_of_value):
#                 raise raise_if_safe(InvalidDereferenceType, self.type_error)
# 
#         return value


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
        if not key_filter or key_filter == self.key:
            if substitute_value is not MISSING:
                return ([ substitute_value ], self.value_type)
            if self.key in target.wrapped:
                return ([ target._get(self.key) ], self.value_type)
        return ([], None)

#     def apply_consistency_heuristic(self, other_micro_op_types):
#         reified_type_to_use = self.value_type.apply_consistency_heuristic(other_micro_op_types)
#         if reified_type_to_use != self.value_type:
#             return ListGetterType(self.key, reified_type_to_use, self.key_error, self.type_error)
#         return self

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, ListGetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return ListGetterType(self.key, new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListGetterType(
            self.key,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

#     def bind(self, source_type, key, target_manager):
#         if key is not None and key != self.key:
#             return
#         value = target_manager.get_obj().wrapped[self.key]
#         bind_type_to_manager(target_manager, source_type, key, "value", self.value_type, get_manager(value))
# 
#     def unbind(self, source_type, key, target_manager):
#         if key is not None and key != self.key:
#             return
#         value = target_manager.get_obj().wrapped[self.key]
#         unbind_type_to_manager(target_manager, source_type, key, "value", get_manager(value))

#     def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
#         default_factory = micro_op_types.get(("default-factory",), None)
#         has_default_factory = default_factory is not None
#         has_value_in_place = self.key >= 0 and self.key < len(obj)
# 
#         if not self.key_error and not has_value_in_place:
#             if not has_default_factory:
#                 raise MicroOpTypeConflict()
#             if not self.value_type.is_copyable_from(default_factory.value_type):
#                 raise MicroOpTypeConflict()
# 
#         return super(ListGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)
# 
#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (ListSetterType, ListWildcardSetterType)):
#             other_key, other_type = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and self.key != other_key:
#                 return False
#             if not self.type_error and not other_micro_op_type.type_error and not self.value_type.is_copyable_from(other_type):
#                 return True
#         if isinstance(other_micro_op_type, (ListInsertType, ListWildcardInsertType)):
#             other_key, other_type = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD:
#                 if self.key < other_key:
#                     return False
#                 elif self.key == other_key:
#                     if not self.type_error and not other_micro_op_type.type_error and not self.value_type.is_copyable_from(other_type):
#                         return True
#                 else:
#                     prior_micro_op = other_micro_op_types.get(("get", self.key - 1), None)
#                     if prior_micro_op:
#                         if not self.type_error and not prior_micro_op.type_error and not self.value_type.is_copyable_from(prior_micro_op.value_type):
#                             return True
#                     else:
#                         if not other_micro_op_type.key_error:
#                             return True
#             else:
#                 other_key, other_type = get_key_and_type(other_micro_op_type)
#                 if not self.value_type.is_copyable_from(other_type):
#                     return True
#         if isinstance(other_micro_op_type, (ListDeletterType, ListWildcardDeletterType)):
#             other_key, _ = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and self.key < other_key:
#                 return False
#             post_opcode = other_micro_op_types.get(("get", self.key + 1), None)
#             if post_opcode:
#                 if not self.type_error and not post_opcode.type_error and not self.value_type.is_copyable_from(post_opcode.value_type):
#                     return True
#             if not other_micro_op_type.key_error:
#                 return True
# 
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         if isinstance(other_micro_op, (ListGetter, ListWildcardGetter)):
#             return
#         if isinstance(other_micro_op, (ListSetter, ListWildcardSetter)):
#             other_key, new_value = get_key_and_new_value(other_micro_op, args)
#             if self.key != other_key:
#                 return
#             if not self.type_error and not self.value_type.is_copyable_from(get_type_of_value(new_value)):
#                 raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
#         if isinstance(other_micro_op, (ListInsert, ListWildcardInsert)):
#             other_key, new_value = get_key_and_new_value(other_micro_op, args)
#             if self.key < other_key:
#                 return
#             elif self.key == other_key:
#                 if not self.value_type.is_copyable_from(get_type_of_value(new_value)):
#                     raise raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
#             elif self.key > other_key:
#                 new_value = other_micro_op.target_manager.get_obj()[self.key - 1]
#                 if not self.value_type.is_copyable_from(get_type_of_value(new_value)):
#                     raise raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
#         if isinstance(other_micro_op, (ListDeletter, ListWildcardDeletter)):
#             other_key, _ = get_key_and_new_value(other_micro_op, args)
#             if self.key < other_key:
#                 return
#             else:
#                 new_value = other_micro_op.target_manager.get_obj()[self.key + 1]
#                 if not self.key_error and not self.value_type.is_copyable_from(get_type_of_value(new_value)):
#                     raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(ListGetterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         if self.key < 0 or self.key > len(obj):
#             return True
#         value = obj.__getitem__(self.key, raw=True)
#         type_of_value = get_type_of_value(value)
#         return not self.value_type.is_copyable_from(type_of_value)

    def merge(self, other_micro_op_type):
        return ListGetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("getL", self.key, self.key_error, self.value_type, self.type_error)

# class ListGetter(MicroOp):
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
#         if self.key >= 0 and self.key < len(target_manager.get_obj()):
#             value = target_manager.get_obj().__getitem__(self.key, raw=True)
#         else:
#             default_factory_op = target_manager.get_micro_op_type(("default-factory",))
# 
#             if default_factory_op:
#                 value = default_factory_op.invoke(self.key)
#             else:
#                 raise_if_safe(InvalidDereferenceKey, self.key_error)
# 
#         type_of_value = get_type_of_value(value)
# 
#         if not self.value_type.is_copyable_from(type_of_value):
#             raise_if_safe(InvalidDereferenceKey, self.can_fail)
# 
#         return value


class ListWildcardSetterType(ListMicroOpType):
    def __init__(self, type, key_error, type_error):
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, new_value, allow_failure)

#         if (is_debug() or not trust_caller):
#             new_value_type = get_type_of_value(new_value)
#             if not self.value_type.is_copyable_from(new_value_type):
#                 raise FatalError()

        if key < 0 or key > len(target_manager.get_obj()):
            if self.key_error:
                raise InvalidAssignmentKey()

        unbind_key(target_manager, key)

        target_manager.get_obj()._set(key, new_value)

        bind_key(target_manager, key)

    def raise_micro_op_invocation_conflicts(self, target_manager, key, new_value, allow_failure):
        target_type = target_manager.get_effective_composite_type()
        if not can_add_composite_type_with_filter(target_manager.get_obj(), target_type, key, new_value):
            raise_if_safe(InvalidAssignmentType, self.type_error or allow_failure)

#         target_type = target_manager.get_effective_composite_type()
# 
#         wildcard_getter = target_type.get_micro_op_type(("get-wildcard",))
#         if wildcard_getter and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
#             raise_if_safe(InvalidAssignmentType, self.type_error)
# 
#         detail_getter = target_type.get_micro_op_type(("get", key))
#         if detail_getter and not detail_getter.type_error and not detail_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
#             raise_if_safe(InvalidAssignmentType, self.type_error)

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

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListWildcardSetterType(
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

#     def apply_consistency_heuristic(self, other_micro_op_types):
#         getter = other_micro_op_types.get(("get-wildcard",), None)
#         type_to_use = self.value_type
#         if getter:
#             type_to_use = getter.value_type
# 
#         reified_type_to_use = type_to_use.apply_consistency_heuristic(other_micro_op_types)
#         if reified_type_to_use != self.value_type:
#             return ListWildcardSetterType(reified_type_to_use, self.key_error, self.type_error)
#         return self

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, ListWildcardSetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return ListWildcardSetterType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
#             if not self.type_error and not other_micro_op_type.type_error and not other_micro_op_type.value_type.is_copyable_from(self.value_type):
#                 return True
# 
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         pass
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(ListWildcardSetterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return ListWildcardSetterType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("setL", "*", self.key_error, self.value_type, self.type_error)

# class ListWildcardSetter(MicroOp):
#     def __init__(self, target_manager, type, key_error, type_error):
#         target_manager = target_manager
#         self.value_type = type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, key, new_value, **kwargs):
#         raise_micro_op_conflicts(self, [ key, new_value ], target_manager.get_flattened_micro_op_types())
# 
#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
# 
#         if key < 0 or key > len(target_manager.get_obj()):
#             if self.key_error:
#                 raise InvalidAssignmentKey()
# 
#         target_manager.unbind_key(key)
# 
#         target_manager.get_obj().__setitem__(key, new_value, raw=True)
# 
#         target_manager.bind_key(key)


class ListSetterType(ListMicroOpType):
    def __init__(self, key, type, key_error, type_error):
        self.key = key
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, new_value, allow_failure)

#         if (is_debug() or not trust_caller):
#             new_value_type = get_type_of_value(new_value)
#             if not self.value_type.is_copyable_from(new_value_type):
#                 raise FatalError()

        if self.key < 0 or self.key > len(target_manager.get_obj()):
            raise_if_safe(InvalidAssignmentKey, self.key_error)

        unbind_key(target_manager, self.key)

        target_manager.get_obj()._set(self.key, new_value)

        bind_key(target_manager, self.key)

    def raise_micro_op_invocation_conflicts(self, target_manager, new_value, allow_failure):
        target_type = target_manager.get_effective_composite_type()
        if not can_add_composite_type_with_filter(target_manager.get_obj(), target_type, self.key, new_value):
            raise_if_safe(InvalidAssignmentType, self.type_error or allow_failure)

#         target_type = target_manager.get_effective_composite_type()
# 
#         wildcard_getter = target_type.get_micro_op_type(("get-wildcard",))
#         if wildcard_getter and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
#             raise_if_safe(InvalidAssignmentType, self.type_error)
# 
#         detail_getter = target_type.get_micro_op_type(("get", self.key))
#         if detail_getter and not detail_getter.type_error and not detail_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
#             raise_if_safe(InvalidAssignmentType, self.type_error)

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

#     def apply_consistency_heuristic(self, other_micro_op_types):
#         getter = other_micro_op_types.get(("get", self.key), None)
#         type_to_use = self.value_type
#         if getter:
#             type_to_use = getter.value_type
# 
#         reified_type_to_use = type_to_use.apply_consistency_heuristic(other_micro_op_types)
#         if reified_type_to_use != self.value_type:
#             return ListSetterType(self.key, reified_type_to_use, self.key_error, self.type_error)
#         return self

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, ListSetterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return ListSetterType(self.key, new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

    def clone(self, value_type):
        return ListSetterType(self.key, value_type, self.key_error, self.type_error)

#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
#             other_key, other_type = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and self.key != other_key:
#                 return False
#             if not self.type_error and not other_micro_op_type.type_error and not other_type.is_copyable_from(self.value_type):
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         pass
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(ListSetterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return ListSetterType(
            self.key,
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("setL", self.key, self.key_error, self.value_type, self.type_error)

# class ListSetter(MicroOp):
#     def __init__(self, target_manager, key, type, key_error, type_error):
#         target_manager = target_manager
#         self.key = key
#         self.value_type = type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, new_value, **kwargs):
#         raise_micro_op_conflicts(self, [ new_value ], target_manager.get_flattened_micro_op_types())
# 
#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
# 
#         if self.key < 0 or self.key > len(target_manager.get_obj()):
#             raise_if_safe(InvalidAssignmentKey, self.can_fail)
# 
#         target_manager.bind_key(self.key)
# 
#         target_manager.get_obj().__setitem__(self.key, new_value, raw=True)
# 
#         target_manager.unbind_key(self.key)


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

#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass

    def is_derivable_from(self, other_type):
        other_micro_op_type = other_type.get_micro_op_type(("delete-wildcard",))
        return (other_micro_op_type and not other_micro_op_type.key_error) or self.key_error

    def conflicts_with(self, our_type, other_type):
#         wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
#         if wildcard_getter and not self.key_error and not wildcard_getter.key_error:
#             return True
# 
#         for tag, other_getter in other_type.micro_op_types.items():
#             if tag[0] == "get":
#                 if not self.key_error and not other_getter.key_error:
#                     return True

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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         return self

#     def apply_consistency_heuristic(self, other_micro_op_types):
#         for tag in other_micro_op_types.keys():
#             if tag[0] == "get":
#                 return None
#         return self

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
#             default_factory = other_micro_op_types.get(("default-factory",), None)
#             has_default_factory = default_factory is not None
# 
#             if not other_micro_op_type.key_error and not self.key_error and not has_default_factory:
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         return False
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(ListWildcardDeletterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return ListWildcardDeletterType(
            self.key_error or other_micro_op_type.key_error
        )

    def __repr__(self):
        return micro_op_repr("deleteL", "*", self.key_error)

# class ListWildcardDeletter(MicroOp):
#     def __init__(self, target_manager, key_error):
#         target_manager = target_manager
#         self.key_error = key_error
# 
#     def invoke(self, key, **kwargs):
#         raise_micro_op_conflicts(self, [ key ], target_manager.get_flattened_micro_op_types())
# 
#         target_manager.unbind_key(self.key)
# 
#         target_manager.get_obj().__delitem__(raw=True)


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
#         wildcard_getter = other_type.get_micro_op_type(("get-wildcard",))
#         if wildcard_getter and not self.key_error and not wildcard_getter.key_error and not has_default_factory:
#             return True
# 
#         detail_getter = other_type.get_micro_op_type(("get", self.key))
#         if detail_getter and not self.key_error and not detail_getter.key_error and not has_default_factory:
#             return True

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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, ListDeletterType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return ListDeletterType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
#             other_key, _ = get_key_and_type(other_micro_op_type)
#             if other_key is not WILDCARD and self.key > other_key:
#                 return False
#             if not self.key_error and not other_micro_op_type.key_error:
#                 return True
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         pass
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(ListDeletterType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return ListDeletterType(self.key, self.can_fail or other_micro_op_type.can_fail)

    def __repr__(self):
        return micro_op_repr("deleteL", self.key, self.key_error)

# class ListDeletter(MicroOp):
#     def __init__(self, target_manager, key):
#         target_manager = target_manager
#         self.key = key
# 
#     def invoke(self, **kwargs):
#         raise_micro_op_conflicts(self, [ ], target_manager.get_flattened_micro_op_types())
# 
#         target_manager.unbind_key(self.key)
# 
#         target_manager.get_obj().__delitem__(self.key, raw=True)


class ListWildcardInsertType(ListMicroOpType):
    def __init__(self, type, key_error, type_error):
        self.value_type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, target_manager, key, new_value, shortcut_checks=False, allow_failure=False, **kwargs):
        if is_debug() or not shortcut_checks or self.key_error or self.type_error:
            self.raise_micro_op_invocation_conflicts(target_manager, key, new_value, allow_failure)

#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
 
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

#         wildcard_getter = target_type.get_micro_op_type(("get-wildcard",))
#         if wildcard_getter and not wildcard_getter.type_error and not wildcard_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
#             raise_if_safe(InvalidAssignmentType, self.type_error)
# 
#         detail_getter = target_type.get_micro_op_type(("get", key))
#         if detail_getter and not detail_getter.type_error and not detail_getter.value_type.is_copyable_from(get_type_of_value(new_value)):
#             raise_if_safe(InvalidAssignmentType, self.type_error)

#         for after_key in range(key, len(target_manager.get_obj())):
#             # In a sense, we are testing whether the new bind_key calls will work before executing them
#             # Should this be rolled into the binding itself?
#             prev_getter = target_type.get_micro_op_type(("get", after_key))
#             next_getter = target_type.get_micro_op_type(("get", after_key + 1))
# 
#             shifted_values, _ = prev_getter.prepare_bind(target_manager.get_obj())
#             _, bind_type = next_getter.prepare_bind(target_manager.get_obj())
# 
#             for shifted_value in shifted_values:
#                 if not bind_type.is_copyable_from(get_type_of_value(shifted_value)):
#                     raise_if_safe(InvalidAssignmentType, self.type_error)

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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, ListWildcardInsertType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return ListWildcardInsertType(new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass

#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
#             _, other_type = get_key_and_type(other_micro_op_type)
#             return not other_type.is_copyable_from(self.value_type)
# 
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         return False
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if super(ListWildcardInsertType, self).check_for_runtime_data_conflict(obj):
#             return True
# 
#         return False

    def merge(self, other_micro_op_type):
        return ListWildcardInsertType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key_error or other_micro_op_type.key_error, self.type_error or other_micro_op_type.type_error
        )

# class ListWildcardInsert(MicroOp):
#     def __init__(self, target_manager, type, key_error, type_error):
#         target_manager = target_manager
#         self.value_type = type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, key, new_value, **kwargs):
#         raise_micro_op_conflicts(self, [ key, new_value ], target_manager.get_flattened_micro_op_types())
# 
#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
# 
#         for after_key in range(key, len(target_manager.get_obj())):
#             target_manager.unbind_key(after_key)
# 
#         target_manager.get_obj().insert(key, new_value, raw=True)
# 
#         for after_key in range(key, len(target_manager.get_obj())):
#             target_manager.unbind_key(after_key)


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
 
#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
 
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

#     def replace_inferred_type(self, other_micro_op_type, cache):
#         if not isinstance(other_micro_op_type, ListInsertType):
#             if isinstance(self.value_type, InferredType):
#                 raise FatalError()
#             return self
#         new_type = self.value_type.replace_inferred_types(other_micro_op_type.value_type, cache)
#         if new_type is not self.value_type:
#             return ListInsertType(self.key, new_type, key_error=self.key_error, type_error=self.type_error)
#         return self

    def is_bindable_to(self, target):
        manager = get_manager(target)
        if not isinstance(target, RDHList):
            return False
        if not manager:
            return False

        return True

    def prepare_bind(self, target, key_filter, substitute_value):
        return ([], None)

#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass

    def clone(self, value_type=MISSING, key_error=MISSING):
        return ListInsertType(
            self.key,
            default(value_type, self.value_type),
            default(key_error, self.key_error),
            self.type_error
        )

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ListGetterType, ListWildcardGetterType)):
            other_key, other_type = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD:
                if self.key > other_key:
                    return False
                elif self.key == other_key:
                    return not other_type.is_copyable_from(self.value_type)
                elif self.key < other_key:
                    prior_micro_op = other_micro_op_types.get(("get", other_key - 1), None)
                    if prior_micro_op is None:
                        return True
                    if not self.type_error and not prior_micro_op.type_error and not other_micro_op_type.value_type.is_copyable_from(prior_micro_op.value_type):
                        return True
            else:
                return not other_type.is_copyable_from(self.value_type)
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        return False

    def check_for_runtime_data_conflict(self, obj):
        if super(ListInsertType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ListInsertType(
            merge_types([ self.value_type, other_micro_op_type.value_type ], "sub"),
            self.key,
            self.key_error or other_micro_op_type.key_error, self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("insertL", self.key, self.key_error, self.value_type, self.type_error)

# class ListInsert(MicroOp):
#     def __init__(self, target_manager, key, type, key_error, type_error):
#         target_manager = target_manager
#         self.key = key
#         self.value_type = type
#         self.key_error = key_error
#         self.type_error = type_error
# 
#     def invoke(self, new_value, **kwargs):
#         raise_micro_op_conflicts(self, [ new_value ], target_manager.get_flattened_micro_op_types())
# 
#         new_value_type = get_type_of_value(new_value)
#         if not self.value_type.is_copyable_from(new_value_type):
#             raise FatalError()
# 
#         for after_key in range(self.key, len(target_manager.get_obj())):
#             target_manager.unbind_key(after_key)
# 
#         target_manager.get_obj().insert(self.key, new_value, raw=True)
# 
#         for after_key in range(self.key, len(target_manager.get_obj())):
#             target_manager.bind_key(after_key)


# def is_list_checker(obj):
#     return isinstance(obj, RDHList)


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

    return CompositeType(micro_ops)


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
