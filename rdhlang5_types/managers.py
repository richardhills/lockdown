import weakref

from rdhlang5_types.core_types import UnitType, NoValueType, Type
from rdhlang5_types.exceptions import FatalError, InvalidData
from rdhlang5_types.runtime import replace_all_refs
from rdhlang5_types.utils import NO_VALUE, InternalMarker


weak_objs_by_id = {}
managers_by_id = {}


def get_manager(obj):
    from rdhlang5_types.object_types import RDHObject
    from rdhlang5_types.dict_types import RDHDict
    from rdhlang5_types.list_types import RDHList
    from rdhlang5_types.composites import CompositeObjectManager, CompositeType
    from rdhlang5_types.composites import Composite
    from rdhlang5.executor.function import *

    if isinstance(obj, InternalMarker):
        return None

    if isinstance(obj, PreparedFunction):
        return None

    if not isinstance(obj, (list, tuple, dict, Composite)) and not hasattr(obj, "__dict__"):
        return None

    if isinstance(obj, Type):
        return None

    manager = managers_by_id.get(id(obj), None)
    if not manager:
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
            obj = RDHDict(obj)
            replace_all_refs(old_obj, obj)
            manager = CompositeObjectManager(obj)
        elif isinstance(obj, object) and hasattr(obj, "__dict__"):
            original_type = obj.__class__
            new_type = type("RDH{}".format(original_type.__name__), (RDHObject, original_type,), {})
            obj = new_type(obj.__dict__)
            replace_all_refs(old_obj, obj)
            manager = CompositeObjectManager(obj)
        else:
            raise FatalError()
        weak_objs_by_id[id(obj)] = weakref.ref(obj)
        managers_by_id[id(obj)] = manager
    return manager


def obj_cleared_callback(obj):
    del weak_objs_by_id[id(obj)]
    del managers_by_id[id(obj)]


def get_type_of_value(value):
    from rdhlang5_types.dict_types import RDHDict
    from rdhlang5_types.list_types import RDHList
    from rdhlang5_types.object_types import RDHObject
    from rdhlang5_types.composites import CompositeObjectManager, CompositeType
    # Changing this to import PreparedFunction gives an import error ... no idea why
    from rdhlang5.executor.function import *

    if isinstance(value, (str, int)):
        return UnitType(value)
    if value is None:
        return NoValueType()
    if value is NO_VALUE:
        return NoValueType()
    if isinstance(value, (RDHObject, RDHList, RDHDict)):
        manager = get_manager(value)
        if manager is None:
            pass
        return CompositeType(manager.get_merged_micro_op_types(), value)
    if isinstance(value, PreparedFunction):
        return value.get_type()
    if isinstance(value, Type):
        return NoValueType()
    raise InvalidData(type(value), value)
