# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict

from lockdown.executor.exceptions import PreparationException
from lockdown.executor.function_type import enrich_break_type, \
    ClosedFunctionType
from lockdown.type_system.composites import InferredType, CompositeType, \
    Composite
from lockdown.type_system.core_types import UnitType, OneOfType, Const, AnyType, \
    IntegerType, BooleanType, NoValueType, StringType
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.universal_type import GetterMicroOpType, \
    SetterMicroOpType, InsertStartMicroOpType, InsertEndMicroOpType, \
    GetterWildcardMicroOpType, SetterWildcardMicroOpType, \
    DeletterWildcardMicroOpType, RemoverWildcardMicroOpType, \
    InserterWildcardMicroOpType, IterMicroOpType, UniversalObjectType, \
    DEFAULT_READONLY_COMPOSITE_TYPE, PythonDict, UniversalListType, PythonList, \
    UniversalTupleType, UniversalLupleType


def build_closed_function_type(data):
    if not isinstance(data.break_types, PythonDict):
        raise FatalError()
    for mode, break_types in data.break_types.items():
        if not isinstance(mode, basestring):
            raise FatalError()
        if not isinstance(break_types, PythonList):
            raise FatalError()
        for break_type in break_types:
            if not isinstance(break_type, PythonDict):
                raise FatalError()

    return ClosedFunctionType(
        enrich_type(data.argument),
        PythonDict({
            mode: PythonList([ enrich_break_type(b) for b in break_types ])
            for mode, break_types in data.break_types.items()
        }, bind=DEFAULT_READONLY_COMPOSITE_TYPE, debug_reason="type")
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
    for name, type in data.properties._items():
        properties[name] = enrich_type(type)
        if getattr(type, "const", False):
            properties[name] = Const(properties[name])

    wildcard_type = getattr(data, "wildcard_type", None)

    if wildcard_type:
        wildcard_type = enrich_type(wildcard_type)

    return UniversalObjectType(
        properties,
        wildcard_type=wildcard_type,
        name="declared-object-type"
    )

def build_list_type(data):
    property_types = [ enrich_type(type) for type in data.entry_types ]
    wildcard_type = getattr(data, "wildcard_type", None)
    if wildcard_type:
        wildcard_type = enrich_type(wildcard_type)

    if wildcard_type and property_types:
        return UniversalLupleType(
            property_types,
            wildcard_type
        )
    elif property_types:
        return UniversalTupleType(
            property_types
        )
    elif wildcard_type:
        return UniversalListType(
            wildcard_type
        )

def inferred_opcode_factory(*args, **kwargs):
    return None

OPCODE_TYPE_FACTORIES = {
    "universal": {
        "get": GetterMicroOpType,
        "set": SetterMicroOpType,
        "insert-start": InsertStartMicroOpType,
        "insert-end": InsertEndMicroOpType,
        "get-wildcard": GetterWildcardMicroOpType,
        "set-wildcard": SetterWildcardMicroOpType,
        "delete-wildcard": DeletterWildcardMicroOpType,
        "remove-wildcard": RemoverWildcardMicroOpType,
        "insert-wildcard": InserterWildcardMicroOpType,
        "iter": IterMicroOpType
    },
#     "object": {
#         "get": ObjectGetterType,
#         "set": ObjectSetterType,
#         "delete": ObjectDeletterType,
#         "get-wildcard": lambda property: ObjectWildcardGetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
#         "set-wildcard": lambda property: ObjectWildcardSetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
#         "delete-wildcard": lambda property: ObjectWildcardDeletterType(property.key_error),
#         "get-inferred": inferred_opcode_factory,
#         "set-inferred": inferred_opcode_factory
#     },
#     "dict": {
#         "get": DictGetterType,
#         "set": DictSetterType,
#         "delete": DictDeletterType,
#         "get-wildcard": lambda property: DictWildcardGetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
#         "set-wildcard": lambda property: DictWildcardSetterType(enrich_type(property.key_type), enrich_type(property.value_type), property.key_error, property.type_error),
#         "delete-wildcard": lambda property: DictWildcardDeletterType(property.key_error),
#         "get-inferred": inferred_opcode_factory,
#         "set-inferred": inferred_opcode_factory
#     },
#     "list": {
#         "get": ListGetterType,
#         "set": ListSetterType,
#         "delete": ListDeletterType,
#         "get-wildcard": ListWildcardGetterType,
#         "set-wildcard": ListWildcardSetterType,
#         "delete-wildcard": ListWildcardDeletterType,
#         "get-inferred": inferred_opcode_factory,
#         "set-inferred": inferred_opcode_factory
#     }
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
    if not isinstance(data, Composite):
        raise PreparationException("Unknown type data {}, {}".format(data, type(data)))
    if not hasattr(data, "type"):
        raise PreparationException("Missing type in data {}".format(data))
    if data.type not in TYPES:
        raise PreparationException("Unknown type {}".format(data.type))

    return TYPES[data.type](data)
