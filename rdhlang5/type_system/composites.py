from collections import defaultdict
from contextlib import contextmanager
import threading
import weakref

from rdhlang5.type_system.core_types import Type, unwrap_types, OneOfType, \
    AnyType, merge_types
from rdhlang5.type_system.exceptions import FatalError, IsNotCompositeType, \
    CompositeTypeIncompatibleWithTarget, CompositeTypeIsInconsistent, \
    DanglingInferredType
from rdhlang5.type_system.managers import get_manager, get_type_of_value
from rdhlang5.type_system.micro_ops import merge_composite_types, MicroOpType
from rdhlang5.utils import MISSING
from __builtin__ import True


class InferredType(Type):
    def is_copyable_from(self, other):
        raise FatalError()

    def replace_inferred_types(self, other, cache=None):
        return other

    def __repr__(self):
        return "Inferred"

composite_type_is_copyable_cache = threading.local()


@contextmanager
def temporary_bind(value, composite_type):
    if not isinstance(composite_type, CompositeType):
        raise FatalError()

    manager = get_manager(value)
    try:
        manager.add_composite_type(composite_type)
        yield
    finally:
        manager.remove_composite_type(composite_type)


class CompositeType(Type):
    def __init__(self, micro_op_types, name=None):
        if not isinstance(micro_op_types, dict):
            raise FatalError()
        for tag in micro_op_types.keys():
            if not isinstance(tag, tuple):
                raise FatalError()

        self.micro_op_types = micro_op_types
        self.name = name or "unknown"
        self._is_self_consistent = None

    def replace_inferred_types(self, other, cache=None):
        if cache is None:
            cache = {}

        cache_key = (id(self), id(other))

        if cache_key in cache:
            return cache[cache_key]

        name = getattr(other, "name", "Unknown")
        result = CompositeType({},
            name="inferred<{} & {}>".format(self.name, name)
        )

        cache[cache_key] = result

        for key, micro_op_type in self.micro_op_types.items():
            if key == ("set", "_temp"):
                pass
            if isinstance(other, CompositeType):
                other_micro_op_type = other.micro_op_types.get(key, None)
            else:
                other_micro_op_type = None

            if other_micro_op_type:
                result.micro_op_types[key] = micro_op_type.replace_inferred_type(other_micro_op_type, cache)
            else:
                result.micro_op_types[key] = micro_op_type

        return result

#     def apply_consistency_heuristic(self, other_micro_ops):
#         # Takes an inconsistent type and hacks it to be consistent, based on our rules of thumb
#         if self.is_self_consistent():
#             return self
# 
#         potential_replacement_opcodes = {}
# 
#         for key, micro_op_type in self.micro_op_types.items():
#             new_micro_op = micro_op_type.apply_consistency_heuristic(self.micro_op_types)
#             if new_micro_op:
#                 potential_replacement_opcodes[key] = new_micro_op
# 
#         return CompositeType(
#             potential_replacement_opcodes,
#             name="reified<{}>".format(self.name)
#         )

    def get_micro_op_type(self, tag):
        return self.micro_op_types.get(tag, None)

#     def check_internal_python_object_type(self, obj):
#         if not self.python_object_type_checker(obj):
#             raise IncorrectObjectTypeForMicroOp()

    def is_self_consistent(self):
        if self._is_self_consistent is None:
            self._is_self_consistent = True
            for micro_op in self.micro_op_types.values():
                if micro_op.conflicts_with(self, self):
                    self._is_self_consistent = False
                    break
        return self._is_self_consistent

#     def internal_is_copyable_from(self, other):
#         raise ValueError()
#         if not isinstance(other, CompositeType):
#             return IsNotCompositeType()
# 
#         if not other.is_revconst:
#             for ours in self.micro_op_types.values():
#                 for theirs in other.micro_op_types.values():
#                     if ours.check_for_new_micro_op_type_conflict(theirs, self.micro_op_types):
#                         ours.check_for_new_micro_op_type_conflict(theirs, self.micro_op_types)
#                         return ConflictingMicroOpTypes()
# 
#         for our_tag, our_micro_op in self.micro_op_types.items():
#             their_micro_op = other.micro_op_types.get(our_tag, None)
# 
#             only_safe_with_initial_data = False
#             if their_micro_op is None:
#                 only_safe_with_initial_data = True
#             if their_micro_op and not our_micro_op.can_be_derived_from(their_micro_op):
#                 only_safe_with_initial_data = True
# 
#             if only_safe_with_initial_data:
#                 if other.initial_data is None:
#                     return NoInitialData()
#                 if our_micro_op.check_for_runtime_data_conflict(other.initial_data):
#                     our_micro_op.check_for_runtime_data_conflict(other.initial_data)
#                     return RuntimeInitialDataConflict(our_micro_op, other.initial_data)
# 
#         return True

    def is_copyable_from(self, other):
        if self is other:
            return True        
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self)
        if not isinstance(other, CompositeType):
            return IsNotCompositeType()
        if self.micro_op_types is other.micro_op_types:
            return True

        try:
            cache_initialized_here = False
            if getattr(composite_type_is_copyable_cache, "_is_copyable_from_cache", None) is None:
                composite_type_is_copyable_cache._is_copyable_from_cache = {}
                cache_initialized_here = True
            cache = composite_type_is_copyable_cache._is_copyable_from_cache

            result_key = (id(self), id(other))

            if result_key in cache:
                return cache[result_key]

            cache[result_key] = True

            for micro_op_type in self.micro_op_types.values():
                if not micro_op_type.is_derivable_from(other):
                    cache[result_key] = False
                    break
        finally:
            if cache_initialized_here:
                composite_type_is_copyable_cache._is_copyable_from_cache = None

        return cache[result_key]

#     def old_is_copyable_from(self, other):
#         raise ValueError()
#         if self is other:
#             return True
# 
#         if isinstance(other, TopType):
#             return True
#         if isinstance(other, OneOfType):
#             return other.is_copyable_to(self)
# 
#         if not isinstance(other, CompositeType):
#             return IsNotCompositeType()
# 
#         if self.micro_op_types is other.micro_op_types:
#             return True
# 
#         try:
#             cache_started_empty = False
#             if getattr(composite_type_is_copyable_cache, "_is_copyable_from_cache", None) is None:
#                 composite_type_is_copyable_cache._is_copyable_from_cache = defaultdict(lambda: defaultdict(lambda: None))
#                 cache_started_empty = True
#             cache = composite_type_is_copyable_cache._is_copyable_from_cache
# 
#             result = None# results_by_target_id[id(self)][id(other)]
# 
#             # Debugging check
# #            if result is False:
# #                check = self.internal_is_copyable_from(other)
# #                if check is True:
# #                    self.internal_is_copyable_from(other)
# #                    raise FatalError()
# 
#             if result is None:
#                 result = cache[id(self)][id(other)]
#             if result is not None:
#                 return result
# 
#             cache[id(self)][id(other)] = True
#             cache[id(other)][id(self)] = True
# 
#             result = self.internal_is_copyable_from(other)
# 
#             cache[id(self)][id(other)] = result
#             cache[id(other)][id(self)] = result
# 
#             if cache_started_empty:
#                 source_weakref = weakrefs_for_type.get(id(other), None)
#                 if source_weakref is None:
#                     source_weakref = weakref.ref(other, type_cleared)
#                     weakrefs_for_type[id(other)] = source_weakref
#                     type_ids_for_weakref_id[id(source_weakref)] = id(other)
# 
#                 target_weakref = weakrefs_for_type.get(id(self), None)
#                 if target_weakref is None:
#                     target_weakref = weakref.ref(self, type_cleared)
#                     weakrefs_for_type[id(self)] = target_weakref
#                     type_ids_for_weakref_id[id(target_weakref)] = id(self)
# 
#                 if target_weakref is not None and target_weakref() is not self:
#                     raise FatalError()
#                 if source_weakref is not None and source_weakref() is not other:
#                     raise FatalError()
# 
#                 results_by_target_id[id(self)][id(other)] = result
#                 results_by_source_id[id(other)][id(self)] = result
# 
#                 # At the moment, garbage collecting types completely breaks composite type comparison.
#                 # Until I'm able to fix, let's keep strong references, leak like hell
#                 strong_links[id(self)] = self
#                 strong_links[id(other)] = other
#         finally:
#             if cache_started_empty:
#                 composite_type_is_copyable_cache._is_copyable_from_cache = None
# 
#         return result

    def __repr__(self):
        return "Composite<{}>".format(", ".join([str(m) for m in self.micro_op_types.values()]))

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

# def bind_type_to_manager(source_manager, source_type, key, rel_type, type, value_manager):
#     if not source_manager or not value_manager:
#         return
# 
#     something_worked = False
#     error_if_all_fails = None
# 
#     for sub_type in unwrap_types(type):
#         if isinstance(sub_type, CompositeType):
#             try:
#                 value_manager.add_composite_type(sub_type)
#                 if rel_type == "value":
#                     source_manager.child_value_type_references[key][id(source_type)].append(sub_type)
#                 elif rel_type == "key":
#                     source_manager.child_key_type_references[key][id(source_type)].append(sub_type)
#                 else:
#                     raise FatalError()
#                 something_worked = True
#             except IncorrectObjectTypeForMicroOp:
#                 pass
#             except MicroOpTypeConflict as e:
#                 error_if_all_fails = capture_raise(MicroOpTypeConflict, e)
#         else:
#             something_worked = True
# 
#     if not something_worked:
#         if error_if_all_fails:
#             raise error_if_all_fails[0], error_if_all_fails[1], error_if_all_fails[2]
#         else:
#             raise FatalError()
# 
# def unbind_type_to_manager(source_manager, source_type, key, rel_type, value_manager):
#     if not source_manager or not value_manager:
#         return
# 
#     references = None
#     if rel_type == "value":
#         references = source_manager.child_value_type_references
#     elif rel_type == "key":
#         references = source_manager.child_key_type_references
#     else:
#         raise FatalError()
# 
#     for sub_type in references[key][id(source_type)]:
#         value_manager.remove_composite_type(sub_type)
# 
#     references[key][id(source_type)] = []

class CompositeObjectManager(object):
    def __init__(self, obj, on_gc_callback):
        self.obj_ref = weakref.ref(obj, self.obj_gced)
        self.obj_id = id(obj)
        self.attached_types = {}
        self.attached_type_counts = defaultdict(int)
#         self.child_key_type_references = defaultdict(lambda: defaultdict(list))
#         self.child_value_type_references = defaultdict(lambda: defaultdict(list))
        self.on_gc_callback = on_gc_callback

        from rdhlang5.type_system.default_composite_types import EMPTY_COMPOSITE_TYPE

        self.cached_effective_composite_type = EMPTY_COMPOSITE_TYPE

        self.default_factory = None
        self.debug_reason = None

    def get_obj(self):
        return self.obj_ref()

    def obj_gced(self, _):
        self.on_gc_callback(self.obj_id)

    def get_effective_composite_type(self):
        if not self.cached_effective_composite_type:
            obj = self.get_obj()
            self.cached_effective_composite_type = merge_composite_types(self.attached_types.values(), name="Composed from {}".format(self.debug_reason))
        return self.cached_effective_composite_type

    def attach_type(self, new_type, multiplier=1):
        new_type_id = id(new_type)

        if self.attached_type_counts[new_type_id] == 0:
            self.cached_effective_composite_type = None

        self.attached_types[new_type_id] = new_type
        self.attached_type_counts[new_type_id] += multiplier

    def detach_type(self, remove_type, multiplier=1):
        remove_type_id = id(remove_type)
        if remove_type_id not in self.attached_type_counts:
            raise FatalError()
        self.attached_type_counts[remove_type_id] -= multiplier
        if self.attached_type_counts[remove_type_id] < 0:
            raise FatalError()
        if self.attached_type_counts[remove_type_id] == 0:
            self.cached_effective_composite_type = None
            del self.attached_types[remove_type_id]
            del self.attached_type_counts[remove_type_id]

    def get_micro_op_type(self, tag):
        effective_composite_type = self.get_effective_composite_type()
        return effective_composite_type.micro_op_types.get(tag, None)

    def add_composite_type(self, new_type):
        # TODO: remove
        add_composite_type(self, new_type)

    def remove_composite_type(self, remove_type):
        # TODO: remove
        remove_composite_type(self, remove_type)

#     def check_for_runtime_data_conflicts(self, type):
#         if isinstance(type, AnyType):
#             return False
#         if isinstance(type, OneOfType):
#             for subtype in type.types:
#                 if not self.check_for_runtime_data_conflicts_with_composite_type(subtype):
#                     return False
#             return True
#         if isinstance(type, CompositeType):
#             return self.check_for_runtime_data_conflicts_with_composite_type(type)
#         return True
# 
#     def check_for_runtime_data_conflicts_with_composite_type(self, type):
#         for micro_op_type in type.micro_op_types.values():
#             if micro_op_type.check_for_runtime_data_conflict(self.obj):
#                 return True
#         return False

#     def check_for_runtime_micro_op_conflicts(self, type):
#         new_merged_composite_type = merge_composite_types([ self.get_effective_composite_type(), type ], name="check_for_runtime_micro_op_conflicts")
# 
#         for micro_op_type in type.micro_op_types.values():
#             micro_op_type.check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(
#                 self.obj, new_merged_composite_type.micro_op_types
#             )

#     def add_composite_type(self, new_type, caller_has_verified_type=False):
#         if not isinstance(new_type, CompositeType):
#             raise FatalError()
#         type_id = id(new_type)
# 
#         new = self.attached_type_counts.get(type_id, 0) == 0 
# 
#         if not new_type.is_self_consistent():
#             raise MicroOpTypeConflict()
# 
#         obj = self.get_obj()
# 
#         new_type.check_internal_python_object_type(obj)
#         existing_type = self.get_effective_composite_type()
# 
#         if new:
#             if is_debug() or not caller_has_verified_type:
#                 new_type.check_internal_python_object_type(obj)
#                 for micro_op in new_type.micro_op_types.values():
#                     if not micro_op.is_derivable_from(existing_type, obj):
#                         micro_op.is_derivable_from(existing_type, obj)
#                         raise MicroOpCannotBeDerived(micro_op, existing_type, obj)
# 
#                     if micro_op.conflicts_with(new_type, existing_type):
#                         raise MicroOpTypeConflict(obj, new_type)
# 
#             self.cached_effective_composite_type = None
#             self.attached_types[type_id] = new_type
# 
#             for tag, micro_op_type in new_type.micro_op_types.items():
#                 micro_op_type.bind(new_type, None, self)
# 
#         self.attached_type_counts[type_id] += 1
# 
#     def old_add_composite_type(self, type, caller_has_verified_type=False):
# #        if self.debug_reason is None:
# #            print self.debug_reason
#         type_id = id(type)
# 
#         if type.is_revconst:
#             raise FatalError()
# 
#         new = self.attached_type_counts.get(type_id, 0) == 0 
# 
#         type.check_internal_python_object_type(self.obj)
# 
#         if new:
#             if is_debug() or not caller_has_verified_type:
#                 if self.check_for_runtime_data_conflicts(type):
#                     type.check_internal_python_object_type(self.obj)
#                     self.check_for_runtime_data_conflicts(type)
#                     raise MicroOpTypeConflict(self.obj, type)
# 
#                 self.check_for_runtime_micro_op_conflicts(type)
# 
#             self.cached_effective_composite_type = None
#             self.attached_types[type_id] = type
# 
#             for tag, micro_op_type in type.micro_op_types.items():
#                 micro_op_type.bind(type, None, self)
# 
#         self.attached_type_counts[type_id] += 1
# 
#     def remove_composite_type(self, type):
#         type_id = id(type)
# 
# #        from rdhlang5.type_system.object_types import RDHObject
# #        if isinstance(self.obj, RDHObject) and hasattr(self.obj, "j"):
# #            print "Removing {} {} {} {} {}".format(id(self.obj), self.obj.__dict__, id(type), type.name, self.attached_type_counts[type_id])
# 
#         if self.attached_type_counts.get(type_id, 0) > 0:
#             self.attached_type_counts[type_id] -= 1
# 
#         dead = self.attached_type_counts.get(type_id, 0) == 0
# 
#         if dead:
#             self.cached_effective_composite_type = None
#             if type_id in self.attached_types:
#                 del self.attached_types[type_id]
#                 del self.attached_type_counts[type_id]
# 
#             for tag, micro_op_type in type.micro_op_types.items():
#                 micro_op_type.unbind(type, None, self)

#     def get_flattened_micro_op_types(self):
#         return self.get_effective_composite_type().micro_op_types.values()

#     def bind_key(self, key):
#         for attached_type in self.attached_types.values():
#             for other_micro_op_type in attached_type.micro_op_types.values():
#                 other_micro_op_type.bind(attached_type, key, self)
# 
#     def unbind_key(self, key):
#         for attached_type in self.attached_types.values():
#             for other_micro_op_type in attached_type.micro_op_types.values():
#                 other_micro_op_type.unbind(attached_type, key, self)

# def add_composite_type(target, new_type):
#     if not isinstance(new_type, CompositeType):
#         raise FatalError()
# 
#     if not new_type.is_self_consistent():
#         raise FatalError()
# 
#     flat_micro_ops = {}
#     flatten_composite_type(new_type, target, flat_micro_ops)
# 
#     for obj_type, obj, micro_op, op_type, _ in flat_micro_ops.values():
#         if isinstance(op_type, CompositeType):
#             effective_target_type = get_manager(obj).get_effective_composite_type()
#             if micro_op.conflicts_with(obj_type, effective_target_type):
#                 raise MicroOpConflict()
#         else:
#             if not micro_op.is_bindable_to(obj):
#                 raise MicroOpCannotBeBound(micro_op)
# 
#     # Finally attach everything
#     get_manager(target).attach_type(new_type)
#     for _, _, micro_op, op_type, value in flat_micro_ops.values():
#         if isinstance(op_type, CompositeType):
#             get_manager(value).attach_type(op_type)
# 
# def build_bindings_for_micro_op(origin_micro_op, target, type, results):
#     if not isinstance(type, CompositeType):
#         raise FatalError()
# 
#     if not type.is_self_consistent():
#         raise FatalError()
# 
#     result_key = (id(origin_micro_op), id(target), id(type))
#     result_if_true = (origin_micro_op, target, type)
# 
#     if result_key in results:
#         return bool(results[result_key])
# 
#     expanded_micro_ops = [
#         (micro_op, micro_op.prepare_bind()) for micro_op in type.micro_op_types.values()
#     ]
# 
#     results[result_key] = result_if_true
# 
#     for micro_op, (values, micro_op_type) in expanded_micro_ops:
#         at_least_one_worked = False
#         for sub_micro_op_type in unwrap_types(micro_op_type):
#             for value in values:
#                 if not isinstance(sub_micro_op_type, CompositeType):
#                     if micro_op.is_bindable_to(value):
#                         at_least_one_worked = True
#                 else:
#                     if build_bindings_for_micro_op(micro_op, value, sub_micro_op_type, results):
#                         at_least_one_worked = True
#         if not at_least_one_worked:
#             results[result_key] = None
# 
# 
# def remove_composite_type(target, remove_type):
#     flat_micro_ops = {}
#     flatten_composite_type(remove_type, target, flat_micro_ops)
# 
#     for _, _, micro_op, op_type, value in flat_micro_ops.values():
#         if isinstance(op_type, CompositeType):
#             get_manager(value).detach_type(op_type)

# def check_micro_op_chain(origin_micro_op, type, target, chain, results):
#     result_key = (id(origin_micro_op), id(type), id(target))
# 
#     if result_key in results:
#         return results[result_key], True
# 
#     results[result_key] = True
# 
#     flat = {}
#     flatten_composite_type(type, target, flat)
# 
#     end_of_chain = True
# 
#     for source_type, source_value, micro_op, target_type, target_value in flat.values():
#         if not isinstance(target_type, OneOfType):
#             if micro_op.is_bindable_to(source_value):
#                 chain.append(source_type, source_value, micro_op, target_type, target_value)
#             else:
#                 results[result_key] = False
#                 return
# 
#     for source_type, source_value, micro_op, target_type, target_value in flat.values():
#         if isinstance(target_type, OneOfType):
#             for sub_target_type in unwrap_types(target_type):
#                 sub_chain = list(chain)
#                 sub_result, already_calced = check_micro_op_chain(sub_target_type, target_value, sub_chain)
#                 if not sub_result:
#                     results[result_key] = False
#                     return
#                 end_of_chain = end_of_chain and already_calced
# 
#     if end_of_chain:
#         attach_chain(chain)
# 
#     return True

def check_dangling_inferred_types(type, results_cache=None):
    if results_cache is None:
        results_cache = {}

    cache_key = id(type)

    if cache_key in results_cache:
        return results_cache[cache_key]

    results_cache[cache_key] = True

    if isinstance(type, InferredType):
        return False

    if isinstance(type, CompositeType):
        for key, micro_op_type in type.micro_op_types.items():
            value_type = getattr(micro_op_type, "value_type", None)
            if value_type:
                if not check_dangling_inferred_types(value_type):
                    return False

    return True

def prepare_lhs_type(type, guide_type, results_cache=None):
    if isinstance(type, InferredType):
        if guide_type is None:
            raise DanglingInferredType()
        return prepare_lhs_type(guide_type, None, results_cache=results_cache)

    if isinstance(type, CompositeType):
        return prepare_composite_lhs_type(type, guide_type, results_cache)

    if isinstance(type, OneOfType):
        if guide_type is None:
            return type
        # TODO
        raise FatalError()

    return type

def prepare_composite_lhs_type(composite_type, guide_type, results_cache=None):
    if hasattr(composite_type, "_prepared_lhs_type"):
        return composite_type

    if results_cache is None:
        results_cache = {}

    cache_key = (id(composite_type), id(guide_type))

    if cache_key in results_cache:
        return results_cache[cache_key]

    result = CompositeType(
        dict(composite_type.micro_op_types),
        name="LHSPrepared<{}>".format(composite_type.name)
    )

    result._prepared_lhs_type = True

    results_cache[cache_key] = result
    something_changed = False

    for tag, micro_op in result.micro_op_types.items():
        getter = None
        if hasattr(micro_op, "value_type") and isinstance(micro_op.value_type, (AnyType, InferredType)):
            if tag[0] == "set":
                getter = result.get_micro_op_type(("get", tag[1]))
            if tag[0] == "set-wildcard":
                getter = result.get_micro_op_type(("get-wildcard", ))
        if getter:
            if micro_op.value_type is not getter.value_type:
                result.micro_op_types[tag] = micro_op.clone(value_type=getter.value_type)
                something_changed = True

    for tag, micro_op in result.micro_op_types.items():
        if hasattr(micro_op, "value_type"):
            guide_micro_op_type = None

            if isinstance(guide_type, CompositeType):
                guide_op = guide_type.get_micro_op_type(tag)

                if hasattr(guide_op, "value_type") and isinstance(guide_op.value_type, AnyType):
                    if tag[0] == "set":
                        guide_op = guide_type.get_micro_op_type(( "get", tag[1] ))
                    if tag[0] == "set-wildcard":
                        guide_op = guide_type.get_micro_op_type(( "get-wildcard" ))

                if hasattr(guide_op, "value_type"):
                    guide_micro_op_type = guide_op.value_type

            new_value_type = prepare_lhs_type(micro_op.value_type, guide_micro_op_type, results_cache)

            if micro_op.value_type is not new_value_type:
                result.micro_op_types[tag] = micro_op.clone(
                    value_type=prepare_lhs_type(micro_op.value_type, guide_micro_op_type, results_cache)
                )
                something_changed = True

    right_shifts = []
    left_shifts = []

    for tag, micro_op in result.micro_op_types.items():
        if tag[0] == "insert":
            right_shifts.append((tag[1], micro_op.value_type))
        if tag[0] == "insert-wildcard":
            right_shifts.append((0, micro_op.value_type))

        if tag[0] == "delete":
            left_shifts.append(tag[1])
        if tag[0] == "delete-wildcard":
            left_shifts.append(0)

    positional_getter_micro_ops = sorted(
        [m for t, m in result.micro_op_types.items() if t[0] == "get" and len(t) == 2 and isinstance(t[1], int)],
        key=lambda m: m.key
    )

    for starting_index, starting_type in right_shifts:
        cumulative_types = [ starting_type ]
        for getter_micro_op in positional_getter_micro_ops:
            if getter_micro_op.key >= starting_index:
                cumulative_types = cumulative_types + [ getter_micro_op.value_type ]
                result.micro_op_types[("get", getter_micro_op.key)] = getter_micro_op.clone(
                    value_type=merge_types(cumulative_types, "super")
                )
                something_changed = True

    positional_getter_micro_ops = sorted(
        [m for t, m in result.micro_op_types.items() if t[0] == "get" and len(t) == 2 and isinstance(t[1], int)],
        key=lambda m: m.key
    )

    for starting_index in left_shifts:
        cumulative_types = []
        for getter_micro_op in reversed(positional_getter_micro_ops):
            if getter_micro_op.key >= starting_index:
                cumulative_types.append(getter_micro_op.value_type)
                result.micro_op_types[("get", getter_micro_op.key)] = getter_micro_op.clone(
                    value_type=merge_types(cumulative_types, "super"),
                    key_error=True
                )
                something_changed = True

    if not something_changed:
        result.micro_op_types = composite_type.micro_op_types

    return result

# 
# 
#     for key, micro_op_type in composite_type.micro_op_types.items():
# 
#         value_type = getattr(micro_op_type, "value_type", None)
# 
#         if not value_type:
#             continue
# 
#         if not isinstance(other_type, CompositeType):
#             continue
# 
#         other_micro_op_type = other_type.micro_op_types.get(key, None)
# 
#         other_value_type = getattr(other_micro_op_type, "value_type", None)
# 
#         if other_value_type is None:
#             continue
# 
#         result.micro_op_types[key] = micro_op_type.clone(
#             value_type=replace_inferred_types(value_type, other_value_type, results_cache)
#         )
#
#    return result

# def replace_inferred_types(type, other_type, results_cache=None):
#     if isinstance(type, CompositeType):
#         return replace_composite_inferred_types(type, other_type, results_cache)
#     elif isinstance(type, InferredType):
#         return other_type
#     elif isinstance(type, OneOfType):
#         # TODO
#         raise FatalError()
#     else:
#         return type
# 
# def replace_composite_inferred_types(composite_type, other_type, results_cache=None):
#     if results_cache is None:
#         results_cache = {}
# 
#     cache_key = (id(composite_type), id(other_type))
# 
#     if cache_key in results_cache:
#         return results_cache[cache_key]
# 
#     result = CompositeType(
#         dict(composite_type.micro_op_types),
#         name="Inferred<{}>".format(composite_type.name)
#     )
# 
#     for key, micro_op_type in composite_type.micro_op_types.items():
#         value_type = getattr(micro_op_type, "value_type", None)
# 
#         if not value_type:
#             continue
# 
#         if not isinstance(other_type, CompositeType):
#             continue
# 
#         other_micro_op_type = other_type.micro_op_types.get(key, None)
# 
#         other_value_type = getattr(other_micro_op_type, "value_type", None)
# 
#         if other_value_type is None:
#             continue
# 
#         result.micro_op_types[key] = micro_op_type.clone(
#             value_type=replace_inferred_types(value_type, other_value_type, results_cache)
#         )
# 
#     results_cache[cache_key] = result
# 
#     return result
# 
# def apply_consistency_heiristic(composite_type, results_cache=None):
# #    if composite_type.is_self_consistent():
# #        return composite_type
# 
#     if results_cache is None:
#         results_cache = {}
# 
#     if id(composite_type) in results_cache:
#         return results_cache[id(composite_type)]
# 
#     result_composite_type = CompositeType(dict(composite_type.micro_op_types), "Heiristic: {}".format(composite_type.name))
#     results_cache[id(result_composite_type)] = result_composite_type
# 
#     for tag, micro_op in result_composite_type.micro_op_types.items():
#         if hasattr(micro_op, "value_type") and isinstance(micro_op.value_type, CompositeType):
#             result_composite_type.micro_op_types[tag] = micro_op.clone(
#                 value_type=apply_consistency_heiristic(micro_op.value_type, results_cache)
#             )
# 
#     for tag, micro_op in result_composite_type.micro_op_types.items():
#         if tag[0] == "set" and isinstance(micro_op.value_type, (AnyType, InferredType)):
#             getter = result_composite_type.micro_op_types[("get", tag[1])]
#             result_composite_type.micro_op_types[tag] = micro_op.clone(value_type=getter.value_type)
#         if tag[0] == "set-wildcard" and isinstance(micro_op.value_type, (AnyType, InferredType)):
#             getter = result_composite_type.micro_op_types[("get-wildcard", )]
#             result_composite_type.micro_op_types[tag] = micro_op.clone(value_type=getter.value_type)
# 
#     right_shifts = []
#     left_shifts = []
# 
#     for tag, micro_op in result_composite_type.micro_op_types.items():
#         if tag[0] == "insert":
#             right_shifts.append((tag[1], micro_op.value_type))
#         if tag[0] == "insert-wildcard":
#             right_shifts.append((0, micro_op.value_type))
# 
#         if tag[0] == "delete":
#             left_shifts.append(tag[1])
#         if tag[0] == "delete-wildcard":
#             left_shifts.append(0)
# 
#     positional_getter_micro_ops = sorted(
#         [m for t, m in result_composite_type.micro_op_types.items() if t[0] == "get" and len(t) == 2 and isinstance(t[1], int)],
#         key=lambda m: m.key
#     )
# 
#     for starting_index, starting_type in right_shifts:
#         cumulative_types = [ starting_type ]
#         for getter_micro_op in positional_getter_micro_ops:
#             if getter_micro_op.key >= starting_index:
#                 cumulative_types = cumulative_types + [ getter_micro_op.value_type ]
#                 result_composite_type.micro_op_types[("get", getter_micro_op.key)] = getter_micro_op.clone(
#                     value_type=merge_types(cumulative_types, "super")
#                 )
# 
#     positional_getter_micro_ops = sorted(
#         [m for t, m in result_composite_type.micro_op_types.items() if t[0] == "get" and len(t) == 2 and isinstance(t[1], int)],
#         key=lambda m: m.key
#     )
# 
#     for starting_index in left_shifts:
#         cumulative_types = []
#         for getter_micro_op in reversed(positional_getter_micro_ops):
#             if getter_micro_op.key >= starting_index:
#                 cumulative_types.append(getter_micro_op.value_type)
#                 result_composite_type.micro_op_types[("get", getter_micro_op.key)] = getter_micro_op.clone(
#                     value_type=merge_types(cumulative_types, "super"),
#                     key_error=True
#                 )
# 
#     return result_composite_type

def add_composite_type(target_manager, new_type, key_filter=None, multiplier=1):
    types_to_bind = {}
    succeeded = build_binding_map_for_type(None, new_type, target_manager.get_obj(), target_manager, key_filter, MISSING, {}, types_to_bind)
    if len(types_to_bind) > 100:
        pass
    if not succeeded:
        raise CompositeTypeIncompatibleWithTarget()

    for _, type, target in types_to_bind.values():
        get_manager(target).attach_type(type, multiplier=multiplier)


def remove_composite_type(target_manager, remove_type, key_filter=None, multiplier=1):
    types_to_bind = {}
    succeeded = build_binding_map_for_type(None, remove_type, target_manager.get_obj(), target_manager, key_filter, MISSING, {}, types_to_bind)
    if len(types_to_bind) > 100:
        pass
    if not succeeded:
        raise CompositeTypeIncompatibleWithTarget()

    for _, type, target in types_to_bind.values():
        get_manager(target).detach_type(type, multiplier=multiplier)

def can_add_composite_type_with_filter(target, new_type, key_filter, substitute_value):
    return build_binding_map_for_type(None, new_type, target, get_manager(target), key_filter, substitute_value, {}, {})

def is_type_bindable_to_value(value, type):
    return build_binding_map_for_type(None, type, value, get_manager(value), None, MISSING, {}, {})

def bind_key(manager, key_filter):
    for attached_type in manager.attached_types.values():
        add_composite_type(
            manager,
            attached_type,
            key_filter=key_filter,
            multiplier=manager.attached_type_counts[id(attached_type)]
        )


def unbind_key(manager, key_filter):
    for attached_type in manager.attached_types.values():
        remove_composite_type(
            manager,
            attached_type,
            key_filter=key_filter,
            multiplier=manager.attached_type_counts[id(attached_type)]
        )

# def bind_micro_op(target, micro_op):
#     if not isinstance(micro_op, MicroOpType):
#         raise FatalError()
#     types_to_bind = {}
#     succeeded = build_binding_map_for_micro_op(micro_op, target, {}, types_to_bind)
#     if not succeeded:
#         raise CompositeTypeIncompatibleWithTarget()
# 
#     for _, type, target in types_to_bind.values():
#         get_manager(target).attach_type(type)
# 
# def unbind_micro_op(target, micro_op):
#     if not isinstance(micro_op, MicroOpType):
#         raise FatalError()
#     types_to_bind = {}
#     succeeded = build_binding_map_for_micro_op(micro_op, target, {}, types_to_bind)
#     if not succeeded:
#         raise CompositeTypeIncompatibleWithTarget()
# 
#     for _, type, target in types_to_bind.values():
#         get_manager(target).detach_type(type)

# def build_binding_map_for_micro_op(micro_op, target, key, multiplier, results, types_to_bind):
#     if not micro_op.is_bindable_to(target):
#         return False
# 
#     values, micro_op_type = micro_op.prepare_bind(target)
# 
#     types_to_bind_from_our_decendants = {}
# 
#     for value in values:
#         atleast_one_sub_type_worked = False
# 
#         for sub_micro_op_type in unwrap_types(micro_op_type):
#             if isinstance(sub_micro_op_type, CompositeType) and isinstance(value, Composite):
#                 if build_binding_map_for_type(micro_op, sub_micro_op_type, value, results, types_to_bind_from_our_decendants):
#                     atleast_one_sub_type_worked = True
#             if not isinstance(sub_micro_op_type, CompositeType) and not isinstance(value, Composite):
#                 if sub_micro_op_type.is_copyable_from(get_type_of_value(value)):
#                     atleast_one_sub_type_worked = True
# 
#         if not atleast_one_sub_type_worked:
#             return False
# 
#     types_to_bind.update(types_to_bind_from_our_decendants)
# 
#     return True
# 
# def build_binding_map_for_type(origin_micro_op, new_type, target, results, types_to_bind):
#     result_key = (id(origin_micro_op), id(new_type), id(target))
# 
#     if result_key in results:
#         return results[result_key]
# 
#     results[result_key] = True
# 
#     manager = get_manager(target)
#     target_effective_type = manager.get_effective_composite_type()
# 
#     types_to_bind_from_our_decendants = {}
# 
#     for micro_op in new_type.micro_op_types.values():
#         if micro_op.conflicts_with(new_type, target_effective_type):
#             results[result_key] = False
#             return False
# 
#         if not build_binding_map_for_micro_op(micro_op, target, results, types_to_bind_from_our_decendants):
#             results[result_key] = False
#             return False
# 
#     types_to_bind.update(types_to_bind_from_our_decendants)
#     types_to_bind[result_key] = (origin_micro_op, new_type, target)
# 
#     return True


def build_binding_map_for_type(source_micro_op, new_type, target, target_manager, key_filter, substitute_value, results, types_to_bind):
    result_key = (id(source_micro_op), id(new_type), id(target))

    if result_key in results:
        return results[result_key]

#    print "{}:{}:{}".format(id(source_micro_op), id(new_type), id(target))

    results[result_key] = True

    extra_types_to_bind = {}

    target_is_composite = isinstance(target, Composite)
    target_effective_type = None
    if target_manager:
        target_effective_type = target_manager.get_effective_composite_type()

#     if isinstance(new_type, CompositeType) and manager:
#         output = "{} => {}".format(new_type.name, manager.debug_reason)
#         if "LHSPrepared<declared-object-type> => object-template" in output:
#             pass
#         print output

#    print "{} => {}".format(new_type, type(target))

    atleast_one_sub_type_worked = False
    for sub_type in unwrap_types(new_type):
        if isinstance(sub_type, CompositeType) and target_is_composite:
            if not sub_type.is_self_consistent():
                raise CompositeTypeIsInconsistent()

            micro_ops_checks_worked = True

            for key, micro_op in sub_type.micro_op_types.items():
                if not micro_op.is_bindable_to(target):
                    micro_ops_checks_worked = False
                    break

                if micro_op.conflicts_with(sub_type, target_effective_type):
                    micro_ops_checks_worked = False
                    break

                next_targets, next_new_type = micro_op.prepare_bind(target, key_filter, substitute_value)

                for next_target in next_targets:
                    if not build_binding_map_for_type(
                        micro_op, next_new_type, next_target, get_manager(next_target), None, MISSING, results, extra_types_to_bind
                    ):
                        micro_ops_checks_worked = False
                        break

            if micro_ops_checks_worked:
                if key_filter is None:
                    extra_types_to_bind[result_key] = (source_micro_op, sub_type, target)
                atleast_one_sub_type_worked = True

        if isinstance(sub_type, AnyType):
            atleast_one_sub_type_worked = True

        if not isinstance(sub_type, CompositeType) and not target_is_composite:
            if sub_type.is_copyable_from(get_type_of_value(target)):
                atleast_one_sub_type_worked = True

    if atleast_one_sub_type_worked:
        types_to_bind.update(extra_types_to_bind)
    if not atleast_one_sub_type_worked:
        results[result_key] = False

    return atleast_one_sub_type_worked

# def flatten_composite_type(type, target, results):
#     for micro_op in type.micro_op_types.values():
#         values, micro_op_type = micro_op.prepare_bind(target)
# 
#         if not isinstance(values, list):
#             raise FatalError(micro_op)
#         if micro_op_type and not isinstance(micro_op_type, Type):
#             raise FatalError()
# 
#         for value in values:
#             map_key = (id(micro_op), id(target), id(value), id(micro_op_type))
#             if map_key not in results:
#                 if isinstance(micro_op_type, CompositeType):
#                     flatten_composite_type(micro_op_type, value, results)
#                 else:
#                     results[map_key] = (type, target, micro_op, micro_op_type, value)

# class DefaultFactoryType(MicroOpType):
#     def __init__(self, type):
#         self.type = type
# 
#     def create(self, target):
#         return DefaultFactory(target)
# 
#     def invoke(self, target_manager, key):
#         return target_manager.default_factory(target_manager.obj, key)
# 
#     def is_derivable_from(self, type, data):
#         other_default_factory = type.get_micro_op_type(("default-factory", ))
#         return other_default_factory and self.type.is_copyable_from(other_default_factory.type)
# 
#     def conflicts_with(self, our_type, other_type):
#         return False
# 
#     def replace_inferred_type(self, other_micro_op_type):
#         return self
# 
#     def bind(self, source_type, key, target):
#         pass
# 
#     def unbind(self, source_type, key, target):
#         pass
# 
#     def merge(self, other_micro_op_type):
#         raise FatalError()
# 
#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         return False
# 
#     def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
#         pass
# 
#     def check_for_runtime_data_conflict(self, obj):
#         if get_manager(obj, "defaultfactory.check_for_runtime_data_conflict").default_factory is None:
#             raise MicroOpTypeConflict()
