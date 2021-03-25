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


    # Visit a parse tree produced by langParser#argumentDestructurings.
    def visitArgumentDestructurings(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#argumentDestructuring.
    def visitArgumentDestructuring(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#symbolInitialization.
    def visitSymbolInitialization(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#assignmentOrInitializationLvalue.
    def visitAssignmentOrInitializationLvalue(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#localVariableDeclaration.
    def visitLocalVariableDeclaration(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticValueDeclaration.
    def visitStaticValueDeclaration(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#typedef.
    def visitTypedef(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toFunctionStatement.
    def visitToFunctionStatement(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toDestructuring.
    def visitToDestructuring(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toExpression.
    def visitToExpression(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toObjectDestructuring.
    def visitToObjectDestructuring(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toListDestructuring.
    def visitToListDestructuring(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toForGeneratorLoop.
    def visitToForGeneratorLoop(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#mod.
    def visitMod(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#singleParameterInvocation.
    def visitSingleParameterInvocation(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#numberExpression.
    def visitNumberExpression(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#lt.
    def visitLt(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toFunctionType.
    def visitToFunctionType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#subtraction.
    def visitSubtraction(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#returnStatement.
    def visitReturnStatement(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticExpression.
    def visitStaticExpression(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#division.
    def visitDivision(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toListType.
    def visitToListType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toDictionaryType.
    def visitToDictionaryType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticDereference.
    def visitStaticDereference(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#stringExpression.
    def visitStringExpression(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#boolAnd.
    def visitBoolAnd(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toWhileLoop.
    def visitToWhileLoop(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#gte.
    def visitGte(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#noParameterInvocation.
    def visitNoParameterInvocation(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toForListLoop.
    def visitToForListLoop(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#multiplication.
    def visitMultiplication(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#neq.
    def visitNeq(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#lte.
    def visitLte(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dynamicAssignment.
    def visitDynamicAssignment(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toIfStatement.
    def visitToIfStatement(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#addition.
    def visitAddition(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dynamicDereference.
    def visitDynamicDereference(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#immediateDereference.
    def visitImmediateDereference(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toObjectType.
    def visitToObjectType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#boolOr.
    def visitBoolOr(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toObjectTemplate.
    def visitToObjectTemplate(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#breakStatement.
    def visitBreakStatement(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#is.
    def visitIs(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#eq.
    def visitEq(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#parenthesis.
    def visitParenthesis(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#gt.
    def visitGt(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dynamicInsertion.
    def visitDynamicInsertion(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toFunctionExpression.
    def visitToFunctionExpression(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#invocation.
    def visitInvocation(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toTupleType.
    def visitToTupleType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#immediateAssignment.
    def visitImmediateAssignment(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#continueStatement.
    def visitContinueStatement(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toListTemplate.
    def visitToListTemplate(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticAssignment.
    def visitStaticAssignment(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#ternary.
    def visitTernary(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectTemplate.
    def visitObjectTemplate(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectPropertyPair.
    def visitObjectPropertyPair(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectType.
    def visitObjectType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectTypePropertyPair.
    def visitObjectTypePropertyPair(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#listTemplate.
    def visitListTemplate(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#tupleType.
    def visitTupleType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#splat.
    def visitSplat(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#listType.
    def visitListType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dictionaryType.
    def visitDictionaryType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#functionType.
    def visitFunctionType(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#ifStatement.
    def visitIfStatement(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#whileLoop.
    def visitWhileLoop(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#forGeneratorLoop.
    def visitForGeneratorLoop(self, ctx):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#forListLoop.
    def visitForListLoop(self, ctx):
        return self.visitChildren(ctx)


