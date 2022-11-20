# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from lockdown.type_system.core_types import Type, BottomType, AnyType
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.universal_type import PythonDict, Universal, \
    PythonList


def enrich_break_type(data):
    from lockdown.executor.type_factories import enrich_type

    if not isinstance(data, Universal):
        raise FatalError()
    if not data._contains("out"):
        raise FatalError()

    result = {
        "out": enrich_type(data._get("out"))
    }
    if data._contains("in"):
        result["in"] = enrich_type(data._get("in"))
    return result

def are_break_types_a_subset(self, other, reasoner):
    if other is None or other.break_types is None:
        raise FatalError
    for mode, other_break_types_for_mode in other.break_types.items():
        for other_break_type_for_mode in other_break_types_for_mode:
            our_break_types_for_mode = self.break_types.get(mode, self.break_types.get("*", None))
            if our_break_types_for_mode is None:
                return False

            if not isinstance(our_break_types_for_mode, list):
                raise FatalError()

            for our_break_type_for_mode in our_break_types_for_mode:
                if not isinstance(our_break_type_for_mode, dict):
                    raise FatalError()

                our_out = our_break_type_for_mode["out"]
                our_in = our_break_type_for_mode.get("in")

                other_out = other_break_type_for_mode["out"]
                other_in = other_break_type_for_mode.get("in")

                if our_in is not None and other_in is None:
                    continue

                out_is_compatible = our_out.is_copyable_from(other_out, reasoner)
                in_is_compatible = our_in is None or other_in.is_copyable_from(our_in, reasoner)

                if out_is_compatible and in_is_compatible:
                    break
            else:
                return False
    return True

class OpenFunctionType(Type):
    def __init__(self, argument_type, outer_type, break_types):
        self.argument_type = argument_type
        self.outer_type = outer_type
        self.break_types = break_types

    def is_copyable_from(self, other, reasoner):
        if not isinstance(other, OpenFunctionType):
            return False
        if not other.argument_type.is_copyable_from(self.argument_type, reasoner):
            return False
        if not other.outer_type.is_copyable_from(self.outer_type, reasoner):
            return False
        if not are_break_types_a_subset(self, other, reasoner):
            return False
        return True

class ClosedFunctionType(Type):
    def __init__(self, argument_type, break_types):
        self.argument_type = argument_type
        self.break_types = break_types

        if argument_type is None:
            raise FatalError()
        if break_types is None:
            raise FatalError()
        if not isinstance(break_types, dict):
            raise FatalError(break_types)
        for break_types_for_mode in break_types.values():
            if not isinstance(break_types_for_mode, list):
                raise FatalError(break_types_for_mode)
            for break_type in break_types_for_mode:
                if not isinstance(break_type, dict):
                    raise FatalError(break_type)

    def is_copyable_from(self, other, reasoner):
        if not isinstance(other, ClosedFunctionType):
            return False
        if not other.argument_type.is_copyable_from(self.argument_type, reasoner):
            return False
        if not are_break_types_a_subset(self, other, reasoner):
            return False
        return True

    def __repr__(self):
        return "ClosedFunctionType<{} => {}>".format(self.argument_type, self.break_types)

