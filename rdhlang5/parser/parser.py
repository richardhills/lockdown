# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from antlr4.CommonTokenStream import CommonTokenStream
from antlr4.InputStream import InputStream
from antlr4.error.ErrorListener import ConsoleErrorListener

from rdhlang5.executor.raw_code_factories import function_lit, nop, comma_op, \
    literal_op, dereference_op, unbound_dereference, addition_op, \
    transform_op, multiplication_op, division_op, subtraction_op, \
    object_type, is_opcode, object_template_op, infer_all, \
    no_value_type, combine_opcodes, invoke_op, assignment_op, \
    unbound_assignment, list_template_op, list_type, context_op, \
    loop_op, condition_op, binary_integer_op, equality_op, dereference, \
    local_function, reset_op, inferred_type, prepare_function_lit, transform
from rdhlang5.parser.grammar.langLexer import langLexer
from rdhlang5.parser.grammar.langParser import langParser
from rdhlang5.parser.grammar.langVisitor import langVisitor
from rdhlang5.type_system.default_composite_types import DEFAULT_OBJECT_TYPE
from rdhlang5.type_system.exceptions import FatalError
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.object_types import RDHObject
from rdhlang5.utils import MISSING, default, spread_dict


class RDHLang5Visitor(langVisitor):
    def visitObj(self, ctx):
        result = {}
        for pair in ctx.pair() or []:
            pair = self.visit(pair)
            result[pair[0]] = pair[1]

        return RDHObject(result, bind=DEFAULT_OBJECT_TYPE)

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
            return self.visit(ctx.function())

    def visitFunction(self, ctx):
        argument_type = ctx.expression()

        if argument_type:
            argument_type = self.visit(argument_type)
        else:
            argument_type = MISSING

        function_builder = CodeBlockBuilder(
            argument_type_expression=argument_type
        ).chain(self.visit(ctx.codeBlock()), get_debug_info(ctx))

        return function_builder.create("function", get_debug_info(ctx))

    def visitSymbolInitialization(self, ctx):
        return (
            ctx.SYMBOL().getText(),
            self.visit(ctx.expression())
        )

    def visitLocalVariableDeclaration(self, ctx):
        type = self.visit(ctx.expression())

        remaining_code = ctx.codeBlock()
        if remaining_code:
            remaining_code = self.visit(remaining_code)

        for symbol_initialization in reversed(ctx.symbolInitialization()):
            name, initial_value = self.visit(symbol_initialization)

            new_code_block = CodeBlockBuilder(
                local_variable_types={ name: type },
                local_initializer=object_template_op({ name: initial_value })
            )
            if remaining_code:
                new_code_block = new_code_block.chain(remaining_code, get_debug_info(ctx))
            remaining_code = new_code_block

        return new_code_block

    def visitStaticValueDeclaration(self, ctx):
        remaining_code = self.visit(ctx.codeBlock())

        name, value = self.visit(ctx.symbolInitialization())

        return CodeBlockBuilder(
            extra_statics={ name: value }
        ).chain(remaining_code, get_debug_info(ctx))

    def visitTypedef(self, ctx):
        remaining_code = self.visit(ctx.codeBlock())

        value = self.visit(ctx.expression())
        name = ctx.SYMBOL().getText()

        return CodeBlockBuilder(
            extra_statics={ name: value },
        ).chain(remaining_code, get_debug_info(ctx))

    def visitToExpression(self, ctx):
        code_expressions = [self.visit(e) for e in ctx.expression()]

        new_function = CodeBlockBuilder(
            code_expressions=code_expressions
        )

        remaining_code = ctx.codeBlock()
        if remaining_code:
            remaining_code = self.visit(remaining_code)
            new_function = new_function.chain(remaining_code, get_debug_info(ctx))

        return new_function

    def visitStringExpression(self, ctx):
        return literal_op(json.loads(ctx.STRING().getText()))

    def visitNumberExpression(self, ctx):
        return literal_op(json.loads(ctx.NUMBER().getText()))

    def visitInvocation(self, ctx):
        function, argument = ctx.expression()
        function = self.visit(function)
        argument = self.visit(argument)
        return invoke_op(function, argument, **get_debug_info(ctx))

    def visitNoParameterInvocation(self, ctx):
        return invoke_op(self.visit(ctx.expression()), **get_debug_info(ctx))

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

    def visitImmediateDereference(self, ctx):
        return unbound_dereference(ctx.SYMBOL().getText(), **get_debug_info(ctx))

    def visitStaticDereference(self, ctx):
        return dereference_op(
            self.visit(ctx.expression()),
            literal_op(ctx.SYMBOL().getText())
        )

    def visitDynamicDereference(self, ctx):
        of, reference = ctx.expression()
        of = self.visit(of)
        reference = self.visit(reference)
        return dereference_op(of, reference)

    def visitParenthesis(self, ctx):
        return self.visit(ctx.expression())

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

    def visitReturnStatement(self, ctx):
        expression = self.visit(ctx.expression())
        return transform_op(
            "value", "return", expression
        )

    def visitBreakStatement(self, ctx):
        return transform_op("break")

    def visitIfStatement(self, ctx):
        condition = self.visit(ctx.expression())
        outcomes = ctx.codeBlock()

        if len(outcomes) == 1:
            when_true, = outcomes
            when_false = nop()
        else:
            when_true, when_false = outcomes
            when_false = self.visit(when_false).create("expression", get_debug_info(ctx))

        when_true = self.visit(when_true).create("expression", get_debug_info(ctx))

        return condition_op(condition, when_true, when_false)

    def visitWhileLoop(self, ctx):
        continue_expression = self.visit(ctx.expression())
        loop_code = self.visit(ctx.codeBlock())

        return transform_op(
            "break", "value",
            loop_op(comma_op(
                condition_op(continue_expression, nop(), transform_op("break")),
                loop_code.create("expression", get_debug_info(ctx))
            ))
        )

    def visitForLoop(self, ctx):
        iterator_name = ctx.SYMBOL().getText()
        generator_expression = self.visit(ctx.expression())
        loop_code = self.visit(ctx.codeBlock())

        loop_code = CodeBlockBuilder(
            argument_type_expression=object_type({
                iterator_name: inferred_type()
            })
        ).chain(loop_code, get_debug_info(ctx))

        loop_code = loop_code.create("function", get_debug_info(ctx))
#        get_manager(loop_code).add_composite_type(READONLY_DEFAULT_OBJECT_TYPE)

        return transform_op(
            "break", "value",
            invoke_op(local_function(
                transform(
                    ("yield", "value"),
                    ("value", "break"),
                    reset_op(
                        invoke_op(
                            generator_expression,
                            **get_debug_info(ctx)
                        ), **get_debug_info(ctx)
                    ),
                ),
                loop_op(
                    comma_op(
                        invoke_op(
                            prepare_function_lit(
                                loop_code,
                                **get_debug_info(ctx)
                            ),
                            object_template_op({
                                iterator_name: dereference("local.value")
                            }, **get_debug_info(ctx))
                        ),
                        assignment_op(
                            context_op(), literal_op("local"),
                            transform(
                                ("yield", "value"),
                                ("value", "break"),
                                reset_op(
                                    dereference("local.continuation", **get_debug_info(ctx)), nop(),
                                    **get_debug_info(ctx)
                                ),
                                **get_debug_info(ctx)
                            )
                        )
                    )
                ),
                **get_debug_info(ctx)
            ))
        )

    def visitObjectTemplate(self, ctx):
        result = {}
        for pair in ctx.objectPropertyPair():
            name, type = self.visit(pair)
            result[name] = type
        return object_template_op(result)

    def visitObjectPropertyPair(self, ctx):
        return [ ctx.SYMBOL().getText(), self.visit(ctx.expression()) ] 

    def visitObjectType(self, ctx):
        result = {}
        for pair in ctx.objectTypePropertyPair():
            name, type = self.visit(pair)
            result[name] = type
        return object_type(result)

    def visitObjectTypePropertyPair(self, ctx):
        return [ ctx.SYMBOL().getText(), self.visit(ctx.expression()) ]

    def visitListTemplate(self, ctx):
        return list_template_op([
            self.visit(e) for e in ctx.expression()
        ])

    def visitTupleType(self, ctx):
        types = [self.visit(e) for e in ctx.expression()]
        return list_type(types, None)

    def visitListType(self, ctx):
        type = self.visit(ctx.expression())
        return list_type([], type)

    def visitToFunctionExpression(self, ctx):
        return prepare_function_lit(self.visit(ctx.function()))

class CodeBlockBuilder(object):
    def __init__(
        self,
        code_expressions=MISSING,
        local_variable_types=MISSING,
        local_initializer=MISSING,
        extra_statics=MISSING,
        argument_type_expression=MISSING,
        breaks_types=MISSING
    ):
        self.code_expressions = code_expressions
        self.local_variable_types = local_variable_types
        self.local_initializer = local_initializer
        self.extra_statics = extra_statics
        self.argument_type_expression = argument_type_expression
        self.breaks_types = breaks_types

    def chain(self, other, debug_info):
        can_merge_code_blocks = True

        if other.argument_type_expression is not MISSING:
            # If the inner function needs an argument, we have no mechanism to provide it
            raise FatalError()
        if other.breaks_types is not MISSING:
            # The newly created function ignores other.breaks_types, so let's fail early if they're provided
            raise FatalError()

        if self.local_variable_types is not MISSING and other.local_variable_types is not MISSING:
            # We can only take local variables from one of the two functions
            can_merge_code_blocks = False
        if self.code_expressions is not MISSING and other.local_variable_types is not MISSING:
            # We have code that should execute before the other functions local variables are declared
            can_merge_code_blocks = False
        if self.extra_statics is not MISSING and other.extra_statics is not MISSING:
            # We can only take extra statics from one of the two functions
            can_merge_code_blocks = False
        if self.extra_statics is not MISSING and other.local_variable_types is not MISSING:
            # The inner local_variable_types might reference something from statics
            can_merge_code_blocks = False

        new_code_expressions = None
        our_code_expressions = default(self.code_expressions, MISSING, [])
        other_code_expressions = default(other.code_expressions, MISSING, [])

        if can_merge_code_blocks:
            new_code_expressions = our_code_expressions + other_code_expressions
            local_variable_types = default(self.local_variable_types, MISSING, other.local_variable_types)
            local_initializer = default(self.local_initializer, MISSING, other.local_initializer)
            extra_statics = default(self.extra_statics, MISSING, other.extra_statics)
        else:
            new_code_expressions = our_code_expressions + [ other.create("expression", debug_info) ]
            local_variable_types = self.local_variable_types
            local_initializer = self.local_initializer
            extra_statics = self.extra_statics

        return CodeBlockBuilder(
            code_expressions=new_code_expressions,
            local_variable_types=local_variable_types,
            local_initializer=local_initializer,
            extra_statics=extra_statics,
            argument_type_expression=self.argument_type_expression,
            breaks_types=self.breaks_types
        )

    def requires_function(self):
        return (
            self.argument_type_expression is not MISSING
            or self.local_variable_types is not MISSING
            or self.extra_statics is not MISSING
            or self.breaks_types is not MISSING
        )

    def create(self, output_mode, debug_info):
        if output_mode not in ("function", "expression"):
            raise FatalError()

        code_expressions = default(self.code_expressions, MISSING, [])

        for c in code_expressions:
            if not is_opcode(c):
                raise FatalError()

        if not self.requires_function() and output_mode == "expression":
            return combine_opcodes(code_expressions)

        statics = {}

        if self.argument_type_expression is not MISSING:
            argument_type = self.argument_type_expression
        else:
            argument_type = no_value_type()

        if self.local_variable_types is not MISSING:
            local_type = object_type(self.local_variable_types)
        else:
            local_type = object_type({})

        if self.local_initializer is not MISSING:
            local_initializer = self.local_initializer
        else:
            local_initializer = object_template_op({})

        if self.breaks_types is not MISSING:
            break_types = object_template_op(self.breaks_types)
        else:
            break_types = infer_all()

        if self.extra_statics is not MISSING:
            raise ValueError()
            statics = spread_dict(self.extra_statics, statics)

        if output_mode == "function":
            code = transform_op(
                "return", "value", combine_opcodes(code_expressions), **debug_info
            )
            return function_lit(
                argument_type, break_types, local_type, local_initializer, code, **debug_info
            )
        elif output_mode == "expression":
            return invoke_op(prepare_function_lit(function_lit(
                argument_type, break_types, local_type, local_initializer, combine_opcodes(code_expressions), **debug_info
            ), **debug_info),  **debug_info)

def get_debug_info(ctx):
    return {
        "column": ctx.start.column,
        "line": ctx.start.line,
        "start_token": getattr(ctx.start, "token", ""),
        "end_token": getattr(getattr(ctx, "end", None), "token", "")
    }

class ParseError(Exception):
    pass

class AlwaysFailErrorListener(ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        super(AlwaysFailErrorListener, self).syntaxError(recognizer, offendingSymbol, line, column, msg, e)
        raise ParseError()


def parse(code, debug=False):
    lexer = langLexer(InputStream(code))
    lexer.addErrorListener(AlwaysFailErrorListener())
    tokens = CommonTokenStream(lexer)
    parser = langParser(tokens)
    parser.addErrorListener(AlwaysFailErrorListener())
    ast = parser.json()
    visitor = RDHLang5Visitor()
    ast = visitor.visit(ast)
    if debug:
        get_manager(ast, "parse-code").add_composite_type(DEFAULT_OBJECT_TYPE)
        ast.raw_code = code
    return ast
