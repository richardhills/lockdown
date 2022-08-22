# -*- coding: utf-8 -*-
"""
Utility functions that make it easy to compile and manipulate Python
ast.* objects, in particular ast.stmt, ast.expr, ast.Module.

These utilities make it easier for Opcodes, Functions and MicroOps to transpile
themselves down to Python. They make it easy to write that Python code in a
template form, and to then declare hooks for so that the Python code can call
back into the interpretor when needed.
"""

from __future__ import unicode_literals

import ast
from types import FunctionType, MethodType

from astor.code_gen import to_source

from lockdown.type_system.exceptions import FatalError
from lockdown.utils.utils import spread_dict, NO_VALUE, get_environment


def compile_module(code, context_name, dependency_builder, **subs):
    """
    Compiles a string of Python code into Python ast.Module, including applying substitutions
    provided as kwargs. It is similar to the string.format function, except that
    the variable substitutions are also converted to AST before being injected into
    the resulting AST for the whole code block.
    """
    string_subs = {}
    ast_subs = {}

    subs["context_name"] = context_name

    for key, value in subs.items():
        if isinstance(value, (str, int)):
            string_subs[key] = value
        elif isinstance(value, ast.FunctionDef):
            string_subs[key] = dependency_builder.add(value)
        elif isinstance(value, (ast.stmt, ast.expr, ast.Module)):
            # For a { key } in our code template, we substitute a unique string
            # similar to "ast_1234". This comes through the parsing step in the
            # resulting ast as a ast.Name node. We later scan the ast for these
            # nodes and replace them with the ast for the original substitution. 
            ast_key = "ast_{}".format(id(value))
            string_subs[key] = ast_key
            ast_subs[ast_key] = value
        else:
            string_subs[key] = dependency_builder.add(value)
    code = code.format(**string_subs)
    code = ast.parse(code)

    for key, sub_ast in ast_subs.items():
        # For each ast_1234 ast.Name node, we now replace with the substitute ast
        code = ASTInliner(key, sub_ast, context_name, dependency_builder).visit(code)

    return code

def compile_statement(code, context_name, dependency_builder, **subs):
    # Compile to a module first, then extract the only statement
    code = compile_module(code, context_name, dependency_builder, **subs)
    return extract_single_statement(code)

def extract_single_statement(module):
    return module.body[0]

def compile_expression(code, context_name, dependency_builder, **subs):
    # Compile to a module, then extract a statement, then extract as a expression,
    # throwing an exception if it's not possible
    code = compile_statement(code, context_name, dependency_builder, **subs)
    return unwrap_expr(code)

def wrap_as_statement(node):
    """
    Python ast treats statements and expressions differently. Always returns a ast.stmt
    object, even if passed an ast.expr.
    """
    if isinstance(node, ast.stmt):
        return node
    if isinstance(node, ast.expr):
        return ast.Expr(node)
    raise FatalError()

def unwrap_expr(node):
    """
    Returns an ast.expr from a statement, but throws an exception if the statement
    can not be converted to an expression.
    """
    if isinstance(node, ast.Expr):
        return node.value
    if isinstance(node, ast.expr):
        return node
    raise FatalError()

def unwrap_modules(nodes):
    """
    Returns an array of ast.stmt objects, expanding out the ast.Module objects to
    extract their ast.stmt objects too.
    """
    resulting_nodes = []
    for n in nodes:
        if isinstance(n, ast.Module):
            resulting_nodes.extend(n.body)
        else:
            resulting_nodes.append(n)
    return resulting_nodes

def compile_function(code, context_name, initial_dependencies=None, **subs):
    dependency_builder = DependencyBuilder(initial_dependencies)
    function_def = compile_statement(code, context_name, dependency_builder, **subs)
    return compile_ast_function_def(function_def, dependency_builder.build())

def build_and_compile_ast_function(name, arguments, body, dependencies):
    return compile_ast_function_def(
        ast.FunctionDef(
            name=name,
            args=ast.arguments(
                args=[
                    ast.Name(id=a, ctx=ast.Load()) for a in arguments
                ],
                vararg=None,
                kwarg=None,
                defaults=[]
            ),
            body=body,
            decorator_list=[]
        ),
        dependencies
    )

def compile_ast_function_def(function_creator_ast, open_function_id, dependencies):
    ast.fix_missing_locations(function_creator_ast)

    if get_environment().output_transpiled_code:
        print("--- {} ---".format(open_function_id))
        print(to_source(function_creator_ast))

    function_creator = compile(function_creator_ast, "<string>", "exec")

    function_creation_context = spread_dict(
        dependencies, default_globals()
    )

    exec(function_creator, function_creation_context, function_creation_context)

    return function_creation_context[open_function_id]

def default_globals():
    from lockdown.executor.function import LockdownFunction, ClosedFunctionType
    from lockdown.executor.flow_control import BreakException
    from lockdown.type_system.managers import get_manager
    from lockdown.type_system.universal_type import PythonObject
    from lockdown.type_system.universal_type import CALCULATE_INITIAL_LENGTH, \
        Universal
    from lockdown.type_system.composites import bind_key, unbind_key
    from lockdown.type_system.composites import scoped_bind
    from lockdown.executor.context import Context

    return {
        "__builtins": None,
        "PythonObject": PythonObject,
        "Universal": Universal,
        "Context": Context,
        "BreakException": BreakException,
        "NoValue": NO_VALUE,
        "get_manager": get_manager,
        "get_environment": get_environment,
        "CALCULATE_INITIAL_LENGTH": CALCULATE_INITIAL_LENGTH,
        "scoped_bind": scoped_bind,
        "bind_key": bind_key,
        "unbind_key": unbind_key,
        "FatalError": FatalError,
        "LockdownFunction": LockdownFunction,
        "ClosedFunctionType": ClosedFunctionType,
    }

def get_dependency_key(dependency):
    if isinstance(dependency, ast.FunctionDef):
        return dependency.name
    if isinstance(dependency, FunctionType):
        return "{}_{}_{}".format(dependency.__name__, id(dependency))
    elif isinstance(dependency, MethodType):
        return "{}{}".format(dependency.__name__, id(dependency))
    else:
        return "{}{}".format(type(dependency).__name__, id(dependency))

class DependencyBuilder(object):
    def __init__(self, initial_dependencies=None):
        self.dependencies = {}
        if initial_dependencies:
            self.dependencies.update(initial_dependencies)
        self.counter = 0

    def get_next_id(self):
        self.counter = self.counter + 1
        return self.counter

    def add(self, dependency):
        key = get_dependency_key(dependency)
        if key not in self.dependencies:
            self.dependencies[key] = dependency
        return key

    def replace(self, key, replacement):
        self.dependencies[key] = replacement

    def build(self):
        return dict(self.dependencies)

class ASTInliner(ast.NodeTransformer):
    def __init__(self, name, replacement_ast, context_name, dependency_builder):
        self.name = name
        self.replacement_ast = replacement_ast
        self.context_name = context_name
        self.dependency_builder = dependency_builder
#        print "Replacing {} => {}".format(self.name, ast.dump(self.replacement_ast))

    def create_new_statements(self, statements):
        if not isinstance(self.replacement_ast, ast.Module):
            return None

        new_body = []
        is_different = False
        for child in statements:
            if isinstance(child, ast.Expr) and isinstance(child.value, ast.Name) and child.value.id == self.name:
                new_body.extend(self.replacement_ast.body)
                is_different = True
            else:
                new_body.append(child)

        if is_different:
            return new_body

    def visit_Module(self, node):
        new_body = self.create_new_statements(node.body)
        if new_body:
            return ast.Module(body=new_body or node.body)
        return self.generic_visit(node)

    def visit_While(self, node):
        new_body = self.create_new_statements(node.body)
        new_orelse = self.create_new_statements(node.orelse)
        if new_body or new_orelse:
            return ast.While(test=node.test, body=new_body or node.body, orelse=new_orelse or node.orelse)
        return self.generic_visit(node)

    def visit_If(self, node):
        new_body = self.create_new_statements(node.body)
        new_orelse = self.create_new_statements(node.orelse)
        if new_body:
            return ast.If(test=node.test, body=new_body or node.body, orelse=new_orelse or node.orelse)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        new_body = self.create_new_statements(node.body)
        if new_body:
            return ast.FunctionDef(name=node.name, args=node.args, body=new_body, decorator_list=node.decorator_list)
        return self.generic_visit(node)

    def visit_Expr(self, node):
        if isinstance(self.replacement_ast, ast.stmt) and isinstance(node.value, ast.Name) and node.value.id == self.name:
            return self.replacement_ast
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == self.name:
            if isinstance(self.replacement_ast, ast.expr):
                return self.replacement_ast
            else:
                new_function = compile_statement("""
def stmt_wrapper_{ast_id}({context_name}, _frame_manager, _hooks):
    {ast}
    return ("value", NoValue, None, None)
                    """,
                    self.context_name, self.dependency_builder,
                    ast_id=self.dependency_builder.get_next_id(),
                    ast=self.replacement_ast
                )
                return compile_expression(
                    "{new_function}({context_name}, _frame_manager, _hooks)",
                    self.context_name, self.dependency_builder,
                    new_function=new_function
                )
        return self.generic_visit(node)
