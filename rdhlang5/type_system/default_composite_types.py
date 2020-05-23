from rdhlang5.type_system.core_types import OneOfType, AnyType
from rdhlang5.type_system.dict_types import RDHDictType, DictWildcardGetterType, \
    DictWildcardSetterType
from rdhlang5.type_system.list_types import RDHListType, ListWildcardGetterType, \
    ListWildcardSetterType, ListInsertType, ListWildcardDeletterType, \
    ListWildcardInsertType
from rdhlang5.type_system.object_types import RDHObjectType, \
    ObjectWildcardGetterType, ObjectWildcardSetterType


DEFAULT_OBJECT_TYPE = RDHObjectType(name="default-object-type")
DEFAULT_LIST_TYPE = RDHListType([], None)
DEFAULT_DICT_TYPE = RDHDictType()

rich_composite_type = OneOfType([ DEFAULT_OBJECT_TYPE, DEFAULT_LIST_TYPE, DEFAULT_DICT_TYPE, AnyType() ])

DEFAULT_OBJECT_TYPE.micro_op_types[("get-wildcard", )] = ObjectWildcardGetterType(rich_composite_type, True, False)
DEFAULT_OBJECT_TYPE.micro_op_types[("set-wildcard", )] = ObjectWildcardSetterType(rich_composite_type, True, True)

DEFAULT_LIST_TYPE.micro_op_types[("get-wildcard", )] = ListWildcardGetterType(rich_composite_type, True, False)
DEFAULT_LIST_TYPE.micro_op_types[("set-wildcard", )] = ListWildcardSetterType(rich_composite_type, True, True)
DEFAULT_LIST_TYPE.micro_op_types[("insert", 0 )] = ListInsertType(rich_composite_type, 0, False, False)
DEFAULT_LIST_TYPE.micro_op_types[("delete-wildcard", )] = ListWildcardDeletterType(True)
DEFAULT_LIST_TYPE.micro_op_types[("insert-wildcard", )] = ListWildcardInsertType(rich_composite_type, True, True)

DEFAULT_DICT_TYPE.micro_op_types[("get-wildcard", )] = DictWildcardGetterType(rich_composite_type, True, False)
DEFAULT_DICT_TYPE.micro_op_types[("set-wildcard", )] = DictWildcardSetterType(rich_composite_type, True, True)
