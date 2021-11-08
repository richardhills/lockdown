# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import OrderedDict

from lockdown.executor.exceptions import PreparationException
from lockdown.executor.function_type import enrich_break_type, \
    ClosedFunctionType
from lockdown.executor.raw_code_factories import one_of_type
from lockdown.type_system.composites import InferredType, CompositeType, \
    Composite
from lockdown.type_system.core_types import UnitType, OneOfType, Const, AnyType, \
    IntegerType, BooleanType, NoValueType, StringType, Type, BottomType
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
        if not isinstance(mode, str):
            raise FatalError()
        if not isinstance(break_types, Universal):
            raise FatalError()
        for break_mode in break_types._keys():
            if not isinstance(break_mode, (str, int)):
                raise FatalError(break_mode)
        for break_type in break_types._values():
            if not isinstance(break_type, Universal):
                raise FatalError(break_type)
            out = break_type._get("out")
            if not out._contains("type"):
                raise FatalError()

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

    wildcard_type = None
    if data._contains("wildcard_type"):
        wildcard_type = enrich_type(data._get("wildcard_type"))

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

class InferRemainerPlaceholder(object):
    def __init__(self, base_type):
        self.base_type = base_type

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
    "iter": lambda kt, vt: IterMicroOpType(enrich_type(kt), enrich_type(vt)),
    "infer-remainder": lambda base_type: InferRemainerPlaceholder(enrich_type(base_type))
}

def build_universal_type(data):    
    micro_ops = OrderedDict({})

    for micro_op in data._get("micro_ops")._to_list():
        if micro_op._contains("index"):
            tag = ( micro_op._get("type"), micro_op._get("index") )
        else:
            tag = ( micro_op._get("type"), )

        Factory = MICRO_OP_FACTORIES[micro_op._get("type")]

        micro_ops[tag] = Factory(*micro_op._get("params")._to_list())

    return CompositeType(micro_ops, name="User")

# def deconstruct_micro_op(micro_op, results):
#     if isinstance(micro_op, GetterMicroOpType):
#         return PythonDict({
#             "type": "get",
#             "index": micro_op.key,
#             "params": PythonList([ micro_op.key, derich_type(micro_op.value_type, results) ])
#         })
#     if isinstance(micro_op, SetterMicroOpType):
#         return PythonDict({
#             "type": "set",
#             "index": micro_op.key,
#             "params": PythonList([ micro_op.key, derich_type(micro_op.value_type, results) ])
#         })
#     if isinstance(micro_op, InsertStartMicroOpType):
#         return PythonDict({
#             "type": "insert-start",
#             "params": PythonList([ derich_type(micro_op.value_type, results), micro_op.type_error ])
#         })
#     if isinstance(micro_op, InsertEndMicroOpType):
#         return PythonDict({
#             "type": "insert-end",
#             "params": PythonList([ derich_type(micro_op.value_type, results), micro_op.type_error ])
#         })
#     if isinstance(micro_op, GetterWildcardMicroOpType):
#         return PythonDict({
#             "type": "get-wildcard",
#             "params": PythonList([ derich_type(micro_op.key_type, results), derich_type(micro_op.value_type, results), micro_op.key_error ])
#         })
#     if isinstance(micro_op, SetterWildcardMicroOpType):
#         return PythonDict({
#             "type": "set-wildcard",
#             "params": PythonList([ derich_type(micro_op.key_type, results), derich_type(micro_op.value_type, results), micro_op.key_error, micro_op.type_error ])
#         })
#     if isinstance(micro_op, DeletterWildcardMicroOpType):
#         return PythonDict({
#             "type": "delete-wildcard",
#             "params": PythonList([ derich_type(micro_op.key_type, results), micro_op.key_error ])
#         })
#     if isinstance(micro_op, RemoverWildcardMicroOpType):
#         return PythonDict({
#             "type": "remove-wildcard",
#             "params": PythonDict([ micro_op.key_error, micro_op.type_error ])
#         })
#     if isinstance(micro_op, InserterWildcardMicroOpType):
#         return PythonDict({
#             "type": "insert-wildcard",
#             "params": PythonDict([ derich_type(micro_op.key_type, results), micro_op.key_error, micro_op.type_error ])
#         })
#     if isinstance(micro_op, IterMicroOpType):
#         return PythonDict({
#             "type": "iter",
#             "params": PythonDict([ derich_type(micro_op.value_type, results) ])
#         })
# 
# def deconstruct_universal_type(type, results):
#     micro_ops = []
#     for key, micro_op_type in type.get_micro_op_types().items():
#         micro_ops.append(deconstruct_micro_op(micro_op_type, results))
# 
#     return PythonDict({
#         "type": "Universal",
#         "micro_ops": PythonList(micro_ops)
#     })

TYPES = {
    "Any": lambda data: AnyType(),
    "Bottom": lambda data: BottomType(),
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

# def deconstruct_function_type(type, results):
#     deconstructed_break_types = {}
#     for mode, break_types in type.break_types.items():
#         for break_type in break_types._to_list():
#             new_break_type = {
#                 "out": derich_type(break_type._get("out"), results)
#             }
#             if break_type._contains("in"):
#                 new_break_type["in"] = derich_type(break_type._get("in"), results)
# 
#         deconstructed_break_types[mode] = new_break_type
#     return PythonDict({
#         "type": "Function",
#         "argument": derich_type(type.argument_type, results),
#         "break_types": PythonDict(deconstructed_break_types)
#     })
# 
# def derich_type(type, results):
#     if id(type) in results:
#         return results[id(type)]
# 
#     if isinstance(type, AnyType):
#         return PythonDict({ "type": "Any" })
#     if isinstance(type, CompositeType):
#         return deconstruct_universal_type(type, results)
#     if isinstance(type, IntegerType):
#         return PythonDict({ "type": "Integer" })
#     if isinstance(type, BooleanType):
#         return PythonDict({ "type": "Boolean" })
#     if isinstance(type, NoValueType):
#         return PythonDict({ "type": "NoValue" })
#     if isinstance(type, StringType):
#         return PythonDict({ "type": "String" })
#     if isinstance(type, UnitType):
#         return PythonDict({ "type": "Integer", "value": type.value })
#     if isinstance(type, ClosedFunctionType):
#         return deconstruct_function_type(type, results)
#     raise FatalError(type)
