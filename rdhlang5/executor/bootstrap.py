# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from _collections import defaultdict

from munch import munchify
from pip._vendor.contextlib2 import ExitStack

from rdhlang5.executor.flow_control import FrameManager, FlowManager, \
    BreakException
from rdhlang5.executor.function import prepare
from rdhlang5.executor.opcodes import get_context_type
from rdhlang5.executor.raw_code_factories import inferred_type, function_lit, \
    int_type, infer_all, dereference, loop_op, comma_op, condition_op, \
    equality_op, binary_integer_op, nop, return_op, yield_op, list_type, \
    function_type, list_template_op, insert_op, transform_op, literal_op, \
    invoke_op, object_template_op, prepared_function, no_value_type, \
    assignment_op, dict_template_op, addition_op, context_op, reset_op, shift_op
from rdhlang5.type_system.core_types import AnyType
from rdhlang5.type_system.default_composite_types import DEFAULT_OBJECT_TYPE
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.object_types import RDHObject
from rdhlang5.utils import NO_VALUE


class ObjectDictWrapper(object):
    def __init__(self, data):
        for k, v in data.items():
            self.__dict__[k] = v


def create_no_escape_flow_manager():
    frame_manager = FrameManager()
    return FlowManager(None, None, {}, frame_manager)


def create_application_flow_manager():
    frame_manager = FrameManager()
    return FlowManager("exit", { "out": AnyType()}, {}, frame_manager, top_level=True)

class BootstrapException(Exception):
    pass

def get_default_global_context():
    return RDHObject({
        "static": RDHObject({
            "int": RDHObject({
                "type": "Integer"
            }, debug_reason="default-global-context"),
            "var": RDHObject({
                "type": "Inferred"
            }, debug_reason="default-global-context"),
            "range": prepare(
                function_lit(
                    list_type([ int_type(), int_type() ], None),
                    infer_all(), int_type(), dereference("argument.0"),
                    prepared_function(
                        transform_op("return", "value",
                            loop_op(
                                condition_op(binary_integer_op("lt", dereference("outer.local"), dereference("outer.argument.1")),
                                    comma_op(
                                        shift_op(dereference("outer.local"), no_value_type()),
                                        assignment_op(dereference("outer"), literal_op("local"), addition_op(dereference("outer.local"), literal_op(1)))
                                    ),
                                    transform_op("return")
                                )
                            )
                        )
                    )
                ),
                None, create_no_escape_flow_manager()
            ).close(None),
            "list": prepare(
                function_lit(
                    function_type(no_value_type(), {
                        "yield": list_template_op([ dict_template_op({
                            "in": no_value_type(),
                            "out": int_type()
                        })]),
                        "value": list_template_op([ dict_template_op({
                            "out": no_value_type()
                        })]),
                    }),
                    infer_all(),
                    inferred_type(),
                    object_template_op({
                        "result": list_template_op([]),
                        "callback": dereference("argument")
                    }),
                    comma_op(
                        loop_op(
                            invoke_op(
                                prepared_function(
                                    no_value_type(),
                                    infer_all(),
                                    inferred_type(),
                                    reset_op(
                                        invoke_op(dereference("outer.local.callback")),
                                    ),
                                    comma_op(
                                        insert_op(
                                            dereference("outer.local.result"),
                                            literal_op(0),
                                            dereference("local.value")
                                        ),
                                        assignment_op(
                                            dereference("outer.local"),
                                            literal_op("callback"),
                                            dereference("local.continuation")
                                        )
                                    )
                                )
                            )
                        ),
                        dereference("local.result")
                    )
                ),
                None, create_no_escape_flow_manager()
            ).close(None)
        }, debug_reason="default-global-context")
    }, bind=DEFAULT_OBJECT_TYPE, debug_reason="default-global-context")

def format_unhandled_break_type(break_type, raw_code):
    if not raw_code:
        return str(break_type)

    out_break_type = break_type["out"]

    opcode = getattr(out_break_type, "from_opcode", None)
    if not opcode:
        return str(break_type)

    line, column = opcode.get_line_and_column()

    if line is None or column is None:
        return str(break_type)

    lines = raw_code.split("\n")

    padding = " " * column

    return """
{}
{}^
{}| {}""".format(lines[line - 1], padding, padding, getattr(out_break_type, "name", None) or str(out_break_type))

def bootstrap_function(data, argument=None, context=None, check_safe_exit=False):
    if argument is None:
        argument = NO_VALUE
    if context is None:
        context = get_default_global_context()

    get_manager(context).add_composite_type(DEFAULT_OBJECT_TYPE)
    break_managers = defaultdict(list)

    with ExitStack() as stack:
        open_function = prepare(
            data,
            context,
            create_no_escape_flow_manager(),
            immediate_context={
                "suggested_outer_type": get_context_type(context)
            }
        )

        break_manager = stack.enter_context(create_application_flow_manager())
        break_managers["exit"].append(break_manager)

        function_break_types = open_function.get_type().break_types

        error_msgs = []

        for mode, break_types in function_break_types.items():
            if mode not in ("exit", "return", "value") and check_safe_exit:
                breaks_messages = [format_unhandled_break_type(break_type, getattr(data, "raw_code", None)) for break_type in break_types]
                for break_message in breaks_messages:
                    error_msgs.append("""---- break mode {} is not safe ----

{}""".format(mode, break_message))
                continue
            for break_type in break_types:
                break_manager = stack.enter_context(break_manager.capture(mode, break_type, top_level=True))
                break_managers[mode].append(break_manager)

        if error_msgs:
            raise BootstrapException("\n\n".join(error_msgs))

        closed_function = open_function.close(context)
        mode, value, opcode, restart_type = closed_function.invoke(argument, break_manager)
        raise BreakException(mode, value, opcode, restart_type)

    for mode, break_managers in break_managers.items():
        for break_manager in break_managers:
            if break_manager.has_result:
                return munchify({
                    "mode": mode,
                    "value": break_manager.result
                })
