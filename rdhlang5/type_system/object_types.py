from collections import OrderedDict

from rdhlang5.executor.ast_utils import compile_statement, compile_expression
from rdhlang5.type_system.composites import InferredType, bind_type_to_value, \
    unbind_type_to_value, DefaultFactoryType, CompositeType, Composite
from rdhlang5.type_system.core_types import merge_types, Type, Const, OneOfType, \
    AnyType
from rdhlang5.type_system.exceptions import FatalError, MicroOpTypeConflict, \
    raise_if_safe, InvalidAssignmentType, InvalidDereferenceKey, \
    InvalidDereferenceType, MissingMicroOp, InvalidInferredType, \
    IncorrectObjectTypeForMicroOp
from rdhlang5.type_system.managers import get_manager, get_type_of_value
from rdhlang5.type_system.micro_ops import MicroOpType, MicroOp, \
    raise_micro_op_conflicts
from rdhlang5.utils import is_debug, MISSING, micro_op_repr


WILDCARD = object()

def get_key_and_type(micro_op_type):
    return getattr(micro_op_type, "key", WILDCARD), getattr(micro_op_type, "type", MISSING)

#     if isinstance(micro_op_type, (ObjectWildcardGetterType, ObjectWildcardSetterType, ObjectWildcardDeletterType)):
#         key = WILDCARD
#     elif isinstance(micro_op_type, (ObjectGetterType, ObjectSetterType, ObjectDeletterType)):
#         key = micro_op_type.key
#     else:
#         raise FatalError()
# 
#     if isinstance(micro_op_type, (ObjectWildcardGetterType, ObjectGetterType, ObjectWildcardSetterType, ObjectSetterType)):
#         type = micro_op_type.type
#     else:
#         type = MISSING
# 
#     return key, type


def get_key_and_new_value(micro_op, args):
    if isinstance(micro_op, (ObjectWildcardGetter, ObjectWildcardDeletter)):
        key, = args
        new_value = MISSING
    elif isinstance(micro_op, (ObjectGetter, ObjectDeletter)):
        key = micro_op.key
        new_value = MISSING
    elif isinstance(micro_op, ObjectWildcardSetter):
        key, new_value = args
    elif isinstance(micro_op, ObjectSetter):
        key = micro_op.key
        new_value = args[0]
    else:
        raise FatalError()
    if new_value is not None:
        get_manager(new_value, "get_key_and_new_value")
    return key, new_value

class ObjectMicroOpType(MicroOpType):
    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        if not isinstance(obj, RDHObject):
            raise IncorrectObjectTypeForMicroOp()
        return super(ObjectMicroOpType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_runtime_data_conflict(self, obj):
        if not isinstance(obj, RDHObject):
            return True


class ObjectWildcardGetterType(ObjectMicroOpType):
    __slots__ = [ "type", "key_error", "type_error" ]

    def __init__(self, type, key_error, type_error):
        if type is None:
            raise FatalError()
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ObjectWildcardGetter(target_manager, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and self.type.is_copyable_from(other_micro_op_type.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ObjectWildcardGetterType):
            if isinstance(self.type, InferredType):
                raise InvalidInferredType()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ObjectWildcardGetterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def reify_revconst_types(self, other_micro_op_types):
        reified_type_to_use = self.type.reify_revconst_types()
        if reified_type_to_use != self.type:
            return ObjectWildcardGetterType(reified_type_to_use, self.key_error, self.type_error)
        return self

    def bind(self, source_type, key, target_manager):
        if key is not None:
            if key not in target_manager.obj.__dict__:
                raise FatalError()
            keys = [ key ]
        else:
            keys = target_manager.obj.__dict__.keys()
        for k in keys:
            value = target_manager.obj.__dict__[k]
            bind_type_to_value(target_manager, source_type, k, self.type, get_manager(value, "ObjectWildcardGetterType.bind"))

    def unbind(self, source_type, key, target_manager):
        if key is not None:
            keys = [ key ]
        else:
            keys = target_manager.obj.__dict__.keys()
        for k in keys:
            if not k in target_manager.obj.__dict__:
                continue
            value = target_manager.obj.__dict__[k]
            unbind_type_to_value(target_manager, source_type, k, self.type, get_manager(value, "ObjectWildcardGetterType.unbind"))


    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        default_factories = [ o for o in micro_op_types.values() if isinstance(o, DefaultFactoryType)]
        has_default_factory = len(default_factories) > 0

        if not self.key_error:
            if not has_default_factory:
                raise MicroOpTypeConflict()
            default_factory = default_factories[0]
            if not self.type.is_copyable_from(default_factory.type):
                raise MicroOpTypeConflict()

        return super(ObjectWildcardGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        default_factory = other_micro_op_types.get(("default-factory",), None)
        has_default_factory = default_factory is not None
        if not self.key_error:
            if not has_default_factory:
                return True

        if isinstance(other_micro_op_type, (ObjectGetterType, ObjectWildcardGetterType)):
            return False
        if isinstance(other_micro_op_type, (ObjectSetterType, ObjectWildcardSetterType)):
            if not self.type_error and not other_micro_op_type.type_error and not self.type.is_copyable_from(other_micro_op_type.type):
                return True
        if isinstance(other_micro_op_type, (ObjectDeletterType, ObjectWildcardDeletterType)):
            if not self.key_error and not other_micro_op_type.key_error and not has_default_factory:
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        if isinstance(other_micro_op, (ObjectSetter, ObjectWildcardSetter)):
            _, new_value = get_key_and_new_value(other_micro_op, args)
            if not self.type_error and not self.type.is_copyable_from(get_type_of_value(new_value)):
                raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)

        if isinstance(other_micro_op, (ObjectDeletter, ObjectWildcardDeletter)):
            if not self.key_error:
                raise_if_safe(InvalidAssignmentType, other_micro_op.key_error)
        return False

    def check_for_runtime_data_conflict(self, obj):
        if super(ObjectWildcardGetterType, self).check_for_runtime_data_conflict(obj):
            return True

        if not self.key_error and get_manager(obj, "ObjectWildcardGetterType.check_for_runtime_data_conflict obj").default_factory is None:
            return True

        if not self.type_error:
            for value in obj.__dict__.values():
                if not self.type.is_copyable_from(get_type_of_value(value)):
                    return True

        return False

    def merge(self, other_micro_op_type):
        return ObjectWildcardGetterType(
            merge_types([ self.type, other_micro_op_type.type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("get", "*", self.key_error, self.type, self.type_error)


class ObjectWildcardGetter(MicroOp):
    __slots__ = [ "target_manager", "type", "key_error", "type_error" ]

    def __init__(self, target_manager, type, key_error, type_error):
        self.target_manager = target_manager
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, key, trust_caller=False, **kwargs):
        if is_debug() or not trust_caller or self.key_error or self.type_error:
            raise_micro_op_conflicts(self, [ key ], self.target_manager.get_flattened_micro_op_types())

        if key in self.target_manager.obj.__dict__:
            value = self.target_manager.obj.__dict__[key]
        else:
            default_factory_op_type = self.target_manager.get_micro_op_type(("default-factory", ))

            if not default_factory_op_type:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

            default_factory_op = default_factory_op_type.create(self.target_manager)
            value = default_factory_op.invoke(key)

        if is_debug() or self.type_error:
            type_of_value = get_type_of_value(value)
            if not self.type.is_copyable_from(type_of_value):
                raise raise_if_safe(InvalidDereferenceType, self.type_error)

        return value

class ObjectGetterType(ObjectMicroOpType):
    __slots__ = [ "key", "type", "key_error", "type_error" ]

    def __init__(self, key, type, key_error, type_error):
        if type is None or not isinstance(type, Type):
            raise FatalError()
        if not isinstance(key, basestring):
            raise FatalError()
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ObjectGetter(target_manager, self.key, self.type, self.key_error, self.type_error)

#     def invoke(self, target_manager, trust_caller):
#         if is_debug():
#             raise FatalError()
#         return target_manager.obj.__dict__[self.key]

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and self.type.is_copyable_from(other_micro_op_type.type)
        )

    def reify_revconst_types(self, other_micro_op_types):
        reified_type_to_use = self.type.reify_revconst_types()
        if reified_type_to_use != self.type:
            return ObjectGetterType(self.key, reified_type_to_use, self.key_error, self.type_error)
        return self

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ObjectGetterType):
            if isinstance(self.type, InferredType):
                raise InvalidInferredType()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ObjectGetterType(self.key, new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target_manager):
        if key is not None and key != self.key:
            return
        value = target_manager.obj.__dict__[self.key]
        bind_type_to_value(target_manager, source_type, self.key, self.type, get_manager(value, "ObjectGetterType.bind"))

    def unbind(self, source_type, key, target_manager):
        if key is not None:
            if key != self.key:
                return
            if key not in target_manager.obj.__dict__:
                return
        value = target_manager.obj.__dict__[self.key]
        unbind_type_to_value(target_manager, source_type, self.key, self.type, get_manager(value, "ObjectGetterType.unbind"))

    def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
        default_factory = micro_op_types.get(("default-factory",), None)
        has_default_factory = default_factory is not None
        has_value_in_place = self.key in obj.__dict__

        if not self.key_error and not has_value_in_place:
            if not has_default_factory:
                raise MicroOpTypeConflict()
            if not self.type.is_copyable_from(default_factory.type):
                raise MicroOpTypeConflict()

        return super(ObjectGetterType, self).check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(obj, micro_op_types)

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ObjectGetterType, ObjectWildcardGetterType)):
            return False
        if isinstance(other_micro_op_type, (ObjectSetterType, ObjectWildcardSetterType)):
            other_key, other_type = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and other_key != self.key:
                return False
            if not self.type_error and not other_micro_op_type.type_error and not self.type.is_copyable_from(other_type):
                return True
        if isinstance(other_micro_op_type, (ObjectDeletterType, ObjectWildcardDeletterType)):
            other_key, _ = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and other_key != self.key:
                return False

            has_default_factory = any(isinstance(o, DefaultFactoryType) for o in other_micro_op_types.values())
            if not self.key_error and not other_micro_op_type.key_error and not has_default_factory:
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        if isinstance(other_micro_op, (ObjectGetter, ObjectWildcardGetter)):
            return
        if isinstance(other_micro_op, (ObjectSetter, ObjectWildcardSetter)):
            other_key, other_new_value = get_key_and_new_value(other_micro_op, args)
            if other_key != self.key:
                return
            if not self.type_error and not self.type.is_copyable_from(get_type_of_value(other_new_value)):
                raise_if_safe(InvalidAssignmentType, other_micro_op.type_error)
        if isinstance(other_micro_op, (ObjectDeletter, ObjectWildcardDeletter)):
            other_key, _ = get_key_and_new_value(other_micro_op, args)
            if not self.key_error and other_key == self.key:
                raise raise_if_safe(InvalidDereferenceKey, other_micro_op.key_error)

    def check_for_runtime_data_conflict(self, obj):
        if super(ObjectGetterType, self).check_for_runtime_data_conflict(obj):
            return True
        if self.key not in obj.__dict__:
            return True
        value_in_place = obj.__dict__[self.key]
        manager = get_manager(value_in_place, "ObjectGetterType.check_for_runtime_data_conflict")
        if manager:
            if manager.check_for_runtime_data_conflicts(self.type):
                return True
        else:
            type_of_value = get_type_of_value(value_in_place)
            if not self.type.is_copyable_from(type_of_value):
                return True

        return False

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return ObjectGetterType(
            self.key,
            merge_types([ self.type, other_micro_op_type.type ], "sub"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def to_ast(self, dependency_builder, target):
        if self.type_error or self.key_error:
            return super(ObjectGetterType, self).to_ast(dependency_builder, target)
        return compile_expression(
            "{target}.__dict__[\"{key}\"]",
            None, dependency_builder, target=target, key=self.key
        )

    def __repr__(self):
        return micro_op_repr("get", self.key, self.key_error, self.type, self.type_error)

class ObjectGetter(MicroOp):
    __slots__ = [ "target_manager", "key", "type", "key_error", "type_error" ]

    def __init__(self, target_manager, key, type, key_error, type_error):
        self.target_manager = target_manager
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, **kwargs):
        if is_debug() or self.key_error or self.type_error:
            raise_micro_op_conflicts(self, [], self.target_manager.get_flattened_micro_op_types())

        if self.key in self.target_manager.obj.__dict__:
            value = self.target_manager.obj.__dict__[self.key]
        else:
            default_factory_op = self.target_manager.get_micro_op_type(("default-factory", ))

            if default_factory_op:
                value = default_factory_op.invoke(self.key)
            else:
                raise_if_safe(InvalidDereferenceKey, self.key_error)

        if is_debug() or self.type_error:
            type_of_value = get_type_of_value(value)

            if not self.type.is_copyable_from(type_of_value):
                raise raise_if_safe(InvalidDereferenceType, self.type_error)

        return value


class ObjectWildcardSetterType(ObjectMicroOpType):
    __slots__ = [ "type", "key_error", "type_error" ]

    def __init__(self, type, key_error, type_error):
        if type is None:
            raise FatalError()
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ObjectWildcardSetter(target_manager, self.type, self.key_error, self.type_error)

    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.type.is_copyable_from(self.type)
        )

    def reify_revconst_types(self, other_micro_op_types):
        getter = other_micro_op_types.get(("get-wildcard", ), None)
        type_to_use = self.type
        if getter:
            type_to_use = getter.type

        reified_type_to_use = type_to_use.reify_revconst_types()
        if reified_type_to_use != self.type:
            return ObjectWildcardSetterType(reified_type_to_use, self.key_error, self.type_error)
        return self

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ObjectWildcardSetterType):
            if isinstance(self.type, InferredType):
                raise InvalidInferredType()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ObjectWildcardSetterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ObjectGetterType, ObjectWildcardGetterType)):
            if not self.type_error and not other_micro_op_type.type_error and not other_micro_op_type.type.is_copyable_from(self.type):
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if super(ObjectWildcardSetterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ObjectWildcardSetterType(
            merge_types([ self.type, other_micro_op_type.type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def __repr__(self):
        return micro_op_repr("set", "*", self.key_error, self.type, self.type_error)

class ObjectWildcardSetter(MicroOp):
    __slots__ = [ "target_manager", "type", "key_error", "type_error" ]

    def __init__(self, target_manager, type, key_error, type_error):
        self.target_manager = target_manager
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, key, new_value, trust_caller=False, **kwargs):
        if is_debug() or not trust_caller or self.key_error or self.type_error:
            raise_micro_op_conflicts(self, [ key, new_value ], self.target_manager.get_flattened_micro_op_types())

        if (is_debug() or not trust_caller):
            new_value_type = get_type_of_value(new_value)
            if not self.type.is_copyable_from(new_value_type):
                raise FatalError()

        self.target_manager.unbind_key(key)

        self.target_manager.obj.__dict__[key] = new_value

        self.target_manager.bind_key(key)

class ObjectSetterType(ObjectMicroOpType):
    __slots__ = [ "key", "type", "key_error", "type_error" ]

    def __init__(self, key, type, key_error, type_error):
        if type is None or not isinstance(type, Type):
            raise FatalError()
        if not isinstance(key, basestring):
            raise FatalError()
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def create(self, target_manager):
        return ObjectSetter(target_manager, self.key, self.type, self.key_error, self.type_error)

#     def invoke(self, target_manager, new_value, trust_caller):
#         if is_debug():
#             raise FatalError()
# 
#         target_manager.unbind_key(self.key)
# 
#         target_manager.obj.__dict__[self.key] = new_value
# 
#         target_manager.bind_key(self.key)


    def can_be_derived_from(self, other_micro_op_type):
        return (
            (not other_micro_op_type.key_error or self.key_error)
            and (not other_micro_op_type.type_error or self.type_error)
            and other_micro_op_type.type.is_copyable_from(self.type)
        )

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ObjectSetterType):
            if isinstance(self.type, InferredType):
                raise InvalidInferredType()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ObjectSetterType(self.key, new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def reify_revconst_types(self, other_micro_op_types):
        getter = other_micro_op_types.get(("get", self.key), None)
        type_to_use = self.type
        if getter:
            type_to_use = getter.type

        reified_type_to_use = type_to_use.reify_revconst_types()
        if reified_type_to_use != self.type:
            return ObjectSetterType(self.key, reified_type_to_use, self.key_error, self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ObjectGetterType, ObjectWildcardGetterType)):
            other_key, other_type = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and other_key != self.key:
                return False
            if not self.type_error and not other_micro_op_type.type_error and not other_type.is_copyable_from(self.type):
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if super(ObjectSetterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        if other_micro_op_type.key != self.key:
            raise FatalError()
        return ObjectSetterType(
            self.key,
            merge_types([ self.type, other_micro_op_type.type ], "super"),
            self.key_error or other_micro_op_type.key_error,
            self.type_error or other_micro_op_type.type_error
        )

    def to_ast(self, dependency_builder, target, new_value):
        if self.type_error or self.key_error:
            return super(ObjectGetterType, self).to_ast(dependency_builder, target, new_value)
        return compile_statement(
            "{target}.__dict__[\"{key}\"] = {rvalue}",
            None, dependency_builder,
            target=target, key=self.key, rvalue=new_value
        )

    def __repr__(self):
        return micro_op_repr("set", self.key, self.key_error, self.type, self.type_error)

class ObjectSetter(MicroOp):
    __slots__ = [ "target_manager", "key", "type", "key_error", "type_error" ]

    def __init__(self, target_manager, key, type, key_error, type_error):
        self.target_manager = target_manager
        self.key = key
        self.type = type
        self.key_error = key_error
        self.type_error = type_error

    def invoke(self, new_value, trust_caller=False, **kwargs):
        if is_debug() or not trust_caller or self.key_error or self.type_error:
            raise_micro_op_conflicts(self, [ new_value ], self.target_manager.get_flattened_micro_op_types())

        if (is_debug() or not trust_caller):
            new_value_type = get_type_of_value(new_value)
            if not self.type.is_copyable_from(new_value_type):
                raise FatalError()

        self.target_manager.unbind_key(self.key)

        self.target_manager.obj.__dict__[self.key] = new_value

        self.target_manager.bind_key(self.key)


class InvalidDeletion(Exception):
    pass


class ObjectWildcardDeletterType(ObjectMicroOpType):
    __slots__ = [ "key_error" ]

    def __init__(self, key_error):
        self.key_error = key_error

    def create(self, target_manager):
        return ObjectWildcardDeletter(target_manager, self.key_error)

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ObjectWildcardDeletter):
            if isinstance(self.type, InferredType):
                raise InvalidInferredType()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ObjectWildcardDeletter(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def can_be_derived_from(self, other_micro_op_type):
        return not other_micro_op_type.key_error or self.key_error

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ObjectGetterType, ObjectWildcardGetterType)):
            default_factory = other_micro_op_types.get(("default-factory",), None)
            has_default_factory = default_factory is not None

            if not self.key_error and not other_micro_op_type.key_error and not has_default_factory:
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        return False

    def check_for_runtime_data_conflict(self, obj):
        if super(ObjectWildcardDeletterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ObjectWildcardDeletterType(
            self.key_error or other_micro_op_type.key_error
        )


class ObjectWildcardDeletter(MicroOp):
    __slots__ = [ "target_manager", "key_error" ]

    def __init__(self, target_manager, key_error):
        self.target_manager = target_manager
        self.key_error = key_error

    def invoke(self, key, **kwargs):
        if is_debug() or self.key_error:
            raise_micro_op_conflicts(self, [ key ], self.target_manager.get_flattened_micro_op_types())

        self.target_manager.unbind_key(key)

        del self.target_manager.obj.__dict__[key]


class ObjectDeletterType(ObjectMicroOpType):
    __slots__ = [ "key", "key_error" ]

    def __init__(self, key, key_error):
        self.key = key
        self.key_error = key_error

    def create(self, target_manager):
        return ObjectDeletter(target_manager, self.key, self.key_error)

    def can_be_derived_from(self, other_micro_op_type):
        return not other_micro_op_type.key_error or self.key_error

    def replace_inferred_type(self, other_micro_op_type):
        if not isinstance(other_micro_op_type, ObjectDeletterType):
            if isinstance(self.type, InferredType):
                raise InvalidInferredType()
            return self
        new_type = self.type.replace_inferred_types(other_micro_op_type.type)
        if new_type is not self.type:
            return ObjectDeletterType(new_type, key_error=self.key_error, type_error=self.type_error)
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        if isinstance(other_micro_op_type, (ObjectGetterType, ObjectWildcardGetterType)):
            other_key, _ = get_key_and_type(other_micro_op_type)
            if other_key is not WILDCARD and other_key != self.key:
                return False
            if not self.key_error and not other_micro_op_type.key_error:
                return True
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if super(ObjectDeletterType, self).check_for_runtime_data_conflict(obj):
            return True

        return False

    def merge(self, other_micro_op_type):
        return ObjectDeletterType(self.key, self.key_error or other_micro_op_type.key_error)


class ObjectDeletter(MicroOp):
    __slots__ = [ "target_manager", "key", "key_error" ]

    def __init__(self, target_manager, key, key_error):
        self.target_manager = target_manager
        self.key = key
        self.key_error = key_error

    def invoke(self, **kwargs):
        if self.key_error:
            raise_micro_op_conflicts(self, [ ], self.target_manager.get_flattened_micro_op_types())

        self.target_manager.unbind_key(self.key)

        del self.target_manager.obj.__dict__[self.key]

def is_object_checker(obj):
    return isinstance(obj, RDHObject)

def RDHObjectType(properties=None, wildcard_type=None, initial_data=None, **kwargs):
    if not properties:
        properties = {}
    micro_ops = OrderedDict({})

    for name, type in properties.items():
        const = False
        if isinstance(type, Const):
            const = True
            type = type.wrapped

        if not isinstance(name, basestring):
            raise FatalError()
        if not isinstance(type, Type):
            raise FatalError()

        micro_ops[("get", name)] = ObjectGetterType(name, type, False, False)
        if not const:
            micro_ops[("set", name)] = ObjectSetterType(name, type, False, False)

    if wildcard_type:
        micro_ops[("get-wildcard",)] = ObjectWildcardGetterType(wildcard_type, True, False)
        micro_ops[("set-wildcard",)] = ObjectWildcardSetterType(wildcard_type, True, True)

    return CompositeType(micro_ops, is_object_checker, initial_data=initial_data, **kwargs)

class PythonObjectType(CompositeType):
    def __init__(self):
        micro_ops = {}

        micro_ops[("get-wildcard",)] = ObjectWildcardGetterType(OneOfType([ self, AnyType() ]), True, False)
        micro_ops[("set-wildcard",)] = ObjectWildcardSetterType(OneOfType([ self, AnyType() ]), False, False)
        micro_ops[("delete-wildcard",)] = ObjectWildcardDeletterType(True)

        super(PythonObjectType, self).__init__(micro_ops, is_object_checker)

class DefaultDictType(CompositeType):
    def __init__(self, type):
        # Use an ordered dict because the default-factory needs to be in place
        # for the later ops to work
        micro_ops = OrderedDict()

        micro_ops[("default-factory",)] = DefaultFactoryType(type)
        micro_ops[("get-wildcard",)] = ObjectWildcardGetterType(type, False, False)
        micro_ops[("set-wildcard",)] = ObjectWildcardSetterType(type, False, False)
        micro_ops[("delete-wildcard",)] = ObjectWildcardDeletterType(False)

        super(DefaultDictType, self).__init__(micro_ops, is_object_checker)

class RDHObject(Composite, object):
    def __init__(self, initial_data=None, default_factory=None, bind=None, instantiator_has_verified_bind=False, debug_reason=None):
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
            manager.add_composite_type(bind, caller_has_verified_type=instantiator_has_verified_bind)

    def __setattr__(self, key, value):
        manager = get_manager(self, "RDHObject.__setattr__")

        micro_op_type = manager.get_micro_op_type(("set", key))
        if micro_op_type is not None:
            micro_op = micro_op_type.create(manager)
            micro_op.invoke(value)
        else:
            micro_op_type = manager.get_micro_op_type(("set-wildcard",))

            if micro_op_type is None:
                manager.get_micro_op_type(("set-wildcard",))
                raise MissingMicroOp()

            micro_op = micro_op_type.create(manager)
            micro_op.invoke(key, value)

    def __getattribute__(self, key):
        if key in ("__dict__", "__class__"):
            return super(RDHObject, self).__getattribute__(key)

        try:
            manager = get_manager(self, "RDHObject.__getattr__")

            micro_op_type = manager.get_micro_op_type(("get", key))
            if micro_op_type is not None:
                micro_op = micro_op_type.create(manager)
                return micro_op.invoke()
            else:
                micro_op_type = manager.get_micro_op_type(("get-wildcard",))
    
                if micro_op_type is None:
                    raise MissingMicroOp()
    
                micro_op = micro_op_type.create(manager)
                return micro_op.invoke(key)
        except InvalidDereferenceKey:
            if key == "of":
                pass
            raise AttributeError(key)

    def __delattr__(self, key):
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

    def __repr__(self):
        return repr(self.__dict__)

    def __str__(self):
        return str(self.__dict__)
