# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict

from lockdown.executor.exceptions import PreparationException
from lockdown.executor.function_type import enrich_break_type, \
    ClosedFunctionType
from lockdown.type_system.composites import InferredType, CompositeType
from lockdown.type_system.core_types import UnitType, OneOfType, Const, AnyType, \
    IntegerType, BooleanType, NoValueType, StringType
from lockdown.type_system.default_composite_types import DEFAULT_DICT_TYPE
from lockdown.type_system.dict_types import RDHDict, DictGetterType, \
    DictSetterType, DictDeletterType, DictWildcardGetterType, \
    DictWildcardSetterType, DictWildcardDeletterType
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.list_types import RDHListType, RDHList, ListGetterType, \
    ListSetterType, ListDeletterType, ListWildcardGetterType, \
    ListWildcardSetterType, ListWildcardDeletterType
from lockdown.type_system.object_types import RDHObjectType, RDHObject, \
    ObjectGetterType, ObjectSetterType, ObjectWildcardGetterType, \
    ObjectWildcardSetterType, ObjectDeletterType, ObjectWildcardDeletterType


def build_closed_function_type(data):
    if not isinstance(data.break_types, RDHDict):
        raise FatalError()
    for mode, break_types in data.break_types.items():
        if not isinstance(mode, basestring):
            raise FatalError()
        if not isinstance(break_types, RDHList):
            raise FatalError()
        for break_type in break_types:
            if not isinstance(break_type, RDHDict):
                raise FatalError()

    return ClosedFunctionType(
        enrich_type(data.argument),
        RDHDict({
            mode: RDHList([ enrich_break_type(b) for b in break_types ])
            for mode, break_types in data.break_types.items()
        }, bind=DEFAULT_DICT_TYPE, debug_reason="type")
    )

def build_unit_type(data):
    if not hasattr(data, "value"):
        raise PreparationException(data)
    return UnitType(data.value)

def build_one_of_type(data):
    if not hasattr(data, "types"):
        raise PreparationException(data)
    return OneOfType(
        [ enrich_type(type) for type in data.types ]
    )

def build_object_type(data):
    properties = {}
    for name, type in data.properties.__dict__.items():
        properties[name] = enrich_type(type)
        if getattr(type, "const", False):
            properties[name] = Const(properties[name])

    wildcard_key_type = getattr(data, "wildcard_key_type", None)
    wildcard_value_type = getattr(data, "wildcard_value_type", None)

    if wildcard_key_type:
        wildcard_key_type = enrich_type(wildcard_key_type)
        wildcard_value_type = enrich_type(wildcard_value_type)

    return RDHObjectType(
        properties,
        wildcard_key_type=wildcard_key_type,
        wildcard_value_type=wildcard_value_type,
        name="declared-object-type"
    )

def build_list_type(data):
    wildcard_type = getattr(data, "wildcard_type", None)
    if wildcard_type:
        wildcard_type = enrich_type(wildcard_type)
    return RDHListType(
        [ enrich_type(type) for type in data.entry_types ],
        wildcard_type
    )

def inferred_opcode_factory(*args, **kwargs):
    return None

OPCODE_TYPE_FACTORIES = {
    "object": {
        "get": ObjectGetterType,
        "set": ObjectSetterType,
        "delete": ObjectDeletterType,
        "get-wildcard": lambda property: ObjectWildcardGetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
        "set-wildcard": lambda property: ObjectWildcardSetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
        "delete-wildcard": lambda property: ObjectWildcardDeletterType(property.key_error),
        "get-inferred": inferred_opcode_factory,
        "set-inferred": inferred_opcode_factory
    },
    "dict": {
        "get": DictGetterType,
        "set": DictSetterType,
        "delete": DictDeletterType,
        "get-wildcard": lambda property: DictWildcardGetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
        "set-wildcard": lambda property: DictWildcardSetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
        "delete-wildcard": lambda property: DictWildcardDeletterType(property.key_error),
        "get-inferred": inferred_opcode_factory,
        "set-inferred": inferred_opcode_factory
    },
    "list": {
        "get": ListGetterType,
        "set": ListSetterType,
        "delete": ListDeletterType,
        "get-wildcard": ListWildcardGetterType,
        "set-wildcard": ListWildcardSetterType,
        "delete-wildcard": ListWildcardDeletterType,
        "get-inferred": inferred_opcode_factory,
        "set-inferred": inferred_opcode_factory
    }
}

def build_composite_type(data):    
    micro_ops = OrderedDict({})

    python_type_name = data.python_type
    opcode_type_factory = OPCODE_TYPE_FACTORIES[python_type_name]

    for property in data.properties:
        if hasattr(property, "name"):
            tag = ( property.opcode, property.name )
        else:
            tag = ( property.opcode, )
        micro_ops[tag] = opcode_type_factory[property.opcode](property)

    return CompositeType(micro_ops, name="App")

TYPES = {
    "Any": lambda data: AnyType(),
    "Object": build_object_type,
    "List": build_list_type,
    "Composite": build_composite_type,
    "Function": build_closed_function_type,
    "OneOf": build_one_of_type,
    "Integer": lambda data: IntegerType(),
    "Boolean": lambda data: BooleanType(),
    "NoValue": lambda data: NoValueType(),
    "String": lambda data: StringType(),
    "Unit": build_unit_type,
    "Inferred": lambda data: InferredType()
}


def enrich_type(data):
    from lockdown.type_system.managers import get_manager
    if not isinstance(data, RDHObject):
        raise PreparationException("Unknown type data {}, {}".format(data, type(data)))
    if not hasattr(data, "type"):
        raise PreparationException("Missing type in data {}".format(data))
    if data.type not in TYPES:
        raise PreparationException("Unknown type {}".format(data.type))

    return TYPES[data.type](data)
