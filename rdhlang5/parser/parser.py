# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from cookielib import offset_from_tz_string
import json

from antlr4.CommonTokenStream import CommonTokenStream
from antlr4.InputStream import InputStream
from antlr4.error.ErrorListener import ConsoleErrorListener

from rdhlang5.executor.raw_code_factories import function_lit, nop, comma_op, \
    literal_op, dereference_op, unbound_dereference, dereference, addition_op, \
    transform_op, int_type, multiplication_op, division_op, subtraction_op,\
    object_type
from rdhlang5.parser.grammar.langLexer import langLexer
from rdhlang5.parser.grammar.langParser import langParser
from rdhlang5.parser.grammar.langVisitor import langVisitor
from rdhlang5.type_system.default_composite_types import DEFAULT_OBJECT_TYPE
from rdhlang5.type_system.object_types import RDHObject


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
        argument_type_expression = ctx.expression()
        code_block = self.visit(ctx.codeBlock())

        if argument_type_expression:
            argument_type_expression = self.visit(argument_type_expression)
            return function_lit(
                argument_type_expression,
                transform_op("return", "value", code_block)
            )
        else:
            return function_lit(
                transform_op("return", "value", code_block)
            )

    def visitCodeBlock(self, ctx):
        expressions = [
            self.visit(e) for e in ctx.expression()
        ]
        if len(expressions) == 0:
            return nop
        if len(expressions) == 1:
            return expressions[0]
        return comma_op(expressions)

    def visitStringExpression(self, ctx):
        return literal_op(json.loads(ctx.STRING().getText()))

    def visitNumberExpression(self, ctx):
        return literal_op(json.loads(ctx.NUMBER().getText()))

    def visitImmediateDereference(self, ctx):
        return unbound_dereference(ctx.SYMBOL().getText())

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

    def visitReturnStatement(self, ctx):
        expression = self.visit(ctx.expression())
        return transform_op(
            "value", "return", expression
        )

    def visitIntTypeLiteral(self, ctx):
        return int_type

    def visitObjectType(self, ctx):
        result = {}
        for pair in ctx.objectTypePropertyPair():
            name, type = self.visit(pair)
            result[name] = type
        return object_type(result)

    def visitObjectTypePropertyPair(self, ctx):
        return [ ctx.SYMBOL().getText(), self.visit(ctx.expression()) ]

class ParseError(Exception):
    pass

class AlwaysFailErrorListener(ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        super(AlwaysFailErrorListener, self).syntaxError(recognizer, offendingSymbol, line, column, msg, e)
        raise ParseError()


def parse(code):
    lexer = langLexer(InputStream(code))
    lexer.addErrorListener(AlwaysFailErrorListener())
    tokens = CommonTokenStream(lexer)
    parser = langParser(tokens)
    parser.addErrorListener(AlwaysFailErrorListener())
    ast = parser.json()
    visitor = RDHLang5Visitor()
    return visitor.visit(ast)
