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
from lockdown.utils import MISSING
import lockdown


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
    def __init__(self, micro_op_types, name):
        if not isinstance(micro_op_types, dict):
            raise FatalError()
        for tag in micro_op_types.keys():
            if not isinstance(tag, tuple):
                raise FatalError()

        self.micro_op_types = micro_op_types
        self.name = name
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

    def get_micro_op_type(self, tag):
        return self.micro_op_types.get(tag, None)

    def is_self_consistent(self):
        if self._is_self_consistent is None:
            self._is_self_consistent = True
            for micro_op in self.micro_op_types.values():
                if micro_op.conflicts_with(self, self):
                    self._is_self_consistent = False
                    break
        return self._is_self_consistent

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

    def __repr__(self):
        return "{}<{}>".format(self.name, ", ".join([str(m) for m in self.micro_op_types.values()]))

    def short_str(self):
        return "Composite<{}>".format(self.name)


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

class CompositeObjectManager(object):
    def __init__(self, obj, on_gc_callback):
        self.obj_ref = weakref.ref(obj, self.obj_gced)
        self.obj_id = id(obj)
        self.attached_types = {}
        self.attached_type_counts = defaultdict(int)
#         self.child_key_type_references = defaultdict(lambda: defaultdict(list))
#         self.child_value_type_references = defaultdict(lambda: defaultdict(list))
        self.on_gc_callback = on_gc_callback

        from lockdown.type_system.default_composite_types import EMPTY_COMPOSITE_TYPE

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
        name="{}<LHSPrepared>".format(composite_type.name)
    )

    # TODO: do this better
    if hasattr(composite_type, "from_opcode"):
        result.from_opcode = composite_type.from_opcode

    if ("get", "best_result") in composite_type.micro_op_types:
        pass

    result._prepared_lhs_type = True

    results_cache[cache_key] = result
    something_changed = False

    # Take any overlapping getter/setter types (typically get X, set Any) and transform so that they
    # are compatible (typically get X, set X)
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

    # Add error codes to get-wildcard and set-wildcard if there are any getters or setters
    setter_or_getter_found = any([ t[0] in ("get", "set") for t in result.micro_op_types.keys() ])
    if setter_or_getter_found:
        wildcard_getter = result.get_micro_op_type(("get-wildcard", ))
        if wildcard_getter:
            result.micro_op_types[("get-wildcard", )] = wildcard_getter.clone(key_error=True)
        wildcard_setter = result.get_micro_op_type(("set-wildcard", ))
        if wildcard_setter:
            result.micro_op_types[("set-wildcard", )] = wildcard_setter.clone(key_error=True, type_error=True)

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

def does_value_fit_through_type(value, type):
    return build_binding_map_for_type(None, type, value, get_manager(value), None, MISSING, {}, None, build_binding_map=False)

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


def build_binding_map_for_type(source_micro_op, new_type, target, target_manager, key_filter, substitute_value, cache, types_to_bind, build_binding_map=True):
    result_key = (id(source_micro_op), id(new_type), id(target))

    if result_key in cache:
        return cache[result_key]

#    print "{}:{}:{}".format(id(source_micro_op), id(new_type), id(target))

    cache[result_key] = True

    extra_types_to_bind = {}

    target_is_composite = isinstance(target, Composite)
    target_effective_type = None
    if target_manager:
        target_effective_type = target_manager.get_effective_composite_type()

    atleast_one_sub_type_worked = False
    for sub_type in unwrap_types(new_type):
        if isinstance(sub_type, CompositeType) and target_is_composite:
            if build_binding_map and not sub_type.is_self_consistent():
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
                        micro_op, next_new_type, next_target, get_manager(next_target), None, MISSING, cache, extra_types_to_bind, build_binding_map=build_binding_map
                    ):
                        micro_ops_checks_worked = False
                        break

            if micro_ops_checks_worked:
                if key_filter is None and build_binding_map:
                    extra_types_to_bind[result_key] = (source_micro_op, sub_type, target)
                atleast_one_sub_type_worked = True

        if isinstance(sub_type, AnyType):
            atleast_one_sub_type_worked = True

        if not isinstance(sub_type, CompositeType) and not target_is_composite:
            if sub_type.is_copyable_from(get_type_of_value(target)):
                atleast_one_sub_type_worked = True

    if atleast_one_sub_type_worked and build_binding_map:
        types_to_bind.update(extra_types_to_bind)
    if not atleast_one_sub_type_worked:
        cache[result_key] = False

    return atleast_one_sub_type_worked

def create_reasonable_composite_type(obj):
    result = CompositeType({}, name="reasonable list type")
    from lockdown.type_system.list_types import RDHList
    from lockdown.type_system.list_types import ListGetterType,\
    ListWildcardGetterType
    if isinstance(obj, RDHList):
        for key in obj._keys():
            result.micro_op_types[("get", key)] = ListGetterType(key, get_type_of_value(obj._get(key)), False, False)
        result.micro_op_types[("get-wildcard", )] = ListWildcardGetterType(AnyType(), True, True)
    return result
