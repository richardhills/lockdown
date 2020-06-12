import weakref

from rdhlang5.type_system.core_types import Type, UnitType, NoValueType
from rdhlang5.type_system.exceptions import FatalError, InvalidData
from rdhlang5.type_system.runtime import replace_all_refs
from rdhlang5.utils import InternalMarker, NO_VALUE


weak_objs_by_id = {}
managers_by_id = {}


def get_manager(obj, trigger=None):
    manager = managers_by_id.get(id(obj), None)
    if manager:
#        if is_debug():
#            logger.debug("{}:{}:{}:{}:{}".format(len(managers_by_id), trigger, id(obj), type(obj), getattr(manager, "debug_reason", None)))
        return manager

    if isinstance(obj, InternalMarker):
        return None

    from rdhlang5.type_system.composites import Composite
    if not isinstance(obj, (list, tuple, dict, Composite)) and not hasattr(obj, "__dict__"):
        return None

    if isinstance(obj, Type):
        return None

    from rdhlang5.executor.function import RDHFunction, OpenFunction
    if isinstance(obj, (RDHFunction, OpenFunction)):
        return None

    from rdhlang5.executor.opcodes import Opcode
    if isinstance(obj, Opcode):
        return None

    from rdhlang5.type_system.composites import CompositeObjectManager

    old_obj = obj
    if isinstance(obj, Composite):
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, list):
        from rdhlang5.type_system.list_types import RDHList
        obj = RDHList(obj)
        replace_all_refs(old_obj, obj)            
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, tuple):
        from rdhlang5.type_system.list_types import RDHList
        obj = RDHList(obj)
        replace_all_refs(old_obj, obj)            
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, dict):
        from rdhlang5.type_system.dict_types import RDHDict
        obj = RDHDict(obj, debug_reason="monkey-patch")
        replace_all_refs(old_obj, obj)
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, object) and hasattr(obj, "__dict__"):
        from rdhlang5.type_system.object_types import RDHObject
        original_type = obj.__class__
        new_type = type("RDH{}".format(original_type.__name__), (RDHObject, original_type,), {})
        obj = new_type(obj.__dict__)
        replace_all_refs(old_obj, obj)
        manager = CompositeObjectManager(obj)
        manager.debug_reason = "monkey-patch"
    else:
        raise FatalError()

    weak_objs_by_id[id(obj)] = weakref.ref(obj, obj_cleared_callback)
    managers_by_id[id(obj)] = manager

    return manager


def obj_cleared_callback(obj):
    del weak_objs_by_id[id(obj)]
    del managers_by_id[id(obj)]


def get_type_of_value(value):
    if isinstance(value, (basestring, int)):
        return UnitType(value)
    if value is None:
        return NoValueType()
    if value is NO_VALUE:
        return NoValueType()
    if isinstance(value, Type):
        return NoValueType()

    from rdhlang5.executor.function import RDHFunction, OpenFunction
    if isinstance(value, (RDHFunction, OpenFunction)):
        return value.get_type()

    manager = get_manager(value, "get_type_of_value")
    if manager:
        return manager.get_effective_composite_type()

    raise InvalidData(type(value), value)
