from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.flow_control import FlowManager, BreakTypesFactory
from rdhlang5.executor.opcodes import enrich_opcode, get_context_type, evaluate, \
    TypeErrorFactory, get_expression_break_types, flatten_out_types
from rdhlang5.executor.type_factories import enrich_type
from rdhlang5.utils import MISSING
from rdhlang5_types.composites import bind_type_to_value
from rdhlang5_types.core_types import AnyType, Type
from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE, \
    DEFAULT_DICT_TYPE
from rdhlang5_types.exceptions import FatalError
from rdhlang5_types.managers import get_type_of_value, get_manager
from rdhlang5_types.object_types import RDHObjectType, RDHObject


def enrich_break_type(data):
    result = {
        "out": enrich_type(data.out)
    }
    if hasattr(data, "in"):
        result["in"] = enrich_type(getattr(data, "in"))
    return RDHObject(result)

def prepare(data, outer_context, flow_manager):
    if not hasattr(data, "code"):
        raise PreparationException()

    actual_break_types_factory = BreakTypesFactory()

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

    get_manager(static).add_composite_type(DEFAULT_OBJECT_TYPE)

    argument_type = enrich_type(static.argument)

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

    local_type = enrich_type(static.local)
    local_initializer = enrich_opcode(data.local_initializer, None)
    actual_local_type, local_other_break_types = get_expression_break_types(local_initializer, context, flow_manager)

    if actual_local_type is MISSING:
        raise PreparationException()

    actual_local_type = flatten_out_types(actual_local_type)

    if not local_type.is_copyable_from(actual_local_type):
        raise PreparationException()

    actual_break_types_factory.merge(local_other_break_types)

    declared_break_types = {
        mode: [enrich_break_type(break_type) for break_type in break_types] for mode, break_types in static.break_types.__dict__.items()
    }

    get_manager(declared_break_types).add_composite_type(DEFAULT_DICT_TYPE)

    context = RDHObject({
        "outer": outer_context,
        "types": RDHObject({
            "outer": get_context_type(outer_context),
            "argument": argument_type,
            "local": local_type
        })
    }, bind=RDHObjectType({
        "outer": get_context_type(outer_context),
        "types": DEFAULT_OBJECT_TYPE
    }))

    _, code_break_types = get_expression_break_types(code, context, flow_manager)

    actual_break_types_factory.merge(code_break_types)

    for mode, actual_break_types in actual_break_types_factory.build().items():
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
                raise PreparationException("""Nothing declared for {}, {}.\nFunction declares break types {}.\nBut local_initialization breaks {} and code breaks {}""".format(
                    mode, actual_break_type, declared_break_types, local_other_break_types, code_break_types
                ))

    return PreparedFunction(data, code, argument_type, local_type, local_initializer, declared_break_types)

class FunctionType(Type):
    def __init__(self, argument_type, break_types):
        self.argument_type = argument_type
        self.break_types = break_types

class PreparedFunction(object):
    DID_NOT_TERMINATE = TypeErrorFactory("PreparedFunction: did_not_terminate")

    def __init__(self, data, code, argument_type, local_type, local_initializer, break_types):
        self.data = data
        self.code = code
        self.argument_type = argument_type
        self.local_type = local_type
        self.local_initializer = local_initializer
        self.break_types = break_types

    def get_type(self):
        return FunctionType(self.argument_type, self.break_types)

    def invoke(self, argument, outer_context, flow_manager):
        if not self.argument_type.is_copyable_from(get_type_of_value(argument)):
            self.argument_type.is_copyable_from(get_type_of_value(argument))
            raise FatalError()

        with flow_manager.get_next_frame(self) as frame:
            new_context = RDHObject({
                "outer": outer_context,
                "argument": argument,
                "types": RDHObject({
                    "outer": get_context_type(outer_context),
                    "argument": self.argument_type
                })
            }, bind=RDHObjectType({
                "outer": get_context_type(outer_context),
                "argument": self.argument_type,
                "types": DEFAULT_OBJECT_TYPE
            }))

            local, _ = frame.step("local", lambda: evaluate(self.local_initializer, new_context, flow_manager))

            if not self.local_type.is_copyable_from(get_type_of_value(local)):
                raise FatalError()

            new_context = RDHObject({
                "outer": outer_context,
                "argument": argument,
                "local": local,
                "types": RDHObject({
                    "outer": get_context_type(outer_context),
                    "argument": self.argument_type,
                    "local": self.local_type
                })
            }, bind=RDHObjectType({
                "outer": get_context_type(outer_context),
                "argument": self.argument_type,
                "local": self.local_type,
                "types": DEFAULT_OBJECT_TYPE
            }))

            frame.step("code", lambda: evaluate(self.code, new_context, flow_manager))

        raise flow_manager.exception(self.DID_NOT_TERMINATE(), self)
