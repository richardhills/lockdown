# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import ast

from lockdown.executor.ast_utils import build_and_compile_ast_function, compile_module, \
    compile_statement, DependencyBuilder, compile_ast_function_def
from lockdown.executor.context import Context
from lockdown.executor.exceptions import PreparationException
from lockdown.executor.flow_control import BreakTypesFactory, FrameManager, \
    is_restartable, BreakException
from lockdown.executor.function_type import enrich_break_type, OpenFunctionType, \
    ClosedFunctionType
from lockdown.executor.opcodes import enrich_opcode, get_context_type, evaluate, \
    get_expression_break_types, flatten_out_types, Nop
from lockdown.executor.raw_code_factories import dynamic_dereference_op, \
    static_op, match_op, prepared_function, inferred_type, invoke_op, \
    object_template_op, object_type, dereference, no_value_type, nop, is_opcode, \
    dynamic_assignment_op
from lockdown.executor.type_factories import enrich_type
from lockdown.executor.utils import ContextSearcher
from lockdown.type_system.composites import prepare_lhs_type, \
    check_dangling_inferred_types, CompositeType, InferredType, \
    is_type_bindable_to_value, Composite, scoped_bind
from lockdown.type_system.core_types import Type, NoValueType, IntegerType, \
    AnyType
from lockdown.type_system.exceptions import FatalError, InvalidInferredType, \
    DanglingInferredType, CompositeTypeIsInconsistent, \
    CompositeTypeIncompatibleWithTarget
from lockdown.type_system.managers import get_manager, get_type_of_value
from lockdown.type_system.reasoner import DUMMY_REASONER, Reasoner
from lockdown.type_system.universal_type import PythonObject, \
    UniversalObjectType, DEFAULT_READONLY_COMPOSITE_TYPE, PythonList, PythonDict, \
    Universal, DEFAULT_COMPOSITE_TYPE, RICH_TYPE, RICH_READONLY_TYPE
from lockdown.utils.utils import MISSING, raise_from, \
    spread_dict, get_environment, NO_VALUE, print_code


def prepare_piece_of_context(declared_type, suggested_type):
    if suggested_type and not isinstance(suggested_type, Type):
        raise FatalError()

    final_type = prepare_lhs_type(declared_type, suggested_type)

    if not check_dangling_inferred_types(final_type, {}):
        raise PreparationException("Invalid inferred types")

    is_piece_self_consistent_reasoner = Reasoner()
    if isinstance(final_type, CompositeType) and not final_type.is_self_consistent(is_piece_self_consistent_reasoner):
        raise FatalError(is_piece_self_consistent_reasoner.to_message())

    return final_type


def prepare(data, outer_context, frame_manager, hooks, raw_code, immediate_context):
    if not isinstance(data, Composite):
        raise FatalError()

    if not data._contains("code"):
        raise PreparationException("Code missing from function")

    actual_break_types_factory = BreakTypesFactory(None)

    context = Context(
        UniversalObjectType({
            "prepare": RICH_READONLY_TYPE
        }),
        DEFAULT_READONLY_COMPOSITE_TYPE,
        prepare=outer_context,
        debug_reason="static-evaluation-context"
    )

    static = evaluate(
        enrich_opcode(
            data._get("static"),
            combine(type_conditional_converter, UnboundDereferenceBinder(context)),
            raw_code
        ),
        context, frame_manager, hooks
    )

    argument_type = enrich_type(static._get("argument"))
    outer_type = enrich_type(static._get("outer"))

    suggested_argument_type = suggested_outer_type = None

    if immediate_context:
        suggested_argument_type = immediate_context.get("suggested_argument_type", None)
        suggested_outer_type = immediate_context.get("suggested_outer_type", None)

    if suggested_outer_type is None:
        suggested_outer_type = NoValueType()

    try:
        argument_type = prepare_piece_of_context(argument_type, suggested_argument_type)
    except DanglingInferredType as e:
        raise PreparationException("Failed to infer argument types in {} from {}".format(argument_type, suggested_argument_type)) from e
    try:
        outer_type = prepare_piece_of_context(outer_type, suggested_outer_type)
    except DanglingInferredType as e:
        raise PreparationException("Failed to infer outer types in {} from {}".format(argument_type, suggested_argument_type)) from e

    declared_local_type = enrich_type(static._get("local"))

    context = Context(
        UniversalObjectType({
            "prepare": RICH_READONLY_TYPE,
            "static": RICH_READONLY_TYPE,
            "outer": outer_type,
            "argument": argument_type,
        }),
        DEFAULT_READONLY_COMPOSITE_TYPE,
        prepare=outer_context,
        static=static,
        debug_reason="local-enrichment-context"
    )

    local_initializer = enrich_opcode(
        data._get("local_initializer"),
        combine(type_conditional_converter, UnboundDereferenceBinder(context)),
        raw_code
    )

    declared_break_types = PythonDict({
        mode: PythonList([
            enrich_break_type(break_type) for break_type in break_types._values()
        ]) for mode, break_types in static._get("break_types")._items()
    })

    try:
        actual_local_type, local_other_break_types = get_expression_break_types(
            local_initializer,
            context,
            frame_manager,
            hooks
        )
    except BreakException as e:
        raise PreparationException() from e

    actual_break_types_factory.merge(local_other_break_types)

    # Be liberal. If the local initializer can not return a value, then we accept that
    # it must exit through some other method, and the code block will never be run
    if actual_local_type is MISSING:
        local_type = NoValueType()
        code = nop()
    else:
        actual_local_type = flatten_out_types(actual_local_type)

        local_type = prepare_piece_of_context(declared_local_type, actual_local_type)

        local_type_reasoner = Reasoner()

        if not local_type.is_copyable_from(actual_local_type, local_type_reasoner):
            raise PreparationException("Invalid local type: {} != {}: {}".format(local_type, actual_local_type, local_type_reasoner.to_message()))

        context = Context(
            UniversalObjectType({
                "prepare": RICH_READONLY_TYPE,
                "static": RICH_READONLY_TYPE,
                "outer": outer_type,
                "argument": argument_type,
                "local": local_type
            }),
            dynamic_type=DEFAULT_READONLY_COMPOSITE_TYPE,
            prepare=outer_context,
            static=static,
            debug_reason="code-enrichment-context"
        )

        code = enrich_opcode(
            data._get("code"),
            combine(type_conditional_converter, UnboundDereferenceBinder(context)),
            raw_code
        )

        try:
            code_break_types = code.get_break_types(context, frame_manager, hooks)
        except BreakException as e:
            raise PreparationException() from e

        actual_break_types_factory.merge(code_break_types)

    final_declared_break_types = BreakTypesFactory(None)

    for mode, actual_break_types in actual_break_types_factory.build().items():
        for actual_break_type in actual_break_types:
            declared_break_types_for_mode = declared_break_types._get(mode, declared_break_types._get("infer-all", None))
            if declared_break_types_for_mode:
                declared_break_types_for_mode = declared_break_types_for_mode._to_list()
            else:
                declared_break_types_for_mode = []

            for declared_break_type_for_mode in declared_break_types_for_mode:
                # Check if this declared_break_type_for_mode is enough to capture the actual_break_types
                declared_out = declared_break_type_for_mode["out"]
                declared_in = declared_break_type_for_mode.get("in", None)
                actual_out = actual_break_type["out"]
                actual_in = actual_break_type.get("in", None)

                final_out = prepare_lhs_type(declared_out, actual_out)
                if declared_in is not None:
                    if isinstance(declared_in, InferredType) and actual_in is None:
                        final_in = None
                    else:
                        final_in = prepare_lhs_type(declared_in, actual_in)
                else:
                    final_in = declared_in

                out_is_compatible = final_out.is_copyable_from(actual_out, DUMMY_REASONER)
                in_is_compatible = final_in is None or actual_in.is_copyable_from(final_in, DUMMY_REASONER)

                if out_is_compatible and in_is_compatible:
                    final_declared_break_types.add(None, mode, final_out, final_in)
                    break
            else:
                raise PreparationException("""Nothing declared for {}, {}.\nFunction declares break types {}.\nBut local_initialization breaks {}, code breaks {}""".format(
                    mode, actual_break_type, declared_break_types, local_other_break_types, code_break_types
                ))

    new_function = OpenFunction(data, code, outer_context, static, argument_type, outer_type, local_type, local_initializer, final_declared_break_types.build())

    if hooks:
        hooks.register_new_function(new_function)

    return new_function

def get_debug_info_from_opcode(opcode):
    return {
        "column": getattr(opcode, "column", None),
        "line": getattr(opcode, "line", None),
    }

class UnboundDereferenceBinder(ContextSearcher):
    def __call__(self, expression):
        from lockdown.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        debug_info = get_debug_info_from_opcode(expression)

        if expression._get("opcode", None) == "unbound_dereference":
            reference = expression._get("reference")
            context_links, is_static = self.search_for_reference(reference, debug_info)

            if context_links is not None:
                bound_context_op = dereference(*context_links)
                new_dereference = dereference_op(bound_context_op, literal_op(reference), **debug_info)
                if is_static:
                    new_dereference = static_op(new_dereference)
                return new_dereference
            else:
                new_dereference = dynamic_dereference_op(reference, **debug_info)
                return new_dereference

        if expression._get("opcode", None) == "unbound_assignment":
            reference = expression._get("reference")
            context_links, _ = self.search_for_reference(reference, debug_info)

            if context_links is not None:
                bound_context_op = dereference(*context_links)
                return assignment_op(bound_context_op, literal_op(reference), expression._get("rvalue"), **debug_info)
            else:
                return dynamic_assignment_op(reference, expression._get("rvalue"), **debug_info)

        return expression

def type_conditional_converter(expression):
    if not isinstance(expression, Universal):
        return expression
    is_conditional = expression._get("opcode", None) == "conditional"
    if not is_conditional:
        return expression
    condition_is_type_check = expression._get_in("condition", "opcode", default=None) == "is"
    if not condition_is_type_check:
        return expression
    lvalue_of_condition_is_dereference = expression._get_in("condition", "expression", "opcode", default=None) == "unbound_dereference"
    if not lvalue_of_condition_is_dereference:
        return expression

    shadow_name = expression._get_in("condition", "expression", "reference")

    new_match = match_op(
        expression._get_in("condition", "expression"), [
            prepared_function(
                expression._get_in("condition", "type"),
                invoke_op(
                    prepared_function(
                        object_type({
                            shadow_name: expression._get_in("condition", "type")
                        }),
                        expression._get("when_true")
                    ),
                    argument_expression=object_template_op({
                        shadow_name: dereference("argument")
                    })
                )
            ),
            prepared_function(
                inferred_type(),
                expression._get("when_false")
            )
        ]
    )
    return new_match


def combine(*funcs):
    def wrapped(expression):
        for func in funcs:
            expression = func(expression)
            if not is_opcode(expression):
                raise PreparationException("Opcode not found {}".format(expression))
        return expression
    return wrapped


class LockdownFunction(object):
    def get_type(self):
        raise NotImplementedError(self)

    def invoke(self, argument, frame_manager):
        raise NotImplementedError()


class OpenFunction(object):
    def __init__(self, data, code, prepare_context, static, argument_type, outer_type, local_type, local_initializer, break_types):
        if not isinstance(break_types, dict):
            raise FatalError()

        self.data = data
        self.code = code
        self.prepare_context = prepare_context
        self.static = static
        self.argument_type = argument_type
        self.outer_type = outer_type
        self.local_type = local_type
        self.local_initializer = local_initializer
        self.break_types = break_types

        self.local_initialization_context_type = UniversalObjectType({
            "outer": self.outer_type,
            "argument": self.argument_type,
            "static": RICH_READONLY_TYPE,
            "prepare": RICH_READONLY_TYPE
        }, name="local-initialization-context-type")

        self.execution_context_type = UniversalObjectType({
            "outer": self.outer_type,
            "argument": self.argument_type,
            "local": self.local_type,
            "static": RICH_READONLY_TYPE,
            "prepare": RICH_READONLY_TYPE
        }, name="code-execution-context-type")

        reasoner = Reasoner()
        if not self.execution_context_type.is_self_consistent(reasoner):
            raise FatalError(reasoner)

        self.compiled_ast = None

    def get_type(self):
        return OpenFunctionType(self.argument_type, self.outer_type, self.break_types)

    def close(self, outer_context):
        if get_environment().opcode_bindings and not is_type_bindable_to_value(outer_context, self.outer_type):
            raise FatalError()

        return ClosedFunction(self, outer_context)

    def get_start_and_end(self):
        return (self.data._get("start", None), self.data._get("end", None))

    def get_function_symbol_start_and_end(self):
        return self.data._get("function_symbol", None)

    def to_ast(self, dependency_builder):
        if is_restartable(self):
            return None
        context_name = "context_{}".format(id(self))

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
    def close(cls, outer_context):
        return cls.Closed_{open_function_id}(cls, outer_context)

    class Closed_{open_function_id}(LockdownFunction):
        def __init__(self, open_function, outer_context):
            self.open_function = open_function
            self.outer_context = outer_context

        def invoke(self, {context_name}_argument, _frame_manager, _hooks):
            {context_name} = Context(
                {local_initialization_context_type},
                prepare={prepare_context},
                outer=self.outer_context,
                argument={context_name}_argument,
                static={static}
            )

            local = None
    
            with scoped_bind(
                {context_name},
                {local_initialization_context_type},
                bind=get_environment().rtti
            ):
                local = {local_initializer}

            {context_name} = Context(
                {execution_context_type},
                prepare={prepare_context},
                outer=self.outer_context,
                argument={context_name}_argument,
                static={static},
                local=local
            )
            """ \
            +(
                """
            with scoped_bind(
                {context_name},
                {execution_context_type},
                bind=get_environment().rtti
            ):
                {function_code}
                return ("value", NoValue, self, None)
                """
                if will_ignore_return_value else 
                """
            with scoped_bind(
                {context_name},
                {execution_context_type},
                bind=get_environment().rtti
            ):
                return ("value", {function_code}, self, None)
                """
            ) + """

        def get_type(self):
            return ClosedFunctionType(
                {open_function_type}.argument_type,
                {open_function_type}.break_types
            )
""",
            context_name, dependency_builder,
            prepare_context=self.prepare_context,
            static=self.static,
            local_initialization_context_type=self.local_initialization_context_type,
            local_initializer=local_initializer_ast,
            execution_context_type=self.execution_context_type,
            open_function_id=open_function_id,
            open_function_type=self.get_type(),
            function_code=code_ast
        )

    def to_inline_ast(self, dependency_builder, outer_context_ast, argument_ast):
        if is_restartable(self):
            return None
        context_name = "context_{}".format(id(self))

        local_initializer_ast = self.local_initializer.to_ast(context_name, dependency_builder)

        will_ignore_return_value = True

        code_ast = self.code.to_ast(
            context_name,
            dependency_builder,
            will_ignore_return_value=will_ignore_return_value
        )

        return compile_module("""
{context_name} = Universal(True, initial_wrapped={{
    "prepare": {prepare_context},
    "outer": {outer_context},
    "argument": {argument},
    "static": {static},
    "_types": {local_initialization_context_type}
}})

local = None

with scoped_bind(
    {context_name},
    {local_initialization_context_type},
    bind=get_environment().rtti
):
    local = {local_initializer}

{context_name} = Universal(True, initial_wrapped={{
    "prepare": {prepare_context},
    "outer": {outer_context},
    "argument": {argument},
    "static": {static},
    "local": local,
    "_types": {execution_context_type}
}}, debug_reason="code-execution-transpiled-context")

with scoped_bind(
    {context_name},
    {execution_context_type},
    bind=get_environment().rtti
):
    {function_code}
            """,
            context_name, dependency_builder,
            prepare_context=self.prepare_context,
            static=self.static,
            local_initialization_context_type=self.local_initialization_context_type,
            local_initializer=local_initializer_ast,
            execution_context_type=self.execution_context_type,
            outer_context=outer_context_ast,
            argument=argument_ast,            
            function_code=code_ast
        )

    def transpile(self):
        dependency_builder = DependencyBuilder()

        our_ast = self.to_ast(dependency_builder)

        for key, dependency in list(dependency_builder.dependencies.items()):
            if isinstance(dependency, OpenFunction):
                open_function_ast = dependency.to_ast(dependency_builder)
                if open_function_ast:
                    dependency_builder.replace(key, open_function_ast)

        compiled_dependencies = {
            key: dependency for key, dependency in dependency_builder.dependencies.items()
            if isinstance(dependency, ast.stmt)
        }

        uncompiled_dependencies = {
            key: dependency for key, dependency in dependency_builder.dependencies.items()
            if not isinstance(dependency, ast.stmt)
        }

        combined_ast = [ our_ast ] + list(compiled_dependencies.values())
        combined_ast = ast.Module(body=combined_ast)

        return compile_ast_function_def(
            combined_ast, our_ast.name, uncompiled_dependencies
        )


class ClosedFunction(LockdownFunction):
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

    def get_start_and_end(self):
        return self.open_function.get_start_and_end()

    def get_function_symbol_start_and_end(self):
        return self.open_function.get_function_symbol_start_and_end()

    def transpile(self):
        open_function_transpile = self.open_function.transpile()

        return open_function_transpile.close(self.outer_context)

    def invoke(self, argument, frame_manager, hooks):
        if get_environment().opcode_bindings:
            bindable_reasoner = Reasoner()
            bindable = is_type_bindable_to_value(argument, self.open_function.argument_type, bindable_reasoner)
            if not bindable:
                raise FatalError(bindable_reasoner.to_message())

        with frame_manager.get_next_frame(self) as frame:
            local_initializer_context_binding_reasoner = Reasoner()
            try:
                new_context = frame.step(
                    "local_initialization_context",
                    lambda: Context(
                        self.open_function.local_initialization_context_type, 
                        prepare=self.open_function.prepare_context,
                        static=self.open_function.static,
                        outer=self.outer_context,
                        argument=argument,
                        debug_reason="local-initialization-context"
                    )
                )

                with scoped_bind(
                    new_context,
                    self.open_function.local_initialization_context_type,
                    bind=get_environment().rtti,
                    reasoner=local_initializer_context_binding_reasoner
                ):
                    #get_manager(new_context)._context_type = self.open_function.local_initialization_context_type
                    local = frame.step("local", lambda: evaluate(self.open_function.local_initializer, new_context, frame_manager, hooks))

                if get_environment().opcode_bindings and not is_type_bindable_to_value(local, self.open_function.local_type):
                    raise FatalError()
            except CompositeTypeIncompatibleWithTarget:
                raise FatalError(local_initializer_context_binding_reasoner.to_message())
            except CompositeTypeIsInconsistent as e:
                raise raise_from(FatalError, e)

            code_context_binding_reasoner = Reasoner()
            try:
                new_context = frame.step(
                    "code_execution_context",
                    lambda: Context(
                        self.open_function.execution_context_type,
                        prepare=self.open_function.prepare_context,
                        static=self.open_function.static,
                        outer=self.outer_context,
                        argument=argument,
                        local=local,
                        debug_reason="code-execution-context"
                    )
                )
                with scoped_bind(
                    new_context,
                    self.open_function.execution_context_type,
                    bind=get_environment().rtti,
                    reasoner=code_context_binding_reasoner
                ):
                    get_manager(new_context)._context_type = self.open_function.execution_context_type
                    with frame_manager.capture("value") as result:
                        result.attempt_capture_or_raise(*self.open_function.code.jump(new_context, frame_manager, hooks))

                    return frame.unwind(
                        *result.reraise(opcode=self),
                        cause=result.caught_break_exception
                    )
            except CompositeTypeIncompatibleWithTarget:
                raise FatalError(code_context_binding_reasoner.to_message())
            except CompositeTypeIsInconsistent as e:
                raise raise_from(FatalError, e)

class Continuation(LockdownFunction):
    __slots__ = [ "frame_manager", "frames", "callback", "restart_type", "break_types" ]

    def __init__(self, frame_manager, frames, callback, restart_type, break_types):
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

    def invoke(self, restart_value, frame_manager, hooks):
        if not self.restart_type.is_copyable_from(get_type_of_value(restart_value), DUMMY_REASONER):
            raise FatalError()
        self.restarted = True
        if self.frame_manager.fully_wound():
            self.frame_manager.prepare_restart(self.frames, restart_value)
        return self.callback()

