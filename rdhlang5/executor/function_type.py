# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rdhlang5.type_system.core_types import Type


def enrich_break_type(data):
    from rdhlang5.executor.type_factories import enrich_type
    result = {
        "out": enrich_type(data["out"])
    }
    if "in" in data:
        result["in"] = enrich_type(data.get("in"))
    return result

class FunctionType(Type):
    def __init__(self, argument_type, break_types):
        self.argument_type = argument_type
        self.break_types = break_types

    def is_copyable_from(self, other):
        if not isinstance(other, FunctionType):
            return False
        if not other.argument_type.is_copyable_from(self.argument_type):
            return False
        for mode, other_break_types_for_mode in other.break_types.items():
            for other_break_type_for_mode in other_break_types_for_mode:
                our_break_types_for_mode = self.break_types.get(mode, None)
                if our_break_types_for_mode is None:
                    return False

                for our_break_type_for_mode in our_break_types_for_mode:
                    our_out = our_break_type_for_mode["out"]
                    our_in = our_break_type_for_mode.get("in", None)

                    other_out = other_break_type_for_mode["out"]
                    other_in = other_break_type_for_mode.get("in", None)

                    if our_in is not None and other_in is None:
                        continue

                    out_is_compatible = our_out.is_copyable_from(other_out)
                    in_is_compatible = our_in is None or other_in.is_copyable_from(our_in)

                    if out_is_compatible and in_is_compatible:
                        break
                else:
                    return False
        return True
