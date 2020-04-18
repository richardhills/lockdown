from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.opcodes import enrich_opcode, get_context_type, evaluate, \
    TypeErrorFactory
from rdhlang5.executor.type_factories import enrich_type
from rdhlang5_types.core_types import AnyType, Type
from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE
from rdhlang5_types.exceptions import FatalError
from rdhlang5_types.managers import get_type_of_value
from rdhlang5_types.object_types import RDHObjectType, RDHObject
from rdhlang5.executor.flow_control import FlowManager


def enrich_break_type(data):
    result = {
        "out": enrich_type(data.out)
    }
    if hasattr(data, "in"):
        result["in"] = enrich_type(getattr(data, "in"))
    return RDHObject(result, bind=DEFAULT_OBJECT_TYPE)

def prepare(data, outer_context, flow_manager):
    if not hasattr(data, "code"):
        raise PreparationException()

    code = enrich_opcode(data.code, None)

    context = RDHObject({
        "outer": outer_context,
        "types": RDHObject({
            "outer": get_context_type(outer_context)
        })
    }, bind=RDHObjectType({
        "outer": get_context_type(outer_context),
        "types": DEFAULT_OBJECT_TYPE
    }))

    static = evaluate(enrich_opcode(data.static, None), context, flow_manager)

    argument_type = enrich_type(static.argument)

    declared_break_types = {
        mode: [enrich_break_type(break_type) for break_type in break_types] for mode, break_types in static.break_types.__dict__.items()
    }

    context = RDHObject({
        "outer": outer_context,
        "types": RDHObject({
            "outer": get_context_type(outer_context),
            "argument": argument_type
        })
    }, bind=RDHObjectType({
        "outer": get_context_type(outer_context),
        "types": DEFAULT_OBJECT_TYPE
    }))

    actual_break_types_for_modes = code.get_break_types(context, flow_manager)

    actual_break_types_for_modes.pop("value", None)

    for mode, actual_break_types in actual_break_types_for_modes.items():
        for actual_break_type in actual_break_types:
            declared_break_types_for_mode = declared_break_types.get(mode, [])
            for declared_break_type_for_mode in declared_break_types_for_mode:
                declared_out = declared_break_type_for_mode.out
                declared_in = getattr(declared_break_type_for_mode, "in", None)
                actual_out = actual_break_type["out"]
                actual_in = actual_break_type.get("in", None)

                if declared_in is not None and actual_in is None:
                    continue

                if declared_out.is_copyable_from(actual_out) and (declared_in is None or actual_in.is_copyable_from(declared_in)):
                    break
            else:
                raise PreparationException()

    return PreparedFunction(data, code, argument_type, declared_break_types)

class FunctionType(Type):
    def __init__(self, argument_type, break_types):
        self.argument_type = argument_type
        self.break_types = break_types

class PreparedFunction(object):
    DID_NOT_TERMINATE = TypeErrorFactory("PreparedFunction: did_not_terminate")

    def __init__(self, data, code, argument_type, break_types):
        self.data = data
        self.code = code
        self.argument_type = argument_type
        self.break_types = break_types

    def get_type(self):
        return FunctionType(self.argument_type, self.break_types)

    def invoke(self, argument, outer_context, break_manager):
        if not self.argument_type.is_copyable_from(get_type_of_value(argument)):
            self.argument_type.is_copyable_from(get_type_of_value(argument))
            raise FatalError()

        new_context = RDHObject({
            "outer": outer_context,
            "argument": argument,
            "types": RDHObject({
                "outer": get_context_type(outer_context)
            }, bind=DEFAULT_OBJECT_TYPE)
        }, bind=RDHObjectType({
            "argument": self.argument_type,
            "outer": get_context_type(outer_context),
            "types": DEFAULT_OBJECT_TYPE
        }))

        evaluate(self.code, new_context, break_manager)

        raise break_manager.exception(self.DID_NOT_TERMINATE(), self)
