# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import ast
from types import FunctionType, MethodType

from lockdown.type_system.exceptions import FatalError
from lockdown.utils import spread_dict, NO_VALUE


def extract_single_statement(module):
    return module.body[0]

def unwrap_expr(node):
    if isinstance(node, ast.Expr):
        return node.value
    if isinstance(node, ast.expr):
        return node
    raise FatalError()

def wrap_as_statement(node):
    if isinstance(node, ast.stmt):
        return node
    if isinstance(node, ast.expr):
        return ast.Expr(node)
    raise FatalError()

def unwrap_modules(nodes):
    resulting_nodes = []
    for n in nodes:
        if isinstance(n, ast.Module):
            resulting_nodes.extend(n.body)
        else:
            resulting_nodes.append(n)
    return resulting_nodes

def compile_module(code, context_name, dependency_builder, **subs):
    string_subs = {}
    ast_subs = {}

    subs["context_name"] = context_name

    for key, value in subs.items():
        if isinstance(value, (basestring, int)):
            string_subs[key] = value
        elif isinstance(value, ast.FunctionDef):
            string_subs[key] = dependency_builder.add(value)
        elif isinstance(value, (ast.stmt, ast.expr, ast.Module)):
            ast_key = "ast_{}".format(id(value))
            string_subs[key] = ast_key
            ast_subs[ast_key] = value
        else:
            string_subs[key] = dependency_builder.add(value)

    try:
        code = code.format(**string_subs)
    except KeyError:
        raise
    code = ast.parse(code)

    for key, sub_ast in ast_subs.items():
        code = ASTInliner(key, sub_ast, context_name, dependency_builder).visit(code)

    rough_check = ast.dump(code)
    for key in ast_subs.keys():
        if key in rough_check:
            print rough_check
            raise FatalError()

    return code

def compile_statement(code, context_name, dependency_builder, **subs):
    code = compile_module(code, context_name, dependency_builder, **subs)
    return extract_single_statement(code)

def compile_expression(code, context_name, dependency_builder, **subs):
    code = compile_statement(code, context_name, dependency_builder, **subs)
    return unwrap_expr(code)

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
#    print ast.dump(function_creator_ast)
    ast.fix_missing_locations(function_creator_ast)

#    print "--- {} ---".format(open_function_id)
#    print to_source(function_creator_ast)

    function_creator = compile(function_creator_ast, "<string>", "exec")

    function_creation_context = spread_dict(
        dependencies, default_globals()
    )

    exec(function_creator, function_creation_context, function_creation_context)

    return function_creation_context[open_function_id]

def default_globals():
    from lockdown.executor.flow_control import BreakException
    from lockdown.type_system.managers import get_manager
    from lockdown.type_system.universal_type import PythonObject
    return {
        "__builtins": None,
        "PythonObject": PythonObject,
        "BreakException": BreakException,
        "NoValue": NO_VALUE,
        "get_manager": get_manager
    }

def get_dependency_key(dependency):
    if isinstance(dependency, int):
        pass
    if isinstance(dependency, ast.FunctionDef):
        return dependency.name
    if isinstance(dependency, FunctionType):
        return "{}{}".format(dependency.__name__, id(dependency))
    elif isinstance(dependency, MethodType):
        return "{}{}{}".format(dependency.im_class.__name__, dependency.__name__, id(dependency))
    else:
        return "{}{}".format(type(dependency).__name__, id(dependency))

class DependencyBuilder(object):
    def __init__(self, initial_dependencies=None):
        self.dependencies = {}
        if initial_dependencies:
            self.dependencies.update(initial_dependencies)

    def add(self, dependency):
        key = get_dependency_key(dependency)
        if key not in self.dependencies:
            self.dependencies[key] = dependency
#        print "{} ===> {}".format(key, type(dependency).__name__)
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
def stmt_wrapper_{ast_id}({context_name}, _frame_manager):
    {ast}
    return ("value", NoValue, None, None)
                    """,
                    self.context_name, self.dependency_builder,
                    ast_id=id(self.replacement_ast),
                    ast=self.replacement_ast
                )
                return compile_expression(
                    "{new_function}({context_name}, _frame_manager)",
                    self.context_name, self.dependency_builder,
                    new_function=new_function
                )
        return self.generic_visit(node)
