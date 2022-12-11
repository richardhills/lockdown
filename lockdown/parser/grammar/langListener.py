# Generated from lang.g4 by ANTLR 4.7.2
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .langParser import langParser
else:
    from langParser import langParser

# This class defines a complete listener for a parse tree produced by langParser.
class langListener(ParseTreeListener):

    # Enter a parse tree produced by langParser#json.
    def enterJson(self, ctx:langParser.JsonContext):
        pass

    # Exit a parse tree produced by langParser#json.
    def exitJson(self, ctx:langParser.JsonContext):
        pass


    # Enter a parse tree produced by langParser#obj.
    def enterObj(self, ctx:langParser.ObjContext):
        pass

    # Exit a parse tree produced by langParser#obj.
    def exitObj(self, ctx:langParser.ObjContext):
        pass


    # Enter a parse tree produced by langParser#pair.
    def enterPair(self, ctx:langParser.PairContext):
        pass

    # Exit a parse tree produced by langParser#pair.
    def exitPair(self, ctx:langParser.PairContext):
        pass


    # Enter a parse tree produced by langParser#arr.
    def enterArr(self, ctx:langParser.ArrContext):
        pass

    # Exit a parse tree produced by langParser#arr.
    def exitArr(self, ctx:langParser.ArrContext):
        pass


    # Enter a parse tree produced by langParser#value.
    def enterValue(self, ctx:langParser.ValueContext):
        pass

    # Exit a parse tree produced by langParser#value.
    def exitValue(self, ctx:langParser.ValueContext):
        pass


    # Enter a parse tree produced by langParser#function.
    def enterFunction(self, ctx:langParser.FunctionContext):
        pass

    # Exit a parse tree produced by langParser#function.
    def exitFunction(self, ctx:langParser.FunctionContext):
        pass


    # Enter a parse tree produced by langParser#codeBlockAsFunction.
    def enterCodeBlockAsFunction(self, ctx:langParser.CodeBlockAsFunctionContext):
        pass

    # Exit a parse tree produced by langParser#codeBlockAsFunction.
    def exitCodeBlockAsFunction(self, ctx:langParser.CodeBlockAsFunctionContext):
        pass


    # Enter a parse tree produced by langParser#lockdownJsonExpression.
    def enterLockdownJsonExpression(self, ctx:langParser.LockdownJsonExpressionContext):
        pass

    # Exit a parse tree produced by langParser#lockdownJsonExpression.
    def exitLockdownJsonExpression(self, ctx:langParser.LockdownJsonExpressionContext):
        pass


    # Enter a parse tree produced by langParser#argumentDestructurings.
    def enterArgumentDestructurings(self, ctx:langParser.ArgumentDestructuringsContext):
        pass

    # Exit a parse tree produced by langParser#argumentDestructurings.
    def exitArgumentDestructurings(self, ctx:langParser.ArgumentDestructuringsContext):
        pass


    # Enter a parse tree produced by langParser#argumentDestructuring.
    def enterArgumentDestructuring(self, ctx:langParser.ArgumentDestructuringContext):
        pass

    # Exit a parse tree produced by langParser#argumentDestructuring.
    def exitArgumentDestructuring(self, ctx:langParser.ArgumentDestructuringContext):
        pass


    # Enter a parse tree produced by langParser#symbolInitialization.
    def enterSymbolInitialization(self, ctx:langParser.SymbolInitializationContext):
        pass

    # Exit a parse tree produced by langParser#symbolInitialization.
    def exitSymbolInitialization(self, ctx:langParser.SymbolInitializationContext):
        pass


    # Enter a parse tree produced by langParser#assignmentOrInitializationLvalue.
    def enterAssignmentOrInitializationLvalue(self, ctx:langParser.AssignmentOrInitializationLvalueContext):
        pass

    # Exit a parse tree produced by langParser#assignmentOrInitializationLvalue.
    def exitAssignmentOrInitializationLvalue(self, ctx:langParser.AssignmentOrInitializationLvalueContext):
        pass


    # Enter a parse tree produced by langParser#localVariableDeclaration.
    def enterLocalVariableDeclaration(self, ctx:langParser.LocalVariableDeclarationContext):
        pass

    # Exit a parse tree produced by langParser#localVariableDeclaration.
    def exitLocalVariableDeclaration(self, ctx:langParser.LocalVariableDeclarationContext):
        pass


    # Enter a parse tree produced by langParser#staticValueDeclaration.
    def enterStaticValueDeclaration(self, ctx:langParser.StaticValueDeclarationContext):
        pass

    # Exit a parse tree produced by langParser#staticValueDeclaration.
    def exitStaticValueDeclaration(self, ctx:langParser.StaticValueDeclarationContext):
        pass


    # Enter a parse tree produced by langParser#typedef.
    def enterTypedef(self, ctx:langParser.TypedefContext):
        pass

    # Exit a parse tree produced by langParser#typedef.
    def exitTypedef(self, ctx:langParser.TypedefContext):
        pass


    # Enter a parse tree produced by langParser#toFunctionStatement.
    def enterToFunctionStatement(self, ctx:langParser.ToFunctionStatementContext):
        pass

    # Exit a parse tree produced by langParser#toFunctionStatement.
    def exitToFunctionStatement(self, ctx:langParser.ToFunctionStatementContext):
        pass


    # Enter a parse tree produced by langParser#toDestructuring.
    def enterToDestructuring(self, ctx:langParser.ToDestructuringContext):
        pass

    # Exit a parse tree produced by langParser#toDestructuring.
    def exitToDestructuring(self, ctx:langParser.ToDestructuringContext):
        pass


    # Enter a parse tree produced by langParser#toExpression.
    def enterToExpression(self, ctx:langParser.ToExpressionContext):
        pass

    # Exit a parse tree produced by langParser#toExpression.
    def exitToExpression(self, ctx:langParser.ToExpressionContext):
        pass


    # Enter a parse tree produced by langParser#toObjectDestructuring.
    def enterToObjectDestructuring(self, ctx:langParser.ToObjectDestructuringContext):
        pass

    # Exit a parse tree produced by langParser#toObjectDestructuring.
    def exitToObjectDestructuring(self, ctx:langParser.ToObjectDestructuringContext):
        pass


    # Enter a parse tree produced by langParser#toListDestructuring.
    def enterToListDestructuring(self, ctx:langParser.ToListDestructuringContext):
        pass

    # Exit a parse tree produced by langParser#toListDestructuring.
    def exitToListDestructuring(self, ctx:langParser.ToListDestructuringContext):
        pass


    # Enter a parse tree produced by langParser#mod.
    def enterMod(self, ctx:langParser.ModContext):
        pass

    # Exit a parse tree produced by langParser#mod.
    def exitMod(self, ctx:langParser.ModContext):
        pass


    # Enter a parse tree produced by langParser#staticInvocation.
    def enterStaticInvocation(self, ctx:langParser.StaticInvocationContext):
        pass

    # Exit a parse tree produced by langParser#staticInvocation.
    def exitStaticInvocation(self, ctx:langParser.StaticInvocationContext):
        pass


    # Enter a parse tree produced by langParser#numberExpression.
    def enterNumberExpression(self, ctx:langParser.NumberExpressionContext):
        pass

    # Exit a parse tree produced by langParser#numberExpression.
    def exitNumberExpression(self, ctx:langParser.NumberExpressionContext):
        pass


    # Enter a parse tree produced by langParser#toBreakTypes.
    def enterToBreakTypes(self, ctx:langParser.ToBreakTypesContext):
        pass

    # Exit a parse tree produced by langParser#toBreakTypes.
    def exitToBreakTypes(self, ctx:langParser.ToBreakTypesContext):
        pass


    # Enter a parse tree produced by langParser#lt.
    def enterLt(self, ctx:langParser.LtContext):
        pass

    # Exit a parse tree produced by langParser#lt.
    def exitLt(self, ctx:langParser.LtContext):
        pass


    # Enter a parse tree produced by langParser#falseExpression.
    def enterFalseExpression(self, ctx:langParser.FalseExpressionContext):
        pass

    # Exit a parse tree produced by langParser#falseExpression.
    def exitFalseExpression(self, ctx:langParser.FalseExpressionContext):
        pass


    # Enter a parse tree produced by langParser#toLoop.
    def enterToLoop(self, ctx:langParser.ToLoopContext):
        pass

    # Exit a parse tree produced by langParser#toLoop.
    def exitToLoop(self, ctx:langParser.ToLoopContext):
        pass


    # Enter a parse tree produced by langParser#division.
    def enterDivision(self, ctx:langParser.DivisionContext):
        pass

    # Exit a parse tree produced by langParser#division.
    def exitDivision(self, ctx:langParser.DivisionContext):
        pass


    # Enter a parse tree produced by langParser#toListType.
    def enterToListType(self, ctx:langParser.ToListTypeContext):
        pass

    # Exit a parse tree produced by langParser#toListType.
    def exitToListType(self, ctx:langParser.ToListTypeContext):
        pass


    # Enter a parse tree produced by langParser#toDictionaryType.
    def enterToDictionaryType(self, ctx:langParser.ToDictionaryTypeContext):
        pass

    # Exit a parse tree produced by langParser#toDictionaryType.
    def exitToDictionaryType(self, ctx:langParser.ToDictionaryTypeContext):
        pass


    # Enter a parse tree produced by langParser#staticDereference.
    def enterStaticDereference(self, ctx:langParser.StaticDereferenceContext):
        pass

    # Exit a parse tree produced by langParser#staticDereference.
    def exitStaticDereference(self, ctx:langParser.StaticDereferenceContext):
        pass


    # Enter a parse tree produced by langParser#stringExpression.
    def enterStringExpression(self, ctx:langParser.StringExpressionContext):
        pass

    # Exit a parse tree produced by langParser#stringExpression.
    def exitStringExpression(self, ctx:langParser.StringExpressionContext):
        pass


    # Enter a parse tree produced by langParser#toWhileLoop.
    def enterToWhileLoop(self, ctx:langParser.ToWhileLoopContext):
        pass

    # Exit a parse tree produced by langParser#toWhileLoop.
    def exitToWhileLoop(self, ctx:langParser.ToWhileLoopContext):
        pass


    # Enter a parse tree produced by langParser#gte.
    def enterGte(self, ctx:langParser.GteContext):
        pass

    # Exit a parse tree produced by langParser#gte.
    def exitGte(self, ctx:langParser.GteContext):
        pass


    # Enter a parse tree produced by langParser#noParameterInvocation.
    def enterNoParameterInvocation(self, ctx:langParser.NoParameterInvocationContext):
        pass

    # Exit a parse tree produced by langParser#noParameterInvocation.
    def exitNoParameterInvocation(self, ctx:langParser.NoParameterInvocationContext):
        pass


    # Enter a parse tree produced by langParser#toForListLoop.
    def enterToForListLoop(self, ctx:langParser.ToForListLoopContext):
        pass

    # Exit a parse tree produced by langParser#toForListLoop.
    def exitToForListLoop(self, ctx:langParser.ToForListLoopContext):
        pass


    # Enter a parse tree produced by langParser#neq.
    def enterNeq(self, ctx:langParser.NeqContext):
        pass

    # Exit a parse tree produced by langParser#neq.
    def exitNeq(self, ctx:langParser.NeqContext):
        pass


    # Enter a parse tree produced by langParser#yieldStatement.
    def enterYieldStatement(self, ctx:langParser.YieldStatementContext):
        pass

    # Exit a parse tree produced by langParser#yieldStatement.
    def exitYieldStatement(self, ctx:langParser.YieldStatementContext):
        pass


    # Enter a parse tree produced by langParser#addition.
    def enterAddition(self, ctx:langParser.AdditionContext):
        pass

    # Exit a parse tree produced by langParser#addition.
    def exitAddition(self, ctx:langParser.AdditionContext):
        pass


    # Enter a parse tree produced by langParser#dynamicDereference.
    def enterDynamicDereference(self, ctx:langParser.DynamicDereferenceContext):
        pass

    # Exit a parse tree produced by langParser#dynamicDereference.
    def exitDynamicDereference(self, ctx:langParser.DynamicDereferenceContext):
        pass


    # Enter a parse tree produced by langParser#toObjectTemplate.
    def enterToObjectTemplate(self, ctx:langParser.ToObjectTemplateContext):
        pass

    # Exit a parse tree produced by langParser#toObjectTemplate.
    def exitToObjectTemplate(self, ctx:langParser.ToObjectTemplateContext):
        pass


    # Enter a parse tree produced by langParser#is.
    def enterIs(self, ctx:langParser.IsContext):
        pass

    # Exit a parse tree produced by langParser#is.
    def exitIs(self, ctx:langParser.IsContext):
        pass


    # Enter a parse tree produced by langParser#eq.
    def enterEq(self, ctx:langParser.EqContext):
        pass

    # Exit a parse tree produced by langParser#eq.
    def exitEq(self, ctx:langParser.EqContext):
        pass


    # Enter a parse tree produced by langParser#parenthesis.
    def enterParenthesis(self, ctx:langParser.ParenthesisContext):
        pass

    # Exit a parse tree produced by langParser#parenthesis.
    def exitParenthesis(self, ctx:langParser.ParenthesisContext):
        pass


    # Enter a parse tree produced by langParser#dynamicInsertion.
    def enterDynamicInsertion(self, ctx:langParser.DynamicInsertionContext):
        pass

    # Exit a parse tree produced by langParser#dynamicInsertion.
    def exitDynamicInsertion(self, ctx:langParser.DynamicInsertionContext):
        pass


    # Enter a parse tree produced by langParser#exportStatement.
    def enterExportStatement(self, ctx:langParser.ExportStatementContext):
        pass

    # Exit a parse tree produced by langParser#exportStatement.
    def exitExportStatement(self, ctx:langParser.ExportStatementContext):
        pass


    # Enter a parse tree produced by langParser#invocation.
    def enterInvocation(self, ctx:langParser.InvocationContext):
        pass

    # Exit a parse tree produced by langParser#invocation.
    def exitInvocation(self, ctx:langParser.InvocationContext):
        pass


    # Enter a parse tree produced by langParser#immediateAssignment.
    def enterImmediateAssignment(self, ctx:langParser.ImmediateAssignmentContext):
        pass

    # Exit a parse tree produced by langParser#immediateAssignment.
    def exitImmediateAssignment(self, ctx:langParser.ImmediateAssignmentContext):
        pass


    # Enter a parse tree produced by langParser#toJsonExpression.
    def enterToJsonExpression(self, ctx:langParser.ToJsonExpressionContext):
        pass

    # Exit a parse tree produced by langParser#toJsonExpression.
    def exitToJsonExpression(self, ctx:langParser.ToJsonExpressionContext):
        pass


    # Enter a parse tree produced by langParser#toListTemplate.
    def enterToListTemplate(self, ctx:langParser.ToListTemplateContext):
        pass

    # Exit a parse tree produced by langParser#toListTemplate.
    def exitToListTemplate(self, ctx:langParser.ToListTemplateContext):
        pass


    # Enter a parse tree produced by langParser#toForGeneratorLoop.
    def enterToForGeneratorLoop(self, ctx:langParser.ToForGeneratorLoopContext):
        pass

    # Exit a parse tree produced by langParser#toForGeneratorLoop.
    def exitToForGeneratorLoop(self, ctx:langParser.ToForGeneratorLoopContext):
        pass


    # Enter a parse tree produced by langParser#singleParameterInvocation.
    def enterSingleParameterInvocation(self, ctx:langParser.SingleParameterInvocationContext):
        pass

    # Exit a parse tree produced by langParser#singleParameterInvocation.
    def exitSingleParameterInvocation(self, ctx:langParser.SingleParameterInvocationContext):
        pass


    # Enter a parse tree produced by langParser#toFunctionType.
    def enterToFunctionType(self, ctx:langParser.ToFunctionTypeContext):
        pass

    # Exit a parse tree produced by langParser#toFunctionType.
    def exitToFunctionType(self, ctx:langParser.ToFunctionTypeContext):
        pass


    # Enter a parse tree produced by langParser#subtraction.
    def enterSubtraction(self, ctx:langParser.SubtractionContext):
        pass

    # Exit a parse tree produced by langParser#subtraction.
    def exitSubtraction(self, ctx:langParser.SubtractionContext):
        pass


    # Enter a parse tree produced by langParser#returnStatement.
    def enterReturnStatement(self, ctx:langParser.ReturnStatementContext):
        pass

    # Exit a parse tree produced by langParser#returnStatement.
    def exitReturnStatement(self, ctx:langParser.ReturnStatementContext):
        pass


    # Enter a parse tree produced by langParser#staticExpression.
    def enterStaticExpression(self, ctx:langParser.StaticExpressionContext):
        pass

    # Exit a parse tree produced by langParser#staticExpression.
    def exitStaticExpression(self, ctx:langParser.StaticExpressionContext):
        pass


    # Enter a parse tree produced by langParser#trueExpression.
    def enterTrueExpression(self, ctx:langParser.TrueExpressionContext):
        pass

    # Exit a parse tree produced by langParser#trueExpression.
    def exitTrueExpression(self, ctx:langParser.TrueExpressionContext):
        pass


    # Enter a parse tree produced by langParser#boolAnd.
    def enterBoolAnd(self, ctx:langParser.BoolAndContext):
        pass

    # Exit a parse tree produced by langParser#boolAnd.
    def exitBoolAnd(self, ctx:langParser.BoolAndContext):
        pass


    # Enter a parse tree produced by langParser#multiplication.
    def enterMultiplication(self, ctx:langParser.MultiplicationContext):
        pass

    # Exit a parse tree produced by langParser#multiplication.
    def exitMultiplication(self, ctx:langParser.MultiplicationContext):
        pass


    # Enter a parse tree produced by langParser#lte.
    def enterLte(self, ctx:langParser.LteContext):
        pass

    # Exit a parse tree produced by langParser#lte.
    def exitLte(self, ctx:langParser.LteContext):
        pass


    # Enter a parse tree produced by langParser#typeof.
    def enterTypeof(self, ctx:langParser.TypeofContext):
        pass

    # Exit a parse tree produced by langParser#typeof.
    def exitTypeof(self, ctx:langParser.TypeofContext):
        pass


    # Enter a parse tree produced by langParser#dynamicAssignment.
    def enterDynamicAssignment(self, ctx:langParser.DynamicAssignmentContext):
        pass

    # Exit a parse tree produced by langParser#dynamicAssignment.
    def exitDynamicAssignment(self, ctx:langParser.DynamicAssignmentContext):
        pass


    # Enter a parse tree produced by langParser#toIfStatement.
    def enterToIfStatement(self, ctx:langParser.ToIfStatementContext):
        pass

    # Exit a parse tree produced by langParser#toIfStatement.
    def exitToIfStatement(self, ctx:langParser.ToIfStatementContext):
        pass


    # Enter a parse tree produced by langParser#immediateDereference.
    def enterImmediateDereference(self, ctx:langParser.ImmediateDereferenceContext):
        pass

    # Exit a parse tree produced by langParser#immediateDereference.
    def exitImmediateDereference(self, ctx:langParser.ImmediateDereferenceContext):
        pass


    # Enter a parse tree produced by langParser#toObjectType.
    def enterToObjectType(self, ctx:langParser.ToObjectTypeContext):
        pass

    # Exit a parse tree produced by langParser#toObjectType.
    def exitToObjectType(self, ctx:langParser.ToObjectTypeContext):
        pass


    # Enter a parse tree produced by langParser#boolOr.
    def enterBoolOr(self, ctx:langParser.BoolOrContext):
        pass

    # Exit a parse tree produced by langParser#boolOr.
    def exitBoolOr(self, ctx:langParser.BoolOrContext):
        pass


    # Enter a parse tree produced by langParser#toPrintStatement.
    def enterToPrintStatement(self, ctx:langParser.ToPrintStatementContext):
        pass

    # Exit a parse tree produced by langParser#toPrintStatement.
    def exitToPrintStatement(self, ctx:langParser.ToPrintStatementContext):
        pass


    # Enter a parse tree produced by langParser#breakStatement.
    def enterBreakStatement(self, ctx:langParser.BreakStatementContext):
        pass

    # Exit a parse tree produced by langParser#breakStatement.
    def exitBreakStatement(self, ctx:langParser.BreakStatementContext):
        pass


    # Enter a parse tree produced by langParser#gt.
    def enterGt(self, ctx:langParser.GtContext):
        pass

    # Exit a parse tree produced by langParser#gt.
    def exitGt(self, ctx:langParser.GtContext):
        pass


    # Enter a parse tree produced by langParser#pipeline.
    def enterPipeline(self, ctx:langParser.PipelineContext):
        pass

    # Exit a parse tree produced by langParser#pipeline.
    def exitPipeline(self, ctx:langParser.PipelineContext):
        pass


    # Enter a parse tree produced by langParser#toFunctionExpression.
    def enterToFunctionExpression(self, ctx:langParser.ToFunctionExpressionContext):
        pass

    # Exit a parse tree produced by langParser#toFunctionExpression.
    def exitToFunctionExpression(self, ctx:langParser.ToFunctionExpressionContext):
        pass


    # Enter a parse tree produced by langParser#toTupleType.
    def enterToTupleType(self, ctx:langParser.ToTupleTypeContext):
        pass

    # Exit a parse tree produced by langParser#toTupleType.
    def exitToTupleType(self, ctx:langParser.ToTupleTypeContext):
        pass


    # Enter a parse tree produced by langParser#toMap.
    def enterToMap(self, ctx:langParser.ToMapContext):
        pass

    # Exit a parse tree produced by langParser#toMap.
    def exitToMap(self, ctx:langParser.ToMapContext):
        pass


    # Enter a parse tree produced by langParser#continueStatement.
    def enterContinueStatement(self, ctx:langParser.ContinueStatementContext):
        pass

    # Exit a parse tree produced by langParser#continueStatement.
    def exitContinueStatement(self, ctx:langParser.ContinueStatementContext):
        pass


    # Enter a parse tree produced by langParser#staticAssignment.
    def enterStaticAssignment(self, ctx:langParser.StaticAssignmentContext):
        pass

    # Exit a parse tree produced by langParser#staticAssignment.
    def exitStaticAssignment(self, ctx:langParser.StaticAssignmentContext):
        pass


    # Enter a parse tree produced by langParser#ternary.
    def enterTernary(self, ctx:langParser.TernaryContext):
        pass

    # Exit a parse tree produced by langParser#ternary.
    def exitTernary(self, ctx:langParser.TernaryContext):
        pass


    # Enter a parse tree produced by langParser#breakTypes.
    def enterBreakTypes(self, ctx:langParser.BreakTypesContext):
        pass

    # Exit a parse tree produced by langParser#breakTypes.
    def exitBreakTypes(self, ctx:langParser.BreakTypesContext):
        pass


    # Enter a parse tree produced by langParser#breakType.
    def enterBreakType(self, ctx:langParser.BreakTypeContext):
        pass

    # Exit a parse tree produced by langParser#breakType.
    def exitBreakType(self, ctx:langParser.BreakTypeContext):
        pass


    # Enter a parse tree produced by langParser#objectTemplate.
    def enterObjectTemplate(self, ctx:langParser.ObjectTemplateContext):
        pass

    # Exit a parse tree produced by langParser#objectTemplate.
    def exitObjectTemplate(self, ctx:langParser.ObjectTemplateContext):
        pass


    # Enter a parse tree produced by langParser#objectType.
    def enterObjectType(self, ctx:langParser.ObjectTypeContext):
        pass

    # Exit a parse tree produced by langParser#objectType.
    def exitObjectType(self, ctx:langParser.ObjectTypeContext):
        pass


    # Enter a parse tree produced by langParser#listTemplate.
    def enterListTemplate(self, ctx:langParser.ListTemplateContext):
        pass

    # Exit a parse tree produced by langParser#listTemplate.
    def exitListTemplate(self, ctx:langParser.ListTemplateContext):
        pass


    # Enter a parse tree produced by langParser#tupleType.
    def enterTupleType(self, ctx:langParser.TupleTypeContext):
        pass

    # Exit a parse tree produced by langParser#tupleType.
    def exitTupleType(self, ctx:langParser.TupleTypeContext):
        pass


    # Enter a parse tree produced by langParser#splat2.
    def enterSplat2(self, ctx:langParser.Splat2Context):
        pass

    # Exit a parse tree produced by langParser#splat2.
    def exitSplat2(self, ctx:langParser.Splat2Context):
        pass


    # Enter a parse tree produced by langParser#listType.
    def enterListType(self, ctx:langParser.ListTypeContext):
        pass

    # Exit a parse tree produced by langParser#listType.
    def exitListType(self, ctx:langParser.ListTypeContext):
        pass


    # Enter a parse tree produced by langParser#dictionaryType.
    def enterDictionaryType(self, ctx:langParser.DictionaryTypeContext):
        pass

    # Exit a parse tree produced by langParser#dictionaryType.
    def exitDictionaryType(self, ctx:langParser.DictionaryTypeContext):
        pass


    # Enter a parse tree produced by langParser#objectProperties.
    def enterObjectProperties(self, ctx:langParser.ObjectPropertiesContext):
        pass

    # Exit a parse tree produced by langParser#objectProperties.
    def exitObjectProperties(self, ctx:langParser.ObjectPropertiesContext):
        pass


    # Enter a parse tree produced by langParser#objectProperty.
    def enterObjectProperty(self, ctx:langParser.ObjectPropertyContext):
        pass

    # Exit a parse tree produced by langParser#objectProperty.
    def exitObjectProperty(self, ctx:langParser.ObjectPropertyContext):
        pass


    # Enter a parse tree produced by langParser#functionType.
    def enterFunctionType(self, ctx:langParser.FunctionTypeContext):
        pass

    # Exit a parse tree produced by langParser#functionType.
    def exitFunctionType(self, ctx:langParser.FunctionTypeContext):
        pass


    # Enter a parse tree produced by langParser#ifStatement.
    def enterIfStatement(self, ctx:langParser.IfStatementContext):
        pass

    # Exit a parse tree produced by langParser#ifStatement.
    def exitIfStatement(self, ctx:langParser.IfStatementContext):
        pass


    # Enter a parse tree produced by langParser#loop.
    def enterLoop(self, ctx:langParser.LoopContext):
        pass

    # Exit a parse tree produced by langParser#loop.
    def exitLoop(self, ctx:langParser.LoopContext):
        pass


    # Enter a parse tree produced by langParser#whileLoop.
    def enterWhileLoop(self, ctx:langParser.WhileLoopContext):
        pass

    # Exit a parse tree produced by langParser#whileLoop.
    def exitWhileLoop(self, ctx:langParser.WhileLoopContext):
        pass


    # Enter a parse tree produced by langParser#forGeneratorLoop.
    def enterForGeneratorLoop(self, ctx:langParser.ForGeneratorLoopContext):
        pass

    # Exit a parse tree produced by langParser#forGeneratorLoop.
    def exitForGeneratorLoop(self, ctx:langParser.ForGeneratorLoopContext):
        pass


    # Enter a parse tree produced by langParser#forListLoop.
    def enterForListLoop(self, ctx:langParser.ForListLoopContext):
        pass

    # Exit a parse tree produced by langParser#forListLoop.
    def exitForListLoop(self, ctx:langParser.ForListLoopContext):
        pass


