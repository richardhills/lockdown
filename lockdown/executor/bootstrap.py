# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import time

from lockdown.executor.flow_control import FrameManager, \
    break_exception_to_string
from lockdown.executor.function import prepare
from lockdown.executor.opcodes import get_context_type
from lockdown.executor.raw_code_factories import function_lit, list_type, \
    int_type, infer_all, dereference, prepared_function, loop_op, condition_op, \
    binary_integer_op, comma_op, shift_op, no_value_type, assignment_op, \
    literal_op, addition_op, transform_op, list_template_op, inferred_type, \
    invoke_op, local_function, transform, reset_op, nop, map_op, \
    object_template_op, function_type
from lockdown.type_system.managers import get_manager
from lockdown.type_system.universal_type import PythonObject, \
    DEFAULT_READONLY_COMPOSITE_TYPE
from lockdown.utils.utils import NO_VALUE, print_code, MISSING, get_environment


class ObjectDictWrapper(object):
    def __init__(self, data):
        for k, v in data.items():
            self.__dict__[k] = v

class BootstrapException(Exception):
    pass

def get_default_global_context():
    return PythonObject({
        "static": PythonObject({
            "any": PythonObject({
                "type": "Any"
            }, debug_reason="default-global-context"),
            "int": PythonObject({
                "type": "Integer"
            }, debug_reason="default-global-context"),
            "bool": PythonObject({
                "type": "Boolean"
            }, debug_reason="default-global-context"),
            "string": PythonObject({
                "type": "String"
            }, debug_reason="default-global-context"),
            "void": PythonObject({
                "type": "NoValue"
            }, debug_reason="default-global-context"),
            "var": PythonObject({
                "type": "Inferred"
            }, debug_reason="default-global-context"),
            "range": prepare(
                function_lit(
                    list_type([ int_type(), int_type() ], None),
                    infer_all(), int_type(), dereference("argument.0"),
                    prepared_function(
                        loop_op(
                            condition_op(
                                binary_integer_op("lt", dereference("outer.local"), dereference("outer.argument.1")),
                                comma_op(
                                    shift_op(dereference("outer.local"), no_value_type()),
                                    assignment_op(dereference("outer"), literal_op("local"), addition_op(dereference("outer.local"), literal_op(1)))
                                ),
                                transform_op("break")
                            )
                        )
                    )
                ),
                NO_VALUE, FrameManager()
            ).close(NO_VALUE),
            "list": prepare(
                function_lit(
                    list_type([
                        function_type(no_value_type(), {
                            "yield": list_template_op([ object_template_op({
                                "in": no_value_type(),
                                "out": int_type()
                            })]),
                            "value": list_template_op([ object_template_op({
                                "out": no_value_type()
                            })]),
                        }),
                    ], None),
                    infer_all(),
                    inferred_type(),
                    dereference("argument.0"),
                    loop_op(
                        invoke_op(
                            local_function(
                                transform(
                                    ("yield", "value"),
                                    ("value", "end"),
                                    reset_op(dereference("outer.local"), nop())
                                ),
                                comma_op(
                                    assignment_op(
                                        dereference("outer"),
                                        literal_op("local"),
                                        dereference("local.continuation")
                                    ),
                                    transform_op(
                                        "value",
                                        "continue",
                                        dereference("local.value")
                                    )
                                )
                            )
                        )
                    )
                ),
                NO_VALUE, FrameManager()
            ).close(NO_VALUE),
            "max": prepare(
                function_lit(
                    list_type([ int_type() ], int_type()),
                    infer_all(),
                    inferred_type(),
                    dereference("argument.0"),
                    comma_op(
                        map_op(
                            dereference("argument"),
                            prepared_function(
                                int_type(),
                                condition_op(
                                    binary_integer_op(
                                        "gt",
                                        dereference("argument"),
                                        dereference("outer.local")
                                    ),
                                    assignment_op(
                                        dereference("outer"),
                                        literal_op("local"),
                                        dereference("argument")
                                    ),
                                    nop()
                                )
                            )
                        ),
                        dereference("local")
                    )
                ),
                NO_VALUE, FrameManager()
            ).close(NO_VALUE),
        }, debug_reason="default-global-context")
    }, bind=DEFAULT_READONLY_COMPOSITE_TYPE, debug_reason="default-global-context")

def format_unhandled_break_type(break_type, raw_code):
    if not raw_code:
        return str(break_type) + " (no raw code)"

    out_break_type = break_type["out"]

    opcode = getattr(out_break_type, "from_opcode", None)
    if not opcode:
        return str(break_type) + " (break_type has no from_opcode)"

    line, column = opcode.get_line_and_column()

    if line is None or column is None:
        return str(break_type) + " (no line and column)"

    lines = raw_code.split("\n")

    padding = " " * column

    return """
{}
{}^
{}| {}""".format(lines[line - 1], padding, padding, str(out_break_type))

def raise_unhandled_break_types(open_function, data):
    function_break_types = open_function.get_type().break_types

    error_msgs = []

    for mode, break_types in function_break_types.items():
        if mode not in ("exit", "return", "value"):
            breaks_messages = [format_unhandled_break_type(break_type, getattr(data, "raw_code", None)) for break_type in break_types]
            for break_message in breaks_messages:
                error_msgs.append("""---- break mode {} is not safe ----

{}""".format(mode, break_message))
            continue

    if error_msgs:
        raise BootstrapException("\n\n".join(error_msgs))

def format_unhandled_break(mode, value, caused_by, opcode, data):
    raw_code = getattr(data, "raw_code", None)

    break_str = break_exception_to_string(mode, value, caused_by)

    if not raw_code:
        return break_str + " (no raw code)"

    if not opcode:
        return break_str + " (break_exception has no from_opcode)"

    line, column = opcode.get_line_and_column()

    if line is None or column is None:
        return break_str + " (no line and column)"

    lines = raw_code.split("\n")

    padding = " " * column

    return """
{}
{}^
{}| {}""".format(lines[line - 1], padding, padding, break_str)

def raise_unhandled_break(mode, value, caused_by, opcode, data):
    raise BootstrapException(format_unhandled_break(mode, value, caused_by, opcode, data))

def bootstrap_function(data, argument=None, outer_context=None, check_safe_exit=True, print_ast=False):
    if argument is None:
        argument = NO_VALUE
    if outer_context is None:
        outer_context = get_default_global_context()

    get_manager(outer_context).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)

    frame_manager = FrameManager()

    with frame_manager.capture() as capture_preparation:
        if print_ast:
            print_code(data)
        open_function = prepare(
            data,
            outer_context,
            frame_manager,
            immediate_context={
                "suggested_outer_type": get_context_type(outer_context)
            }
        )

        if check_safe_exit:
            raise_unhandled_break_types(open_function, data)

        closed_function = open_function.close(outer_context)

    if capture_preparation.caught_break_mode is not MISSING:
        raise_unhandled_break(capture_preparation.caught_break_mode, capture_preparation.value, None, capture_preparation.opcode, data)

    with frame_manager.capture() as capture_result:
        if get_environment().transpile:
            closed_function = closed_function.transpile()

        capture_result.attempt_capture_or_raise(*closed_function.invoke(argument, frame_manager))

    return closed_function, capture_result
