# Generated from lang.g4 by ANTLR 4.7.2
from antlr4 import *

# This class defines a complete generic visitor for a parse tree produced by langParser.

class langVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by langParser#json.
    def visitJson(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#obj.
    def visitObj(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#pair.
    def visitPair(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#arr.
    def visitArr(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#value.
    def visitValue(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#function.
    def visitFunction(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#codeBlock.
    def visitCodeBlock(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dynamicDereference.
    def visitDynamicDereference(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#intTypeLiteral.
    def visitIntTypeLiteral(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#immediateDereference.
    def visitImmediateDereference(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toObjectType.
    def visitToObjectType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#numberExpression.
    def visitNumberExpression(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#subtraction.
    def visitSubtraction(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#returnStatement.
    def visitReturnStatement(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#parenthesis.
    def visitParenthesis(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#division.
    def visitDivision(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticDereference.
    def visitStaticDereference(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#stringExpression.
    def visitStringExpression(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#multiplication.
    def visitMultiplication(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#addition.
    def visitAddition(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectType.
    def visitObjectType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectTypePropertyPair.
    def visitObjectTypePropertyPair(self, ctx):
        return self.visitChildren(ctx)


