# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from lockdown.executor.ast_utils import compile_expression


class MicroOpType(object):
    """
    An operation that can be invoked against a CompositeObject. CompositeTypes
    are just collections of MicroOpTypes supported by the type.

    This is the abstract base class. There are implementations for getting, setting, adding,
    removing and inserting values into objects, dictionaries and lists.
    """
    def invoke(self, target_manager, *args, **kwargs):
        """
        Invoke the MicroOp. target_manager refers to the ComponsiteObject. Also accepts
        any other parameters needed for the MicroOp.
        """
        raise NotImplementedError(self)

    def is_derivable_from(self, other_type, reasoner):
        """
        Returns True if the MicroOp can be derived from the MicroOps on the other
        type (if it's a CompositeType).

        A MicroOp can be derived from another one if its functionality is somehow a
        "subset" of the functionality on the other type.

        For example, get.x.int is derivable from a CompositeType{ get.x.unit<4>, set.x.any }

        In an assignment statement, the derivability of all LHS MicroOps against the RHS CompositeType
        is checked. If all MicroOps are derivable, the assignment is valid.
        """
        raise NotImplementedError(self)

    def is_bindable_to(self, target):
        """
        Returns True if the current data in the target CompositeObject allows the MicroOp
        can be bound to it.

        Typical checks are:
        1. If the MicroOp can not generate a KeyError, that there is a value on the target.
        2. If the MicroOp can not generate a TypeError, that the current value is of the right type
        3. If the MicroOp is a wildcard type, and can not generate a KeyError, that there is a
            default factory
        """
        raise NotImplementedError(self)

    def conflicts_with(self, our_type, other_type, reasoner):
        """
        Returns True if the MicroOp would conflict with the other_type CompositeType - meaning that
        the MicroOp could not be added to the CompositeType without risking some data corruption.

        There are lots of cases where a MicroOp might not be derivable from a CompositeType,
        but that does not mean they are in conflict.

        Examples of conflicts include:
        1. get.x.int against CompositeType { set.x.any }
        2. set.x.any against CompositeType { get.x.int }

        The following are not conflicts, although they might not be bindable:
        1. get.x.int against CompositeType { get.x.any }
        2. set.x.int against CompositeType { get.x.any }
        3. get.x.any against CompositeType { get.y.any }
        """
        raise NotImplementedError(self)

    def prepare_bind(self, target, key_filter, substitute_value):
        """
        For a given target CompositeObject, returns objects or values referred to by this
        MicroOp, and the type constraint of this MicroOp.

        This is used when preparing to bind CompositeTypes against CompositeObjects at
        run time, for example when local variables are created.

        This is also used when making mutations to CompositeObjects, to make sure that
        changes to bindings (either applying or reversing it) is permitted at run time,
        for example when an object is mutated.

        In both cases, it allows the binding algorithm to traverse the tree of CompositeObjects
        through the MicroOps, without having to know the internals of them.

        When provided with a key_filter, this means the function should only return
        objects and types matching this filter. And when provided with a substitute_value,
        this means the function should return this value instead of that already on the object.
        This is used when considering mutations.        
        """
        # Returns a tuple (nested_targets, nested_type)
        raise NotImplementedError(self)

    def merge(self, other_micro_op_type):
        """
        Returns a new MicroOp that has the other one merged in.

        The other MicroOp must be the same type (ie, get.x) but might have a different
        attached type or error conditions.
        """
        raise NotImplementedError(self)

    def clone(self, **kwargs):
        """
        Returns a new MicroOp, with some properties overriden by kwargs
        """
        raise NotImplementedError(self)

    def to_ast(self, dependency_builder, target, *args):
        """
        Returns a Python ast.expr object that executes the opcode.

        The default implementation creates a module level Python Function that
        calls the invoke() method on the opcode directly. i.e. is drops back
        from Python code into the interpreter.

        Subclasses can provide more efficient Python code that doesn't require
        a function call for each MicroOp
        """
        args_parameters = { "arg{}".format(i): a for i, a in enumerate(args) }
        args_string = ", {" + "},{".join(args_parameters.keys()) + "}" if len(args_parameters) > 0 else ""

        return compile_expression(
            "{invoke}(get_manager({target})" + args_string + ")",
            None, dependency_builder,
            invoke=self.invoke, target=target, **args_parameters
        )

def merge_composite_types(types, name=None):
    from lockdown.type_system.composites import CompositeType

    types_with_opcodes = [t for t in types if t.get_micro_op_types()]

    from lockdown.type_system.universal_type import EMPTY_COMPOSITE_TYPE

    if len(types_with_opcodes) == 0:
        return EMPTY_COMPOSITE_TYPE
    if len(types_with_opcodes) == 1:
        singular = types_with_opcodes[0]
        if singular.frozen:
            return singular
        return singular.clone(name=name)

    result = {}
    for type in types_with_opcodes:
        for tag, micro_op_type in type.get_micro_op_types().items():
            if tag in result:
                result[tag] = result[tag].merge(micro_op_type)
            else:
                result[tag] = micro_op_type

    return CompositeType(result, name=name).freeze()

