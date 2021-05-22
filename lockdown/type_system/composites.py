# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import defaultdict
from contextlib import contextmanager
import threading
import weakref

from lockdown.type_system.core_types import Type, unwrap_types, OneOfType, \
    AnyType, merge_types
from lockdown.type_system.exceptions import FatalError, IsNotCompositeType, \
    CompositeTypeIncompatibleWithTarget, CompositeTypeIsInconsistent, \
    DanglingInferredType
from lockdown.type_system.managers import get_manager, get_type_of_value
from lockdown.type_system.micro_ops import merge_composite_types
from lockdown.type_system.reasoner import Reasoner, DUMMY_REASONER
from lockdown.utils import MISSING


composite_type_is_copyable_cache = threading.local()

class CompositeType(Type):
    """
    A Product Type for Lockdown: https://en.wikipedia.org/wiki/Product_type

    Can be thought of as a value that contains several other types at the same time.

    In Lockdown, this is achieved with MicroOps that can be executed against the value at run time.
    These MicroOps themselves refer to other types, and have flags indicating how safe they are.

    The MicroOps are stored against a tag, which is a Python Tuple of strings/ints. A readonly object,
    as found in JS or Python, might be represented as:

    {
        ("get", "foo"): ObjectGetter("foo"),
        ("get", "bar"): ObjectGetter("bar")
    }

    Concretely, these are used for Lists, Arrays, Dictionaries, Objects etc - types
    that contain other types.
    """
    def __init__(self, micro_op_types, name):
        if not isinstance(micro_op_types, dict):
            raise FatalError()
        for tag in micro_op_types.keys():
            if not isinstance(tag, tuple):
                raise FatalError()

        self.micro_op_types = micro_op_types
        self.name = name
        self._is_self_consistent = None

    def clone(self, name):
        result = CompositeType(dict(self.micro_op_types), name)
        if hasattr(self, "from_opcode"):
            result.from_opcode = self.from_opcode
        return result

    def get_micro_op_type(self, tag):
        return self.micro_op_types.get(tag, None)

    def is_self_consistent(self, reasoner):
        """
        Returns True if the CompositeType is self_consistent.

        Self consistency of CompositeTypes means that none of the opcodes on the type conflict.

        Non-self-consistent types are supported in Lockdown, and are actually important to achieving
        dynamic programming effects. But they have limitations: can not be bound at runtime against
        actual composite values, because they would allow data corruption.

        See lockdown/type_system/README.md for a more details description.
        """
        if self._is_self_consistent is None:
            self._is_self_consistent = True

            for micro_op in self.micro_op_types.values():
                if micro_op.conflicts_with(self, self, reasoner):
                    reasoner.push_micro_op_conflicts_with_type(micro_op, self)
                    self._is_self_consistent = False
                    break

        return self._is_self_consistent

    def is_copyable_from(self, other, reasoner):
        if self is other:
            return True        
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        if not isinstance(other, CompositeType):
            return IsNotCompositeType()
        if self.micro_op_types is other.micro_op_types:
            return True

        try:
            # CompositeTypes contain other types... which can contain other types, including
            # the one we started with. These can form a cyclic graph, where types contain
            # themselves, or other types that then contain themselves.
            # We build a cache of results during this calculation so we do not execute loops.
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
                if micro_op_type is None:
                    pass
                if not micro_op_type.is_derivable_from(other, reasoner):
                    cache[result_key] = False
                    break

            for micro_op_type in self.micro_op_types.values():
                if micro_op_type is None:
                    pass
                if not micro_op_type.is_derivable_from(other, reasoner):
                    cache[result_key] = False
                    break
        finally:
            if cache_initialized_here:
                composite_type_is_copyable_cache._is_copyable_from_cache = None

        return cache[result_key]

    def __repr__(self):
        return "{}[{}]".format(self.name, ";".join([str(m) for m in self.micro_op_types.values()]))

    def short_str(self):
        return "Composite<{}>".format(self.name)

class Composite(object):
    """
    Subclass for all Composite objects we create at runtime.

    To achieve Python interopability there are separate implementations for Python
    Lists, Dictionaries, Objects etc that all subclass Composite.

    This does not give us any behaviour, but makes it easier to identify these objects.
    """
    pass

class CompositeObjectManager(object):
    """
    A Manage Object that exists alongside every Composite Object at runtime to manage
    type constraints that should be enforced at runtime.
    """
    def __init__(self, obj, on_gc_callback, is_sparse):
        self.obj_ref = weakref.ref(obj, self.obj_gced)
        self.obj_id = id(obj)
        self.attached_types = {}
        self.attached_type_counts = defaultdict(int)
        self.on_gc_callback = on_gc_callback

        self.cached_effective_composite_type = None

        self.default_factory = None
        self.debug_reason = None
        self.is_sparse = is_sparse

    def get_obj(self):
        return self.obj_ref()

    def obj_gced(self, _):
        self.on_gc_callback(self.obj_id)

    def get_effective_composite_type(self):
        """
        Returns a CompositeType that is a combination of all the CompositeTypes that are bound
        to this runtime object. The MicroOps on the returned CompositeType are safe to use
        to interact with the object.
        """
        if not self.cached_effective_composite_type:
            self.cached_effective_composite_type = merge_composite_types(
                self.attached_types.values(), name="Composed from {}".format(self.debug_reason)
            )
        return self.cached_effective_composite_type

    def attach_type(self, new_type, multiplier=1):
        """
        Attaches a CompositeType to this CompositeObject at run time. All modifications to this object
        (even done naively by Python code) will be passed through these CompositeTypes to make sure they
        are compatible.

        This does not check whether the new type conflicts with any of the existing CompositeTypes
        attached - so should not be called directly. Instead call

        lockdown.type_system.composites.add_composite_type
        """
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

    def add_composite_type(self, new_type, reasoner=None):
        # TODO: remove
        add_composite_type(self, new_type, reasoner=reasoner)

    def remove_composite_type(self, remove_type, reasoner=None):
        # TODO: remove
        remove_composite_type(self, remove_type, reasoner=reasoner)

class InferredType(Type):
    """
    A placeholder Type that should be replaced by a real type before getting new the actual verification
    or run time systems.
    """
    def is_copyable_from(self, other, reasoner):
        raise FatalError()

    def __repr__(self):
        return "Inferred"

def prepare_lhs_type(lhs_type, rhs_type):
    """
    A "heuristicy" function that takes a declared LHS type (which can include gaps for inferrence,
    inconsistencies etc) and a realized RHS type (which can also include inconsistencies) and
    generates a "sensible" LHS type that hopefully corresponds to what the developer was aiming for.

    For example:

    Tuple<...int> foo = [ 1, 2, 3 ]; -> LHS: Tuple<int, int, int>
    """

    post_inferred_lhs_type = replace_inferred_types(lhs_type, rhs_type, {})

    post_conflict_resolution_lhs_type = resolve_micro_op_conflicts(post_inferred_lhs_type, {})

    if not check_dangling_inferred_types(post_conflict_resolution_lhs_type, {}):
        replace_inferred_types(lhs_type, rhs_type, {})
        raise DanglingInferredType()

    return post_conflict_resolution_lhs_type

def check_dangling_inferred_types(type, results):
    """
    Recursively checks a CompositeType and all related types for any InferredTypes
    that haven't been replaced.

    Returns False if any InferredTypes are found
    """
    if id(type) in results:
        return results[id(type)]

    if isinstance(type, InferredType):
        return False

    if not isinstance(type, CompositeType):
        return True

    results[id(type)] = True

    for tag, micro_op_type in type.micro_op_types.items():
        if tag[0] == "infer-remainder":
            return False
        if hasattr(micro_op_type, "value_type"):
            if not check_dangling_inferred_types(micro_op_type.value_type, results):
                return False

    return True

def replace_inferred_types(lhs_type, rhs_type, results):
    result_key = (id(lhs_type), id(rhs_type))

    if result_key in results:
        return results[result_key]

    if isinstance(lhs_type, InferredType):
        if rhs_type is None or isinstance(rhs_type, InferredType):
            return lhs_type
        return rhs_type

    if not isinstance(lhs_type, CompositeType):
        return lhs_type

    finished_type = lhs_type.clone("{}<post-inference>".format(lhs_type.name))

    results[result_key] = finished_type

    infer_remainder = ("infer-remainder", ) in lhs_type.micro_op_types

    if infer_remainder:
        if isinstance(rhs_type, CompositeType):
            for rhs_tag, rhs_micro_op in rhs_type.micro_op_types.items():
                if rhs_tag not in finished_type.micro_op_types:
                    finished_type.micro_op_types[rhs_tag] = rhs_micro_op

            finished_type.micro_op_types.pop(( "infer-remainder", ), None)

    for tag, lhs_micro_op in lhs_type.micro_op_types.items():
        if hasattr(lhs_micro_op, "value_type"):
            rhs_value_type = None

            if rhs_type and isinstance(rhs_type, CompositeType):
                rhs_micro_op = rhs_type.get_micro_op_type(tag)
                if hasattr(rhs_micro_op, "value_type"):
                    rhs_value_type = rhs_micro_op.value_type

            finished_type.micro_op_types[tag] = lhs_micro_op.clone(
                value_type=replace_inferred_types(
                    lhs_micro_op.value_type,
                    rhs_value_type,
                    results
                )
            )

    return finished_type

def resolve_micro_op_conflicts(type, results):
    if id(type) in results:
        return results[id(type)]

    if not isinstance(type, CompositeType):
        return type

    finished_type = type.clone("{}<post-conflict-resolution>".format(type.name))

    results[id(type)] = finished_type

    for tag, micro_op in finished_type.micro_op_types.items():
        if hasattr(micro_op, "value_type"):
            finished_type.micro_op_types[tag] = micro_op.clone(
                value_type=resolve_micro_op_conflicts(micro_op.value_type, results)
            )

    for tag, micro_op in finished_type.micro_op_types.items():
        if len(tag) == 2 and tag[0] == "get":
            setter = finished_type.get_micro_op_type(( "set", tag[1] ))
            if setter:
                finished_type.micro_op_types[( "set", tag[1] )] = setter.clone(
                    value_type=micro_op.value_type
                )
            wildcard_setter = finished_type.get_micro_op_type(( "set-wildcard", ))
            if wildcard_setter and not wildcard_setter.type_error:
                finished_type.micro_op_types[( "set-wildcard", )] = wildcard_setter.clone(
                    type_error=True
                )
        if len(tag) == 1 and tag[0] == "get-wildcard":
            setter = finished_type.get_micro_op_type(( "set-wildcard", ))
            if setter:
                finished_type.micro_op_types[( "set-wildcard", )] = setter.clone(
                    value_type=micro_op.value_type
                )
        if tag[0] in ("get", "get-wildcard") and not micro_op.key_error:
            finished_type.micro_op_types.pop(( "insert-start", ), None)
            finished_type.micro_op_types.pop(( "insert-wildcard", ), None)
            finished_type.micro_op_types.pop(( "remove-wildcard", ), None)

    return finished_type

# def prepare_lhs_type(lhs_type, rhs_type, results_cache=None):
#     """
#     A Heuristic. Takes the LHS (left-hand-side) Type and returns a new (always more specific) Type based
#     on some rules to make the type more useful to the developer.
# 
#     The rules within this function are both:
#     1. A core part of the nature of Lockdown for a normal developer
#     2. Largely arbitrary, and can be changed without impacting the real core ideas behind Lockdown
# 
#     For example, a developer might write:
# 
#     var foo = [ 3, 6 ];
# 
#     What type should foo be? RHS is an Inconsistent Type with these micro ops:
# 
#     (get, 0) => Get.0.unit<3>
#     (set, 0) => Set.0.any
#     (get, 1) => Get.1.unit<6>
#     (set, 1) => Set.1.any
#     ... any some other inconsistent micro ops!
# 
#     There are several types for foo that would be Consistent with this Inconsistent Type. All of the
#     following could be substituted for var, and the code will compile:
# 
#     Any
#     List<any>
#     List<int>
#     Tuple<any, any>
#     Tuple<int, int> # and combinations with the previous version!
#     Tuple<unit<3>, unit<6>> # and combinations again!
# 
#     So when we use "var", which do we select? Lockdown uses Tuple<int, int> - this is likely to be most useful.
#     """
#     if isinstance(lhs_type, InferredType):
#         if rhs_type is None:
#             raise DanglingInferredType()
#         lhs_type = rhs_type
# 
#     if isinstance(lhs_type, CompositeType):
#         lhs_type = prepare_composite_lhs_type(lhs_type, rhs_type, results_cache)
# 
#     return lhs_type
# 
# def prepare_composite_lhs_type(composite_lhs_type, rhs_type, results_cache=None):
#     """
#     See the comment on prepare_lhs_type
#     """
#     if hasattr(composite_lhs_type, "_prepared_lhs_type"):
#         return composite_lhs_type
# 
#     if results_cache is None:
#         results_cache = {}
# 
#     cache_key = (id(composite_lhs_type), id(rhs_type))
# 
#     if cache_key in results_cache:
#         return results_cache[cache_key]
# 
#     result = CompositeType(
#         dict(composite_lhs_type.micro_op_types),
#         name="{}<LHSPrepared>".format(composite_lhs_type.name)
#     )
# 
#     rhs_composite_type = None
#     if isinstance(rhs_type, CompositeType):
#         rhs_composite_type = CompositeType(
#             dict(rhs_type.micro_op_types),
#             name="{}<RHSComposite>".format(rhs_type.name)
#         )
# 
#     # TODO: do this better
#     if hasattr(composite_lhs_type, "from_opcode"):
#         result.from_opcode = composite_lhs_type.from_opcode
# 
#     result._prepared_lhs_type = True
# 
#     results_cache[cache_key] = result
#     something_changed = False
# 
#     # Call recursively on both LHS and RHS types to start 
#     for tag, micro_op in result.micro_op_types.items():
#         if hasattr(micro_op, "value_type"):
#             guide_micro_op_type = None
# 
#             if isinstance(rhs_type, CompositeType):
#                 guide_op = rhs_type.get_micro_op_type(tag)
#                 guide_micro_op_type = guide_op.value_type
# 
#             new_value_type = prepare_lhs_type(micro_op.value_type, guide_micro_op_type, results_cache)
# 
#             if micro_op.value_type is not new_value_type:
#                 result.micro_op_types[tag] = micro_op.clone(
#                     value_type=prepare_lhs_type(micro_op.value_type, guide_micro_op_type, results_cache)
#                 )
#                 something_changed = True
# 
#     # Replace all inferred types in the LHS by taking types from the RHS
#     for lhs_tag, micro_op in result.micro_op_types.items():
#         if len(lhs_tag) != 1:
#             continue
#         if lhs_tag[0] in ("get-inferred-key", "set-inferred-key"):
#             lhs_method = lhs_tag[0][:3] # get or set
#             if not isinstance(rhs_type, CompositeType):
#                 raise DanglingInferredType()
# 
#             del result.micro_op_types[lhs_tag]
#             for rhs_tag, rhs_micro_op in rhs_type.micro_op_types.items():
#                 if not len(rhs_tag) == 2:
#                     continue
#                 rhs_method, rhs_key = rhs_tag
#                 if rhs_method == lhs_method:
#                     new_tag = (lhs_method, rhs_key)
#                     if new_tag not in result.micro_op_types:
#                         result.micro_op_types[new_tag] = rhs_micro_op
# 
# 
# 
# 
# 
#     # Take any overlapping getter/setter types (typically get X, set Any) and transform so that they
#     # are compatible (typically get X, set X)
#     for tag, micro_op in result.micro_op_types.items():
#         getter = None
#         if hasattr(micro_op, "value_type") and isinstance(micro_op.value_type, (AnyType, InferredType)):
#             if tag[0] == "set":
#                 getter = result.get_micro_op_type(("get", tag[1]))
#             if tag[0] == "set-wildcard":
#                 getter = result.get_micro_op_type(("get-wildcard", ))
#         if getter:
#             if micro_op.value_type is not getter.value_type:
#                 result.micro_op_types[tag] = micro_op.clone(value_type=getter.value_type)
#                 something_changed = True
# 
# #     # Add error codes to get-wildcard and set-wildcard if there are any getters or setters
# #     setter_or_getter_found = any([ t[0] in ("get", "set") for t in result.micro_op_types.keys() ])
# #     if setter_or_getter_found:
# #         wildcard_getter = result.get_micro_op_type(("get-wildcard", ))
# #         if wildcard_getter:
# #             result.micro_op_types[("get-wildcard", )] = wildcard_getter.clone(key_error=True)
# #         wildcard_setter = result.get_micro_op_type(("set-wildcard", ))
# #         if wildcard_setter:
# #             result.micro_op_types[("set-wildcard", )] = wildcard_setter.clone(key_error=True, type_error=True)
# 
#     # Replace set.x.Any + get.x.T with set.x.T + get.x.T
#     for tag, micro_op in result.micro_op_types.items():
#         if hasattr(micro_op, "value_type"):
#             guide_micro_op_type = None
# 
#             if isinstance(rhs_type, CompositeType):
#                 guide_op = rhs_type.get_micro_op_type(tag)
# 
#                 if hasattr(guide_op, "value_type") and isinstance(guide_op.value_type, AnyType):
#                     if tag[0] == "set":
#                         guide_op = rhs_type.get_micro_op_type(( "get", tag[1] ))
#                     if tag[0] == "set-wildcard":
#                         guide_op = rhs_type.get_micro_op_type(( "get-wildcard" ))
# 
#                 if hasattr(guide_op, "value_type"):
#                     guide_micro_op_type = guide_op.value_type
# 
#             new_value_type = prepare_lhs_type(micro_op.value_type, guide_micro_op_type, results_cache)
# 
#             if micro_op.value_type is not new_value_type:
#                 result.micro_op_types[tag] = micro_op.clone(
#                     value_type=prepare_lhs_type(micro_op.value_type, guide_micro_op_type, results_cache)
#                 )
#                 something_changed = True
# 
#     right_shifts = []
#     left_shifts = []
# 
#     for tag, micro_op in result.micro_op_types.items():
#         if tag[0] == "insert-start":
#             right_shifts.append((0, micro_op.value_type))
#         if tag[0] == "insert-wildcard":
#             right_shifts.append((0, micro_op.value_type))
# 
#         if tag[0] == "delete-wildcard":
#             left_shifts.append(0)
# 
#     positional_getter_micro_ops = sorted(
#         [m for t, m in result.micro_op_types.items() if t[0] == "get" and len(t) == 2 and isinstance(t[1], int)],
#         key=lambda m: m.key
#     )
# 
#     for starting_index, starting_type in right_shifts:
#         cumulative_types = [ starting_type ]
#         for getter_micro_op in positional_getter_micro_ops:
#             if getter_micro_op.key >= starting_index:
#                 cumulative_types = cumulative_types + [ getter_micro_op.value_type ]
#                 result.micro_op_types[("get", getter_micro_op.key)] = getter_micro_op.clone(
#                     value_type=merge_types(cumulative_types, "super")
#                 )
#                 something_changed = True
# 
#     positional_getter_micro_ops = sorted(
#         [m for t, m in result.micro_op_types.items() if t[0] == "get" and len(t) == 2 and isinstance(t[1], int)],
#         key=lambda m: m.key
#     )
# 
#     for starting_index in left_shifts:
#         cumulative_types = []
#         for getter_micro_op in reversed(positional_getter_micro_ops):
#             if getter_micro_op.key >= starting_index:
#                 cumulative_types.append(getter_micro_op.value_type)
#                 result.micro_op_types[("get", getter_micro_op.key)] = getter_micro_op.clone(
#                     value_type=merge_types(cumulative_types, "super"),
#                     key_error=True
#                 )
#                 something_changed = True
# 
#     if not something_changed:
#         result.micro_op_types = composite_lhs_type.micro_op_types
# 
#     return result

def add_composite_type(target_manager, new_type, reasoner=None, key_filter=None, multiplier=1):
    """
    Safely adds a new CompositeType to a CompositeObjectManager, so that run time verification
    of mutations to the object owned by the CompositeObjectManager can be enforced.

    It checks whether the new CompositeType is compatible with any CompositeTypes that
    have been added previously. If it is found to conflict, this function raises a
    CompositeTypeIncompatibleWithTarget exception.
    """
    if not reasoner:
        reasoner = Reasoner()

    types_to_bind = {}
    succeeded = build_binding_map_for_type(None, new_type, target_manager.get_obj(), target_manager, key_filter, MISSING, {}, types_to_bind, reasoner)
    if not succeeded:
        raise CompositeTypeIncompatibleWithTarget()

    for _, type, target in types_to_bind.values():
        get_manager(target).attach_type(type, multiplier=multiplier)


def remove_composite_type(target_manager, remove_type, reasoner=None, key_filter=None, multiplier=1):
    if not reasoner:
        reasoner = Reasoner()

    types_to_bind = {}
    succeeded = build_binding_map_for_type(None, remove_type, target_manager.get_obj(), target_manager, key_filter, MISSING, {}, types_to_bind, reasoner)
    if not succeeded:
        raise CompositeTypeIncompatibleWithTarget()

    for _, type, target in types_to_bind.values():
        get_manager(target).detach_type(type, multiplier=multiplier)

def can_add_composite_type_with_filter(target, new_type, key_filter, substitute_value):
    return build_binding_map_for_type(None, new_type, target, get_manager(target), key_filter, substitute_value, {}, {}, DUMMY_REASONER)

def is_type_bindable_to_value(value, type):
    return build_binding_map_for_type(None, type, value, get_manager(value), None, MISSING, {}, {}, DUMMY_REASONER)

def does_value_fit_through_type(value, type):
    return build_binding_map_for_type(None, type, value, get_manager(value), None, MISSING, {}, None, DUMMY_REASONER, build_binding_map=False)

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


def build_binding_map_for_type(source_micro_op, new_type, target, target_manager, key_filter, substitute_value, cache, types_to_bind, reasoner, build_binding_map=True):
    """
    Builds a binding map of the Type new_type against the object target.

    The binding map is stored in types_to_bind, a dictionary of:

    {
        (id(source_micro_op), id(new_type), id(target)) : (source_micro_op, new_type, target),
        ...
    }

    It stores every MicroOp that uses a particular Type against a particular target Object. It is then possible
    to loop over all these ops to bind the types (done elsewhere).
    """
    result_key = (id(source_micro_op), id(new_type), id(target))

    if result_key in cache:
        return cache[result_key]

    cache[result_key] = True

    extra_types_to_bind = {}

    target_is_composite = isinstance(target, Composite)
    target_effective_type = None
    if target_manager:
        target_effective_type = target_manager.get_effective_composite_type()

    child_reasoners = []

    atleast_one_sub_type_worked = False
    for sub_type in unwrap_types(new_type):
        child_reasoner = Reasoner()
        child_reasoners.append(child_reasoner)

        if isinstance(sub_type, CompositeType) and target_is_composite:
            sub_type_consistent_reasoner = Reasoner()
            if not sub_type.is_self_consistent(sub_type_consistent_reasoner):
                child_reasoner.push_inconsistent_type(sub_type)
                raise CompositeTypeIsInconsistent(sub_type_consistent_reasoner.to_message())

            micro_ops_checks_worked = True

            for key, micro_op in sub_type.micro_op_types.items():
                if not micro_op.is_bindable_to(sub_type, target):
                    child_reasoner.push_micro_op_not_bindable_to(micro_op, sub_type, target)
                    micro_ops_checks_worked = False
                    break

                if micro_op.conflicts_with(sub_type, target_effective_type, child_reasoner):
                    micro_ops_checks_worked = False
                    break

                next_targets, next_new_type = micro_op.prepare_bind(target, key_filter, substitute_value)

                for next_target in next_targets:
                    if not build_binding_map_for_type(
                        micro_op, next_new_type, next_target, get_manager(next_target), None, MISSING, cache, extra_types_to_bind, child_reasoner, build_binding_map=build_binding_map
                    ):
                        micro_ops_checks_worked = False
                        break

            if micro_ops_checks_worked:
                if key_filter is None and build_binding_map:
                    extra_types_to_bind[result_key] = (source_micro_op, sub_type, target)
                atleast_one_sub_type_worked = True

        if isinstance(sub_type, CompositeType) and not target_is_composite:
            child_reasoner.push_target_should_be_composite(sub_type, target)

        if isinstance(sub_type, AnyType):
            atleast_one_sub_type_worked = True

        if not isinstance(sub_type, CompositeType) and not target_is_composite:
            if sub_type.is_copyable_from(get_type_of_value(target), child_reasoner):
                atleast_one_sub_type_worked = True

    if atleast_one_sub_type_worked and build_binding_map:
        types_to_bind.update(extra_types_to_bind)
    if not atleast_one_sub_type_worked:
        cache[result_key] = False
        reasoner.attach_child_reasoners(child_reasoners, source_micro_op, new_type, target)

    return atleast_one_sub_type_worked

@contextmanager
def scoped_bind(value, composite_type):
    if not isinstance(composite_type, CompositeType):
        raise FatalError()

    manager = get_manager(value)
    try:
        manager.add_composite_type(composite_type)
        yield
    finally:
        manager.remove_composite_type(composite_type)

