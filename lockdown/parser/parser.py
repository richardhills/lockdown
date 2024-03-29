# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from antlr4.CommonTokenStream import CommonTokenStream
from antlr4.InputStream import InputStream
from antlr4.error.ErrorListener import ConsoleErrorListener
from antlr4.error.Errors import ParseCancellationException

from lockdown.executor.raw_code_factories import function_lit, nop, comma_op, \
    literal_op, dereference_op, unbound_dereference, addition_op, \
    transform_op, multiplication_op, division_op, subtraction_op, \
    object_type, is_opcode, object_template_op, infer_all, \
    no_value_type, combine_opcodes, invoke_op, assignment_op, \
    unbound_assignment, list_template_op, list_type, context_op, \
    loop_op, condition_op, binary_integer_op, equality_op, dereference, \
    local_function, reset_op, inferred_type, prepare_function_lit, transform, \
    continue_op, check_is_opcode, is_op, function_type, \
    composite_type, static_op, map_op, insert_op, prepared_function, int_type, \
    any_type, print_op, shift_op, prepare_op, close_op, rich_type, typeof_op, \
    merge_op, unary_op, dynamic_eval_op
from lockdown.parser.grammar.langLexer import langLexer
from lockdown.parser.grammar.langParser import langParser
from lockdown.parser.grammar.langVisitor import langVisitor
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.managers import get_manager
from lockdown.type_system.universal_type import DEFAULT_READONLY_COMPOSITE_TYPE, \
    PythonObject, PythonDict, Universal
from lockdown.utils.utils import MISSING, default, spread_dict


class RDHLang5Visitor(langVisitor):
    def __init__(self, post_chain_function=None, pre_chain_function=None):
        self.pre_chain_function = pre_chain_function
        self.post_chain_function = post_chain_function

    def visitObj(self, ctx):
        result = {}
        for pair in ctx.pair() or []:
            pair = self.visit(pair)
            result[pair[0]] = pair[1]

        return PythonObject(result)

    def visitPair(self, ctx):
        return [ ctx.STRING().getText()[1:-1], self.visit(ctx.value()) ]

    def visitArr(self, ctx):
        return [ self.visit(v) for v in ctx.value() ]

    def visitValue(self, ctx):
        if ctx.STRING():
            return json.loads(ctx.STRING().getText())
        if ctx.NUMBER():
            return json.loads(ctx.NUMBER().getText())
        if ctx.obj():
            return self.visit(ctx.obj())
        if ctx.arr():
            return self.visit(ctx.arr())
        if ctx.getText() == "true":
            return True
        if ctx.getText() == "false":
            return False
        if ctx.getText() == "null":
            return None
        if ctx.function():
            return self.visit(ctx.function())[1]
        if ctx.codeBlockAsFunction():
            return self.visit(ctx.codeBlockAsFunction())
        if ctx.lockdownJsonExpression():
            return self.visit(ctx.lockdownJsonExpression())

    def visitFunction(self, ctx):
        arguments = ctx.objectProperties()
        if arguments:
            arguments, final_splat = self.visit(arguments)

        code_block = self.visit(ctx.codeBlock())

        if arguments:
            if final_splat:
                raise ParseCancellationException

            argument_types = []
            local_variable_types = {}
            local_variable_initializers = {}
            wildcard_argument_type = None
            raw_argument_type = None

            for index, (is_splat, lhs_value, lhs_mode, rhs) in enumerate(arguments):
                if lhs_mode == "literal-key":
                    if not isinstance(lhs_value, str):
                        raise ParseCancellationException()

                    if is_splat:
                        if index != len(arguments) - 1:
                            raise ParseCancellationException()

                        wildcard_argument_type = rhs
                        local_variable_types[lhs_value] = inferred_type()
                        local_variable_initializers[lhs_value] = map_op(
                            dereference("argument"), prepared_function(
                                object_type({ "index": int_type(), "value": rhs }),
                                condition_op(
                                    binary_integer_op("gte", unbound_dereference("index"), literal_op(index)),
                                    continue_op(unbound_dereference("value")), nop()
                                )
                            )
                        )
                    else:
                        if rhs is None:
                            raw_argument_type = unbound_dereference(lhs_value)
                        else:
                            argument_types.append(rhs)
                            local_variable_types[lhs_value] = rhs
                            local_variable_initializers[lhs_value] = dereference("argument", index)

                if lhs_mode == "expression-key":
                    if rhs is None:
                        raw_argument_type = lhs_value
                    else:
                        raise ParseCancellationException()
                if lhs_mode == "computed-expression-key":
                    raise ParseCancellationException()

            if raw_argument_type is None:
                raw_argument_type = list_type(argument_types, wildcard_argument_type)

            argument_code_builder = CodeBlockBuilder(
                argument_type_expression=raw_argument_type,
                local_variable_type=object_type(
                    local_variable_types,
                    wildcard_type=rich_type()
                ),
                local_initializer=object_template_op(local_variable_initializers)
            )

            function_builder = argument_code_builder.chain(code_block)
        else:
            function_builder = CodeBlockBuilder(
                argument_type_expression=list_type([], None)
            ).chain(code_block)

        if ctx.functionBreakTypes:
            break_types = self.visit(ctx.functionBreakTypes)
            function_builder.set_breaks_types(break_types)

        function_name = None
        function_name_symbol = ctx.SYMBOL()
        if function_name_symbol:
            function_name = function_name_symbol.getText()

        return function_name, function_builder.create(
            "first-class-function",
            spread_dict(
                get_context_debug_info(ctx), {
                    "function_symbol": get_token_debug_info(ctx.children[0].symbol)
                }
            )
        )

    def visitCodeBlockAsFunction(self, ctx):
        function_builder = self.visit(ctx.codeBlock())

        if self.pre_chain_function:
            function_builder = self.pre_chain_function.chain(function_builder)

        if self.post_chain_function:
            function_builder = function_builder.chain(self.post_chain_function)

        return function_builder.create("first-class-function", get_context_debug_info(ctx))

    def visitLockdownJsonExpression(self, ctx):
        return self.visit(ctx.expression())

    # def visitArgumentDestructurings(self, ctx):
    #     initializers = [self.visit(l) for l in ctx.argumentDestructuring()]
    #
    #     argument_types = [ None ] * len(initializers)
    #     local_variable_types = {}
    #     local_variable_initializers = {}
    #
    #     for index, (type, name) in enumerate(initializers):
    #         argument_types[index] = type
    #         local_variable_types[name] = type
    #         local_variable_initializers[name] = dereference("argument", index)
    #
    #     return CodeBlockBuilder(
    #         argument_type_expression=list_type(argument_types, None),
    #         local_variable_type=object_type(local_variable_types),
    #         local_initializer=object_template_op(local_variable_initializers)
    #     )
    #
    # def visitArgumentDestructuring(self, ctx):
    #     symbol = ctx.SYMBOL().getText()
    #     type = self.visit(ctx.expression())
    #     return (type, symbol)

    def visitSymbolInitialization(self, ctx):
        return (
            ctx.SYMBOL().getText(),
            self.visit(ctx.expression())
        )

    def visitAssignmentOrInitializationLvalue(self, ctx):
        symbol = ctx.SYMBOL().getText()
        type = ctx.expression()
        if type:
            type = self.visit(type)
            return (type, symbol)
        return symbol

    def visitToObjectDestructuring(self, ctx):
        lvalues = [self.visit(l) for l in ctx.assignmentOrInitializationLvalue()]
        rvalue = self.visit(ctx.expression())

        code_block = ctx.codeBlock()
        if code_block:
            code_block = self.visit(code_block)

        assignments = [n for n in lvalues if isinstance(n, str)]
        initializers = [n for n in lvalues if isinstance(n, tuple)]

        local_variable_types = {}
        local_variable_initializers = {}

        for type, name in initializers:
            local_variable_types[name] = type
            local_variable_initializers[name] = dereference("outer.local._temp", name)

        code_block = CodeBlockBuilder(
            local_variable_type=object_type(local_variable_types),
            local_initializer=object_template_op(local_variable_initializers)
        ).chain(code_block)

        code_block = CodeBlockBuilder(
            local_variable_type=inferred_type(),
            local_initializer=object_template_op({
                "_temp": rvalue
            }),
            code_expressions=[
                unbound_assignment(name, dereference("local._temp", name)) for name in assignments
            ]
        ).chain(code_block)

        return code_block

    def visitToListDestructuring(self, ctx):
        lvalues = [self.visit(l) for l in ctx.assignmentOrInitializationLvalue()]
        rvalue = self.visit(ctx.expression())

        code_block = ctx.codeBlock()
        if code_block:
            code_block = self.visit(code_block)

        assignments = [(i, n) for i, n in enumerate(lvalues) if isinstance(n, str)]
        initializers = [(i, n) for i, n in enumerate(lvalues) if isinstance(n, tuple)]

        local_variable_types = {}
        local_variable_initializers = {}

        for index, (type, name) in initializers:
            local_variable_types[name] = type
            local_variable_initializers[name] = dereference("outer.local._temp", index)

        code_block = CodeBlockBuilder(
            local_variable_type=object_type(local_variable_types),
            local_initializer=object_template_op(local_variable_initializers)
        ).chain(code_block)

        code_block = CodeBlockBuilder(
            local_variable_type=object_type({
                "_temp": list_type(
                    [ inferred_type() ] * len(lvalues), None
                )
            }),
            local_initializer=object_template_op({
                "_temp": rvalue
            }),
            code_expressions=[
                unbound_assignment(name, dereference("local._temp", index)) for index, name in assignments
            ]
        ).chain(code_block)

        return code_block

    def visitLocalVariableDeclaration(self, ctx):
        type = self.visit(ctx.expression())

        remaining_code = ctx.codeBlock()
        if remaining_code:
            remaining_code = self.visit(remaining_code)

        for symbol_initialization in reversed(ctx.symbolInitialization()):
            name, initial_value = self.visit(symbol_initialization)

            new_code_block = CodeBlockBuilder(
                local_variable_type=object_type({
                    name: type
                }, wildcard_type=rich_type()),
                local_initializer=object_template_op({ name: initial_value })
            )
            if remaining_code:
                new_code_block = new_code_block.chain(remaining_code)
            remaining_code = new_code_block

        return new_code_block

    def visitStaticValueDeclaration(self, ctx):
        name, value = self.visit(ctx.symbolInitialization())

        result = CodeBlockBuilder(
            extra_statics={ literal_op(name): value }
        )

        remaining_code = ctx.codeBlock()
        if ctx.codeBlock():
            remaining_code = self.visit(ctx.codeBlock())
            result = result.chain(remaining_code)

        return result

    def visitTypedef(self, ctx):
        remaining_code = self.visit(ctx.codeBlock())

        value = self.visit(ctx.expression())
        name = ctx.SYMBOL().getText()

        return CodeBlockBuilder(
            extra_statics={ literal_op(name): value },
        ).chain(remaining_code)

    def visitToFunctionStatement(self, ctx):
        remaining_code = ctx.codeBlock()
        if remaining_code:
            remaining_code = self.visit(remaining_code)

        name, function = self.visit(ctx.function())
        prepared_function = prepare_function_lit(function)
        builder = CodeBlockBuilder(
#            local_variable_type=object_type({ name: prepared_function }),
#            local_initializer=object_template_op({ name: prepared_function })
            extra_statics={ literal_op(name): prepared_function }
        )

        if remaining_code:
            builder = builder.chain(remaining_code)

        return builder

    def visitToPrepareExpression(self, ctx):
        expression = self.visit(ctx.expression())
        return prepare_op(expression)

    def visitToPrintStatement(self, ctx):
        expr = self.visit(ctx.expression())

        return print_op(expr)

    def visitToExpression(self, ctx):
        code_expressions = [self.visit(e) for e in ctx.expression()]

        new_function = CodeBlockBuilder(
            code_expressions=code_expressions
        )

        remaining_code = ctx.codeBlock()
        if remaining_code:
            remaining_code = self.visit(remaining_code)
            new_function = new_function.chain(remaining_code)

        return new_function

    def visitStringExpression(self, ctx):
        return literal_op(json.loads(ctx.STRING().getText()))

    def visitNumberExpression(self, ctx):
        return literal_op(json.loads(ctx.NUMBER().getText()))

    def visitTrueExpression(self, ctx):
        return literal_op(True)

    def visitFalseExpression(self, ctx):
        return literal_op(False)

    def visitInvocation(self, ctx):
        function = self.visit(ctx.expression())

        properties, splat = self.visit(ctx.objectProperties())

        if splat:
            raise ParseCancellationException()

        arguments = []

        for is_splat, lhs_value, lhs_mode, rhs in properties:
            extra_argument = None

            if is_splat:
                raise NotImplementedError()
            if rhs is not None:
                raise ParseCancellationException()
            if lhs_mode == "literal-key":
                if isinstance(lhs_value, str):
                    extra_argument = unbound_dereference(lhs_value)
                elif isinstance(lhs_value, int):
                    extra_argument = literal_op(lhs_value)
            if lhs_mode == "expression-key":
                extra_argument = lhs_value
            if lhs_mode == "computed-expression-key":
                raise ParseCancellationException()

            arguments.append(extra_argument)

        return invoke_op(function, list_template_op(arguments), **get_context_debug_info(ctx))

    def visitStaticInvocation(self, ctx):
        return static_op(self.visitInvocation(ctx))

    def visitPipeline(self, ctx):
        argument, function = ctx.expression()
        argument = self.visit(argument)
        function = self.visit(function)
        return invoke_op(function, list_template_op([ argument ]), **get_context_debug_info(ctx))

    def visitParenthesis(self, ctx):
        return self.visit(ctx.expression())

    def visitStaticExpression(self, ctx):
        return static_op(self.visit(ctx.expression()))

    def visitIs(self, ctx):
        expression, type = ctx.expression()
        expression = self.visit(expression)
        type = self.visit(type)
        return is_op(
            expression, type
        )

    def visitImmediateDereference(self, ctx):
        return unbound_dereference(ctx.SYMBOL().getText(), **get_context_debug_info(ctx))

    def visitStaticDereference(self, ctx):
        return dereference_op(
            self.visit(ctx.expression()),
            literal_op(ctx.SYMBOL().getText())
        )

    def visitDynamicDereference(self, ctx):
        of, reference = ctx.expression()
        of = self.visit(of)
        reference = self.visit(reference)
        unsafe = bool(ctx.unsafe)
        result = dereference_op(of, reference)
        if unsafe:
            result = transform_op("exception", "value", result, True)
        return result

    def visitNegation(self, ctx):
        expression = self.visit(ctx.expression())
        return unary_op("not", expression)

    def visitMultiplication(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return multiplication_op(
            lvalue, rvalue
        )

    def visitDivision(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return division_op(
            lvalue, rvalue
        )
        
    def visitAddition(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return addition_op(
            lvalue, rvalue
        )

    def visitSubtraction(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return subtraction_op(
            lvalue, rvalue
        )

    def visitMod(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("mod", lvalue, rvalue)

    def visitEq(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return equality_op(lvalue, rvalue)

    def visitNeq(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("neq", lvalue, rvalue)

    def visitLt(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("lt", lvalue, rvalue)

    def visitLte(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("lte", lvalue, rvalue)

    def visitGt(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("gt", lvalue, rvalue)

    def visitGte(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("gte", lvalue, rvalue)

    def visitBoolOr(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("or", lvalue, rvalue)

    def visitBoolAnd(self, ctx):
        lvalue, rvalue = ctx.expression()
        lvalue = self.visit(lvalue)
        rvalue = self.visit(rvalue)
        return binary_integer_op("and", lvalue, rvalue)

    def visitImmediateAssignment(self, ctx):
        return unbound_assignment(
            ctx.SYMBOL().getText(),
            self.visit(ctx.expression())
        )

    def visitStaticAssignment(self, ctx):
        of, rvalue = ctx.expression()
        of = self.visit(of)
        rvalue = self.visit(rvalue)
        reference = ctx.SYMBOL().getText()
        return assignment_op(
            of, literal_op(reference), rvalue
        )

    def visitDynamicAssignment(self, ctx):
        of, reference, rvalue = ctx.expression()
        of = self.visit(of)
        reference = self.visit(reference)
        rvalue = self.visit(rvalue)
        return assignment_op(
            of, reference, rvalue
        )

    def visitDynamicInsertion(self, ctx):
        of, reference, rvalue = ctx.expression()
        of = self.visit(of)
        reference = self.visit(reference)
        rvalue = self.visit(rvalue)
        return insert_op(
            of, reference, rvalue
        )

    def visitTernary(self, ctx):
        condition, when_true, when_false = ctx.expression()

        return condition_op(
            self.visit(condition),
            self.visit(when_true),
            self.visit(when_false)
        )

    def visitTypeof(self, ctx):
        return typeof_op(self.visit(ctx.expression()))

    def visitReturnStatement(self, ctx):
        expression = self.visit(ctx.expression())
        return transform_op(
            "value", "return", expression
        )

    def visitYieldStatement(self, ctx):
        expression = self.visit(ctx.expression())
        return shift_op(expression, any_type())

    def visitExportStatement(self, ctx):
        expression = self.visit(ctx.expression())
        return transform_op(
            "value", "export", expression
        )

    def visitToJsonExpression(self, ctx):
        return self.visit(ctx.json())      

    def visitContinueStatement(self, ctx):
        return continue_op(self.visit(ctx.expression()))

    def visitBreakStatement(self, ctx):
        return transform_op("break")

    def visitIfStatement(self, ctx):
        expressions = [self.visit(e) for e in ctx.expression()]
        code_blocks = [self.visit(c).create("expression") for c in ctx.codeBlock()]

        if len(expressions) == len(code_blocks):
            other_branch = nop()
        else:
            other_branch = code_blocks[-1]

        for condition, when_true in reversed(list(zip(expressions, code_blocks))):
            other_branch = condition_op(condition, when_true, other_branch)

        return other_branch

    def visit_conditional_pair(self, condition, when_true, when_false):
        return condition_op(condition, when_true, when_false)

    def visitLoop(self, ctx):
        loop_code = self.visit(ctx.codeBlock())
        return loop_op(loop_code.create("expression"))

    def visitWhileLoop(self, ctx):
        continue_expression = self.visit(ctx.expression())
        loop_code = self.visit(ctx.codeBlock())

        return transform_op(
            "break", "value",
            loop_op(comma_op(
                condition_op(continue_expression, nop(), transform_op("break")),
                loop_code.create("expression")
            ))
        )

    def visitForGeneratorLoop(self, ctx):
        iterator_name = ctx.SYMBOL().getText()
        generator_expression = self.visit(ctx.expression())
        loop_code = self.visit(ctx.codeBlock())

        loop_code = CodeBlockBuilder(
            argument_type_expression=object_type({
                iterator_name: inferred_type()
            })
        ).chain(loop_code)

        loop_code = loop_code.create("second-class-function")
#        get_manager(loop_code).add_composite_type(READONLY_DEFAULT_OBJECT_TYPE)

        return transform_op(
            "break", "value",
            invoke_op(local_function(
                object_template_op({
                    "callback": generator_expression
                }),
                loop_op(
                    invoke_op(local_function(
                        transform(
                            ("yield", "value"),
                            ("value", "end"),
                            reset_op(
                                dereference("outer.local.callback", **get_context_debug_info(ctx)),
                                list_template_op([])
                            )
                        ),
                        comma_op(
                            assignment_op(
                                dereference("outer.local"),
                                literal_op("callback"),
                                dereference("local.continuation")
                            ),
                            invoke_op(
                                prepare_function_lit(loop_code),
                                object_template_op({
                                    iterator_name: dereference("local.value")
                                }),
                            )
                        )
                    )),
                ),
            ))
        )

    def visitForListLoop(self, ctx):
        iterator_name = ctx.SYMBOL().getText()
        composite_expression = self.visit(ctx.expression())
        loop_code = self.visit(ctx.codeBlock())

        loop_code = CodeBlockBuilder(
            argument_type_expression=object_type({
                iterator_name: inferred_type()
            })
        ).chain(loop_code)

        loop_code = loop_code.create("second-class-function")

        return map_op(
            composite_expression,
            prepared_function(
                inferred_type(),
                invoke_op(
                    prepare_function_lit(loop_code, **get_context_debug_info(ctx)),
                    object_template_op({
                        iterator_name: dereference("argument.value", **get_context_debug_info(ctx))
                    }, **get_context_debug_info(ctx)),
                    **get_context_debug_info(ctx)
                ),
                **get_context_debug_info(ctx)
            )
        )

    def visitToMap(self, ctx):
        composite = ctx.expression()
        composite = self.visit(composite)

        code_block = ctx.codeBlock()
        code_block = self.visit(code_block)

        code_block = CodeBlockBuilder(
            argument_type_expression=inferred_type()
        ).chain(code_block)

        return map_op(
            composite,
            prepare_function_lit(
                code_block.create("second-class-function")
            )
        )

    def visitBreakTypes(self, ctx):
        value_type = self.visit(ctx.valueType)
        break_types = [self.visit(b) for b in ctx.breakType()]

        check_is_opcode(value_type)

        result = object_template_op({
            break_mode: types for break_mode, types in [
                ("value", list_template_op([ object_template_op({ "out": value_type }) ])),
                *break_types
            ]
        })

        return result

    def visitBreakType(self, ctx):
        break_mode = str(ctx.SYMBOL())

        if break_mode[-1] == "s":
            break_mode = break_mode[:-1]

        types = {}
        output_type = self.visit(ctx.output_type)
        check_is_opcode(output_type)
        types["out"] = output_type
        input_type = ctx.input_type
        if input_type:
            input_type = self.visit(input_type)
            check_is_opcode(output_type)
            types["in"] = input_type

        return (break_mode, list_template_op([ object_template_op(types) ]))

    def visitObjectTemplate(self, ctx):
        builder = ObjectTemplateBuilder()
        
        properties, splat = self.visit(ctx.objectProperties())

        if splat:
            raise ParseCancellationException()

        for is_splat, lhs_value, lhs_mode, rhs in properties:
            if lhs_mode == "literal-key":
                if is_splat:
                    builder = builder.merge(unbound_dereference(lhs_value))
                else:
                    builder.add(literal_op(lhs_value), rhs or unbound_dereference(lhs_value))
            if lhs_mode == "expression-key":
                if is_splat:
                    builder = builder.merge(lhs_value)
                else:
                    builder.add(lhs_value, rhs)
            if lhs_mode == "computed-expression-key":
                builder.add(lhs_value, rhs)

        return builder.build()

    def visitObjectProperties(self, ctx):
        return ( [ self.visit(p) for p in ctx.objectProperty() ], ctx.splat is not None )

    def visitObjectProperty(self, ctx):
        is_splat = ctx.splat is not None
        lhs_value, lhs_mode = self.visit(ctx.objectKey())
        rhs = ctx.expression()
        if rhs:
            rhs = self.visit(rhs)

        return [ is_splat, lhs_value, lhs_mode, rhs ]

    def visitObjectKey(self, ctx):
        expression = ctx.expression()
        if expression:
            expression = self.visit(expression)
        symbol = ctx.SYMBOL()
        if symbol:
            symbol = symbol.getText()
        number = ctx.NUMBER()
        if number:
            number = json.loads(ctx.NUMBER().getText())
        computed = ctx.computed is not None

        if symbol is not None:
            return [ symbol, "literal-key" ]
        if number is not None:
            return [ number, "literal-key" ]
        if expression:
            if computed:
                return [ expression, "computed-expression-key" ]
            else:
                return [ expression, "expression-key" ]

    def visitObjectType(self, ctx):
        result = {}
        properties, splat = self.visit(ctx.objectProperties())

        if splat:
            raise ParseCancellationException()

        for is_splat, lhs_value, lhs_mode, rhs in properties:
            if is_splat:
                raise NotImplementedError()
            if lhs_mode == "literal-key":
                lhs_value = literal_op(lhs_value)
            if lhs_mode == "expression-key":
                raise ParseCancellationException()
            if lhs_mode == "computed-expression-key":
                raise ParseCancellationException()

            result[lhs_value] = rhs
        return object_type(result, any_type())

    def visitListTemplate(self, ctx):
        result = []
        properties, splat = self.visit(ctx.objectProperties())

        if splat:
            raise ParseCancellationException()

        for is_splat, lhs_value, lhs_mode, rhs in properties:
            value_type = None

            if is_splat:
                raise NotImplementedError()
            if rhs is not None:
                raise ParseCancellationException("RHS found in list template")
            if lhs_mode == "literal-key":
                if isinstance(lhs_value, str):
                    value_type = unbound_dereference(lhs_value)
                elif isinstance(lhs_value, int):
                    value_type = literal_op(lhs_value)
            if lhs_mode == "expression-key":
                value_type = lhs_value
            if lhs_mode == "computed-expression-key":
                raise ParseCancellationException()

            result.append(value_type)

        return list_template_op(result)

    def visitTupleType(self, ctx):
        micro_ops = []
        expressions = [self.visit(e) for e in ctx.expression()]

        inferred_splat_type = None
        if ctx.splat2():
            inferred_splat_type = expressions.pop()

        for index, expression in enumerate(expressions):
            micro_ops.append(object_template_op({
                "type": literal_op("get"),
                "index": literal_op(index),
                "params": list_template_op([
                    literal_op(index),
                    expression
                ])
            }))
            micro_ops.append(object_template_op({
                "type": literal_op("set"),
                "index": literal_op(index),
                "params": list_template_op([
                    literal_op(index),
                    any_type()
                ])
            }))

        if inferred_splat_type:
            micro_ops.append(object_template_op({
                "type": literal_op("infer-remainder"),
                "params": list_template_op([ inferred_splat_type ])
            }))

        return composite_type(micro_ops)

    def visitListType(self, ctx):
        type = self.visit(ctx.expression())
        return list_type([], type)

    def visitDictionaryType(self, ctx):
        key_type, value_type = ctx.expression()
        key_type = self.visit(key_type)
        value_type = self.visit(value_type)

        return composite_type([
            object_template_op({
                "type": literal_op("get-wildcard"),
                "params": list_template_op([
                    key_type,
                    value_type,
                    literal_op(True)
                ])
            }),
            object_template_op({
                "type": literal_op("set-wildcard"),
                "params": list_template_op([
                    key_type,
                    value_type,
                    literal_op(False),
                    literal_op(False),
                ])
            }),
            object_template_op({
                "type": literal_op("delete-wildcard"),
                "params": list_template_op([
                    key_type, literal_op(True)
                ])
            }),
        ])

    # def visitToValueBreakFunctionType(self, ctx):
    #     expressions = ctx.expression()
    #     if len(expressions) == 2:
    #         argument_type, return_type = expressions
    #         argument_type = self.visit(argument_type)
    #         argument_type = list_type([ argument_type ], None)
    #     else:
    #         return_type, = ctx.expression()
    #         argument_type = no_value_type()
    #
    #     return_type = self.visit(return_type)
    #
    #     return function_type(argument_type, {
    #         "value": list_template_op([ object_template_op({ "out": return_type }) ])
    #     })

    def visitFunctionType(self, ctx):
        expressions = ctx.expression()
        if len(expressions) >= 2:
            *argument_types, break_types = expressions
            argument_types = [ self.visit(argument_type) for argument_type in argument_types ]
            argument_type = list_type(argument_types, None)
        else:
            break_types, = ctx.expression()
            argument_type = list_type([], None)

        break_types = self.visit(break_types)

        return function_type(argument_type, break_types)

    def visitToFunctionExpression(self, ctx):
        dynamic = bool(ctx.dynamic)
        _, function = self.visit(ctx.function())

        info = get_context_debug_info(ctx)
        function = prepare_op(literal_op(function), **info)
        if not dynamic:
            function = static_op(function)
        function = close_op(function, context_op())

        return function

    def visitToDynamicEval(self, ctx):
        expression = self.visit(ctx.expression())
        return dynamic_eval_op(expression)

    def visitToDefer(self, ctx):
        expression = self.visit(ctx.expression())
        return literal_op(expression)

class ObjectTemplateBuilder(object):
    def __init__(self, previous_op=None):
        self.properties = {}
        self.previous_op = previous_op

    def add(self, lhs, rhs):
        self.properties[lhs] = rhs

    def merge(self, rhs):
        return ObjectTemplateBuilder(merge_op(
            self.build(),
            rhs
        ))

    def build(self):
        template_op = None
        if self.properties or not self.previous_op:
            template_op = object_template_op(self.properties, op_keys=True)

        if self.previous_op and template_op:
            return merge_op(self.previous_op, template_op)

        result = self.previous_op or template_op
        if result is None:
            print("Asd")
        return result

class CodeBlockBuilder(object):
    def __init__(
        self,
        code_expressions=MISSING,
        local_variable_type=MISSING,
        local_initializer=MISSING,
        extra_statics=MISSING,
        argument_type_expression=MISSING,
        breaks_types=MISSING
    ):
        if argument_type_expression is not MISSING:
            check_is_opcode(argument_type_expression)
        self.code_expressions = code_expressions
        self.local_variable_type = local_variable_type
        self.local_initializer = local_initializer
        self.extra_statics = extra_statics
        self.argument_type_expression = argument_type_expression
        self.breaks_types = breaks_types

    def set_breaks_types(self, breaks_types):
        self.breaks_types = breaks_types

    def chain(self, other):
        can_merge_code_blocks = True

        if other is None:
            return self

        if other.argument_type_expression is not MISSING:
            # If the inner function needs an argument, we have no mechanism to provide it
            raise FatalError()
        if other.breaks_types is not MISSING:
            # The newly created function ignores other.breaks_types, so let's fail early if they're provided
            raise FatalError()

        if self.local_variable_type is not MISSING and other.local_variable_type is not MISSING:
            # We can only take local variables from one of the two functions
            can_merge_code_blocks = False
        if self.code_expressions is not MISSING and other.local_variable_type is not MISSING:
            # We have code that should execute before the other functions local variables are declared
            can_merge_code_blocks = False
        if self.extra_statics is not MISSING and other.extra_statics is not MISSING:
            # We can only take extra statics from one of the two functions
            can_merge_code_blocks = False
        if self.extra_statics is not MISSING and other.local_variable_type is not MISSING:
            # The inner local_variable_type might reference something from statics
            can_merge_code_blocks = False

        new_code_expressions = None
        our_code_expressions = default(self.code_expressions, MISSING, [])
        other_code_expressions = default(other.code_expressions, MISSING, [])

        if can_merge_code_blocks:
            new_code_expressions = our_code_expressions + other_code_expressions
            local_variable_type = default(self.local_variable_type, MISSING, other.local_variable_type)
            local_initializer = default(self.local_initializer, MISSING, other.local_initializer)
            extra_statics = default(self.extra_statics, MISSING, other.extra_statics)
        else:
            new_code_expressions = our_code_expressions + [ other.create("expression") ]
            local_variable_type = self.local_variable_type
            local_initializer = self.local_initializer
            extra_statics = self.extra_statics

        return CodeBlockBuilder(
            code_expressions=new_code_expressions,
            local_variable_type=local_variable_type,
            local_initializer=local_initializer,
            extra_statics=extra_statics,
            argument_type_expression=self.argument_type_expression,
            breaks_types=self.breaks_types
        )

    def requires_function(self):
        return (
            self.argument_type_expression is not MISSING
            or self.local_variable_type is not MISSING
            or self.extra_statics is not MISSING
            or self.breaks_types is not MISSING
        )

    def create(self, output_mode, function_debug_info={}):
        if output_mode not in ("first-class-function", "second-class-function", "expression"):
            raise FatalError()

        code_expressions = default(self.code_expressions, MISSING, [])

        for c in code_expressions:
            if not is_opcode(c):
                raise FatalError()

        if not self.requires_function() and output_mode == "expression":
            return combine_opcodes(code_expressions)

        if self.argument_type_expression is not MISSING:
            argument_type = self.argument_type_expression
        else:
            argument_type = no_value_type()

        if self.local_variable_type is not MISSING:
            local_type = self.local_variable_type
        else:
            local_type = object_type({}, wildcard_type=rich_type())  # For future python local variables...

        if self.local_initializer is not MISSING:
            local_initializer = self.local_initializer
        else:
            local_initializer = object_template_op({})

        if self.breaks_types is not MISSING:
            break_types = self.breaks_types
        else:
            break_types = infer_all()

        if self.extra_statics is not MISSING:
            extra_statics = self.extra_statics
        else:
            extra_statics = {}

        if output_mode == "first-class-function":
            # A function created by the user, which mangles returns as expected
            code = transform_op(
                "return", "value", combine_opcodes(code_expressions)
            )
            return function_lit(
                extra_statics, argument_type, break_types, local_type, local_initializer, code, **function_debug_info
            )
        if output_mode == "second-class-function":
            # A function created by the environment, which leaves returns unmangled
            code = combine_opcodes(code_expressions)
            return function_lit(
                extra_statics, argument_type, break_types, local_type, local_initializer, code, **function_debug_info
            )
        elif output_mode == "expression":
            return invoke_op(prepare_function_lit(function_lit(
                extra_statics, argument_type, break_types, local_type, local_initializer, combine_opcodes(code_expressions), **function_debug_info
            )))

def get_token_debug_info(common_token):
    return PythonDict({
        "column": common_token.column,
        "line": common_token.line,
        "text": common_token.text
    })

def get_context_debug_info(ctx):
    return {
        "start": PythonDict({
            "column": ctx.start.column,
            "line": ctx.start.line
        }),
        "end": PythonDict({
            "column": ctx.stop.column,
            "line": ctx.stop.line
        })
    }

class ParseError(Exception):
    def __init__(self, msg, line, column):
        self.msg = msg
        self.line = line
        self.column = column

class AlwaysFailErrorListener(ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        super(AlwaysFailErrorListener, self).syntaxError(recognizer, offendingSymbol, line, column, msg, e)
        raise ParseError(msg, line, column)


def parse(code, pre_chain_function=None, post_chain_function=None):
    lexer = langLexer(InputStream(code))
    lexer.addErrorListener(AlwaysFailErrorListener())
    tokens = CommonTokenStream(lexer)
    parser = langParser(tokens)
    parser.addErrorListener(AlwaysFailErrorListener())
    ast = parser.json()
    visitor = RDHLang5Visitor(pre_chain_function=pre_chain_function, post_chain_function=post_chain_function)
    ast = visitor.visit(ast)
    if isinstance(ast, Universal):
        get_manager(ast).raw_code = code
    return ast
