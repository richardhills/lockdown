# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import functools
from time import time

from lockdown.executor.context import Context
from lockdown.executor.flow_control import FrameManager, \
    break_exception_to_string
from lockdown.executor.function import prepare
from lockdown.executor.opcodes import get_context_type
from lockdown.executor.raw_code_factories import function_lit, list_type, \
    int_type, infer_all, dereference, prepared_function, loop_op, condition_op, \
    binary_integer_op, comma_op, shift_op, no_value_type, assignment_op, \
    literal_op, addition_op, transform_op, list_template_op, inferred_type, \
    invoke_op, local_function, transform, reset_op, nop, map_op, \
    object_template_op, function_type, length_op, composite_type, \
    build_break_types, any_type, bottom_type, iter_micro_op, close_op, \
    prepare_op, context_op, bool_type
from lockdown.parser.parser import parse
from lockdown.type_system.core_types import NoValueType
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.managers import get_manager
from lockdown.type_system.universal_type import PythonObject, \
    DEFAULT_READONLY_COMPOSITE_TYPE, IterMicroOpType, UniversalObjectType, \
    RICH_READONLY_TYPE
from lockdown.utils.utils import NO_VALUE, print_code, MISSING, get_environment, \
    spread_dict


class ObjectDictWrapper(object):
    def __init__(self, data):
        for k, v in data.items():
            self.__dict__[k] = v

class BootstrapException(Exception):
    pass

@functools.lru_cache(maxsize=65536)
def get_default_global_context():
    with open("./lockdown/executor/builtins.lkdn") as builtins_file:
        frame_manager = FrameManager()
        with frame_manager.capture() as capture_preparation:
            builtins_code = builtins_file.read()
            builtins_data = parse(builtins_code)
            builtins_function = prepare(
                builtins_data,
                NO_VALUE, FrameManager(), None
            ).close(NO_VALUE)

        if capture_preparation.caught_break_mode is not None:
            raise_unhandled_break(capture_preparation.caught_break_mode, capture_preparation.value, None, capture_preparation.opcode, builtins_data)

        with frame_manager.capture("export") as capture_export:
            capture_export.attempt_capture_or_raise(
                *builtins_function.invoke(NO_VALUE, frame_manager, None)
            )

        if capture_export.caught_break_mode != "export":
            raise FatalError()

        return Context(
            UniversalObjectType({
                "static": RICH_READONLY_TYPE
            }),
            DEFAULT_READONLY_COMPOSITE_TYPE,
            static=capture_export.value
        )

def format_unhandled_break_type(break_type, raw_code):
    if not raw_code:
        return str(break_type) + " (no raw code)"

    out_break_type = break_type["out"]

    opcode = break_type["opcode"]
    if not opcode:
        return str(break_type) + " <!! break_type has no from_opcode !!>"

    start, _ = opcode.get_start_and_end()

    if start is None:
        return str(break_type) + " (no line and column)"

    lines = raw_code.split("\n")

    padding = " " * start["column"]

    return """
{}
{}^
{}| {}""".format(lines[start["line"] - 1], padding, padding, str(out_break_type))

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

    start, _ = opcode.get_start_and_end()

    if not start:
        return break_str + " (no line and column)"

    lines = raw_code.split("\n")

    padding = " " * start["column"]

    return """
{}
{}^
{}| {}""".format(lines[start["line"] - 1], padding, padding, break_str)

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
            None,
            immediate_context={
                "suggested_outer_type": get_context_type(outer_context)
            }
        )

        if check_safe_exit:
            raise_unhandled_break_types(open_function, data)

        closed_function = open_function.close(outer_context)

    if capture_preparation.caught_break_mode is not None:
        raise_unhandled_break(capture_preparation.caught_break_mode, capture_preparation.value, None, capture_preparation.opcode, data)

    with frame_manager.capture() as capture_result:
        if get_environment().transpile:
            closed_function = closed_function.transpile()

        capture_result.attempt_capture_or_raise(*closed_function.invoke(argument, frame_manager, None))

    return closed_function, capture_result
