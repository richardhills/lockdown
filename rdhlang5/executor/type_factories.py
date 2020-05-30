# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.function_type import enrich_break_type, \
    ClosedFunctionType
from rdhlang5.type_system.composites import InferredType
from rdhlang5.type_system.core_types import UnitType, OneOfType, Const, AnyType, \
    IntegerType, BooleanType, NoValueType, StringType
from rdhlang5.type_system.default_composite_types import DEFAULT_DICT_TYPE
from rdhlang5.type_system.dict_types import RDHDict
from rdhlang5.type_system.exceptions import FatalError
from rdhlang5.type_system.list_types import RDHListType, RDHList
from rdhlang5.type_system.object_types import RDHObjectType, RDHObject


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
            mode: [ enrich_break_type(b) for b in break_types ]
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
    return RDHObjectType(properties, name="declared-object-type")

def build_list_type(data):
    wildcard_type = getattr(data, "wildcard_type", None)
    if wildcard_type:
        wildcard_type = enrich_type(wildcard_type)
    return RDHListType(
        [ enrich_type(type) for type in data.entry_types ],
        wildcard_type
    )

TYPES = {
    "Any": lambda data: AnyType(),
    "Object": build_object_type,
    "List": build_list_type,
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
    if not isinstance(data, RDHObject):
        raise PreparationException("Unknown type data {}, {}".format(data, type(data)))
    if not hasattr(data, "type"):
        raise PreparationException("Missing type in data {}".format(data))
    if data.type not in TYPES:
        raise PreparationException("Unknown type {}".format(data.type))

    return TYPES[data.type](data)
