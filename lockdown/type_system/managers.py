# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import weakref

from lockdown.type_system.core_types import Type, UnitType, NoValueType
from lockdown.type_system.exceptions import FatalError, InvalidData
#from lockdown.type_system.runtime import replace_all_refs
from lockdown.utils.utils import InternalMarker, NO_VALUE, get_environment

def replace_all_refs(*args, **kwargs):
    raise FatalError("TODO: implement replace_all_refs in python 3")

managers_by_object_id = {}

def get_manager(obj, trigger=None):
    """
    Returns the run time CompositeManager for an object (if it needs one!)

    CompositeManager objects are needed for objects that can have CompositeTypes. In Lockdown, this is
    Python Lists, Objects, Dictionaries, Tuples, etc

    CompositeManagers exist alongside the base Python objects for their lifetime. They are GCed when the
    Python object is GCed.

    When code interacts with these base Python objects, they will often use the CompositeManager to
    determine what interactions are allowed or not, to maintain consistency with the rest of the Lockdown
    application. The CompositeManager maintains a weak ref to the object for which it is responsible.
    """
    manager = managers_by_object_id.get(id(obj), None)
    if manager:
        return manager

    if isinstance(obj, InternalMarker):
        return None

    from lockdown.type_system.composites import Composite
    if not isinstance(obj, (list, tuple, dict, Composite)) and not hasattr(obj, "__dict__"):
        return None

    if isinstance(obj, Type):
        return None

    try:
        from lockdown.executor.function import LockdownFunction, OpenFunction
        if isinstance(obj, (LockdownFunction, OpenFunction)):
            return None
    except ImportError:
        pass

    from lockdown.executor.opcodes import Opcode
    if isinstance(obj, Opcode):
        return None

    from lockdown.type_system.composites import CompositeObjectManager

    old_obj = obj
    if isinstance(obj, Composite):
        manager = CompositeObjectManager(obj, obj_cleared_callback, False)
    elif isinstance(obj, list):
        if not get_environment().consume_python_objects:
            raise FatalError()
        from lockdown.type_system.universal_type import PythonList
        obj = PythonList(obj)
        replace_all_refs(old_obj, obj)            
        manager = CompositeObjectManager(obj, obj_cleared_callback, False)
    elif isinstance(obj, tuple):
        if not get_environment().consume_python_objects:
            raise FatalError()
        from lockdown.type_system.universal_type import PythonList
        obj = PythonList(obj)
        replace_all_refs(old_obj, obj)            
        manager = CompositeObjectManager(obj, obj_cleared_callback, False)
    elif isinstance(obj, dict):
        if not get_environment().consume_python_objects:
            raise FatalError()
        from lockdown.type_system.universal_type import PythonDict
        obj = PythonDict(obj, debug_reason="monkey-patch")
        replace_all_refs(old_obj, obj)
        manager = CompositeObjectManager(obj, obj_cleared_callback, True)
    elif isinstance(obj, object) and hasattr(obj, "__dict__"):
        if not get_environment().consume_python_objects:
            raise FatalError()
        from lockdown.type_system.universal_type import PythonObject
        original_type = obj.__class__
        new_type = type("Lockdown{}".format(original_type.__name__).encode("utf-8"), (PythonObject, original_type,), {})
        obj = new_type(obj.__dict__)
        replace_all_refs(old_obj, obj)
        manager = CompositeObjectManager(obj, obj_cleared_callback, True)
        manager.debug_reason = "monkey-patch"
    else:
        raise FatalError()

    managers_by_object_id[id(obj)] = manager

    return manager


def obj_cleared_callback(obj_id):
    del managers_by_object_id[obj_id]


def get_type_of_value(value):
    if isinstance(value, (str, int)):
        return UnitType(value)
    if value is None:
        return NoValueType()
    if value is NO_VALUE:
        return NoValueType()
    if isinstance(value, Type):
        return NoValueType()

    from lockdown.executor.function import LockdownFunction, OpenFunction
    if isinstance(value, (LockdownFunction, OpenFunction)):
        return value.get_type()

    manager = get_manager(value, "get_type_of_value")
    if manager:
        return manager.get_effective_composite_type()

    raise InvalidData(type(value), value)
