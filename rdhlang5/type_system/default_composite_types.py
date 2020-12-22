from rdhlang5.type_system.composites import CompositeType
from rdhlang5.type_system.core_types import OneOfType, AnyType
from rdhlang5.type_system.dict_types import RDHDictType, DictWildcardGetterType, \
    DictWildcardSetterType, DictWildcardDeletterType
from rdhlang5.type_system.list_types import RDHListType, ListWildcardGetterType, \
    ListWildcardSetterType, ListInsertType, ListWildcardDeletterType, \
    ListWildcardInsertType
from rdhlang5.type_system.object_types import RDHObjectType, \
    ObjectWildcardGetterType, ObjectWildcardSetterType
from rdhlang5.utils import runtime_type_information


READONLY_DEFAULT_OBJECT_TYPE = RDHObjectType(name="readonly-default-object-type")
READONLY_DEFAULT_LIST_TYPE = RDHListType([], None)
READONLY_DEFAULT_DICT_TYPE = RDHDictType()

readonly_rich_composite_type = OneOfType([ READONLY_DEFAULT_OBJECT_TYPE, READONLY_DEFAULT_LIST_TYPE, READONLY_DEFAULT_DICT_TYPE, AnyType() ])

READONLY_DEFAULT_OBJECT_TYPE.micro_op_types[("get-wildcard", )] = ObjectWildcardGetterType(readonly_rich_composite_type, readonly_rich_composite_type, True, False)
READONLY_DEFAULT_LIST_TYPE.micro_op_types[("get-wildcard", )] = ListWildcardGetterType(readonly_rich_composite_type, True, False)
READONLY_DEFAULT_DICT_TYPE.micro_op_types[("get-wildcard", )] = DictWildcardGetterType(readonly_rich_composite_type, readonly_rich_composite_type, True, False)


DEFAULT_OBJECT_TYPE = RDHObjectType(name="default-object-type")
DEFAULT_LIST_TYPE = RDHListType([], None)
DEFAULT_DICT_TYPE = RDHDictType()

rich_composite_type = OneOfType([ DEFAULT_OBJECT_TYPE, DEFAULT_LIST_TYPE, DEFAULT_DICT_TYPE, AnyType() ])

DEFAULT_OBJECT_TYPE.micro_op_types[("get-wildcard", )] = ObjectWildcardGetterType(readonly_rich_composite_type, rich_composite_type, True, False)
if runtime_type_information():
    DEFAULT_OBJECT_TYPE.micro_op_types[("set-wildcard", )] = ObjectWildcardSetterType(readonly_rich_composite_type, rich_composite_type, True, True)

DEFAULT_LIST_TYPE.micro_op_types[("get-wildcard", )] = ListWildcardGetterType(rich_composite_type, True, False)
DEFAULT_LIST_TYPE.micro_op_types[("insert", 0 )] = ListInsertType(0, rich_composite_type, False, False)
DEFAULT_LIST_TYPE.micro_op_types[("delete-wildcard", )] = ListWildcardDeletterType(True)
if runtime_type_information():
    DEFAULT_LIST_TYPE.micro_op_types[("set-wildcard", )] = ListWildcardSetterType(rich_composite_type, True, True)
    DEFAULT_LIST_TYPE.micro_op_types[("insert-wildcard", )] = ListWildcardInsertType(rich_composite_type, True, True)

DEFAULT_DICT_TYPE.micro_op_types[("get-wildcard", )] = DictWildcardGetterType(readonly_rich_composite_type, rich_composite_type, True, False)
if runtime_type_information():
    DEFAULT_DICT_TYPE.micro_op_types[("set-wildcard", )] = DictWildcardSetterType(readonly_rich_composite_type, rich_composite_type, True, True)
DEFAULT_DICT_TYPE.micro_op_types[("delete-wildcard", )] = DictWildcardDeletterType(True)

EMPTY_OBJECT_TYPE = CompositeType({}, name="empty")
EMPTY_LIST_TYPE = CompositeType({}, name="empty")
EMPTY_DICT_TYPE = CompositeType({}, name="empty")

