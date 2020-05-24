import weakref

from log import logger
from rdhlang5.type_system.core_types import Type, UnitType, NoValueType
from rdhlang5.type_system.exceptions import FatalError, InvalidData
from rdhlang5.type_system.runtime import replace_all_refs
from rdhlang5.utils import InternalMarker, NO_VALUE


weak_objs_by_id = {}
managers_by_id = {}


def get_manager(obj, trigger=None):
    from rdhlang5.type_system.object_types import RDHObject
    from rdhlang5.type_system.dict_types import RDHDict
    from rdhlang5.type_system.list_types import RDHList
    from rdhlang5.type_system.composites import CompositeObjectManager, CompositeType
    from rdhlang5.type_system.composites import Composite
    from rdhlang5.executor.function import *

    manager = managers_by_id.get(id(obj), None)
    if manager:
        logger.debug( "{}:{}:{}:{}:{}".format(len(managers_by_id), trigger, id(obj), type(obj), getattr(manager, "debug_reason", None)))
        return manager

    if isinstance(obj, InternalMarker):
        return None

    if isinstance(obj, (RDHFunction, OpenFunction)):
        return None

    if not isinstance(obj, (list, tuple, dict, Composite)) and not hasattr(obj, "__dict__"):
        return None

    if isinstance(obj, Type):
        return None

    old_obj = obj
    if isinstance(obj, RDHObject):
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, RDHList):
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, RDHDict):
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, list):
        obj = RDHList(obj)
        replace_all_refs(old_obj, obj)            
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, tuple):
        obj = RDHList(obj)
        replace_all_refs(old_obj, obj)            
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, dict):
        obj = RDHDict(obj, debug_reason="monkey-patch")
        replace_all_refs(old_obj, obj)
        manager = CompositeObjectManager(obj)
    elif isinstance(obj, object) and hasattr(obj, "__dict__"):
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
    from rdhlang5.type_system.dict_types import RDHDict
    from rdhlang5.type_system.list_types import RDHList
    from rdhlang5.type_system.object_types import RDHObject
    from rdhlang5.type_system.composites import CompositeObjectManager, CompositeType
    # Changing this to import PreparedFunction gives an import error ... no idea why
    from rdhlang5.executor.function import *

    if isinstance(value, (basestring, int)):
        return UnitType(value)
    if value is None:
        return NoValueType()
    if value is NO_VALUE:
        return NoValueType()
    if isinstance(value, (RDHFunction, OpenFunction)):
        return value.get_type()
    if isinstance(value, Type):
        return NoValueType()
    manager = get_manager(value, "get_type_of_value")
    if manager:
        return manager.get_effective_composite_type()
    raise InvalidData(type(value), value)
