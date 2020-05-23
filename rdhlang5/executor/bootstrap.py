# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from _collections import defaultdict

from munch import munchify
from pip._vendor.contextlib2 import ExitStack

from rdhlang5.executor.flow_control import FrameManager, FlowManager
from rdhlang5.executor.function import prepare
from rdhlang5.type_system.core_types import AnyType
from rdhlang5.type_system.default_composite_types import DEFAULT_OBJECT_TYPE
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.object_types import RDHObject
from rdhlang5.utils import NO_VALUE
from rdhlang5.executor.raw_code_factories import inferred_type
from rdhlang5.executor.opcodes import get_context_type


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
            }),
            "var": RDHObject({
                "type": "Inferred"
            })
        })
    }, bind=DEFAULT_OBJECT_TYPE)

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
        closed_function.invoke(argument, break_manager)

    for mode, break_managers in break_managers.items():
        for break_manager in break_managers:
            if break_manager.has_result:
                return munchify({
                    "mode": mode,
                    "value": break_manager.result
                })
