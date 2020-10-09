# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from _ast import AST
import ast
import sys

from astor.code_gen import to_source

from log import logger
from rdhlang5.executor.ast_utils import unwrap_expr, \
    build_and_compile_ast_function, compile_module, compile_statement, \
    DependencyBuilder, compile_function, compile_ast_function_def, \
    get_dependency_key
from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.flow_control import BreakTypesFactory, FrameManager, \
    is_restartable
from rdhlang5.executor.function_type import enrich_break_type, OpenFunctionType, \
    ClosedFunctionType
from rdhlang5.executor.opcodes import enrich_opcode, get_context_type, evaluate, \
    get_expression_break_types, flatten_out_types, TransformOp
from rdhlang5.executor.raw_code_factories import dynamic_dereference_op, \
    static_op, match_op, prepared_function, inferred_type
from rdhlang5.executor.type_factories import enrich_type
from rdhlang5.type_system.composites import CompositeType
from rdhlang5.type_system.core_types import Type, NoValueType, IntegerType, \
    TopType, AnyType
from rdhlang5.type_system.default_composite_types import DEFAULT_OBJECT_TYPE, \
    DEFAULT_DICT_TYPE, READONLY_DEFAULT_OBJECT_TYPE, \
    readonly_rich_composite_type
from rdhlang5.type_system.dict_types import RDHDict
from rdhlang5.type_system.exceptions import FatalError, InvalidInferredType, \
    MicroOpTypeConflict, IncorrectObjectTypeForMicroOp
from rdhlang5.type_system.list_types import RDHList
from rdhlang5.type_system.managers import get_manager, get_type_of_value
from rdhlang5.type_system.object_types import RDHObject, RDHObjectType
from rdhlang5.utils import MISSING, is_debug, runtime_type_information, raise_from, \
    spread_dict


def prepare(data, outer_context, frame_manager, immediate_context=None):
    if not isinstance(data, RDHObject):
        raise FatalError()
    get_manager(data).add_composite_type(READONLY_DEFAULT_OBJECT_TYPE)

    if not hasattr(data, "code"):
        raise PreparationException("Code missing from function")

    actual_break_types_factory = BreakTypesFactory(None)

    context = RDHObject({
        "prepare": outer_context
    }, bind=READONLY_DEFAULT_OBJECT_TYPE, debug_reason="static-prepare-context")

    static = evaluate(
        enrich_opcode(
            data.static,
            combine(type_conditional_converter, UnboundDereferenceBinder(context))
        ),
        context, frame_manager
    )

    get_manager(static).add_composite_type(READONLY_DEFAULT_OBJECT_TYPE)

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
        raise FatalError()
    if not isinstance(suggested_outer_type, Type):
        raise FatalError()

    try:
        argument_type = argument_type.replace_inferred_types(suggested_argument_type)
    except InvalidInferredType:
        raise PreparationException("Invalid argument inferred types")
    try:
        outer_type = outer_type.replace_inferred_types(suggested_outer_type)
    except InvalidInferredType:
        raise PreparationException("Invalid outer inferred types")

    argument_type = argument_type.reify_revconst_types()
    outer_type = outer_type.reify_revconst_types()
    local_type = enrich_type(static.local)

    context = RDHObject({
        "prepare": outer_context,
        "static": static,
        "types": RDHObject({
            "outer": outer_type,
            "argument": argument_type,
#            "local": local_type
        }, debug_reason="local-prepare-context")
    },
        bind=READONLY_DEFAULT_OBJECT_TYPE,
        instantiator_has_verified_bind=True,
        debug_reason="local-prepare-context"
    )

# optimization to avoid generating context_type lazily
    get_manager(context)._context_type = RDHObjectType({
        "outer": outer_type,
        "argument": argument_type,
#        "local": local_type
    }, wildcard_value_type=AnyType(), name="local-prepare-context-type")

    local_initializer = enrich_opcode(
        data.local_initializer,
        combine(type_conditional_converter, UnboundDereferenceBinder(context))
    )
    actual_local_type, local_other_break_types = get_expression_break_types(
        local_initializer,
        context,
        frame_manager
    )

    get_manager(context).remove_composite_type(READONLY_DEFAULT_OBJECT_TYPE)

    if actual_local_type is MISSING:
        raise PreparationException("Actual local type missing")

    actual_local_type = flatten_out_types(actual_local_type)

    try:
        local_type = local_type.replace_inferred_types(actual_local_type)
    except InvalidInferredType:
        local_type = local_type.replace_inferred_types(actual_local_type)
        raise PreparationException("Invalid local inferred type")

    local_type = local_type.reify_revconst_types()

    if not local_type.is_copyable_from(actual_local_type):
        local_type.is_copyable_from(actual_local_type)
        raise PreparationException("Invalid local type: {} != {}".format(local_type, actual_local_type))

    actual_break_types_factory.merge(local_other_break_types)

    declared_break_types = RDHDict({
        mode: RDHList([enrich_break_type(break_type) for break_type in break_types]) for mode, break_types in static.break_types.__dict__.items()
    })

    get_manager(declared_break_types).add_composite_type(DEFAULT_DICT_TYPE)

    context = RDHObject({
        "prepare": outer_context,
        "static": static,
        "types": RDHObject({
            "outer": outer_type,
            "argument": argument_type,
            "local": local_type
        }, debug_reason="code-prepare-context")
    },
        bind=READONLY_DEFAULT_OBJECT_TYPE,
        instantiator_has_verified_bind=True,
        debug_reason="code-prepare-context"
    )

    get_manager(context)._context_type = RDHObjectType({
        "outer": outer_type,
        "argument": argument_type,
        "local": local_type
    }, wildcard_value_type=AnyType(), name="code-prepare-context-type")

    code = enrich_opcode(
        data.code,
        combine(type_conditional_converter, UnboundDereferenceBinder(context))
    )

    code_break_types = code.get_break_types(context, frame_manager)

    get_manager(context).remove_composite_type(READONLY_DEFAULT_OBJECT_TYPE)

    actual_break_types_factory.merge(code_break_types)

    final_declared_break_types = BreakTypesFactory(None)

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


def get_debug_info_from_opcode(opcode):
    return {
        "column": getattr(opcode, "column", None),
        "line": getattr(opcode, "line", None),
    }


class UnboundDereferenceBinder(object):
    def __init__(self, context, search_types=True):
        self.context = context
        self.search_types = search_types
        self.context_type = get_context_type(self.context)

    def search_context_type_area_for_reference(self, reference, area, context_type, prepend_context, debug_info):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        area_getter = context_type.micro_op_types.get(("get", area), None)
        if not area_getter:
            return None
        area_type = area_getter.value_type
        if not isinstance(area_type, CompositeType):
            return None
        getter = area_type.micro_op_types.get(("get", reference), None)
        if getter:
            return dereference(prepend_context, area, **debug_info)

    def search_context_type_for_reference(self, reference, context_type, prepend_context, debug_info):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        argument_search = self.search_context_type_area_for_reference(reference, "argument", context_type, prepend_context, debug_info)
        if argument_search:
            return argument_search
        local_search = self.search_context_type_area_for_reference(reference, "local", context_type, prepend_context, debug_info)
        if local_search:
            return local_search

        outer_getter = context_type.micro_op_types.get(("get", "outer"), None)
        if outer_getter:
            outer_search = self.search_context_type_for_reference(reference, outer_getter.value_type, prepend_context + [ "outer" ], debug_info)
            if outer_search:
                return outer_search

    def search_statics_for_reference(self, reference, context, prepend_context, debug_info):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        static = getattr(context, "static", None)
        if static and hasattr(static, reference):
            return dereference(prepend_context, "static", **debug_info)

        prepare = getattr(context, "prepare", None)
        if prepare:
            prepare_search = self.search_statics_for_reference(reference, prepare, prepend_context + [ "prepare" ], debug_info)
            if prepare_search:
                return prepare_search

    def search_for_reference(self, reference, debug_info):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        if not isinstance(reference, basestring):
            raise FatalError()

        if reference in ("prepare", "local", "argument", "outer", "static"):
            return context_op(), False

        types_search = self.search_context_type_for_reference(reference, self.context_type, [], debug_info)
        if types_search:
            return types_search, False
        statics_search = self.search_statics_for_reference(reference, self.context, [], debug_info)
        if statics_search:
            return statics_search, True

        return None, False

    def __call__(self, expression):
        from rdhlang5.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        debug_info = get_debug_info_from_opcode(expression)

        if getattr(expression, "opcode", None) == "unbound_dereference":
            reference = expression.reference
            if reference == "cachedResults":
                pass
            bound_countext_op, is_static = self.search_for_reference(reference, debug_info)

            if bound_countext_op:
                new_dereference = dereference_op(bound_countext_op, literal_op(reference), True, **debug_info)
                if is_static:
                    new_dereference = static_op(new_dereference)
                get_manager(new_dereference).add_composite_type(DEFAULT_OBJECT_TYPE)
                return new_dereference
            else:
                new_dereference = dynamic_dereference_op(reference, **debug_info)
                get_manager(new_dereference).add_composite_type(DEFAULT_OBJECT_TYPE)
                return new_dereference

        if getattr(expression, "opcode", None) == "unbound_assignment":
            reference = expression.reference
            bound_countext_op, _ = self.search_for_reference(reference, debug_info)

            if bound_countext_op:
                new_assignment = assignment_op(bound_countext_op, literal_op(reference), expression.rvalue, **debug_info)
                get_manager(new_assignment).add_composite_type(DEFAULT_OBJECT_TYPE)
                return new_assignment
            else:
                raise FatalError()  # TODO, dynamic assignment

        return expression


def type_conditional_converter(expression):
    if not hasattr(expression, "opcode"):
        pass
    is_conditional = expression.opcode == "conditional"
    if not is_conditional:
        return expression
    condition_is_type_check = expression.condition.opcode == "is"
    if not condition_is_type_check:
        return expression

    new_match = match_op(
        expression.condition.expression, [
            prepared_function(
                expression.condition.type,
                expression.when_true
            ),
            prepared_function(
                inferred_type(),
                expression.when_false
            )
        ]
    )
    get_manager(new_match).add_composite_type(DEFAULT_OBJECT_TYPE)
    return new_match

def combine(*funcs):
    def wrapped(expression):
        for func in funcs:
            expression = func(expression)
        return expression
    return wrapped

class RDHFunction(object):
    def get_type(self):
        raise NotImplementedError(self)

    def invoke(self, argument, frame_manager):
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

        self.types_context = RDHObject({
            "outer": self.outer_type,
            "argument": self.argument_type
        }, debug_reason="local-initialization-context")

        self.local_initialization_context_type = RDHObjectType({
            "outer": self.outer_type,
            "argument": self.argument_type,
            "types": readonly_rich_composite_type
        }, wildcard_value_type=AnyType(), name="local-initialization-context-type")

        self.execution_context_type = RDHObjectType({
            "prepare": readonly_rich_composite_type,
            "outer": self.outer_type,
            "argument": self.argument_type,
            "static": readonly_rich_composite_type,
            "local": self.local_type,
            "types": readonly_rich_composite_type
        }, wildcard_value_type=AnyType(), name="code-execution-context-type")

        self.compiled_ast = None

    def get_type(self):
        return OpenFunctionType(self.argument_type, self.outer_type, self.break_types)

    def close(self, outer_context):
        if is_debug() and not self.outer_type.is_copyable_from(get_type_of_value(outer_context)):
            raise FatalError()

        return ClosedFunction(self, outer_context)

    def to_ast(self, dependency_builder):
        if is_restartable(self):
            return None
        context_name = b"context_{}".format(id(self))

        local_initializer_ast = self.local_initializer.to_ast(context_name, dependency_builder)

        return_types = self.break_types.get("value", [])
        will_ignore_return_value = True
        for return_type in return_types:
            if not isinstance(return_type["out"], NoValueType):
                will_ignore_return_value = False

        code_ast = self.code.to_ast(
            context_name,
            dependency_builder,
            will_ignore_return_value=will_ignore_return_value
        )

        open_function_id = "OpenFunction{}".format(id(self))

        return compile_statement("""
class {open_function_id}(object):
    @classmethod
    def invoke(cls, {context_name}_argument, {context_name}_outer_context, _frame_manager):
        {context_name} = RDHObject({{
            "prepare": {prepare_context},
            "outer": {context_name}_outer_context,
            "argument": {context_name}_argument,
            "static": {static},
            "types": {types_context}
        }})
        {context_name}.__dict__["local"] = {local_initializer}
        """ \
        +(
            """
        {function_code}
        return ("value", NoValue, None, None)
            """
            if will_ignore_return_value else 
            """
        return ("value", {function_code}, None, None)
            """
        ) + """

    class Closed_{open_function_id}(object):
        def __init__(self, open_function, outer_context):
            self.open_function = open_function
            self.outer_context = outer_context

        def invoke(self, argument, frame_manager):
            return self.open_function.invoke(argument, self.outer_context, frame_manager)

    @classmethod
    def close(cls, outer_context):
        return cls.Closed_{open_function_id}(cls, outer_context)
""",
            context_name, dependency_builder,
            prepare_context=self.prepare_context,
            static=self.static,
            types_context=self.types_context,
            open_function_id=open_function_id,
            local_initializer=local_initializer_ast,
            function_code=code_ast
        )

    def to_inline_ast(self, dependency_builder, outer_context_ast, argument_ast):
        if is_restartable(self):
            return None
        context_name = b"context_{}".format(id(self))

        local_initializer_ast = self.local_initializer.to_ast(context_name, dependency_builder)

        return_types = self.break_types.get("value", [])
        will_ignore_return_value = True
        for return_type in return_types:
            if not isinstance(return_type["out"], NoValueType):
                will_ignore_return_value = False

        code_ast = self.code.to_ast(
            context_name,
            dependency_builder,
            will_ignore_return_value=will_ignore_return_value
        )

        return compile_module("""
{context_name} = RDHObject({{
    "prepare": {prepare_context},
    "outer": {outer_context},
    "argument": {argument},
    "static": {static},
    "types": {types_context}
}})
{context_name}.__dict__["local"] = {local_initializer}
{function_code}
            """,
            context_name, dependency_builder,
            prepare_context=self.prepare_context,
            outer_context=outer_context_ast,
            argument=argument_ast,
            static=self.static,
            types_context=self.types_context,
            local_initializer=local_initializer_ast,
            function_code=code_ast
        )

    def transpile(self):
        dependency_builder = DependencyBuilder()

        our_ast = self.to_ast(dependency_builder)
        open_function_id = our_ast.name

        combined_ast = [ our_ast ]

        while True:
            for key, dependency in dependency_builder.dependencies.items():
                if isinstance(dependency, OpenFunction):
                    open_function_ast = dependency.to_ast(dependency_builder)
                    if open_function_ast:
                        dependency_builder.replace(key, open_function_ast)
                    break
            else:
                break

        for key, dependency in dependency_builder.dependencies.items():
            if isinstance(dependency, ast.stmt):
                combined_ast = combined_ast + [ dependency ]

        dependencies = {
            key: dependency for key, dependency in dependency_builder.dependencies.items()
            if not isinstance(dependency, ast.stmt)
        }

        combined_ast = ast.Module(body=combined_ast)

        return compile_ast_function_def(combined_ast, open_function_id, dependencies)

    def to_code(self):
        break_types_code = ";".join(["{}: [{}]".format(mode, ",".join([format_break_type(b) for b in break_types])) for mode, break_types in self.break_types.items()])
        return "OpenFunction({} => {}\nOuter:{}\nLocal:{}\n{{\n{}\n}}\n)".format(
            self.argument_type.to_code(), break_types_code, self.outer_type.to_code(), self.local_type.to_code(), self.code.to_code()
        )


class ClosedFunction(RDHFunction):
    def __init__(self, open_function, outer_context):
        self.open_function = open_function
        self.outer_context = outer_context

    def get_type(self):
        return ClosedFunctionType(
            self.open_function.argument_type, self.open_function.break_types
        )

    @property
    def break_types(self):
        return self.open_function.break_types

    def transpile(self):
        open_function_transpile = self.open_function.transpile()

        return open_function_transpile.close(self.outer_context)

    def invoke(self, argument, frame_manager):
        logger.debug("ClosedFunction")
        if is_debug() and not self.open_function.argument_type.is_copyable_from(get_type_of_value(argument)):
            raise FatalError()
        logger.debug("ClosedFunction:argument_check")

        with frame_manager.get_next_frame(self) as frame:
            try:
                new_context = frame.step("local_initialization_context", lambda: RDHObject({
                        "prepare": self.open_function.prepare_context,
                        "outer": self.outer_context,
                        "argument": argument,
                        "static": self.open_function.static,
                        "types": self.open_function.types_context
                    },
                        bind=self.open_function.local_initialization_context_type if runtime_type_information() else None,
                        instantiator_has_verified_bind=True,
                        debug_reason="local-initialization-context"
                    )
                )
            except MicroOpTypeConflict as e:
                raise_from(FatalError, e)

            get_manager(new_context)._context_type = self.open_function.local_initialization_context_type

            logger.debug("ClosedFunction:local_initializer")
            local = frame.step("local", lambda: evaluate(self.open_function.local_initializer, new_context, frame_manager))

            if runtime_type_information():
                frame.step("remove_local_initialization_context_type", lambda: get_manager(new_context).remove_composite_type(self.open_function.local_initialization_context_type))

            logger.debug("ClosedFunction:local_check")
            if is_debug() and not self.open_function.local_type.is_copyable_from(get_type_of_value(local)):
                self.open_function.local_type.is_copyable_from(get_type_of_value(local))
                raise FatalError()

            logger.debug("ClosedFunction:code_context")
            try:
                new_context = frame.step("code_execution_context", lambda: RDHObject({
                        "prepare": self.open_function.prepare_context,
                        "outer": self.outer_context,
                        "argument": argument,
                        "static": self.open_function.static,
                        "local": local,
                        "types": self.open_function.types_context
                    },
                        bind=self.open_function.execution_context_type if runtime_type_information() else None,
                        instantiator_has_verified_bind=True,
                        debug_reason="code-execution-context"
                    )
                )
            except MicroOpTypeConflict as e:
                raise raise_from(FatalError, e)

            # In conjunction with get_context_type, for performance
            get_manager(new_context)._context_type = self.open_function.execution_context_type

            logger.debug("ClosedFunction:code_execute")
            result = frame.step("code", lambda: evaluate(self.open_function.code, new_context, frame_manager))

            if runtime_type_information():
                frame.step("remove_code_execution_context_type", lambda: get_manager(new_context).remove_composite_type(self.open_function.execution_context_type))

            return frame.value(result)

    def to_code(self):
        break_types_code = ";".join(["{}: [{}]".format(mode, ",".join([format_break_type(b) for b in break_types])) for mode, break_types in self.open_function.break_types.items()])
        return "ClosedFunction({} => {}\n{{\n{}\n}}\n)".format(
            self.open_function.argument_type.to_code(), break_types_code, self.open_function.code.to_code()
        )


class WrappedFunction(RDHFunction):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def invoke(self, *args, **kwargs):
        return self.wrapped(*args, **kwargs)


class TranspiledFunction(RDHFunction):
    def __init__(self, body, dependency_builder, context_name):
        function_name = b"ClosedFunction_{}".format(id(self))

        final_thing = body[-1]
        if isinstance(final_thing, ast.Expr):
            body[-1] = compile_statement('return ("value", {value}, None, None)', context_name, dependency_builder, value=final_thing.value)
        elif isinstance(final_thing, ast.expr):
            body[-1] = compile_statement('return ("value", {value}, None, None)', context_name, dependency_builder, value=final_thing)
        else:
            raise FatalError()

        body = [ast.Expr(part) if isinstance(part, ast.expr) else part for part in body]

        self.wrapped_function = build_and_compile_ast_function(
            function_name, [ b"_argument", b"_frame_manager"], body, dependency_builder.build()
        )

    def invoke(self, argument, frame_manager):
        return self.wrapped_function(argument, frame_manager)


class Continuation(RDHFunction):
    __slots__ = [ "frame_manager", "frames", "callback", "restart_type", "break_types" ]

    def __init__(self, frame_manager, frames, callback, restart_type, break_types):
        if isinstance(restart_type, TopType):
            pass
        if not isinstance(frame_manager, FrameManager):
            raise FatalError()
        self.frame_manager = frame_manager
        self.frames = frames
        self.callback = callback
        self.restart_type = restart_type
        self.break_types = break_types

        for frame in frames:
            if frame.has_restart_value():
                raise FatalError()

        if break_types is None:
            raise FatalError()

    def get_type(self):
        return ClosedFunctionType(self.restart_type, self.break_types)

    def invoke(self, restart_value, frame_manager):
        if not self.restart_type.is_copyable_from(get_type_of_value(restart_value)):
            raise FatalError()
        self.restarted = True
        if self.frame_manager.fully_wound():
            self.frame_manager.prepare_restart(self.frames, restart_value)
        return self.callback()


def format_break_type(break_type):
    if "in" in break_type:
        return "{ out: {}, in: {} }".format(break_type["out"].to_code(), break_type["in"].to_code())
    else:
        return break_type["out"].to_code()

