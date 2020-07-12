import ast
from types import FunctionType, MethodType

from astor.code_gen import to_source

from rdhlang5.executor.flow_control import BreakException
from rdhlang5.type_system.exceptions import FatalError
from rdhlang5.type_system.object_types import RDHObject
from rdhlang5.utils import spread_dict, NO_VALUE


def extract_single_statement(module):
    return module.body[0]

def unwrap_expr(node):
    if isinstance(node, ast.Expr):
        return node.value
    if isinstance(node, ast.expr):
        return node
    raise FatalError()

def compile_module(code, context_name, dependency_builder, **subs):
    string_subs = {}
    ast_subs = {}

    subs["context_name"] = context_name

    for key, value in subs.items():
        if isinstance(value, (basestring, int)):
            string_subs[key] = value
        elif isinstance(value, ast.FunctionDef):
            string_subs[key] = dependency_builder.add(value)
        elif isinstance(value, (ast.stmt, ast.expr)):
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
    function_creator = compile(to_source(function_creator_ast), "<string>", "exec")

    function_creation_context = spread_dict(
        dependencies, default_globals()
    )

#    print "--- {} ---".format(open_function_id)
#    print to_source(function_creator_ast)

    exec(function_creator, function_creation_context, function_creation_context)

    return function_creation_context[open_function_id]

def default_globals():
    return {
        "__builtins": None,
        "RDHObject": RDHObject,
        "BreakException": BreakException,
        "NoValue": NO_VALUE
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
        if not isinstance(self.dependency_builder, DependencyBuilder):
            pass

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
