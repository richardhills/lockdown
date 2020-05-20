from __builtin__ import False
from collections import defaultdict
import threading
import weakref

from rdhlang5.type_system.core_types import Type, unwrap_types, AnyType, \
    OneOfType
from rdhlang5.type_system.exceptions import FatalError, MicroOpTypeConflict
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.micro_ops import merge_micro_op_types, MicroOpType, \
    MicroOp


class InferredType(Type):
    def is_copyable_from(self, other):
        raise FatalError()

    def replace_inferred_types(self, other):
        return other

composite_type_is_copyable_cache = threading.local()

class CompositeType(Type):
    def __init__(self, micro_op_types, initial_data=None, is_revconst=False, name=None):
        if not isinstance(micro_op_types, dict):
            raise FatalError()
        for tag in micro_op_types.keys():
            if not isinstance(tag, tuple):
                raise FatalError()
        from rdhlang5.type_system.dict_types import RDHDict

        if isinstance(initial_data, RDHDict):
            pass
        self.micro_op_types = micro_op_types
        self.initial_data = initial_data
        self.is_revconst = is_revconst
        self.name = name or "unknown"

    def replace_inferred_types(self, other):
        if not isinstance(other, CompositeType):
            return self

        potential_replacement_opcodes = {}

        for key, micro_op_type in self.micro_op_types.items():
            other_micro_op_type = other.micro_op_types.get(key, None)

            potential_replacement_opcodes[key] = micro_op_type.replace_inferred_type(other_micro_op_type)

        return CompositeType(
            micro_op_types=potential_replacement_opcodes,
            initial_data=self.initial_data,
            is_revconst=other.is_revconst
        )

    def reify_revconst_types(self):
        if not self.is_revconst:
            return self

        potential_replacement_opcodes = {}
        need_to_replace = False

        for key, micro_op_type in self.micro_op_types.items():
            potential_replacement_opcodes[key] = micro_op_type.reify_revconst_types(self.micro_op_types)
            need_to_replace = need_to_replace or bool(micro_op_type is not potential_replacement_opcodes[key])

        if need_to_replace:
            return CompositeType(micro_op_types=potential_replacement_opcodes, initial_data=self.initial_data, is_revconst=self.is_revconst)
        else:
            return self


    def get_micro_op_type(self, tag):
        return self.micro_op_types.get(tag, None)

    def internal_is_copyable_from(self, other):
        if not isinstance(other, CompositeType):
            return False

        if not other.is_revconst:
            for ours in self.micro_op_types.values():
                for theirs in other.micro_op_types.values():
                    if ours.check_for_new_micro_op_type_conflict(theirs, self.micro_op_types):
                        return False

        for our_tag, our_micro_op in self.micro_op_types.items():
            their_micro_op = other.micro_op_types.get(our_tag, None)

            no_initial_data_to_make_safe = not other.initial_data or our_micro_op.check_for_runtime_data_conflict(other.initial_data)
            if no_initial_data_to_make_safe: # and not our_micro_op.key_error:
                if their_micro_op is None:
                    our_micro_op.check_for_runtime_data_conflict(other.initial_data)
                    return False
                if not our_micro_op.can_be_derived_from(their_micro_op):
                    our_micro_op.can_be_derived_from(their_micro_op)
                    return False

        return True

    def is_copyable_from(self, other):
        try:
            cache_started_empty = False
            if getattr(composite_type_is_copyable_cache, "_is_copyable_from_cache", None) is None:
                composite_type_is_copyable_cache._is_copyable_from_cache = defaultdict(lambda: defaultdict(lambda: None))
                cache_started_empty = True
            cache = composite_type_is_copyable_cache._is_copyable_from_cache

            if isinstance(other, OneOfType):
                return other.is_copyable_to(self)

            if not isinstance(other, CompositeType):
                return False
            if self is other:
                return True

            result = results_by_target_id[id(self)][id(other)]

            # Debugging check
            if result is False:
                check = self.internal_is_copyable_from(other)
                if check is True:
                    self.internal_is_copyable_from(other)
                    raise FatalError()

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

def bind_type_to_value(source, key, type, value):
    if not isinstance(value, Composite):
        return

    from rdhlang5.type_system.object_types import RDHObject

    if isinstance(value, RDHObject) and value.__dict__.get("x", None) == 5:
        pass

    manager = get_manager(value)

    source_manager = get_manager(source)

    something_worked = False
    for sub_type in unwrap_types(type):
        if isinstance(sub_type, CompositeType):
            try:
                manager.add_composite_type(sub_type)
                source_manager.child_type_references[key].append(sub_type)
                something_worked = True
            except MicroOpTypeConflict as e:
                pass
        else:
            something_worked = True

    if not something_worked:
        for sub_type in unwrap_types(type):
            if isinstance(sub_type, CompositeType):
                try:
                    manager.add_composite_type(sub_type)
                    source_manager.child_type_references[key].append(sub_type)
                except MicroOpTypeConflict as e:
                    pass

        raise MicroOpTypeConflict()

def unbind_type_to_value(source, key, type, value):
    if not isinstance(value, Composite):
        return
    source_manager = get_manager(source)
    for sub_type in source_manager.child_type_references[key]:
        get_manager(value).remove_composite_type(sub_type)
    source_manager.child_type_references[key] = []


class CompositeObjectManager(object):
    def __init__(self, obj):
        self.obj = obj
        self.micro_op_types = defaultdict(dict)
        self.type_references = defaultdict(int)
        # A dictionary of key (names) to a list of types bound to the remote object
        self.child_type_references = defaultdict(list)

        self.default_factory = None

    def get_merged_micro_op_types(self, new_micro_op_types={}):
        return merge_micro_op_types(self.micro_op_types.values() + [ new_micro_op_types ])

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
        for micro_op_type in type.micro_op_types.values():
            micro_op_type.check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(
                self.obj, self.get_merged_micro_op_types(type.micro_op_types)
            )

    def add_composite_type(self, type):
        if self.check_for_runtime_data_conflicts(type):
            self.check_for_runtime_data_conflicts(type)
            raise MicroOpTypeConflict()
            
        self.check_for_runtime_micro_op_conflicts(type)

        self.type_references[id(type)] += 1

        if id(type) in self.micro_op_types:
            return

        self.micro_op_types[id(type)] = dict(type.micro_op_types)

        for tag, micro_op_type in type.micro_op_types.items():
            micro_op_type.bind(None, self.obj)

    def remove_composite_type(self, type):
        type_id = id(type)
        if self.type_references[type_id] > 0:
            self.type_references[type_id] -= 1
        if self.type_references[type_id] == 0:
            del self.micro_op_types[type_id]

    def get_micro_op_type(self, tag):
        merged_micro_op_types = self.get_merged_micro_op_types()
        return merged_micro_op_types.get(tag, None)
#         if id(type) not in self.micro_op_types:
#             raise FatalError()
#         return self.micro_op_types.get(id(type)).get(tag, None)

    def get_flattened_micro_op_types(self):
        # TODO: consider replacing with self.get_merged_micro_op_types().values()
        result = []
        for micro_op_types in self.micro_op_types.values():
            for micro_op_type in micro_op_types.values():
                result.append(micro_op_type)
        return result


class DefaultFactoryType(MicroOpType):
    def __init__(self, type):
        self.type = type

    def create(self, target):
        return DefaultFactory(target)

    def can_be_derived_from(self, other_micro_op):
        return self.type.is_copyable_from(other_micro_op.type)

    def replace_inferred_type(self, other_micro_op_type):
        return self

    def bind(self, key, target):
        pass

    def unbind(self, key, target):
        pass

    def merge(self, other_micro_op_type):
        raise FatalError()

    def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
        return False

    def raise_on_runtime_micro_op_conflict(self, other_micro_op, args):
        pass

    def check_for_runtime_data_conflict(self, obj):
        if get_manager(obj).default_factory is None:
            raise MicroOpTypeConflict()

class DefaultFactory(MicroOp):
    def __init__(self, target):
        self.target = target

    def invoke(self, key):
        return get_manager(self.target).default_factory(self.target, key)
