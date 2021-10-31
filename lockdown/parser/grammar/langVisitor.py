# Generated from lang.g4 by ANTLR 4.7.2
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .langParser import langParser
else:
    from langParser import langParser

# This class defines a complete generic visitor for a parse tree produced by langParser.

class langVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by langParser#json.
    def visitJson(self, ctx:langParser.JsonContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#obj.
    def visitObj(self, ctx:langParser.ObjContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#pair.
    def visitPair(self, ctx:langParser.PairContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#arr.
    def visitArr(self, ctx:langParser.ArrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#value.
    def visitValue(self, ctx:langParser.ValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#function.
    def visitFunction(self, ctx:langParser.FunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#codeBlockAsFunction.
    def visitCodeBlockAsFunction(self, ctx:langParser.CodeBlockAsFunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#argumentDestructurings.
    def visitArgumentDestructurings(self, ctx:langParser.ArgumentDestructuringsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#argumentDestructuring.
    def visitArgumentDestructuring(self, ctx:langParser.ArgumentDestructuringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#symbolInitialization.
    def visitSymbolInitialization(self, ctx:langParser.SymbolInitializationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#assignmentOrInitializationLvalue.
    def visitAssignmentOrInitializationLvalue(self, ctx:langParser.AssignmentOrInitializationLvalueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#localVariableDeclaration.
    def visitLocalVariableDeclaration(self, ctx:langParser.LocalVariableDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticValueDeclaration.
    def visitStaticValueDeclaration(self, ctx:langParser.StaticValueDeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#typedef.
    def visitTypedef(self, ctx:langParser.TypedefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toFunctionStatement.
    def visitToFunctionStatement(self, ctx:langParser.ToFunctionStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toDestructuring.
    def visitToDestructuring(self, ctx:langParser.ToDestructuringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toExpression.
    def visitToExpression(self, ctx:langParser.ToExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toObjectDestructuring.
    def visitToObjectDestructuring(self, ctx:langParser.ToObjectDestructuringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toListDestructuring.
    def visitToListDestructuring(self, ctx:langParser.ToListDestructuringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#mod.
    def visitMod(self, ctx:langParser.ModContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticInvocation.
    def visitStaticInvocation(self, ctx:langParser.StaticInvocationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#numberExpression.
    def visitNumberExpression(self, ctx:langParser.NumberExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#lt.
    def visitLt(self, ctx:langParser.LtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#falseExpression.
    def visitFalseExpression(self, ctx:langParser.FalseExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toLoop.
    def visitToLoop(self, ctx:langParser.ToLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#division.
    def visitDivision(self, ctx:langParser.DivisionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toListType.
    def visitToListType(self, ctx:langParser.ToListTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toDictionaryType.
    def visitToDictionaryType(self, ctx:langParser.ToDictionaryTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticDereference.
    def visitStaticDereference(self, ctx:langParser.StaticDereferenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#stringExpression.
    def visitStringExpression(self, ctx:langParser.StringExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toWhileLoop.
    def visitToWhileLoop(self, ctx:langParser.ToWhileLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#gte.
    def visitGte(self, ctx:langParser.GteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#noParameterInvocation.
    def visitNoParameterInvocation(self, ctx:langParser.NoParameterInvocationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toForListLoop.
    def visitToForListLoop(self, ctx:langParser.ToForListLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#neq.
    def visitNeq(self, ctx:langParser.NeqContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#yieldStatement.
    def visitYieldStatement(self, ctx:langParser.YieldStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#addition.
    def visitAddition(self, ctx:langParser.AdditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dynamicDereference.
    def visitDynamicDereference(self, ctx:langParser.DynamicDereferenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toObjectTemplate.
    def visitToObjectTemplate(self, ctx:langParser.ToObjectTemplateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#is.
    def visitIs(self, ctx:langParser.IsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#eq.
    def visitEq(self, ctx:langParser.EqContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#parenthesis.
    def visitParenthesis(self, ctx:langParser.ParenthesisContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dynamicInsertion.
    def visitDynamicInsertion(self, ctx:langParser.DynamicInsertionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#invocation.
    def visitInvocation(self, ctx:langParser.InvocationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#immediateAssignment.
    def visitImmediateAssignment(self, ctx:langParser.ImmediateAssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toListTemplate.
    def visitToListTemplate(self, ctx:langParser.ToListTemplateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toForGeneratorLoop.
    def visitToForGeneratorLoop(self, ctx:langParser.ToForGeneratorLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#singleParameterInvocation.
    def visitSingleParameterInvocation(self, ctx:langParser.SingleParameterInvocationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toFunctionType.
    def visitToFunctionType(self, ctx:langParser.ToFunctionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#subtraction.
    def visitSubtraction(self, ctx:langParser.SubtractionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#returnStatement.
    def visitReturnStatement(self, ctx:langParser.ReturnStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticExpression.
    def visitStaticExpression(self, ctx:langParser.StaticExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#trueExpression.
    def visitTrueExpression(self, ctx:langParser.TrueExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#boolAnd.
    def visitBoolAnd(self, ctx:langParser.BoolAndContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#multiplication.
    def visitMultiplication(self, ctx:langParser.MultiplicationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#lte.
    def visitLte(self, ctx:langParser.LteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dynamicAssignment.
    def visitDynamicAssignment(self, ctx:langParser.DynamicAssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toIfStatement.
    def visitToIfStatement(self, ctx:langParser.ToIfStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#immediateDereference.
    def visitImmediateDereference(self, ctx:langParser.ImmediateDereferenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toObjectType.
    def visitToObjectType(self, ctx:langParser.ToObjectTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#boolOr.
    def visitBoolOr(self, ctx:langParser.BoolOrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toPrintStatement.
    def visitToPrintStatement(self, ctx:langParser.ToPrintStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#breakStatement.
    def visitBreakStatement(self, ctx:langParser.BreakStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#gt.
    def visitGt(self, ctx:langParser.GtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#pipeline.
    def visitPipeline(self, ctx:langParser.PipelineContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toFunctionExpression.
    def visitToFunctionExpression(self, ctx:langParser.ToFunctionExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toTupleType.
    def visitToTupleType(self, ctx:langParser.ToTupleTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#toMap.
    def visitToMap(self, ctx:langParser.ToMapContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#continueStatement.
    def visitContinueStatement(self, ctx:langParser.ContinueStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#staticAssignment.
    def visitStaticAssignment(self, ctx:langParser.StaticAssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#ternary.
    def visitTernary(self, ctx:langParser.TernaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectTemplate.
    def visitObjectTemplate(self, ctx:langParser.ObjectTemplateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectPropertyPair.
    def visitObjectPropertyPair(self, ctx:langParser.ObjectPropertyPairContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectType.
    def visitObjectType(self, ctx:langParser.ObjectTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#objectTypePropertyPair.
    def visitObjectTypePropertyPair(self, ctx:langParser.ObjectTypePropertyPairContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#listTemplate.
    def visitListTemplate(self, ctx:langParser.ListTemplateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#tupleType.
    def visitTupleType(self, ctx:langParser.TupleTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#splat.
    def visitSplat(self, ctx:langParser.SplatContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#listType.
    def visitListType(self, ctx:langParser.ListTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#dictionaryType.
    def visitDictionaryType(self, ctx:langParser.DictionaryTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#functionType.
    def visitFunctionType(self, ctx:langParser.FunctionTypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#ifStatement.
    def visitIfStatement(self, ctx:langParser.IfStatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#loop.
    def visitLoop(self, ctx:langParser.LoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#whileLoop.
    def visitWhileLoop(self, ctx:langParser.WhileLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#forGeneratorLoop.
    def visitForGeneratorLoop(self, ctx:langParser.ForGeneratorLoopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by langParser#forListLoop.
    def visitForListLoop(self, ctx:langParser.ForListLoopContext):
        return self.visitChildren(ctx)



del langParser