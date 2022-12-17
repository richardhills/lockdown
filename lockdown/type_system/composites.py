# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import defaultdict
from contextlib import contextmanager
import threading
import weakref

from lockdown.type_system.core_types import Type, unwrap_types, OneOfType, \
    AnyType, merge_types, BottomType, ValueType
from lockdown.type_system.exceptions import FatalError, IsNotCompositeType, \
    CompositeTypeIncompatibleWithTarget, CompositeTypeIsInconsistent, \
    DanglingInferredType
from lockdown.type_system.managers import get_manager, get_type_of_value
from lockdown.type_system.micro_ops import merge_composite_types
from lockdown.type_system.reasoner import Reasoner, DUMMY_REASONER
from lockdown.utils.utils import MISSING, WeakIdentityKeyDictionary, \
    get_environment


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
    def __init__(self, micro_op_types, name, delegate=None):
        if not isinstance(micro_op_types, dict):
            raise FatalError()
        for tag in micro_op_types.keys():
            if not isinstance(tag, tuple):
                raise FatalError()

        self._micro_op_types = micro_op_types
        self.name = name
        self._is_self_consistent = None
        self.is_copyable_cache = WeakIdentityKeyDictionary()
        self.delegate = delegate

    def clone(self, name):
        if self.delegate:
            return self.delegate.clone(name)

        result = CompositeType(dict(self._micro_op_types), name, delegate=self)

        return result

    def get_micro_op_type(self, tag):
        if not isinstance(tag, tuple):
            raise FatalError()

        if self.delegate:
            return self.delegate.get_micro_op_type(tag)

        return self._micro_op_types.get(tag, None)

    def set_micro_op_type(self, tag, micro_op):
        if not isinstance(tag, tuple):
            raise FatalError()

        if self.delegate:
            self.delegate = None

        self._micro_op_types[tag] = micro_op

    def remove_micro_op_type(self, tag):
        if tag not in self._micro_op_types:
            return

        if self.delegate:
            self.delegate = None

        self._micro_op_types.pop(tag, None)

    def get_micro_op_types(self):
        if self.delegate:
            return self.delegate.get_micro_op_types()

        return self._micro_op_types

    def is_self_consistent(self, reasoner):
        """
        Returns True if the CompositeType is self_consistent.

        Self consistency of CompositeTypes means that none of the opcodes on the type conflict.

        Non-self-consistent types are supported in Lockdown, and are actually important to achieving
        dynamic programming effects. But they have limitations: can not be bound at runtime against
        actual composite values, because they would allow data corruption.

        See lockdown/type_system/README.md for a more details description.
        """
        if self.delegate:
            return self.delegate.is_self_consistent(reasoner)

        if self._is_self_consistent is None:
            self._is_self_consistent = True

            for micro_op in self._micro_op_types.values():
                if micro_op.conflicts_with(self, self, reasoner):
                    reasoner.push_micro_op_conflicts_with_type(micro_op, self)
                    self._is_self_consistent = False
                    break

        return self._is_self_consistent

    def is_nominally_the_same(self, other):
        if not isinstance(other, CompositeType):
            return False

        return self.get_delegate() is other.get_delegate()

    def get_delegate(self):
        if self.delegate:
            return self.delegate.get_delegate()
        return self

    def is_copyable_from(self, other, reasoner):
        if self.delegate:
            return self.delegate.is_copyable_from(other, reasoner)

        if isinstance(other, BottomType):
            return True
        if self is other:
            return True        
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        if not isinstance(other, CompositeType):
            return IsNotCompositeType()

        other = other.get_delegate()

        if self._micro_op_types is other._micro_op_types:
            return True

        if other not in self.is_copyable_cache:
            self.is_copyable_cache[other] = True
            for micro_op_type in self._micro_op_types.values():
                if micro_op_type is None:
                    pass
                if not micro_op_type.is_derivable_from(other, reasoner):
                    reasoner.push_micro_op_not_derivable_from(micro_op_type, other)
                    self.is_copyable_cache[other] = False
                    break

        return self.is_copyable_cache[other]

    def __repr__(self):
        return "{}[{}]".format(self.name, ";".join([str(m) for m in self._micro_op_types.values()]))

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

        self.attached_nodes = WeakIdentityKeyDictionary()
        self.attached_nodes_by_type = WeakIdentityKeyDictionary()

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
                [ n.type for n in self.get_attached_nodes() ], name="Composed from {}".format(self.debug_reason)
            )
        return self.cached_effective_composite_type

    def get_attached_nodes(self):
        try:
            attached_nodes = [ n() for n in self.attached_nodes.values() ]
        except KeyError:
            pass
        attached_nodes = [ n for n in attached_nodes if n ]
        return attached_nodes

    def get_attached_node_for_type(self, type):
        ref = self.attached_nodes_by_type.get(type)
        if ref:
            return ref()

    def attach_node(self, new_node):
        """
        Attaches a CompositeType to this CompositeObject at run time. All modifications to this object
        (even done naively by Python code) will be passed through these CompositeTypes to make sure they
        are compatible.

        This does not check whether the new type conflicts with any of the existing CompositeTypes
        attached - so should not be called directly. Instead call

        lockdown.type_system.composites.add_composite_type
        """
        if not new_node or not isinstance(new_node, Node):
            raise FatalError()
        self.cached_effective_composite_type = None
        # TODO handle GCs on the weakrefs
        weakref_to_node = weakref.ref(new_node, self.node_gced)
        self.attached_nodes[new_node] = weakref_to_node
        self.attached_nodes_by_type[new_node.type] = weakref_to_node

    def node_gced(self, weakref_to_node):
        self.cached_effective_composite_type = None

    def get_micro_op_type(self, tag):
        if not isinstance(tag, tuple):
            raise FatalError()
        effective_composite_type = self.get_effective_composite_type()
        return effective_composite_type.get_micro_op_type(tag)    

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

    for tag, micro_op_type in type.get_micro_op_types().items():
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

    if isinstance(lhs_type, CompositeType):
        return replace_inferred_types_in_composite(lhs_type, rhs_type, results)

    if isinstance(lhs_type, OneOfType):
        return merge_types(
            replace_inferred_types(unwrap_types(lhs_type), rhs_type, results),
            "exact"
        )

    return lhs_type

def replace_inferred_types_in_composite(lhs_type, rhs_type, results):
    result_key = (id(lhs_type), id(rhs_type))

    finished_type = lhs_type.clone("{}<post-inference>".format(lhs_type.name))

    results[result_key] = finished_type

    infer_remainder = lhs_type.get_micro_op_type(( "infer-remainder", ))

    if infer_remainder and isinstance(rhs_type, CompositeType):
        missing_rhs_tags = [
            (tag, op) for (tag, op) in rhs_type.get_micro_op_types().items()
            if tag not in finished_type.get_micro_op_types()
        ]

        for rhs_tag, rhs_micro_op in missing_rhs_tags:
            new_lhs_micro_op = rhs_micro_op

            if rhs_tag in ( ( "set-wildcard", ), ):
                if not rhs_micro_op.value_type.is_copyable_from(infer_remainder.base_type, DUMMY_REASONER):
                    raise FatalError()

                new_lhs_micro_op = new_lhs_micro_op.clone(
                    value_type=infer_remainder.base_type
                )

            finished_type.set_micro_op_type(rhs_tag, new_lhs_micro_op)

        finished_type.remove_micro_op_type(( "infer-remainder", ))

    for tag, lhs_micro_op in lhs_type.get_micro_op_types().items():
        if hasattr(lhs_micro_op, "value_type"):
            rhs_value_type = None

            if rhs_type and isinstance(rhs_type, CompositeType):
                rhs_micro_op = rhs_type.get_micro_op_type(tag)
                if hasattr(rhs_micro_op, "value_type"):
                    rhs_value_type = rhs_micro_op.value_type

            new_value_type = replace_inferred_types(
                lhs_micro_op.value_type,
                rhs_value_type,
                results
            )

            if not new_value_type.is_nominally_the_same(lhs_micro_op.value_type):
                finished_type.set_micro_op_type(tag, lhs_micro_op.clone(value_type=new_value_type))

    return finished_type

def resolve_micro_op_conflicts(type, results):
    if id(type) in results:
        return results[id(type)]

    if isinstance(type, OneOfType):
        return type.map(lambda t: resolve_micro_op_conflicts(t, results))

    if not isinstance(type, CompositeType):
        return type

    finished_type = type.clone("({})<pcr>".format(type.name))

    results[id(type)] = finished_type

    for tag, micro_op in finished_type.get_micro_op_types().items():
        if hasattr(micro_op, "value_type"):
            new_value_type = resolve_micro_op_conflicts(micro_op.value_type, results)
            if not new_value_type.is_nominally_the_same(micro_op.value_type):
                finished_type.set_micro_op_type(tag, micro_op.clone(
                    value_type=new_value_type
                ))

    for tag, micro_op in finished_type.get_micro_op_types().items():
        if len(tag) == 2 and tag[0] == "get":
            setter = finished_type.get_micro_op_type(( "set", tag[1] ))
            if setter and replace_setter_value_type_with_getter(setter, micro_op):
                finished_type.set_micro_op_type(( "set", tag[1] ), setter.clone(
                    value_type=micro_op.value_type
                ))
            wildcard_setter = finished_type.get_micro_op_type(( "set-wildcard", ))
            if wildcard_setter and not wildcard_setter.type_error:
                finished_type.set_micro_op_type(( "set-wildcard", ), wildcard_setter.clone(
                    type_error=True
                ))

    wildcard_setter = finished_type.get_micro_op_type(( "set-wildcard", ))
    wildcard_getter = finished_type.get_micro_op_type(( "get-wildcard", ))

    if wildcard_setter and wildcard_getter:
        finished_type.set_micro_op_type(( "get-wildcard", ), wildcard_getter.clone(
            value_type=wildcard_setter.value_type
        ))

    wildcard_getter = finished_type.get_micro_op_type(( "get-wildcard", ))
    iter = finished_type.get_micro_op_type(( "iter", ))

    if wildcard_getter and iter:
        finished_type.set_micro_op_type(( "iter", ), iter.clone(
            key_type=wildcard_getter.key_type,
            value_type=wildcard_getter.value_type
        ))

    for tag, micro_op in list(finished_type.get_micro_op_types().items()):
        if tag[0] in ("get", "get-wildcard") and not micro_op.key_error:
            finished_type.remove_micro_op_type(( "insert-start", ))
            finished_type.remove_micro_op_type(( "insert-wildcard", ))
            finished_type.remove_micro_op_type(( "remove-wildcard", ))

    return finished_type

def replace_setter_value_type_with_getter(setter, getter):
    # Identify those cases where we can get away without replacing the setter value_type with
    # the getter, so that we don't end up creating a load of new CompositeTypes and having
    # to calculate the relationships between them all
    if isinstance(setter.value_type, InferredType):
        return True
    if not isinstance(setter.value_type, CompositeType) and not isinstance(getter.value_type, CompositeType):
        return not getter.value_type.is_copyable_from(setter.value_type, DUMMY_REASONER)
    if isinstance(setter.value_type, CompositeType) and isinstance(getter.value_type, CompositeType):
        return not setter.value_type.is_nominally_the_same(getter.value_type)
    return True

def add_composite_type(target_manager, new_type, key_filter=MISSING, reasoner=DUMMY_REASONER):
    """
    Safely adds a new CompositeType to a CompositeObjectManager, so that run time verification
    of mutations to the object owned by the CompositeObjectManager can be enforced.

    It checks whether the new CompositeType is compatible with any CompositeTypes that
    have been added previously. If it is found to conflict, this function raises a
    CompositeTypeIncompatibleWithTarget exception.
    """
    if not isinstance(target_manager, CompositeObjectManager):
        raise FatalError()
    if not isinstance(new_type, Type):
        raise FatalError()
    if key_filter is not MISSING and not isinstance(key_filter, (str, int)):
        raise FatalError()

    builder = NetworkVerifierAndBuilder(target_manager.get_obj(), new_type, True)
    succeeded, top_nodes = builder.build(key_filter, MISSING, reasoner)

    if not succeeded:
        raise CompositeTypeIncompatibleWithTarget()

    if len(top_nodes) > 1:
        raise FatalError()

    top_node = top_nodes[0]

    existing_node = target_manager.get_attached_node_for_type(new_type)

    if existing_node:
        existing_node.update(top_node)
        existing_node.attach()
    else:
        top_node.attach()

    return top_node

def bind_key(target_manager, key):
    for attached_node in target_manager.get_attached_nodes():
        add_composite_type(target_manager, attached_node.type, key)

def can_add_composite_type_with_filter(target, new_type, key_filter, substitute_value):
    builder = NetworkVerifierAndBuilder(target, new_type, False)
    succeeded, _ = builder.build(key_filter, substitute_value, DUMMY_REASONER)
    return succeeded

def is_type_bindable_to_value(value, type, reasoner=DUMMY_REASONER):
    builder = NetworkVerifierAndBuilder(value, type, True)
    succeeded, _ = builder.build(MISSING, MISSING, DUMMY_REASONER)
    return succeeded

def does_value_fit_through_type(value, type, reasoner=DUMMY_REASONER):
    builder = NetworkVerifierAndBuilder(value, type, False)
    succeeded, _ = builder.build(MISSING, MISSING, DUMMY_REASONER)
    return succeeded

# def rebind_networks(manager):
#     for attached_node in manager.get_attached_nodes():
#         old_network = attached_node.network
#         old_network.detach()
#
#         builder = NetworkVerifierAndBuilder(True)
#         succeeded = verify_and_or_build_network(
#             old_network.top_node.type,
#             old_network.top_node.target_manager().get_obj(),
#             old_network.top_node.target_manager(),
#             None, None,
#             MISSING, MISSING, builder, DUMMY_REASONER
#         )
#
#         if not succeeded:
#             raise CompositeTypeIncompatibleWithTarget()
#
#         new_network = builder.build()
#         print("Rebinding {} to {} on {}".format(id(old_network), id(new_network), id(old_network.top_node.target_manager())))
#         new_network.attach()
#
#         old_network.bind_context.network = new_network
#         new_network.bind_context = old_network.bind_context
#
# class Network(object):
#     def __init__(self):
#         self.top_node = None
#         self.bind_context = NetworkBindContext(self)
#
#     def walk(self):
#         yield from self.top_node.walk()
#
#     def attach(self):
#         target_manager = self.top_node.target_manager()
#         if target_manager:
#             nodes = list(self.walk())
#             print("attaching {} nodes".format(len(nodes)))
#             for node in nodes:
#                 node.attach()
#
#     def detach(self):
#         target_manager = self.top_node.target_manager()
#         if target_manager:
#             for node in self.walk():
#                 node.detach()

class Node(object):
    def __init__(self, target_manager, type):
        self.target_manager = target_manager
        self.type = type
        self.child_nodes = {}
        self.attached = False

    def attach(self):
        count = 0
        if self.attached:
            return count
        count += 1
        self.attached = True
        self.target_manager.attach_node(self)
        for child in self.child_nodes.values():
            count += child.attach()
        return count

    def get_stack(self):
        result = [ self ]
        for child in self.child_nodes.values():
            result.extend(child.get_stack())
        return result

    def add_child_node(self, micro_op, key, child_node):
        if not isinstance(key, (str, int)):
            raise FatalError()
        self.child_nodes[(id(micro_op), key)] = child_node

    def update(self, other_node):
        self.attached = False
        if other_node.target_manager is not self.target_manager:
            raise FatalError()
        if other_node.type is not self.type:
            raise FatalError()
        self.child_nodes.update(other_node.child_nodes)

class NetworkVerifierAndBuilder(object):
    def __init__(self, target, type, binding):
        self.target = target
        self.type = type
        self.binding = binding
        self.nodes = {}

    def build(self, key_filter, substitute_value, reasoner):
        target_manager = get_manager(self.target)
        result = self.visit(
            self.type,
            self.target,
            target_manager,
            None, None, None,
            key_filter,
            substitute_value,
            reasoner
        )

        top_nodes = []

        if target_manager:
            top_nodes_and_acceptances = [ self.get_node(target_manager, t) for t in unwrap_types(self.type) ]
            top_nodes = [ n for n, a in top_nodes_and_acceptances if a ]

        return result, top_nodes

    def get_node(self, target_manager, type):
        result_key = (id(target_manager), id(type))
        node_and_accepted_from_builder = self.nodes.get(result_key)

        if node_and_accepted_from_builder:
            return node_and_accepted_from_builder

        if target_manager.get_obj() is not self.target:
            node_from_existing_type = target_manager.get_attached_node_for_type(type)
            if node_from_existing_type:
                return node_from_existing_type, True

        node = Node(target_manager, type)
        self.nodes[result_key] = (node, True)

        return node, None

    def accept_node(self, node, parent_node, parent_micro_op, parent_key):
        if node.target_manager.get_obj() is not self.target:
            parent_node.add_child_node(parent_micro_op, parent_key, node)

    def reject_node(self, node):
        result_key = (id(node.target_manager), id(node.type))
        self.nodes[result_key] = (node, False)

    def visit(self, new_type, target, target_manager, parent_node, parent_micro_op, parent_key, key_filter, substitute_value, reasoner):
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
                potential_target_node, previously_accepted = self.get_node(target_manager, sub_type)

                if previously_accepted is True:
                    self.accept_node(potential_target_node, parent_node, parent_micro_op, parent_key)
                    atleast_one_sub_type_worked = True
                    continue
                if previously_accepted is False:
                    continue

                if self.binding:
                    # It only matters that the subtype is consistent if we intend to actually bind the types
                    # at the end, since inconsistent types can't be bound to runtime objects. But if we're
                    # simply testing that the data structure has the right shape to fit an inconsistent type
                    # that's absolutely fine
                    sub_type_consistent_reasoner = Reasoner()
                    if not sub_type.is_self_consistent(sub_type_consistent_reasoner):
                        child_reasoner.push_inconsistent_type(sub_type)
                        raise CompositeTypeIsInconsistent(sub_type_consistent_reasoner.to_message())

                micro_ops_checks_worked = True

                for micro_op in sub_type.get_micro_op_types().values():
                    if not micro_op.is_bindable_to(sub_type, target):
                        micro_op.is_bindable_to(sub_type, target)
                        child_reasoner.push_micro_op_not_bindable_to(micro_op, sub_type, target)
                        micro_ops_checks_worked = False
                        break

                    if micro_op.conflicts_with(sub_type, target_effective_type, child_reasoner):
                        micro_op.conflicts_with(sub_type, target_effective_type, child_reasoner)
                        micro_ops_checks_worked = False
                        break

                    # Have prepare_bind return keys to be used for building the network
                    next_keys_and_targets, next_new_type = micro_op.prepare_bind(target, key_filter, substitute_value)

                    for next_key, next_target in next_keys_and_targets.items():
                        if not self.visit(
                            next_new_type,
                            next_target,
                            get_manager(next_target),
                            potential_target_node,
                            micro_op,
                            next_key,
                            MISSING,
                            MISSING,
                            child_reasoner,
                        ):
                            micro_ops_checks_worked = False
                            break

                if micro_ops_checks_worked:
                    self.accept_node(potential_target_node, parent_node, parent_micro_op, parent_key)
                    atleast_one_sub_type_worked = True
                else:
                    self.reject_node(potential_target_node)

            if isinstance(sub_type, CompositeType) and not target_is_composite:
                child_reasoner.push_target_should_be_composite(sub_type, target)

            if not isinstance(sub_type, CompositeType) and target_is_composite:
                child_reasoner.push_target_should_not_be_composite(sub_type, target)

            if isinstance(sub_type, (AnyType, ValueType)):
                atleast_one_sub_type_worked = True

            if not isinstance(sub_type, CompositeType) and not target_is_composite:
                if sub_type.is_copyable_from(get_type_of_value(target), child_reasoner):
                    atleast_one_sub_type_worked = True

        if not atleast_one_sub_type_worked:
            reasoner.attach_child_reasoners(child_reasoners, parent_micro_op, new_type, target)

        return atleast_one_sub_type_worked

@contextmanager
def scoped_bind(value, composite_type, bind=True, reasoner=DUMMY_REASONER):
    if not isinstance(composite_type, CompositeType):
        raise FatalError()

    try:
        if bind:
            manager = get_manager(value)
            top_node = add_composite_type(manager, composite_type, reasoner=reasoner)
        yield
    finally:
        top_node = None
        # Wait for GC to unbind everything
        pass
