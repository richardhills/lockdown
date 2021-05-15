# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict

from lockdown.executor.exceptions import PreparationException
from lockdown.executor.function_type import enrich_break_type, \
    ClosedFunctionType
from lockdown.type_system.composites import InferredType, CompositeType, \
    Composite
from lockdown.type_system.core_types import UnitType, OneOfType, Const, AnyType, \
    IntegerType, BooleanType, NoValueType, StringType, Type
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.universal_type import GetterMicroOpType, \
    SetterMicroOpType, InsertStartMicroOpType, InsertEndMicroOpType, \
    GetterWildcardMicroOpType, SetterWildcardMicroOpType, \
    DeletterWildcardMicroOpType, RemoverWildcardMicroOpType, \
    InserterWildcardMicroOpType, IterMicroOpType, UniversalObjectType, \
    DEFAULT_READONLY_COMPOSITE_TYPE, PythonDict, UniversalListType, PythonList, \
    UniversalTupleType, UniversalLupleType, EMPTY_COMPOSITE_TYPE, Universal


def build_closed_function_type(data):
    if not isinstance(data._get("break_types"), Universal):
        raise FatalError()
    for mode, break_types in data._get("break_types")._items():
        if not isinstance(mode, basestring):
            raise FatalError()
        if not isinstance(break_types, Universal):
            raise FatalError()
        for break_type in break_types._values():
            if not isinstance(break_type, Universal):
                raise FatalError(break_type)

    return ClosedFunctionType(
        enrich_type(data._get("argument")),
        PythonDict({
            mode: PythonList([ enrich_break_type(b) for b in break_types._values() ])
            for mode, break_types in data._get("break_types")._items()
        }, bind=DEFAULT_READONLY_COMPOSITE_TYPE, debug_reason="type")
    )

def build_unit_type(data):
    if not data._contains("value"):
        raise PreparationException(data)
    return UnitType(data._get("value"))

def build_one_of_type(data):
    if not data._contains("types"):
        raise PreparationException(data)
    return OneOfType(
        [ enrich_type(type) for type in data._get("types")._values() ]
    )

def build_object_type(data):
    properties = {}
    for name, type in data._get("properties")._items():
        properties[name] = enrich_type(type)
        if type._contains("const") and type._get("const"):
            properties[name] = Const(properties[name])

    wildcard_type = data._contains("wildcard_type")

    if wildcard_type:
        wildcard_type = enrich_type(wildcard_type)

    return UniversalObjectType(
        properties,
        wildcard_type=wildcard_type,
        name="declared-object-type"
    )

def build_list_type(data):
    property_types = [ enrich_type(type) for type in data._get("entry_types")._values() ]
    wildcard_type = data._get("wildcard_type", default=None)
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
    else:
        return EMPTY_COMPOSITE_TYPE

def inferred_opcode_factory(*args, **kwargs):
    return None

MICRO_OP_FACTORIES = {
    "get": lambda k, v: GetterMicroOpType(k, enrich_type(v)),
    "set": lambda k, v: SetterMicroOpType(k, enrich_type(v)),
    "insert-start": lambda v, t: InsertStartMicroOpType(enrich_type(v), t),
    "insert-end": lambda v, t: InsertEndMicroOpType(enrich_type(v), t),
    "get-wildcard": lambda k, v, e: GetterWildcardMicroOpType(enrich_type(k), enrich_type(v), e),
    "set-wildcard": lambda k, v, ke, te: SetterWildcardMicroOpType(enrich_type(k), enrich_type(v), ke, te),
    "delete-wildcard": lambda kt, ke: DeletterWildcardMicroOpType(enrich_type(kt), ke),
    "remove-wildcard": lambda ke, te: RemoverWildcardMicroOpType(ke, te),
    "insert-wildcard": lambda vt, ke, te: InserterWildcardMicroOpType(enrich_type(vt), ke, te),
    "iter": lambda vt: IterMicroOpType(enrich_type(vt))
}

def build_universal_type(data):    
    micro_ops = OrderedDict({})

    for micro_op in data._get("micro_ops"):
        if micro_op._contains("index"):
            tag = ( micro_op._get("type"), micro_op._get("index") )
        else:
            tag = ( micro_op._get("type"), )

        Factory = MICRO_OP_FACTORIES[micro_op._get("type")]

        try:
            micro_ops[tag] = Factory(*micro_op.params)
        except TypeError:
            raise

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
    if not isinstance(data, Universal):
        raise PreparationException("Unknown type data {}, {}".format(data, type(data)))
    if not data._contains("type"):
        raise PreparationException("Missing type in data {}".format(data))
    if data._get("type") not in TYPES:
        raise PreparationException("Unknown type {}".format(data.type))

    new_type = TYPES[data._get("type")](data)
    if not isinstance(new_type, Type):
        raise FatalError(data)

    return new_type
