# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.flow_control import BreakTypesFactory
from rdhlang5.executor.function_type import enrich_break_type, OpenFunctionType, \
    ClosedFunctionType
from rdhlang5.executor.opcodes import enrich_opcode, get_context_type, evaluate, \
    get_expression_break_types, flatten_out_types
from rdhlang5.executor.raw_code_factories import dynamic_dereference_op
from rdhlang5.executor.type_factories import enrich_type
from rdhlang5.type_system.composites import CompositeType
from rdhlang5.type_system.core_types import Type, NoValueType
from rdhlang5.type_system.default_composite_types import DEFAULT_OBJECT_TYPE, \
    DEFAULT_DICT_TYPE
from rdhlang5.type_system.exceptions import FatalError
from rdhlang5.type_system.managers import get_manager, get_type_of_value
from rdhlang5.type_system.object_types import RDHObject, RDHObjectType
from rdhlang5.utils import MISSING


def prepare(data, outer_context, flow_manager, immediate_context=None):
    get_manager(data).add_composite_type(DEFAULT_OBJECT_TYPE)

    if not hasattr(data, "code"):
        raise PreparationException()

    actual_break_types_factory = BreakTypesFactory()

    context = RDHObject({
        "prepare": outer_context
    }, bind=DEFAULT_OBJECT_TYPE)

    static = evaluate(
        enrich_opcode(data.static, UnboundDereferenceBinder(context)),
        context, flow_manager
    )

    get_manager(static).add_composite_type(DEFAULT_OBJECT_TYPE)

    argument_type = enrich_type(static.argument)
    outer_type = enrich_type(static.outer)

    suggested_argument_type = suggested_outer_type = None

    if immediate_context:
        suggested_argument_type = immediate_context.get("suggested_argument_type", None)
        suggested_outer_type = immediate_context.get("suggested_outer_type", None)

    if suggested_argument_type is None:
        suggested_argument_type = NoValueType()
    if suggested_outer_type is None:
        suggested_outer_type = NoValueType()

    if not isinstance(suggested_argument_type, Type):
        raise PreparationException()
    if not isinstance(suggested_outer_type, Type):
        raise PreparationException()

    argument_type = argument_type.replace_inferred_types(suggested_argument_type)
    argument_type = argument_type.reify_revconst_types()
    outer_type = outer_type.replace_inferred_types(suggested_outer_type)
    outer_type = outer_type.reify_revconst_types()

    context = RDHObject({
        "prepare": outer_context, 
        "static": static,
        "types": RDHObject({
            "outer": outer_type,
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
        local_type.is_copyable_from(actual_local_type)
        raise PreparationException()

    actual_break_types_factory.merge(local_other_break_types)

    declared_break_types = {
        mode: [enrich_break_type(break_type) for break_type in break_types] for mode, break_types in static.break_types.__dict__.items()
    }

    get_manager(declared_break_types).add_composite_type(DEFAULT_DICT_TYPE)

    context = RDHObject({
        "prepare": outer_context,
        "static": static,
        "types": RDHObject({
            "outer": outer_type,
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

    return OpenFunction(data, code, outer_context, static, argument_type, outer_type, local_type, local_initializer, final_declared_break_types.build())


class UnboundDereferenceBinder(object):
    def __init__(self, context, search_types=True):
        self.context = context
        self.search_types = search_types
        self.context_type = get_context_type(self.context)

#     def search_outer_type_for_reference(self, reference, outer_type, prepend_context):
#         from rdhlang5.executor.raw_code_factories import dereference
# 
#         getter = outer_type.micro_op_types.get(("get", reference))
#         if getter:
#             return dereference(prepend_context, "outer")
# 
#         next_outer = outer_type.micro_op_types.get(("get", "outer"))
#         if next_outer:
#             return self.search_outer_type_for_reference(reference, next_outer.type, prepend_context + [ "outer" ])

    def search_context_type_area_for_reference(self, reference, area, context_type, prepend_context):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        area_getter = context_type.micro_op_types.get(("get", area), None)
        if not area_getter:
            return None
        area_type = area_getter.type
        if not isinstance(area_type, CompositeType):
            return None
        getter = area_type.micro_op_types.get(("get", reference), None)
        if getter:
            return dereference(prepend_context, area)

    def search_context_type_for_reference(self, reference, context_type, prepend_context):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        argument_search = self.search_context_type_area_for_reference(reference, "argument", context_type, prepend_context)
        if argument_search:
            return argument_search
        local_search = self.search_context_type_area_for_reference(reference, "local", context_type, prepend_context)
        if local_search:
            return local_search

        outer_getter = context_type.micro_op_types.get(("get", "outer"), None)
        if outer_getter:
            outer_search = self.search_context_type_for_reference(reference, outer_getter.type, prepend_context + [ "outer" ])
            if outer_search:
                return outer_search

    def search_statics_for_reference(self, reference, context, prepend_context):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        static = getattr(context, "static", None)
        if static and hasattr(static, reference):
            return dereference(prepend_context, "static")

        prepare = getattr(context, "prepare", None)
        if prepare:
            prepare_search = self.search_statics_for_reference(reference, prepare, prepend_context + [ "prepare" ])
            if prepare_search:
                return prepare_search

    def search_for_reference(self, reference):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        if not isinstance(reference, basestring):
            raise FatalError()

        if reference in ("prepare", "local", "argument", "outer", "static"):
            return context_op()

        types_search = self.search_context_type_for_reference(reference, self.context_type, [])
        if types_search:
            return types_search
        statics_search = self.search_statics_for_reference(reference, self.context, [])
        if statics_search:
            return statics_search

        return None

    def __call__(self, expression):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        if getattr(expression, "opcode", None) == "unbound_dereference":
            reference = expression.reference
            if reference == "foom":
                pass
            bound_countext_op = self.search_for_reference(reference)

            if bound_countext_op:
                new_dereference = dereference_op(bound_countext_op, literal_op(reference))
                get_manager(new_dereference).add_composite_type(DEFAULT_OBJECT_TYPE)
                return new_dereference
            else:
                new_dereference = dynamic_dereference_op(reference)
                get_manager(new_dereference).add_composite_type(DEFAULT_OBJECT_TYPE)
                return new_dereference

        if getattr(expression, "opcode", None) == "unbound_assignment":
            reference = expression.reference
            bound_countext_op = self.search_for_reference(reference)

            if bound_countext_op:
                new_assignment = assignment_op(bound_countext_op, literal_op(reference), expression.rvalue)
                get_manager(new_assignment).add_composite_type(DEFAULT_OBJECT_TYPE)
                return new_assignment
            else:
                raise FatalError() # TODO, dynamic dereference

        return expression

class RDHFunction(object):
    def get_type(self):
        raise NotImplementedError(self)

    def invoke(self, argument, flow_manager):
        raise NotImplementedError()

class OpenFunction(object):
    def __init__(self, data, code, prepare_context, static, argument_type, outer_type, local_type, local_initializer, break_types):
        self.data = data
        self.code = code
        self.prepare_context = prepare_context
        self.static = static
        self.argument_type = argument_type
        self.outer_type = outer_type
        self.local_type = local_type
        self.local_initializer = local_initializer
        self.break_types = break_types

    def get_type(self):
        return OpenFunctionType(self.argument_type, self.outer_type, self.break_types)

    def close(self, outer_context):
        if not self.outer_type.is_copyable_from(get_type_of_value(outer_context)):
            raise FatalError()

        return ClosedFunction(
            self.data,
            self.code,
            self.prepare_context,
            self.static,
            self.argument_type,
            self.outer_type,
            self.local_type,
            outer_context,
            self.local_initializer,
            self.break_types
        )

class ClosedFunction(RDHFunction):
    def __init__(self, data, code, prepare_context, static, argument_type, outer_type, local_type, outer_context, local_initializer, break_types):
        self.data = data
        self.code = code
        self.prepare_context = prepare_context
        self.static = static
        self.argument_type = argument_type
        self.outer_type = outer_type
        self.local_type = local_type
        self.outer_context = outer_context
        self.local_initializer = local_initializer
        self.break_types = break_types

    def get_type(self):
        return ClosedFunctionType(
            self.argument_type, self.break_types
        )

    def invoke(self, argument, flow_manager):
        if not self.argument_type.is_copyable_from(get_type_of_value(argument)):
            raise FatalError()

        with flow_manager.get_next_frame(self) as frame:
            new_context = RDHObject({
                "prepare": self.prepare_context,
                "outer": self.outer_context,
                "argument": argument,
                "static": self.static,
                "types": RDHObject({
                    "outer": self.outer_type,
                    "argument": self.argument_type
                })
            }, bind=RDHObjectType({
                "outer": self.outer_type,
                "argument": self.argument_type,
                "types": DEFAULT_OBJECT_TYPE
            }))

            local, _ = frame.step("local", lambda: evaluate(self.local_initializer, new_context, flow_manager))

            if not self.local_type.is_copyable_from(get_type_of_value(local)):
                raise FatalError()

            new_context = RDHObject({
                "prepare": self.prepare_context,
                "outer": self.outer_context,
                "argument": argument,
                "static": self.static,
                "local": local,
                "types": RDHObject({
                    "outer": self.outer_type,
                    "argument": self.argument_type,
                    "local": self.local_type
                })
            }, bind=RDHObjectType({
                "prepare": DEFAULT_OBJECT_TYPE,
                "outer": self.outer_type,
                "argument": self.argument_type,
                "static": DEFAULT_OBJECT_TYPE,
                "local": self.local_type,
                "types": DEFAULT_OBJECT_TYPE
            }))

            result, _ = frame.step("code", lambda: evaluate(self.code, new_context, flow_manager))

        raise flow_manager.value(result, self)
