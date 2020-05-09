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

def bootstrap_function(data, argument=None, context=None, check_safe_exit=False):
    if argument is None:
        argument = NO_VALUE
    if context is None:
        context = RDHObject({})

    get_manager(context).add_composite_type(DEFAULT_OBJECT_TYPE)
    break_managers = defaultdict(list)

    with ExitStack() as stack:
        function = prepare(data, context, create_no_escape_flow_manager())

        break_manager = stack.enter_context(create_application_flow_manager())
        break_managers["exit"].append(break_manager)

        function_break_types = function.get_type().break_types

        for mode, break_types in function_break_types.items():
            if mode not in ("exit", "return", "value") and check_safe_exit:
                raise BootstrapException("break mode {}: {} not safe".format(mode, break_types))
            for break_type in break_types:
                break_manager = stack.enter_context(break_manager.capture(mode, break_type, top_level=True))
                break_managers[mode].append(break_manager)

        function.invoke(argument, context, break_manager)

    for mode, break_managers in break_managers.items():
        for break_manager in break_managers:
            if break_manager.has_result:
                return munchify({
                    "mode": mode,
                    "value": break_manager.result
                })
