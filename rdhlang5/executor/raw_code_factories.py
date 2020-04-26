from rdhlang5.utils import spread_dict
from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE
from rdhlang5_types.dict_types import RDHDict
from rdhlang5_types.exceptions import FatalError
from rdhlang5_types.list_types import RDHList
from rdhlang5_types.object_types import RDHObject, RDHObjectType


def check_is_opcode(data):
    if not isinstance(data, RDHObject):
        raise FatalError()
    if not "opcode" in data.__dict__:
        raise FatalError

def type_lit(name):
    return literal_op(RDHObject({
        "type": name
    }))

def unit_type(value):
    return object_template_op({
        "type": literal_op("Unit"),
        "value": literal_op(value)
    })

def object_type(properties):
    return object_template_op({
        "type": literal_op("Object"),
        "properties": object_template_op(properties)
    })

def function_type(argument_type, break_types):
    if not isinstance(break_types, dict):
        raise FatalError()
    return object_template_op({
        "type": literal_op("Function"),
        "argument": argument_type,
        "break_types": dict_template_op(break_types)
    })

def build_break_types(return_type=None, exception_type=None, yield_types=None, value_type=None):
    break_types = {}

    if return_type:
        break_types["return"] = list_template_op([ dict_template_op({ "out": return_type }) ])
    if yield_types:
        break_types["yield"] = list_template_op([ dict_template_op(yield_types) ])
    if exception_type:
        break_types["exception"] = list_template_op([ dict_template_op({ "out": exception_type }) ])
    if value_type:
        break_types["value"] = list_template_op([ dict_template_op({ "out": value_type }) ])

    return break_types

def infer_all():
    return {
        "wildcard": list_template_op([ dict_template_op({ "out": inferred_type, "in": inferred_type }) ])
    }

def function_lit(*args):
    if len(args) == 1:
        code, = args
        argument_type = local_type = no_value_type
        break_types = infer_all()
        local_initializer = nop
    elif len(args) == 2:
        argument_type, code = args
        local_type = no_value_type
        break_types = infer_all()
        local_initializer = nop
    elif len(args) == 3:
        argument_type, break_types, code = args
        local_type = no_value_type
        local_initializer = nop
    elif len(args) == 5:
        argument_type, break_types, local_type, local_initializer, code = args
    else:
        raise FatalError()

    check_is_opcode(local_initializer)
    check_is_opcode(argument_type)
    check_is_opcode(local_type)
    if not isinstance(break_types, dict):
        raise FatalError()

    static = {
        "argument": argument_type,
        "local": local_type,
        "break_types": object_template_op(break_types)
    }

    func = {
        "code": code,
        "static": object_template_op(static),
        "local_initializer": local_initializer
    }

    return RDHObject(func)

def literal_op(value):
    return RDHObject({
        "opcode": "literal",
        "value": value
    })

def object_template_op(values):
    for v in values.values():
        check_is_opcode(v)
    return RDHObject({
        "opcode": "object_template",
        "opcodes": RDHDict(values)
    })

def dict_template_op(values):
    for v in values.values():
        check_is_opcode(v)
    return RDHObject({
        "opcode": "dict_template",
        "opcodes": RDHDict(values)
    })

def list_template_op(values):
    for v in values:
        check_is_opcode(v)
    return RDHObject({
        "opcode": "list_template",
        "opcodes": RDHList(values)
    })

def binary_integer_op(name, lvalue, rvalue):
    check_is_opcode(lvalue)
    check_is_opcode(rvalue)
    return RDHObject({
        "opcode": name,
        "lvalue": lvalue,
        "rvalue": rvalue
    })

def addition_op(lvalue, rvalue):
    return binary_integer_op("addition", lvalue, rvalue)

def equality_op(lvalue, rvalue):
    return binary_integer_op("equality", lvalue, rvalue)

def comma_op(*opcodes):
    for v in opcodes:
        check_is_opcode(v)
    return RDHObject({
        "opcode": "comma",
        "opcodes": RDHList(opcodes)
    })

def loop_op(opcode):
    check_is_opcode(opcode)
    return RDHObject({
        "opcode": "loop",
        "code": opcode
    })

def return_op(code):
    check_is_opcode(code)
    return RDHObject({
        "opcode": "transform",
        "output": "return",
        "input": "value",
        "code": code
    })

def yield_op(code, restart_type):
    check_is_opcode(code)
    check_is_opcode(restart_type)
    return RDHObject({
        "opcode": "transform",
        "output": "yield",
        "input": "value",
        "restart": "value",
        "restart_type": restart_type,
        "code": code
    })

def context_op():
    return RDHObject({
        "opcode": "context",
    })

def dereference_op(of, reference):
    check_is_opcode(of)
    check_is_opcode(reference)
    return RDHObject({
        "opcode": "dereference",
        "of": of,
        "reference": reference
    })

def assignment_op(of, reference, rvalue):
    check_is_opcode(of)
    check_is_opcode(reference)
    check_is_opcode(rvalue)
    return RDHObject({
        "opcode": "assignment",
        "of": of,
        "reference": reference,
        "rvalue": rvalue
    })

def condition_op(condition, when_true, when_false):
    check_is_opcode(condition)
    check_is_opcode(when_true)
    check_is_opcode(when_false)
    return RDHObject({
        "opcode": "conditional",
        "condition": condition,
        "when_true": when_true,
        "when_false": when_false
    })

def prepare_op(function_expression):
    check_is_opcode(function_expression)
    return RDHObject({
        "opcode": "prepare",
        "code": function_expression
    })

def invoke_op(function_expression, argument_expression=None):
    if argument_expression is None:
        argument_expression = nop
    check_is_opcode(function_expression)
    check_is_opcode(argument_expression)
    return RDHObject({
        "opcode": "invoke",
        "function": function_expression,
        "argument": argument_expression
    })

def match_op(value_expression, matchers):
    check_is_opcode(value_expression)
    for matcher in matchers:
        check_is_opcode(matcher)
    return RDHObject({
        "opcode": "match",
        "value": value_expression,
        "matchers": RDHList(matchers)
    })


nop = RDHObject({ "opcode": "nop" })
no_value_type = type_lit("NoValue")
inferred_type = type_lit("Inferred")
any_type = type_lit("Any")
int_type = type_lit("Integer")
bool_type = type_lit("Boolean")

def unbound_dereference(name):
    return RDHObject({
        "opcode": "unbound_dereference",
        "reference": name
    })

def prepared_function(*args):
    return prepare_op(literal_op(function_lit(*args)))

def dereference(*vars):
    result = context_op()

    for var in vars:
        if isinstance(var, str):
            for v in var.split("."):
                result = dereference_op(result, literal_op(v))
        if isinstance(var, list):
            for v in var:
                result = dereference_op(result, literal_op(v))

    return result
