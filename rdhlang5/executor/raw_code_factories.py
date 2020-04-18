from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE
from rdhlang5_types.dict_types import RDHDict
from rdhlang5_types.exceptions import FatalError
from rdhlang5_types.list_types import RDHList
from rdhlang5_types.object_types import RDHObject
from rdhlang5.utils import spread_dict


def check_is_opcode(data):
    if not hasattr(data, "opcode"):
        raise FatalError

def type_lit(name):
    return literal_op(RDHObject({
        "type": name
    }))

def build_break_types(return_type, exception_type=None, yield_types=None):
    break_types = {
        "return": list_template_op([ object_template_op({ "out": return_type }) ])
    }
    if yield_types:
        break_types["yield"] = list_template_op([ object_template_op(yield_types) ])
    if exception_type:
        break_types["exception"] = list_template_op([ object_template_op({ "out": exception_type }) ])

    return break_types

def function_lit(argument_type, break_types, code):
    check_is_opcode(argument_type)

    return RDHObject({
        "code": code,
        "static": object_template_op({
            "argument": argument_type,
            "break_types": object_template_op(break_types)
        })
    }, bind=DEFAULT_OBJECT_TYPE)

def literal_op(value):
    return RDHObject({
        "opcode": "literal",
        "value": value
    }, bind=DEFAULT_OBJECT_TYPE)

def object_template_op(values):
    for v in values.values():
        check_is_opcode(v)
    return RDHObject({
        "opcode": "object_template",
        "opcodes": RDHDict(values)
    }, bind=DEFAULT_OBJECT_TYPE)

def list_template_op(values):
    for v in values:
        check_is_opcode(v)
    return RDHObject({
        "opcode": "list_template",
        "opcodes": RDHList(values)
    }, bind=DEFAULT_OBJECT_TYPE)

def addition_op(lvalue, rvalue):
    check_is_opcode(lvalue)
    check_is_opcode(rvalue)
    return RDHObject({
        "opcode": "addition",
        "lvalue": lvalue,
        "rvalue": rvalue
    }, bind=DEFAULT_OBJECT_TYPE)

def comma_op(*opcodes):
    for v in opcodes:
        check_is_opcode(v)
    return RDHObject({
        "opcode": "comma",
        "opcodes": RDHList(opcodes)
    }, bind=DEFAULT_OBJECT_TYPE)

def return_op(code):
    check_is_opcode(code)
    return RDHObject({
        "opcode": "transform",
        "output": "return",
        "input": "value",
        "code": code
    }, bind=DEFAULT_OBJECT_TYPE)

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
    }, bind=DEFAULT_OBJECT_TYPE)

def context_op():
    return RDHObject({
        "opcode": "context",
    }, bind=DEFAULT_OBJECT_TYPE)

def dereference_op(of, reference):
    check_is_opcode(of)
    check_is_opcode(reference)
    return RDHObject({
        "opcode": "dereference",
        "of": of,
        "reference": reference
    }, bind=DEFAULT_OBJECT_TYPE)

no_value_type = type_lit("NoValue")
any_type = type_lit("Any")
int_type = type_lit("Integer")
