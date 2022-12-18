from lockdown.executor.flow_control import BreakException
from lockdown.type_system.composites import CompositeType, \
    is_type_bindable_to_value
from lockdown.type_system.core_types import Type, merge_types, Const, UnitType, \
    StringType, AnyType, unwrap_types, PermittedValuesDoesNotExist, NoValueType
from lockdown.type_system.exceptions import FatalError, InvalidDereferenceKey
from lockdown.type_system.managers import get_manager
from lockdown.type_system.reasoner import DUMMY_REASONER
from lockdown.type_system.universal_type import PythonDict, PythonObject, \
    UniversalDictType, UniversalObjectType, DEFAULT_READONLY_COMPOSITE_TYPE, \
    Universal
from lockdown.utils.utils import get_environment, MISSING, NO_VALUE


def evaluate(expression, context, frame_manager, hooks, immediate_context=None):
    if get_environment().return_value_optimization:
        # Optimized version that avoids creating a Capturer object, but only works for values
        try:
            mode, value, opcode, restart_type = expression.jump(context, frame_manager, hooks, immediate_context=immediate_context)
        except BreakException as b:
            if b.mode == "value":
                return b.value
            raise
        if mode == "value":
            return value
        raise BreakException(mode, value, opcode, restart_type)
    else:
        with frame_manager.capture("value") as result:
            result.attempt_capture_or_raise(*expression.jump(context, frame_manager, hooks, immediate_context=immediate_context))
        return result.value


def get_expression_break_types(expression, context, frame_manager, hooks, immediate_context=None):
    other_break_types = dict(expression.get_break_types(context, frame_manager, hooks, immediate_context))

    if get_environment().validate_flow_control:
        if not isinstance(other_break_types, dict):
            raise FatalError()
        for mode, break_types in other_break_types.items():
            if not isinstance(mode, str):
                raise FatalError()
            if not isinstance(break_types, (list, tuple)):
                raise FatalError()
            for break_type in break_types:
                if not isinstance(break_type, (dict, PythonDict)):
                    raise FatalError()
                if "out" not in break_type:
                    raise FatalError()
                if not isinstance(break_type["out"], Type):
                    raise FatalError()
                if "in" in break_type and not isinstance(break_type["in"], Type):
                    raise FatalError()

    target_break_types = other_break_types.pop("value", MISSING)
    return target_break_types, other_break_types


def flatten_out_types(break_types):
    if get_environment().opcode_bindings:
        if not isinstance(break_types, list):
            raise FatalError()
        for b in break_types:
            if not isinstance(b, (dict, PythonDict)):
                raise FatalError()
            if "out" not in b:
                raise FatalError()

    return merge_types([b["out"] for b in break_types], "super")


class OpcodeErrorType(object):
    def __init__(self, name, **params):
        self.name = name
        self.params = params
        for name, type in self.params.items():
            if not isinstance(name, str):
                raise FatalError()
            if not isinstance(type, Type):
                raise FatalError()

    def __call__(self, **kwargs):
        data = {
            "type": self.name
        }
        for key, value in kwargs.items():
            if not key in self.params:
                raise FatalError("{} not in {}".format(key, self.params))
            data[key] = value
        return PythonObject(data, debug_reason="type-error")

    def get_type(self, **param_values):
        properties = {
            "type": Const(UnitType(self.name))
        }
        for name, type in self.params.items():
            properties[name] = Const(type)
        for name, value in param_values.items():
            properties[name] = UnitType(value)
        return UniversalObjectType(properties, name="TypeError")

def get_operand_type(expression, context, frame_manager, hooks, break_types, immediate_context=None):
    value_type, other_break_types = get_expression_break_types(
        expression, context, frame_manager, hooks, immediate_context=immediate_context
    )
    break_types.merge(other_break_types)
    if value_type is not MISSING:
        value_type = flatten_out_types(value_type)
 
    return value_type

def each_reference(reference_types, of_types):
    if reference_types is MISSING or of_types is MISSING:
        return

    for reference_type in unwrap_types(reference_types):
        try:
            possible_references = reference_type.get_all_permitted_values()
        except PermittedValuesDoesNotExist:
            possible_references = None

        for of_type in unwrap_types(of_types):
            if possible_references is None:
                yield [ MISSING, of_type ]
                continue
            for possible_reference in possible_references:
                yield [ possible_reference, of_type ]

def get_best_micro_op(tags, type):
    for tag in tags:
        micro_op = type.get_micro_op_type(tag)
        if micro_op:
            return ( tag, micro_op )

    return ( None, None )

class MicroOpBinder(object):
    def __init__(self):
        self.bound = {}

    def bind(self, key, tags, type):
        if not isinstance(type, CompositeType):
            return

        tag, micro_op = get_best_micro_op(tags, type)
        if micro_op:
            self.bound[key] = ( tag, micro_op )

        return micro_op

    def get(self, keys):
        for key in keys:
            if key in self.bound:
                return self.bound[key]

        return ( None, None ) 

    def simple_bind(self):
        if len(self.bound) == 1:
            return list(self.bound.values())[0]

        return (None, None)

def get_context_type(context):
    if context is None:
        return NoValueType()
    manager = get_manager(context)
    if not hasattr(manager, "_context_type"):
        print("BAD")
    return manager._context_type
#    if context._contains("_types"):
#        return context._get("_types")
#    raise FatalError()

# def get_context_type(context):
#     if context is None:
#         return NoValueType()
#     context_manager = get_manager(context)
#     if not hasattr(context_manager, "_context_type"):
#         value_type = {}
#         if context is NO_VALUE:
#             return NoValueType()
#         if hasattr(context, "_types"):
#             if hasattr(context._types, "argument"):
#                 value_type["argument"] = context._types.argument
#             if hasattr(context._types, "local"):
#                 value_type["local"] = context._types.local
#             if hasattr(context._types, "outer"):
#                 value_type["outer"] = context._types.outer
#         if hasattr(context, "prepare"):
#             value_type["prepare"] = DEFAULT_READONLY_COMPOSITE_TYPE
#         if hasattr(context, "static"):
#             value_type["static"] = DEFAULT_READONLY_COMPOSITE_TYPE
#         context_manager._context_type = UniversalObjectType(value_type, name="context-type-{}".format(context_manager.debug_reason))
#
#     return context_manager._context_type

class ContextSearcher(object):
    def __init__(self, context, check_wildcards=False):
        self.context = context
        self.context_type = get_context_type(self.context)
        self.check_wildcards = check_wildcards

    def search_context_type_area_for_reference(self, reference, area_name, context, context_type, prepend_context, debug_info):
        from lockdown.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        area_getter = context_type.get_micro_op_type(("get", area_name))
        if not area_getter:
            return None
        area_type = area_getter.value_type
        if not isinstance(area_type, CompositeType):
            return None
        getter = area_type.get_micro_op_type(("get", reference))
        if getter:
            return [ *prepend_context, area_name ]

        if self.check_wildcards:
            area = area_getter.invoke(get_manager(context))
            wildcard_getter = area_type.get_micro_op_type(("get-wildcard", ))
            try:
                if wildcard_getter:
                    wildcard_getter.invoke(get_manager(area), reference)
                    return [ *prepend_context, area_name ]
            except InvalidDereferenceKey:
                pass

    def search_context_type_for_reference(self, reference, context, context_type, prepend_context, debug_info):
        from lockdown.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        if not isinstance(context_type, CompositeType):
            return None

        argument_search = self.search_context_type_area_for_reference(reference, "argument", context, context_type, prepend_context, debug_info)
        if argument_search:
            return argument_search
        local_search = self.search_context_type_area_for_reference(reference, "local", context, context_type, prepend_context, debug_info)
        if local_search:
            return local_search

        outer_getter = context_type.get_micro_op_type(("get", "outer"))
        if outer_getter:
            if self.check_wildcards:
                outer_context = outer_getter.invoke(get_manager(context))
            else:
                outer_context = None
            outer_search = self.search_context_type_for_reference(reference, outer_context, outer_getter.value_type, [ *prepend_context, "outer" ], debug_info)
            if outer_search:
                return outer_search

    def search_statics_for_reference(self, reference, context, prepend_context, debug_info):
        from lockdown.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        static = context._get("static", NO_VALUE)
        if static is not NO_VALUE and static._contains(reference):
            return [ *prepend_context, "static" ]

        prepare = context._get("prepare", NO_VALUE)
        if prepare is not NO_VALUE:
            prepare_search = self.search_statics_for_reference(reference, prepare, [ *prepend_context, "prepare" ], debug_info)
            if prepare_search:
                return prepare_search

    def search_for_reference(self, reference, debug_info):
        from lockdown.executor.raw_code_factories import dereference_op, assignment_op, \
            literal_op, dereference, context_op

        if not isinstance(reference, str):
            raise FatalError()

        if reference in ("prepare", "local", "argument", "outer", "static"):
            return [], False

        types_search = self.search_context_type_for_reference(reference, self.context, self.context_type, [], debug_info)
        if types_search:
            return types_search, False
        statics_search = self.search_statics_for_reference(reference, self.context, [], debug_info)
        if statics_search:
            return statics_search, True

        return None, False

