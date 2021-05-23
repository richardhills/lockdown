# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.universal_type import PythonObject, PythonList
from lockdown.utils import spread_dict


def is_opcode(data):
    if not isinstance(data, (PythonObject, PythonObject)):
        raise FatalError()
    return data._contains("opcode")

def check_is_opcode(data):
    if not is_opcode(data):
        raise FatalError()


def type_lit(name):
    return object_template_op({
        "type": literal_op(name)
    }, debug_reason="type-literal")


def unit_type(value):
    return object_template_op({
        "type": literal_op("Unit"),
        "value": literal_op(value)
    }, debug_reason="type-literal")


def one_of_type(types):
    return object_template_op({
        "type": literal_op("OneOf"),
        "types": list_template_op(types)
    }, debug_reason="type-literal")


def object_type(properties, wildcard_type=None):
    type = {
        "type": literal_op("Object"),
        "properties": object_template_op(properties),
    }
    if wildcard_type:
        type["wildcard_type"] = wildcard_type
    return object_template_op(type, debug_reason="type-literal")


def list_type(entry_types, wildcard_type):
    type = {
        "type": literal_op("List"),
        "entry_types": list_template_op(entry_types)
    }
    if wildcard_type:
        type["wildcard_type"] = wildcard_type
    return object_template_op(type, debug_reason="type-literal")


def composite_type(micro_ops):
    return object_template_op({
        "type": literal_op("Universal"),
        "micro_ops": list_template_op(micro_ops)
    })


def function_type(argument_type, break_types):
    if not isinstance(break_types, dict):
        raise FatalError()
    return object_template_op({
        "type": literal_op("Function"),
        "argument": argument_type,
        "break_types": object_template_op(break_types)
    }, debug_reason="type-literal")


def build_break_types(return_type=None, exception_type=None, yield_types=None, value_type=None):
    break_types = {}

    if return_type:
        break_types["return"] = list_template_op([ object_template_op({ "out": return_type }) ])
    if yield_types:
        break_types["yield"] = list_template_op([ object_template_op(yield_types) ])
    if exception_type:
        break_types["exception"] = list_template_op([ object_template_op({ "out": exception_type }) ])
    if value_type:
        break_types["value"] = list_template_op([ object_template_op({ "out": value_type }) ])

    return break_types


def infer_all():
    return {
        "wildcard": list_template_op([
            object_template_op({
                "out": inferred_type(),
                "in": inferred_type()
            }) ])
    }


def function_lit(*args, **kwargs):
    if len(args) == 1:
        extra_statics = {}
        code, = args
        argument_type = local_type = no_value_type()
        break_types = infer_all()
        local_initializer = nop()
    elif len(args) == 2:
        extra_statics = {}
        argument_type, code = args
        local_type = no_value_type()
        break_types = infer_all()
        local_initializer = nop()
    elif len(args) == 3:
        extra_statics = {}
        argument_type, break_types, code = args
        local_type = no_value_type()
        local_initializer = nop()
    elif len(args) == 5:
        extra_statics = {}
        argument_type, break_types, local_type, local_initializer, code = args
    elif len(args) == 6:
        extra_statics, argument_type, break_types, local_type, local_initializer, code = args
    else:
        raise FatalError()

    check_is_opcode(local_initializer)
    check_is_opcode(argument_type)
    check_is_opcode(local_type)
    check_is_opcode(code)
    if not isinstance(break_types, dict):
        raise FatalError()

    static = spread_dict({
        "argument": argument_type,
        "local": local_type,
        "outer": inferred_type(),
        "break_types": object_template_op(break_types)
    }, extra_statics)

    func = spread_dict({
        "code": code,
        "static": object_template_op(static),
        "local_initializer": local_initializer
    }, **kwargs)

    return PythonObject(func)


def literal_op(value):
    return PythonObject({
        "opcode": "literal",
        "value": value
    }, debug_reason="code")

def print_op(expression):
    return PythonObject({
        "opcode": "print",
        "expression": expression
    }, debug_reason="code")

def object_template_op(values, debug_reason="code", **kwargs):
    values_list = []

    for k, v in values.items():
        check_is_opcode(v)
        if isinstance(k, basestring):
            k = literal_op(k)

        values_list.append(PythonList([ k, v ]))

    return PythonObject(spread_dict({
        "opcode": "template",
        "opcodes": PythonList(values_list, debug_reason=debug_reason)
    }, **kwargs), debug_reason=debug_reason)


def list_template_op(values):
    for v in values:
        check_is_opcode(v)
    return PythonObject({
        "opcode": "template",
        "opcodes": PythonList([
            PythonList([ literal_op(i), v ]) for i, v in enumerate(values)
        ])
    }, debug_reason="code")


def binary_integer_op(name, lvalue, rvalue):
    check_is_opcode(lvalue)
    check_is_opcode(rvalue)
    return PythonObject({
        "opcode": name,
        "lvalue": lvalue,
        "rvalue": rvalue
    }, debug_reason="code")


def multiplication_op(lvalue, rvalue):
    return binary_integer_op("multiplication", lvalue, rvalue)


def division_op(lvalue, rvalue):
    return binary_integer_op("division", lvalue, rvalue)


def addition_op(lvalue, rvalue):
    return binary_integer_op("addition", lvalue, rvalue)


def subtraction_op(lvalue, rvalue):
    return binary_integer_op("subtraction", lvalue, rvalue)


def equality_op(lvalue, rvalue):
    return binary_integer_op("eq", lvalue, rvalue)


def comma_op(*opcodes):
    for v in opcodes:
        check_is_opcode(v)
    return PythonObject({
        "opcode": "comma",
        "opcodes": PythonList(opcodes)
    }, debug_reason="code")


def loop_op(opcode, **kwargs):
    check_is_opcode(opcode)
    return PythonObject(spread_dict({
        "opcode": "loop",
        "code": opcode
    }, **kwargs), debug_reason="code")


def transform(*args, **kwargs):
    transforms = args[:-1]
    code = args[-1]
    for input, output in reversed(transforms):
        code = transform_op(input, output, code, **kwargs)
    return code


def transform_op(*args, **kwargs):
    if len(args) == 1:
        output, = args
        input = code = None
    elif len(args) == 3:
        input, output, code = args
    else:
        raise FatalError()
    if code:
        check_is_opcode(code)
    if input and not isinstance(input, basestring):
        raise FatalError()
    if not isinstance(output, basestring):
        raise FatalError()
    op = {
        "opcode": "transform",
        "output": output,
    }
    if input:
        op["input"] = input
        op["code"] = code
    return PythonObject(spread_dict(op, **kwargs), debug_reason="code")


def shift_op(code, restart_type, **kwargs):
    check_is_opcode(code)
    check_is_opcode(restart_type)
    return PythonObject(spread_dict({
        "opcode": "shift",
        "code": code,
        "restart_type": restart_type
    }, **kwargs), debug_reason="code")


def reset_op(*args, **kwargs):
    if len(args) == 1:
        code, = args
        function = argument = None
        check_is_opcode(code)
    if len(args) == 2:
        code = None
        function, argument = args
        check_is_opcode(function)
        check_is_opcode(argument)

    result = {
        "opcode": "reset"
    }

    if code:
        result["code"] = code
    if function and argument:
        result["function"] = function
        result["argument"] = argument

    return PythonObject(spread_dict(result, **kwargs), debug_reason="code")


def return_op(code):
    return transform_op("value", "return", code)


def break_op(break_mode):
    return transform_op(break_mode)


def try_catch_op(try_opcode, catch_function, finally_opcode=None):
    check_is_opcode(try_opcode)
    if not finally_opcode:
        finally_opcode = nop()
    check_is_opcode(finally_opcode)
    return comma_op(
        transform_op(
            "success", "value",
            invoke_op(
                prepared_function(
                    inferred_type(),
                    match_op(
                        dereference("argument"), [
                            catch_function,
                            prepared_function(
                                inferred_type(),
                                throw_op(dereference("argument"))
                            )
                        ]
                    )
                ),
                transform_op(
                    "exception", "value",
                    transform_op(
                        "value", "success",
                        try_opcode
                    )
                )
            )
        ),
        finally_opcode
    )


def throw_op(code):
    return transform_op("value", "exception", code)


def continue_op(code):
    return transform_op("value", "continue", code)


def context_op(**kwargs):
    return PythonObject(spread_dict({
        "opcode": "context",
    }, **kwargs), debug_reason="code")


def is_op(expression, type, **kwargs):
    check_is_opcode(expression)
    check_is_opcode(type)
    return PythonObject(spread_dict({
        "opcode": "is",
        "expression": expression,
        "type": type
    }, **kwargs), debug_reason="code")


def dereference_op(of, reference, safe, **kwargs):
    check_is_opcode(of)
    check_is_opcode(reference)
    return PythonObject(spread_dict({
        "opcode": "dereference",
        "of": of,
        "reference": reference,
        "safe": safe
    }, **kwargs), debug_reason="code")


def dynamic_dereference_op(reference, **kwargs):
    if not isinstance(reference, basestring):
        raise FatalError()
    return PythonObject(spread_dict({
        "opcode": "dynamic_dereference",
        "reference": reference
    }, **kwargs), debug_reason="code")


def assignment_op(of, reference, rvalue, **kwargs):
    check_is_opcode(of)
    check_is_opcode(reference)
    check_is_opcode(rvalue)
    return PythonObject(spread_dict({
        "opcode": "assignment",
        "of": of,
        "reference": reference,
        "rvalue": rvalue
    }, **kwargs), debug_reason="code")


def insert_op(of, reference, rvalue):
    check_is_opcode(of)
    check_is_opcode(reference)
    check_is_opcode(rvalue)
    return PythonObject({
        "opcode": "insert",
        "of": of,
        "reference": reference,
        "rvalue": rvalue
    }, debug_reason="code")


def map_op(composite, mapper):
    check_is_opcode(composite)
    check_is_opcode(mapper)
    return PythonObject({
        "opcode": "map",
        "composite": composite,
        "mapper": mapper
    }, debug_reason="code")


def condition_op(condition, when_true, when_false):
    check_is_opcode(condition)
    check_is_opcode(when_true)
    check_is_opcode(when_false)
    return PythonObject({
        "opcode": "conditional",
        "condition": condition,
        "when_true": when_true,
        "when_false": when_false
    }, debug_reason="code")


def prepare_op(function_expression, **kwargs):
    check_is_opcode(function_expression)
    return PythonObject(spread_dict({
        "opcode": "prepare",
        "code": function_expression
    }, **kwargs), debug_reason="code")


def close_op(function, context, **kwargs):
    check_is_opcode(function)
    check_is_opcode(context)
    return PythonObject(spread_dict({
        "opcode": "close",
        "function": function,
        "outer_context": context
    }, **kwargs), debug_reason="code")


def static_op(expression, **kwargs):
    check_is_opcode(expression)
    return PythonObject(spread_dict({
        "opcode": "static",
        "code": expression
    }, **kwargs), debug_reason="code")


def invoke_op(function_expression, argument_expression=None, **kwargs):
    if "line" not in kwargs:
        pass
    if argument_expression is None:
        argument_expression = nop()
    check_is_opcode(function_expression)
    check_is_opcode(argument_expression)
    return PythonObject(spread_dict({
        "opcode": "invoke",
        "function": function_expression,
        "argument": argument_expression
    }, kwargs), debug_reason="code")


def match_op(value_expression, matchers):
    check_is_opcode(value_expression)
    for matcher in matchers:
        check_is_opcode(matcher)
    return PythonObject({
        "opcode": "match",
        "value": value_expression,
        "matchers": PythonList(matchers)
    }, debug_reason="code")


def nop():
    return PythonObject({ "opcode": "nop" }, debug_reason="code")


def no_value_type():
    return type_lit("NoValue")


def inferred_type():
    return type_lit("Inferred")


def any_type():
    return type_lit("Any")


def int_type():
    return type_lit("Integer")


def bool_type():
    return type_lit("Boolean")


def string_type():
    return type_lit("String")


def combine_opcodes(opcodes):
    flattened_opcodes = []
    for opcode in opcodes:
        check_is_opcode(opcode)
    for opcode in opcodes:
        if opcode._get("opcode") == "comma":
            flattened_opcodes.extend(opcode.opcodes)
        else:
            flattened_opcodes.append(opcode)
    if len(flattened_opcodes) == 0:
        return nop()
    if len(flattened_opcodes) == 1:
        return opcodes[0]
    if len(flattened_opcodes) > 1:
        return comma_op(*flattened_opcodes)


def const_string_type():
    # TODO make neater
    return literal_op(PythonObject({
        "type": "String",
        "const": True
    }, debug_reason="type-literal"))


def unbound_dereference(name, **kwargs):
    if not isinstance(name, basestring):
        raise FatalError()
    return PythonObject(spread_dict({
        "opcode": "unbound_dereference",
        "reference": name
    }, **kwargs), debug_reason="code")


def unbound_assignment(name, rvalue):
    if not isinstance(name, basestring):
        raise FatalError()
    check_is_opcode(rvalue)
    return PythonObject({
        "opcode": "unbound_assignment",
        "reference": name,
        "rvalue": rvalue
    }, debug_reason="code")


def prepare_function_lit(function_lit, **kwargs):
    return close_op(static_op(prepare_op(literal_op(function_lit), **kwargs), **kwargs), context_op(**kwargs), **kwargs)


def prepared_function(*args, **kwargs):
    return prepare_function_lit(function_lit(*args, **kwargs), **kwargs)


def local_function(local_initializer, code, **kwargs):
    return prepared_function(
        no_value_type(),
        infer_all(),
        inferred_type(),
        local_initializer,
        code,
        **kwargs
    )


def munge_ints(v):
    if v.isdigit():
        return int(v)
    return v


def dereference(*vars, **kwargs):
    result = context_op()

    for var in vars:
        if isinstance(var, basestring):
            for v in var.split("."):
                result = dereference_op(result, literal_op(munge_ints(v)), True, **kwargs)
        elif isinstance(var, int):
            result = dereference_op(result, literal_op(var), True, **kwargs)
        elif isinstance(var, list):
            for v in var:
                result = dereference_op(result, literal_op(munge_ints(v)), True, **kwargs)
        else:
            raise FatalError(var)

    return result
