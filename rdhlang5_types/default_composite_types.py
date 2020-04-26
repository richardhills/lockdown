from rdhlang5_types.composites import CompositeType
from rdhlang5_types.core_types import OneOfType, AnyType
from rdhlang5_types.dict_types import DictWildcardGetterType, \
    DictWildcardSetterType, RDHDictType
from rdhlang5_types.list_types import ListWildcardGetterType, \
    ListWildcardSetterType, ListInsertType, ListWildcardDeletterType, \
    ListWildcardInsertType, RDHListType
from rdhlang5_types.object_types import  ObjectWildcardGetterType, \
    ObjectWildcardSetterType, RDHObjectType


DEFAULT_OBJECT_TYPE = RDHObjectType({}, None)
DEFAULT_LIST_TYPE = RDHListType([], None)
DEFAULT_DICT_TYPE = RDHDictType()

rich_composite_type = OneOfType([ DEFAULT_OBJECT_TYPE, DEFAULT_LIST_TYPE, DEFAULT_DICT_TYPE, AnyType() ])

DEFAULT_OBJECT_TYPE.micro_op_types[("get-wildcard", )] = ObjectWildcardGetterType(rich_composite_type, True, False)
DEFAULT_OBJECT_TYPE.micro_op_types[("set-wildcard", )] = ObjectWildcardSetterType(rich_composite_type, True, True)

DEFAULT_LIST_TYPE.micro_op_types[("get-wildcard", )] = ListWildcardGetterType(rich_composite_type, True, False)
DEFAULT_LIST_TYPE.micro_op_types[("set-wildcard", )] = ListWildcardSetterType(rich_composite_type, True, False)
DEFAULT_LIST_TYPE.micro_op_types[("insert", )] = ListInsertType(rich_composite_type, 0, False, False)
DEFAULT_LIST_TYPE.micro_op_types[("delete-wildcard", )] = ListWildcardDeletterType(True)
DEFAULT_LIST_TYPE.micro_op_types[("insert-wildcard", )] = ListWildcardInsertType(rich_composite_type, True, False)

DEFAULT_DICT_TYPE.micro_op_types[("get-wildcard", )] = DictWildcardGetterType(rich_composite_type, True, False)
DEFAULT_DICT_TYPE.micro_op_types[("set-wildcard", )] = DictWildcardSetterType(rich_composite_type, True, False)
