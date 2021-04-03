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

MICRO_OP_FACTORIES = {
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
}

def build_universal_type(data):    
    micro_ops = OrderedDict({})

    for micro_op in data.micro_op:
        if hasattr(property, "name"):
            tag = ( property.opcode, property.name )
        else:
            tag = ( property.opcode, )
        micro_ops[tag] = MICRO_OP_FACTORIES[micro_op.type](micro_op.params)

    return CompositeType(micro_ops, name="App")

TYPES = {
    "Any": lambda data: AnyType(),
    "Object": build_object_type,
    "List": build_list_type,
    "Universal": build_universal_type,
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
