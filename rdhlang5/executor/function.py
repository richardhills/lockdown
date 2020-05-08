from _collections import defaultdict

from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.flow_control import FlowManager, BreakTypesFactory
from rdhlang5.executor.function_type import FunctionType, enrich_break_type
from rdhlang5.executor.opcodes import enrich_opcode, get_context_type, evaluate, \
    TypeErrorFactory, get_expression_break_types, flatten_out_types
from rdhlang5.executor.type_factories import enrich_type
from rdhlang5.utils import MISSING
from rdhlang5_types.composites import CompositeType
from rdhlang5_types.core_types import Type
from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE, \
    DEFAULT_DICT_TYPE
from rdhlang5_types.exceptions import FatalError
from rdhlang5_types.managers import get_type_of_value, get_manager
from rdhlang5_types.object_types import RDHObjectType, RDHObject
from rdhlang5_types.utils import NO_VALUE


def prepare(data, outer_context, flow_manager, immediate_context=None):
    get_manager(data).add_composite_type(DEFAULT_OBJECT_TYPE)

    if not hasattr(data, "code"):
        raise PreparationException()

    actual_break_types_factory = BreakTypesFactory()

    context = RDHObject({
        "outer": outer_context,
        "types": RDHObject({
            "outer": get_context_type(outer_context)
        })
    }, bind=DEFAULT_OBJECT_TYPE)

    static = evaluate(enrich_opcode(data.static, UnboundDereferenceBinder(context)), context, flow_manager)

    get_manager(static).add_composite_type(DEFAULT_OBJECT_TYPE)

    argument_type = enrich_type(static.argument)

    if immediate_context:
        suggested_argument_type = immediate_context.get("suggested_argument_type", None)
        if not isinstance(suggested_argument_type, Type):
            raise PreparationException()
        if suggested_argument_type:
            argument_type = argument_type.replace_inferred_types(suggested_argument_type)
            argument_type = argument_type.reify_revconst_types()

    context = RDHObject({
        "outer": outer_context,
        "static": static,
        "types": RDHObject({
            "outer": get_context_type(outer_context),
            "argument": argument_type
        })
    }, bind=DEFAULT_OBJECT_TYPE)

    local_type = enrich_type(static.local)
    local_initializer = enrich_opcode(data.local_initializer, UnboundDereferenceBinder(context))
    actual_local_type, local_other_break_types = get_expression_break_types(local_initializer, context, flow_manager)

    if actual_local_type is MISSING:
        raise PreparationException()

    actual_local_type = flatten_out_types(actual_local_type)

    local_type = local_type.replace_inferred_types(actual_local_type)
    local_type = local_type.reify_revconst_types()

    if not local_type.is_copyable_from(actual_local_type):
        raise PreparationException()

    actual_break_types_factory.merge(local_other_break_types)

    declared_break_types = {
        mode: [enrich_break_type(break_type) for break_type in break_types] for mode, break_types in static.break_types.__dict__.items()
    }

    get_manager(declared_break_types).add_composite_type(DEFAULT_DICT_TYPE)

    context = RDHObject({
        "outer": outer_context,
        "static": static,
        "types": RDHObject({
            "outer": get_context_type(outer_context),
            "argument": argument_type,
            "local": local_type
        })
    }, bind=DEFAULT_OBJECT_TYPE)

    code = enrich_opcode(data.code, UnboundDereferenceBinder(context))

    code_break_types = code.get_break_types(context, flow_manager)

    actual_break_types_factory.merge(code_break_types)

    final_declared_break_types = BreakTypesFactory()

    for mode, actual_break_types in actual_break_types_factory.build().items():
        for actual_break_type in actual_break_types:
            declared_break_types_for_mode = declared_break_types.get(mode, declared_break_types.get("wildcard", []))
            for declared_break_type_for_mode in declared_break_types_for_mode:
                # Check if this declared_break_type_for_mode is enough to capture the actual_break_types
                declared_out = declared_break_type_for_mode["out"]
                declared_in = declared_break_type_for_mode.get("in", None)
                actual_out = actual_break_type["out"]
                actual_in = actual_break_type.get("in", None)

                declared_out = declared_out.replace_inferred_types(actual_out)
                if declared_in is not None:
                    declared_in = declared_in.replace_inferred_types(actual_in)

                if declared_in is not None and actual_in is None:
                    continue

                out_is_compatible = declared_out.is_copyable_from(actual_out)
                in_is_compatible = declared_in is None or actual_in.is_copyable_from(declared_in)

                if out_is_compatible and in_is_compatible:
                    final_declared_break_types.add(mode, declared_out, declared_in)
                    break
            else:
                raise PreparationException("""Nothing declared for {}, {}.\nFunction declares break types {}.\nBut local_initialization breaks {}, code breaks {}""".format(
                    mode, actual_break_type, declared_break_types, local_other_break_types, code_break_types
                ))

    return PreparedFunction(data, code, argument_type, local_type, local_initializer, final_declared_break_types.build())


class UnboundDereferenceBinder(object):
    def __init__(self, context):
        self.context = context

    def search_for_reference(self, reference, prepend_context=[]):
        from rdhlang5.executor.raw_code_factories import dereference

        types = getattr(self.context, "types", None)
        if types:
            argument_type = getattr(self.context.types, "argument", None)
            if isinstance(argument_type, CompositeType):
                getter = argument_type.micro_op_types.get(("get", reference), None)
                if getter:
                    return dereference(prepend_context, "argument", reference)
            local_type = getattr(self.context.types, "local", None)
            if isinstance(local_type, CompositeType):
                getter = local_type.micro_op_types.get(("get", reference), None)
                if getter:
                    return dereference(prepend_context, "local", reference)
        static = getattr(self.context, "static", None)
        if static and hasattr(static, reference):
            return dereference(prepend_context, "static", reference)
        outer_context = getattr(self.context, "outer", None)
        if outer_context:
            return UnboundDereferenceBinder(outer_context).search_for_reference(prepend_context + [ "outer" ], reference)

    def __call__(self, expression):
        if getattr(expression, "opcode", None) == "unbound_dereference":
            reference = expression.reference
            bound_reference = self.search_for_reference(reference)

            if bound_reference:
                get_manager(bound_reference).add_composite_type(DEFAULT_OBJECT_TYPE)
                return bound_reference
            else:
                raise FatalError() # TODO, dynamic dereference

        return expression


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

            result, _ = frame.step("code", lambda: evaluate(self.code, new_context, flow_manager))

        raise flow_manager.value(result, self)
