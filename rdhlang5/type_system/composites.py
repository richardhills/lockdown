from collections import defaultdict
import threading
import weakref

from rdhlang5.type_system.core_types import Type, unwrap_types, AnyType, \
    OneOfType, TopType
from rdhlang5.type_system.exceptions import FatalError, MicroOpTypeConflict, \
    IncorrectObjectTypeForMicroOp
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.micro_ops import MicroOpType, \
    MicroOp, merge_composite_types
from rdhlang5.utils import is_debug, raise_from, capture_raise


class InferredType(Type):
    def is_copyable_from(self, other):
        raise FatalError()

    def replace_inferred_types(self, other):
        return other

composite_type_is_copyable_cache = threading.local()

class CompositeType(Type):
    def __init__(self, micro_op_types, python_object_type_checker, initial_data=None, is_revconst=False, name=None):
        if not isinstance(micro_op_types, dict):
            raise FatalError()
        for tag in micro_op_types.keys():
            if tag == ("get", "result"):
                pass
            if not isinstance(tag, tuple):
                raise FatalError()
        from rdhlang5.type_system.dict_types import RDHDict

        if isinstance(initial_data, dict):
            pass
        self.micro_op_types = micro_op_types
        self.initial_data = initial_data
        self.is_revconst = is_revconst
        self.name = name or "unknown"
        self.python_object_type_checker = python_object_type_checker

#         if is_debug():
#             for micro_op_type in micro_op_types.values():
#                 micro_op_type_type = getattr(micro_op_type, "type", None)
#                 if not micro_op_type_type:
#                     continue
#                 for micro_op_type_subtype in unwrap_types(micro_op_type_type):
#                     if isinstance(micro_op_type_subtype, CompositeType) and micro_op_type_subtype.is_revconst != is_revconst:
#                         raise FatalError()

    def replace_inferred_types(self, other):
        if not isinstance(other, CompositeType):
            return self

        potential_replacement_opcodes = {}

        for key, micro_op_type in self.micro_op_types.items():
            other_micro_op_type = other.micro_op_types.get(key, None)

            potential_replacement_opcodes[key] = micro_op_type.replace_inferred_type(other_micro_op_type)

        return CompositeType(
            potential_replacement_opcodes,
            self.python_object_type_checker,
            initial_data=self.initial_data,
            is_revconst=other.is_revconst,
            name="inferred<{} & {}>".format(self.name, other.name)
        )

    def reify_revconst_types(self):
        if not self.is_revconst:
            return self

        potential_replacement_opcodes = {}

        for key, micro_op_type in self.micro_op_types.items():
            new_micro_op = micro_op_type.reify_revconst_types(self.micro_op_types)
            if new_micro_op:
                potential_replacement_opcodes[key] = new_micro_op

        return CompositeType(
            potential_replacement_opcodes,
            self.python_object_type_checker,
            initial_data=self.initial_data,
            is_revconst=False,
            name="reified<{}>".format(self.name)
        )

    def get_micro_op_type(self, tag):
        return self.micro_op_types.get(tag, None)

    def check_internal_python_object_type(self, obj):
        if not self.python_object_type_checker(obj):
            raise IncorrectObjectTypeForMicroOp()

    def check_for_self_micro_op_conflicts(self):
        for first in self.micro_op_types.values():
            for second in self.micro_op_types.values():
                first_check = first.check_for_new_micro_op_type_conflict(second, self.micro_op_types)
                second_check = second.check_for_new_micro_op_type_conflict(first, self.micro_op_types)
                if first_check != second_check:
                    pass
                if first_check is True:
                    first_check = first.check_for_new_micro_op_type_conflict(second, self.micro_op_types)
                    return True
        return False

    def internal_is_copyable_from(self, other):
        if not isinstance(other, CompositeType):
            return False

        if not other.is_revconst:
            for ours in self.micro_op_types.values():
                for theirs in other.micro_op_types.values():
                    if ours.check_for_new_micro_op_type_conflict(theirs, self.micro_op_types):
                        ours.check_for_new_micro_op_type_conflict(theirs, self.micro_op_types)
                        return False

        for our_tag, our_micro_op in self.micro_op_types.items():
            their_micro_op = other.micro_op_types.get(our_tag, None)

            if True:
                only_safe_with_initial_data = False
                if their_micro_op is None:
                    only_safe_with_initial_data = True
                if their_micro_op and not our_micro_op.can_be_derived_from(their_micro_op):
                    only_safe_with_initial_data = True

                if only_safe_with_initial_data:
                    if other.initial_data is None:
                        return False
                    if our_micro_op.check_for_runtime_data_conflict(other.initial_data):
                        return False
            else:
                no_initial_data_to_make_safe = not other.initial_data or our_micro_op.check_for_runtime_data_conflict(other.initial_data)
                if no_initial_data_to_make_safe:
                    if their_micro_op is None:
                        return False
                    if not our_micro_op.can_be_derived_from(their_micro_op):
                        return False

        return True

    def is_copyable_from(self, other):
        if self is other:
            return True

        if isinstance(other, TopType):
            return True
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self)

        if not isinstance(other, CompositeType):
            return False

        if self.micro_op_types is other.micro_op_types:
            return True

        try:
            cache_started_empty = False
            if getattr(composite_type_is_copyable_cache, "_is_copyable_from_cache", None) is None:
                composite_type_is_copyable_cache._is_copyable_from_cache = defaultdict(lambda: defaultdict(lambda: None))
                cache_started_empty = True
            cache = composite_type_is_copyable_cache._is_copyable_from_cache

            result = None# results_by_target_id[id(self)][id(other)]

            # Debugging check
#            if result is False:
#                check = self.internal_is_copyable_from(other)
#                if check is True:
#                    self.internal_is_copyable_from(other)
#                    raise FatalError()

            if result is None:
                result = cache[id(self)][id(other)]
            if result is not None:
                return result

            cache[id(self)][id(other)] = True
            cache[id(other)][id(self)] = True

            result = self.internal_is_copyable_from(other)

            cache[id(self)][id(other)] = result
            cache[id(other)][id(self)] = result

            if cache_started_empty:
                source_weakref = weakrefs_for_type.get(id(other), None)
                if source_weakref is None:
                    source_weakref = weakref.ref(other, type_cleared)
                    weakrefs_for_type[id(other)] = source_weakref
                    type_ids_for_weakref_id[id(source_weakref)] = id(other)

                target_weakref = weakrefs_for_type.get(id(self), None)
                if target_weakref is None:
                    target_weakref = weakref.ref(self, type_cleared)
                    weakrefs_for_type[id(self)] = target_weakref
                    type_ids_for_weakref_id[id(target_weakref)] = id(self)

                if target_weakref is not None and target_weakref() is not self:
                    raise FatalError()
                if source_weakref is not None and source_weakref() is not other:
                    raise FatalError()

                results_by_target_id[id(self)][id(other)] = result
                results_by_source_id[id(other)][id(self)] = result

                # At the moment, garbage collecting types completely breaks composite type comparison.
                # Until I'm able to fix, let's keep strong references, leak like hell
                strong_links[id(self)] = self
                strong_links[id(other)] = other
        finally:
            if cache_started_empty:
                composite_type_is_copyable_cache._is_copyable_from_cache = None

        return result

    def __repr__(self):
        return "Composite<{}; {}>".format(", ".join([str(m) for m in self.micro_op_types.values()]), self.initial_data)

    def short_str(self):
        return "Composite<{}>".format(self.name)

    def to_code(self):
        keys = set()
        getters = set()
        setters = set()
        type = {}
        for micro_op_type in self.micro_op_types.values():
            if not hasattr(micro_op_type, "key"):
                continue
            keys.add(micro_op_type.key)
            if "Get" in str(micro_op_type.__class__):
                getters.add(micro_op_type.key)
                type[micro_op_type.key] = micro_op_type.type
            if "Set" in str(micro_op_type.__class__):
                setters.add(micro_op_type.key)
        return "Composite {{\n{}\n}}".format(
            ";\n".join(["{}: {}{} {}".format(k, "g" if k in getters else "", "s" if k in setters else "", type[k].to_code()) for k in keys])
        )

weakrefs_for_type = {}
type_ids_for_weakref_id = {}
results_by_target_id = defaultdict(lambda: defaultdict(lambda: None))
results_by_source_id = defaultdict(lambda: defaultdict(lambda: None))
strong_links = {}

def type_cleared(type_weakref):
    type_id = type_ids_for_weakref_id[id(type_weakref)]
    for source_id in results_by_target_id[type_id].keys():
        del results_by_source_id[source_id]
    del results_by_target_id[type_id]
    del weakrefs_for_type[type_id]
    del type_ids_for_weakref_id[id(type_weakref)]

class Composite(object):
    pass

def bind_type_to_manager(source_manager, source_type, key, rel_type, type, value_manager):
    if not source_manager or not value_manager:
        return

    something_worked = False
    error_if_all_fails = None

    for sub_type in unwrap_types(type):
        if isinstance(sub_type, CompositeType):
            try:
                value_manager.add_composite_type(sub_type)
                if rel_type == "value":
                    source_manager.child_value_type_references[key][id(source_type)].append(sub_type)
                elif rel_type == "key":
                    source_manager.child_key_type_references[key][id(source_type)].append(sub_type)
                else:
                    raise FatalError()
                something_worked = True
            except IncorrectObjectTypeForMicroOp:
                pass
            except MicroOpTypeConflict as e:
                error_if_all_fails = capture_raise(MicroOpTypeConflict, e)
        else:
            something_worked = True

    if not something_worked:
        if error_if_all_fails:
            raise error_if_all_fails[0], error_if_all_fails[1], error_if_all_fails[2]
        else:
            raise FatalError()

def unbind_type_to_manager(source_manager, source_type, key, rel_type, value_manager):
    if not source_manager or not value_manager:
        return

    references = None
    if rel_type == "value":
        references = source_manager.child_value_type_references
    elif rel_type == "key":
        references = source_manager.child_key_type_references
    else:
        raise FatalError()

    for sub_type in references[key][id(source_type)]:
        value_manager.remove_composite_type(sub_type)

    references[key][id(source_type)] = []


class CompositeObjectManager(object):
    def __init__(self, obj):
        self.obj = obj
        self.attached_types = {}
        self.attached_type_counts = defaultdict(int)
        self.child_key_type_references = defaultdict(lambda: defaultdict(list))
        self.child_value_type_references = defaultdict(lambda: defaultdict(list))

        self.cached_effective_composite_type = None

        self.default_factory = None
        self.debug_reason = None

    def get_effective_composite_type(self):
        if not self.cached_effective_composite_type:
            self.cached_effective_composite_type = merge_composite_types(self.attached_types.values(), self.obj, "Composed from {}".format(self.debug_reason))
        return self.cached_effective_composite_type

    def check_for_runtime_data_conflicts(self, type):
        if isinstance(type, AnyType):
            return False
        if isinstance(type, OneOfType):
            for subtype in type.types:
                if not self.check_for_runtime_data_conflicts_with_composite_type(subtype):
                    return False
            return True
        if isinstance(type, CompositeType):
            return self.check_for_runtime_data_conflicts_with_composite_type(type)
        return True

    def check_for_runtime_data_conflicts_with_composite_type(self, type):
        for micro_op_type in type.micro_op_types.values():
            if micro_op_type.check_for_runtime_data_conflict(self.obj):
                return True
        return False

    def check_for_runtime_micro_op_conflicts(self, type):
        new_merged_composite_type = merge_composite_types([ self.get_effective_composite_type(), type ], "check_for_runtime_micro_op_conflicts")

        for micro_op_type in type.micro_op_types.values():
            micro_op_type.check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(
                self.obj, new_merged_composite_type.micro_op_types
            )

    def add_composite_type(self, type, caller_has_verified_type=False):
        type_id = id(type)

        if type.is_revconst:
            raise FatalError()

        new = self.attached_type_counts.get(type_id, 0) == 0 

        type.check_internal_python_object_type(self.obj)

        if new:
            if is_debug() or not caller_has_verified_type:
                if self.check_for_runtime_data_conflicts(type):
                    type.check_internal_python_object_type(self.obj)
                    self.check_for_runtime_data_conflicts(type)
                    raise MicroOpTypeConflict(self.obj, type)

                self.check_for_runtime_micro_op_conflicts(type)

            self.cached_effective_composite_type = None
            self.attached_types[type_id] = type

            for tag, micro_op_type in type.micro_op_types.items():
                micro_op_type.bind(type, None, self)

        self.attached_type_counts[type_id] += 1

    def remove_composite_type(self, type):
        type_id = id(type)

#        from rdhlang5.type_system.object_types import RDHObject
#        if isinstance(self.obj, RDHObject) and hasattr(self.obj, "j"):
#            print "Removing {} {} {} {} {}".format(id(self.obj), self.obj.__dict__, id(type), type.name, self.attached_type_counts[type_id])

        if self.attached_type_counts.get(type_id, 0) > 0:
            self.attached_type_counts[type_id] -= 1

        dead = self.attached_type_counts.get(type_id, 0) == 0

        if dead:
            self.cached_effective_composite_type = None
            del self.attached_types[type_id]
            del self.attached_type_counts[type_id]

            for tag, micro_op_type in type.micro_op_types.items():
                micro_op_type.unbind(type, None, self)

    def get_micro_op_type(self, tag):
        effective_composite_type = self.get_effective_composite_type()
        return effective_composite_type.micro_op_types.get(tag, None)

    def get_flattened_micro_op_types(self):
        return self.get_effective_composite_type().micro_op_types.values()

    def unbind_key(self, key):
        for attached_type in self.attached_types.values():
            for other_micro_op_type in attached_type.micro_op_types.values():
                other_micro_op_type.unbind(attached_type, key, self)

    def bind_key(self, key):
        for attached_type in self.attached_types.values():
            for other_micro_op_type in attached_type.micro_op_types.values():
                other_micro_op_type.bind(attached_type, key, self)

class DefaultFactoryType(MicroOpType):
    def __init__(self, type):
        self.type = type

    def create(self, target):
        return DefaultFactory(target)

    def can_be_derived_from(self, other_micro_op):
        return self.type.is_copyable_from(other_micro_op.type)

    def replace_inferred_type(self, other_micro_op_type):
        return self

    def bind(self, source_type, key, target):
        pass

    def unbind(self, source_type, key, target):
        pass

    def merge(self, other_micro_op_type):
        raise FatalError()

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if get_manager(obj, "defaultfactory.check_for_runtime_data_conflict").default_factory is None:
            raise MicroOpTypeConflict()

class DefaultFactory(MicroOp):
    def __init__(self, target_manager):
        self.target_manager = target_manager

    def invoke(self, key, **kwargs):
        return self.target_manager.default_factory(self.target_manager.obj, key)
