from lockdown.executor.flow_control import BreakException
from lockdown.type_system.composites import CompositeType, \
    is_type_bindable_to_value
from lockdown.type_system.core_types import Type, merge_types, Const, UnitType, \
    StringType, AnyType, unwrap_types, PermittedValuesDoesNotExist
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.universal_type import PythonDict, PythonObject, \
    UniversalDictType, UniversalObjectType
from lockdown.utils.utils import get_environment, MISSING
from lockdown.type_system.reasoner import DUMMY_REASONER


def evaluate(expression, context, frame_manager, immediate_context=None):
    if get_environment().return_value_optimization:
        # Optimized version that avoids creating a Capturer object, but only works for values
        try:
            mode, value, opcode, restart_type = expression.jump(context, frame_manager, immediate_context=immediate_context)
        except BreakException as b:
            if b.mode == "value":
                return b.value
            raise
        if mode == "value":
            return value
        raise BreakException(mode, value, opcode, restart_type)
    else:
        with frame_manager.capture("value") as result:
            result.attempt_capture_or_raise(*expression.jump(context, frame_manager, immediate_context=immediate_context))
        return result.value


def get_expression_break_types(expression, context, frame_manager, immediate_context=None):
    other_break_types = dict(expression.get_break_types(context, frame_manager, immediate_context))

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


class TypeErrorFactory(object):
    def __init__(self, message):
        self.message = message

    def __call__(self, message=None, **kwargs):
        data = {
            "type": "TypeError",
            "message": message or self.message,
            "kwargs": PythonDict(kwargs)
        }
        return PythonObject(data, bind=self.get_type(message), debug_reason="type-error")

    def get_type(self, message=None):
        properties = {
            "type": Const(UnitType("TypeError")),
            "message": Const(UnitType(message or self.message)),
            "kwargs": Const(UniversalDictType(StringType(), AnyType()))
        }
        return UniversalObjectType(properties, wildcard_type=AnyType(), name="TypeError")

def get_operand_type(expression, context, frame_manager, break_types, immediate_context=None):
    value_type, other_break_types = get_expression_break_types(
        expression, context, frame_manager, immediate_context=immediate_context
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
