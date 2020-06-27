# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from functools import wraps
import sys

from rdhlang5.type_system.exceptions import FatalError


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

def default(value, marker, default_if_marker):
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

def one_shot_memoize(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if getattr(self, "_result", MISSING) is not MISSING:
            raise FatalError()
        self._args = args
        self._kwargs = kwargs
        self._result = func(self, *args, **kwargs)
        return self._result
    return wrapper

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

BIND_RUNTIME_CONTEXTS = None

def bind_runtime_contexts():
    global BIND_RUNTIME_CONTEXTS
    if BIND_RUNTIME_CONTEXTS is None:
        raise FatalError()
    return BIND_RUNTIME_CONTEXTS

def set_bind_runtime_contexts(bind):
    global BIND_RUNTIME_CONTEXTS
    if BIND_RUNTIME_CONTEXTS is not None:
        raise FatalError()
    BIND_RUNTIME_CONTEXTS = bind

NO_VALUE = InternalMarker("NO_VALUE")
MISSING = InternalMarker("MISSING")
