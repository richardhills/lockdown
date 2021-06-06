# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from UserDict import DictMixin
import cProfile
from collections import OrderedDict
from contextlib import contextmanager
from json.encoder import JSONEncoder
import sys
import weakref

from lockdown.type_system.exceptions import FatalError


class InternalMarker(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

NO_VALUE = InternalMarker("NO_VALUE")
MISSING = InternalMarker("MISSING")
NOTHING = InternalMarker("NOTHING")

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

def sort_dict_output(key_value):
    if key_value[0] == "opcode": return -1
    return 0

def print_code(ast):
    class RDHObjectEncoder(JSONEncoder):
        def default(self, o):
            from lockdown.type_system.universal_type import PythonList, Universal
            if isinstance(o, PythonList):
                return o._to_list()
            if isinstance(o, Universal):
                items = o._to_dict().items()
                items = [ i for i in items if i[0] not in ("column", "line") ]
                items = sorted(items, key=sort_dict_output)
                return OrderedDict(items)
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

class Environment(object):
    def __init__(
            self,
            rtti=True,
            frame_shortcut=True,
            validate_flow_control=True,
            opcode_bindings=True,
            consume_python_objects=True,
            return_value_optimization=True,
            transpile=False
        ):
        self.rtti = rtti
        self.frame_shortcut = frame_shortcut
        self.validate_flow_control = validate_flow_control
        self.opcode_bindings = opcode_bindings
        self.consume_python_objects = consume_python_objects
        self.return_value_optimization = return_value_optimization
        self.transpile = transpile

    def clone(
        self,
        rtti=MISSING,
        frame_shortcut=MISSING,
        validate_flow_control=MISSING,
        opcode_bindings=MISSING,
        consume_python_objects=MISSING,
        return_value_optimization=MISSING,
        transpile=MISSING
    ):
        return Environment(
            rtti=default(rtti, self.rtti),
            frame_shortcut=default(frame_shortcut, self.frame_shortcut),
            validate_flow_control=default(validate_flow_control, self.validate_flow_control),
            opcode_bindings=default(opcode_bindings, self.opcode_bindings),
            consume_python_objects=default(consume_python_objects, self.consume_python_objects),
            return_value_optimization=default(return_value_optimization, self.return_value_optimization),
            transpile=default(transpile, self.transpile)
        )

environment_stack = None

def get_environment():
    if environment_stack:
        return environment_stack[-1]

fastest = {
    "rtti": False,
    "frame_shortcut": True,
    "validate_flow_control": False,
    "opcode_bindings": False,
    "consume_python_objects": False,
    "return_value_optimization": True,
    "transpile": True
}

@contextmanager
def environment(
    rtti=MISSING,
    frame_shortcut=MISSING,
    validate_flow_control=MISSING,
    opcode_bindings=MISSING,
    consume_python_objects=MISSING,
    return_value_optimization=MISSING,
    transpile=MISSING,
    base=False
):
    environment = get_environment()
    if (environment and environment.transpile or transpile is True) and not (environment and environment.return_value_optimization or return_value_optimization is True):
        raise FatalError("Transpiling has return_value_optomization baked in")

    if base:
        global environment_stack
        if environment_stack is not None:
            raise FatalError()
        environment_stack = []
        new_environment = Environment(
            rtti=rtti,
            frame_shortcut=frame_shortcut,
            validate_flow_control=validate_flow_control,
            opcode_bindings=opcode_bindings,
            consume_python_objects=consume_python_objects,
            return_value_optimization=return_value_optimization,
            transpile=transpile
        )
    else:
        new_environment = get_environment().clone(
            rtti=rtti,
            frame_shortcut=frame_shortcut,
            validate_flow_control=validate_flow_control,
            opcode_bindings=opcode_bindings,
            consume_python_objects=consume_python_objects,
            return_value_optimization=return_value_optimization,
            transpile=transpile
        )

    environment_stack.append(new_environment)

    try:
        yield new_environment
    finally:
        environment_stack.pop()

class WeakIdentityKeyDictionary(DictMixin, object):
    def __init__(self, dict={}):
        self.weak_refs_by_id = {}
        self.weak_ref_ids_by_key_id = {}
        self.key_ids_by_weak_ref_id = {}
        self.values_by_key_id = {}

        for k, v in dict.items():
            self[k] = v

    def __setitem__(self, key, value):
        if id(key) in self.weak_ref_ids_by_key_id:
            weak_ref_id = self.weak_ref_ids_by_key_id[id(key)]
        else:
            ref = weakref.ref(key, self.key_gced)
            weak_ref_id = id(ref)
            self.weak_refs_by_id[id(ref)] = ref

        self.weak_ref_ids_by_key_id[id(key)] = weak_ref_id
        self.key_ids_by_weak_ref_id[weak_ref_id] = id(key)
        self.values_by_key_id[id(key)] = value

    def key_gced(self, ref):
        key_id = self.key_ids_by_weak_ref_id[id(ref)]
        del self.weak_refs_by_id[id(ref)]
        del self.weak_ref_ids_by_key_id[key_id]
        del self.key_ids_by_weak_ref_id[id(ref)]
        del self.values_by_key_id[key_id]

    def __getitem__(self, key):
        return self.values_by_key_id[id(key)]

    def __delitem__(self, key):
        weak_ref_id = self.weak_ref_ids_by_key_id[id(key)]
        del self.weak_refs_by_id[weak_ref_id]
        del self.weak_ref_ids_by_key_id[id(key)]
        del self.key_ids_by_weak_ref_id[weak_ref_id]
        del self.values_by_key_id[id(key)]

    def keys(self):
        return [v for v in (ref() for ref in self.weak_refs_by_id.values()) if v]
