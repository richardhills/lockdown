# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import cProfile
from contextlib import contextmanager
from json.encoder import JSONEncoder
import sys

from lockdown.type_system.exceptions import FatalError


class InternalMarker(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

def spread_dict(*args, **kwargs):
    result = {}
    for arg in args:
        result.update(arg)
    result.update(kwargs)
    return result

def default(value, *args):
    if len(args) == 1:
        marker = MISSING
        default_if_marker, = args
    else:
        marker, default_if_marker = args
    if value is marker:
        return default_if_marker
    return value

def raise_from(T, e):
    raise T, T(e), sys.exc_info()[2]

def capture_raise(T, e):
    return T, T(e), sys.exc_info()[2]

def micro_op_repr(opname, key, key_error, type=None, type_error=None):
    if type:
        return "{}.{}{}.{}{}".format(opname, key, "!" if key_error else "", type.short_str(), "!" if type_error else "")
    else:
        return "{}.{}{}".format(opname, key, "!" if key_error else "")

def print_code(ast):
    class RDHObjectEncoder(JSONEncoder):
        def default(self, o):
            from lockdown.type_system.universal_type import PythonList, Universal
            if isinstance(o, PythonList):
                return o._to_list()
            if isinstance(o, Universal):
                return o._to_dict()
            return o
    print RDHObjectEncoder().encode(ast)

@contextmanager
def profile(output_file):
    try:
        pr = cProfile.Profile()
        pr.enable()
        yield
    finally:
        pr.disable()
        pr.dump_stats(output_file)

DEBUG_MODE = None

def is_debug():
    global DEBUG_MODE
    if DEBUG_MODE is None:
        raise FatalError()
    return DEBUG_MODE

def set_debug(debug):
    global DEBUG_MODE
    if DEBUG_MODE is not None:
        raise FatalError()
    DEBUG_MODE = debug


runtime_type_information_active = None

def runtime_type_information():
    global runtime_type_information_active
    if runtime_type_information_active is None:
        raise FatalError()
    return runtime_type_information_active

def set_runtime_type_information(bind):
    global runtime_type_information_active
    if runtime_type_information_active is not None:
        raise FatalError()
    runtime_type_information_active = bind

NO_VALUE = InternalMarker("NO_VALUE")
MISSING = InternalMarker("MISSING")
NOTHING = InternalMarker("NOTHING")
