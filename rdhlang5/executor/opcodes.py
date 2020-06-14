# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from _collections import defaultdict
from abc import abstractmethod

from log import logger
from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.flow_control import BreakTypesFactory, BreakException
from rdhlang5.executor.function_type import OpenFunctionType, ClosedFunctionType
from rdhlang5.executor.type_factories import enrich_type
from rdhlang5.type_system.composites import CompositeType
from rdhlang5.type_system.core_types import AnyType, Type, merge_types, Const, \
    UnitType, NoValueType, AllowedValuesNotAvailable, unwrap_types, IntegerType, \
    BooleanType, remove_type
from rdhlang5.type_system.default_composite_types import rich_composite_type
from rdhlang5.type_system.dict_types import RDHDict, DictGetterType, \
    DictSetterType, DictWildcardGetterType, DictWildcardSetterType
from rdhlang5.type_system.exceptions import FatalError, InvalidDereferenceType, \
    InvalidDereferenceKey, InvalidAssignmentType, InvalidAssignmentKey
from rdhlang5.type_system.list_types import RDHList, ListGetterType, \
    ListSetterType, ListWildcardGetterType, ListWildcardSetterType, \
    ListWildcardDeletterType, ListInsertType, ListWildcardInsertType
from rdhlang5.type_system.managers import get_type_of_value, get_manager
from rdhlang5.type_system.object_types import RDHObject, RDHObjectType, \
    ObjectGetterType, ObjectSetterType, ObjectWildcardGetterType, \
    ObjectWildcardSetterType
from rdhlang5.utils import MISSING, NO_VALUE, is_debug, one_shot_memoize
from pydoc import visiblename

EVALUATE_CAPTURE_TYPES = { "out": AnyType() }


def evaluate(expression, context, frame_manager, immediate_context=None):
    if not is_debug():
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


def get_expression_break_types(expression, context, frame_manager, immediate_context=None, target_break_mode="value"):
    other_break_types = dict(expression.get_break_types(context, frame_manager, immediate_context))

    if is_debug():
        if not isinstance(other_break_types, dict):
            raise FatalError()
        for mode, break_types in other_break_types.items():
            if not isinstance(mode, basestring):
                raise FatalError()
            if not isinstance(break_types, (list, tuple)):
                raise FatalError()
            for break_type in break_types:
                if not isinstance(break_type, (dict, RDHDict)):
                    raise FatalError()
                if "out" not in break_type:
                    raise FatalError()
                if not isinstance(break_type["out"], Type):
                    raise FatalError()
                if "in" in break_type and not isinstance(break_type["in"], Type):
                    raise FatalError()

    target_break_types = other_break_types.pop(target_break_mode, MISSING)
    return target_break_types, other_break_types


def flatten_out_types(break_types):
    if is_debug():
        if not isinstance(break_types, list):
            raise FatalError()
        for b in break_types:
            if not isinstance(b, dict):
                raise FatalError()
            if "out" not in b:
                raise FatalError()

    return merge_types([b["out"] for b in break_types], "super")


class TypeErrorFactory(object):
    def __init__(self, message=None):
        self.message = message

    def __call__(self, **kwargs):
        data = {
            "type": "TypeError",
        }
        message = self.message
        if message:
            message = self.message.format(**kwargs)
            data["message"] = message
        return RDHObject(data, bind=self.get_type(**kwargs), debug_reason="type-error")

    def get_type(self, **kwargs):
        properties = {
            "type": Const(UnitType("TypeError"))
        }
        message = self.message
        if message:
            message = self.message.format(**kwargs)
            properties["message"] = Const(UnitType(message))
        return RDHObjectType(properties, name=message)


class Opcode(object):
    def __init__(self, data, visitor):
        self.data = data
        self.allowed_break_types = None
        self._is_restartable = None

#    __metaclass__ = ABCMeta

    @abstractmethod
    def get_break_types(self, context, frame_manager, immediate_context=None):
        raise NotImplementedError()

    @abstractmethod
    def jump(self, context, frame_manager, immediate_context=None):
        raise NotImplementedError()

    @property
    def is_restartable(self):
        if self._is_restartable is None:
            if not self.allowed_break_types:
                return True
            for break_types in self.allowed_break_types.values():
                for break_type in break_types:
                    if "in" in break_type:
                        self._is_restartable = True
                        return True
            self._is_restartable = False
        return self._is_restartable

    def get_line_and_column(self):
        return getattr(self.data, "line", None), getattr(self.data, "column", None)

    def to_code(self):
        return str(type(self))


class Nop(Opcode):
    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)
        break_types.add("value", NoValueType())
        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            return frame.value(NO_VALUE)

    def to_code(self):
        return "nop"


class LiteralOp(Opcode):
    def __init__(self, data, visitor):
        super(LiteralOp, self).__init__(data, visitor)
        self.value = data.value
        self.type = get_type_of_value(self.value)

    def get_break_types(self, context, frame_manager, immediate_context=None):
        if self.value == 42:
            pass
        break_types = BreakTypesFactory(self)
        break_types.add("value", self.type)
        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            return frame.value(self.value)

    def __str__(self):
        return "LiteralOp<{}>".format(self.value)

    def to_code(self):
        return self.value


class ObjectTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(ObjectTemplateOp, self).__init__(data, visitor)
        self.opcodes = { key: enrich_opcode(opcode, visitor) for key, opcode in data.opcodes.items() }

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        micro_ops = {}
        initial_data = {}

        all_value_types = []

        for key, opcode in self.opcodes.items():
            value_type, other_break_types = get_expression_break_types(opcode, context, frame_manager)
            break_types.merge(other_break_types)

            if value_type is MISSING:
                continue

            value_type = flatten_out_types(value_type)
            all_value_types.append(value_type)

            micro_ops[("get", key)] = ObjectGetterType(key, value_type, False, False)
            micro_ops[("set", key)] = ObjectSetterType(key, AnyType(), False, False)

            initial_value = MISSING

            if isinstance(value_type, CompositeType) and value_type.initial_data:
                initial_value = value_type.initial_data

            try:
                allowed_values = value_type.get_allowed_values()
                if len(allowed_values) == 1:
                    initial_value = allowed_values[0]
            except AllowedValuesNotAvailable:
                pass

            if initial_value is not MISSING:
                initial_data[key] = initial_value

        combined_value_types = merge_types(all_value_types, "exact")

        micro_ops[("get-wildcard",)] = ObjectWildcardGetterType(combined_value_types, True, False)
        micro_ops[("set-wildcard",)] = ObjectWildcardSetterType(AnyType(), True, True)

        break_types.add("value", CompositeType(micro_ops, initial_data=initial_data, is_revconst=True))

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            result = {}
            for key, opcode in self.opcodes.items():
                result[key] = frame.step(key, lambda: evaluate(opcode, context, frame_manager))

            return frame.value(RDHObject(result, debug_reason="object-template"))


class DictTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(DictTemplateOp, self).__init__(data, visitor)
        self.opcodes = { key: enrich_opcode(opcode, visitor) for key, opcode in data.opcodes.items() }

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        micro_ops = {}
        initial_data = {}

        for key, opcode in self.opcodes.items():
            value_type, other_break_types = get_expression_break_types(opcode, context, frame_manager)
            break_types.merge(other_break_types)
            value_type = flatten_out_types(value_type)

            micro_ops[("get", key)] = DictGetterType(key, value_type, False, False)
            micro_ops[("set", key)] = DictSetterType(key, AnyType(), False, False)

            initial_value = MISSING

            if isinstance(value_type, CompositeType) and value_type.initial_data:
                initial_value = value_type.initial_data

            try:
                allowed_values = value_type.get_allowed_values()
                if len(allowed_values) == 1:
                    initial_value = allowed_values[0]
            except AllowedValuesNotAvailable:
                pass

            if initial_value is not MISSING:
                initial_data[key] = initial_value

        micro_ops[("get-wildcard",)] = DictWildcardGetterType(rich_composite_type, True, False)
        micro_ops[("set-wildcard",)] = DictWildcardSetterType(rich_composite_type, True, True)

        break_types.add("value", CompositeType(micro_ops, initial_data=initial_data, is_revconst=True))

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            result = {}
            for key, opcode in self.opcodes.items():
                result[key] = frame.step(key, lambda: evaluate(opcode, context, frame_manager))

            return frame.value(RDHDict(result))


class ListTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(ListTemplateOp, self).__init__(data, visitor)
        self.opcodes = [ enrich_opcode(opcode, visitor) for opcode in data.opcodes ]

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        micro_ops = {}
        initial_data = {}

        all_value_types = []

        for index, opcode in enumerate(self.opcodes):
            value_type, other_break_types = get_expression_break_types(opcode, context, frame_manager)
            break_types.merge(other_break_types)
            value_type = flatten_out_types(value_type)
            all_value_types.append(value_type)

            micro_ops[("get", index)] = ListGetterType(index, value_type, False, False)
            micro_ops[("set", index)] = ListSetterType(index, AnyType(), False, False)

            initial_value = MISSING

            if isinstance(value_type, CompositeType) and value_type.initial_data:
                initial_value = value_type.initial_data

            try:
                allowed_values = value_type.get_allowed_values()
                if len(allowed_values) == 1:
                    initial_value = allowed_values[0]
            except AllowedValuesNotAvailable:
                pass

            if initial_value is not MISSING:
                initial_data[index] = initial_value

        if len(all_value_types) == 0:
            all_value_types.append(AnyType())

        combined_value_types = merge_types(all_value_types, "exact")

        micro_ops[("get-wildcard",)] = ListWildcardGetterType(combined_value_types, True, False)
        micro_ops[("set-wildcard",)] = ListWildcardSetterType(AnyType(), True, True)
        micro_ops[("insert", 0)] = ListInsertType(AnyType(), 0, False, False)
        micro_ops[("delete-wildcard",)] = ListWildcardDeletterType(True)
        micro_ops[("insert-wildcard",)] = ListWildcardInsertType(AnyType(), True, False)

        break_types.add("value", CompositeType(micro_ops, initial_data=initial_data, is_revconst=True))

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            result = []
            for index, opcode in enumerate(self.opcodes):
                new_value = frame.step(index, lambda: evaluate(opcode, context, frame_manager))
                result.append(new_value)

            return frame.value(RDHList(result))


def get_context_type(context):
    if context is None:
        return NoValueType()
    context_manager = get_manager(context)
    if not hasattr(context_manager, "_context_type"):
        value_type = {}
        if context is NO_VALUE:
            return NoValueType()
        if hasattr(context, "types"):
            if hasattr(context.types, "argument"):
                value_type["argument"] = context.types.argument
            if hasattr(context.types, "local"):
                value_type["local"] = context.types.local
            if hasattr(context.types, "outer"):
                value_type["outer"] = context.types.outer
        if hasattr(context, "prepare"):
            value_type["prepare"] = get_type_of_value(context.prepare)
        if hasattr(context, "static"):
            value_type["static"] = get_type_of_value(context.static)
        context_manager._context_type = RDHObjectType(value_type, name="context-type-{}".format(context_manager.debug_reason))

    return context_manager._context_type


class ContextOp(Opcode):
    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)
        break_types.add("value", get_context_type(context))
        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            return frame.value(context)

    def __str__(self):
        return "Context"

    def to_code(self):
        return "Context"


class DereferenceOp(Opcode):
    INVALID_DEREFERENCE = TypeErrorFactory("DereferenceOp: invalid_dereference {reference}")

    def __init__(self, data, visitor):
        super(DereferenceOp, self).__init__(data, visitor)
        self.of = enrich_opcode(data.of, visitor)
        self.reference = enrich_opcode(data.reference, visitor)
        self.direct_micro_ops = {}
        self.wildcard_micro_ops = {}

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        reference_types, reference_break_types = get_expression_break_types(self.reference, context, frame_manager)
        break_types.merge(reference_break_types)
        if reference_types is not MISSING:
            reference_types = flatten_out_types(reference_types)

        of_types, of_break_types = get_expression_break_types(self.of, context, frame_manager)
        break_types.merge(of_break_types)
        if of_types is not MISSING:
            of_types = flatten_out_types(of_types)

        invalid_dereferences = set()

        if reference_types is not MISSING and of_types is not MISSING:
            for of_type in unwrap_types(of_types):
                if isinstance(of_type, CompositeType):
                    try:
                        for reference_type in unwrap_types(reference_types):
                            for reference in reference_type.get_allowed_values():
                                micro_op = of_type.get_micro_op_type(("get", reference))
                                if micro_op:
                                    self.direct_micro_ops[reference] = micro_op
                                if micro_op is None:
                                    micro_op = of_type.get_micro_op_type(("get-wildcard",))
                                    if micro_op:
                                        self.wildcard_micro_ops[reference] = micro_op

                                if micro_op:
                                    break_types.add("value", micro_op.type)
                                    if micro_op.type_error or micro_op.key_error:
                                        invalid_dereferences.add(reference)
                                else:
                                    invalid_dereferences.add(reference)
                    except AllowedValuesNotAvailable:
                        invalid_dereferences.add(reference)
                elif of_type is not MISSING:
                    break_types.add("value", AnyType())

        self.invalid_dereference_error = len(list(invalid_dereferences)) > 0

        for invalid_dereference in invalid_dereferences:
            break_types.add("exception", self.INVALID_DEREFERENCE.get_type(reference=invalid_dereference), opcode=self)

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            of = frame.step("of", lambda: evaluate(self.of, context, frame_manager))
            reference = frame.step("reference", lambda: evaluate(self.reference, context, frame_manager))

#            print "{}".format(reference)

            manager = get_manager(of)

            if manager is None:
                return frame.exception(self.INVALID_DEREFERENCE(reference=reference))

            try:
                direct_micro_op_type = self.direct_micro_ops.get(reference, None)
                if direct_micro_op_type:
                    if not is_debug():
                        return frame.value(direct_micro_op_type.invoke(manager, True))
                    micro_op = direct_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(trust_caller=True))

                wildcard_micro_op_type = self.wildcard_micro_ops.get(reference, None)
                if wildcard_micro_op_type:
                    if not is_debug():
                        return frame.value(wildcard_micro_op_type.invoke(manager, reference, True))
                    micro_op = wildcard_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(reference, trust_caller=True))

                direct_micro_op_type = manager.get_micro_op_type(("get", reference))
                if direct_micro_op_type:
                    micro_op = direct_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(trust_caller=True))
 
                wildcard_micro_op_type = manager.get_micro_op_type(("get-wildcard",))
                if wildcard_micro_op_type:
                    micro_op = wildcard_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(reference, trust_caller=True))

                return frame.exception(self.INVALID_DEREFERENCE(reference=reference))
            except InvalidDereferenceType:
                return frame.exception(self.INVALID_DEREFERENCE(reference=reference))
            except InvalidDereferenceKey:
                return frame.exception(self.INVALID_DEREFERENCE(reference=reference))

    def __str__(self):
        return "{}.{}".format(self.of, self.reference)

    def to_code(self):
        return "{}.{}".format(self.of.to_code(), self.reference.to_code())


class DynamicDereferenceOp(Opcode):
    INVALID_DEREFERENCE = TypeErrorFactory("DynamicDereferenceOp: invalid_dereference")

    def __init__(self, data, visitor):
        super(DynamicDereferenceOp, self).__init__(data, visitor)
        self.reference = data.reference

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        break_types.add("exception", self.INVALID_DEREFERENCE.get_type(reference=self.reference))

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        raise FatalError(self.reference)


class AssignmentOp(Opcode):
    INVALID_LVALUE = TypeErrorFactory("AssignmentOp: invalid_lvalue")
    INVALID_RVALUE = TypeErrorFactory("AssignmentOp: invalid_rvalue")
    INVALID_ASSIGNMENT = TypeErrorFactory("AssignmentOp: invalid_assignment")

    def __init__(self, data, visitor):
        super(AssignmentOp, self).__init__(data, visitor)
        self.of = enrich_opcode(data.of, visitor)
        self.reference = enrich_opcode(data.reference, visitor)
        self.rvalue = enrich_opcode(data.rvalue, visitor)
        self.direct_micro_ops = {}
        self.wildcard_micro_ops = {}

    @one_shot_memoize
    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        reference_types, reference_break_types = get_expression_break_types(self.reference, context, frame_manager)
        break_types.merge(reference_break_types)
        if reference_types is not MISSING:
            reference_types = flatten_out_types(reference_types)

        of_types, of_break_types = get_expression_break_types(self.of, context, frame_manager)
        break_types.merge(of_break_types)
        if of_types is not MISSING:
            of_types = flatten_out_types(of_types)

        rvalue_type, rvalue_break_types = get_expression_break_types(self.rvalue, context, frame_manager)
        break_types.merge(rvalue_break_types)
        if rvalue_type is not MISSING:
            rvalue_type = flatten_out_types(rvalue_type)

        self.invalid_assignment_error = self.invalid_rvalue_error = self.invalid_lvalue_error = False

        if reference_types is not MISSING and of_types is not MISSING and rvalue_type is not MISSING:
            for reference_type in unwrap_types(reference_types):
                try:
                    for reference in reference_type.get_allowed_values():    
                        for of_type in unwrap_types(of_types):
                            micro_op = None
                            if isinstance(of_type, CompositeType) and reference is not None:
                                micro_op = of_type.get_micro_op_type(("set", reference))
                                if micro_op:
                                    self.direct_micro_ops[reference] = micro_op

                                if not micro_op:
                                    micro_op = of_type.get_micro_op_type(("set-wildcard",))
                                    if micro_op:
                                        self.wildcard_micro_ops[reference] = micro_op

                            if micro_op:
                                if not micro_op.type.is_copyable_from(rvalue_type):
                                    micro_op.type.is_copyable_from(rvalue_type)
                                    self.invalid_rvalue_error = True

                                break_types.add("value", NoValueType())

                                if micro_op.type_error or micro_op.key_error:
                                    self.invalid_assignment_error = True
                            else:
                                self.invalid_lvalue_error = True
                except AllowedValuesNotAvailable:
                    self.invalid_lvalue_error = True
        else:
            self.invalid_assignment_error = self.invalid_rvalue_error = self.invalid_lvalue_error = True

        if self.invalid_assignment_error:
            break_types.add("exception", self.INVALID_ASSIGNMENT.get_type())
        if self.invalid_rvalue_error:
            break_types.add("exception", self.INVALID_RVALUE.get_type())
        if self.invalid_lvalue_error:
            break_types.add("exception", self.INVALID_LVALUE.get_type())

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            of = frame.step("of", lambda: evaluate(self.of, context, frame_manager))
            reference = frame.step("reference", lambda: evaluate(self.reference, context, frame_manager))
            rvalue = frame.step("rvalue", lambda: evaluate(self.rvalue, context, frame_manager))

            #print "{} = {}".format(reference, rvalue)

            manager = get_manager(of)

            try:
                direct_micro_op_type = self.direct_micro_ops.get(reference, None)
                if direct_micro_op_type:
                    if (is_debug() or self.invalid_rvalue_error) and not direct_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
                        return frame.exception(self.INVALID_RVALUE())

                    if not is_debug():
                        return frame.value(direct_micro_op_type.invoke(manager, rvalue, True))
                    micro_op = direct_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(rvalue, trust_caller=True))

                wildcard_micro_op_type = self.wildcard_micro_ops.get(reference, None)
                if wildcard_micro_op_type:
                    if (is_debug() or self.invalid_rvalue_error) and not wildcard_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
                        return frame.exception(self.INVALID_RVALUE())

                    if not is_debug():
                        return frame.value(direct_micro_op_type.invoke(manager, rvalue, True))
                    micro_op = wildcard_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(reference, rvalue, trust_caller=True))
 
#                 direct_micro_op_type = manager.get_micro_op_type(("set", reference))
#                 if direct_micro_op_type:
#                     if (is_debug() or self.invalid_rvalue_error) and not direct_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
#                         return frame.exception(self.INVALID_RVALUE())
# 
#                     micro_op = direct_micro_op_type.create(manager)
#                     return frame.value(micro_op.invoke(rvalue, trust_caller=True))
# 
#                 wildcard_micro_op_type = manager.get_micro_op_type(("set-wildcard",))
#                 if wildcard_micro_op_type:
#                     if (is_debug() or self.invalid_rvalue_error) and not wildcard_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
#                         return frame.exception(self.INVALID_RVALUE())
# 
#                     micro_op = wildcard_micro_op_type.create(manager)
#                     return frame.value(micro_op.invoke(reference, rvalue, trust_caller=True))

                return frame.exception(self.INVALID_LVALUE())
            except InvalidAssignmentType:
                return frame.exception(self.INVALID_ASSIGNMENT())
            except InvalidAssignmentKey:
                return frame.exception(self.INVALID_ASSIGNMENT())

    def to_code(self):
        return "{}.{} = {}".format(self.of.to_code(), self.reference.to_code(), self.rvalue.to_code())


class InsertOp(Opcode):
    INVALID_LVALUE = TypeErrorFactory("InsertOp: invalid_lvalue")
    INVALID_RVALUE = TypeErrorFactory("InsertOp: invalid_rvalue")
    INVALID_ASSIGNMENT = TypeErrorFactory("InsertOp: invalid_assignment")

    def __init__(self, data, visitor):
        super(InsertOp, self).__init__(data, visitor)
        self.of = enrich_opcode(data.of, visitor)
        self.reference = enrich_opcode(data.reference, visitor)
        self.rvalue = enrich_opcode(data.rvalue, visitor)
        self.direct_micro_ops = {}
        self.wildcard_micro_ops = {}

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        reference_types, reference_break_types = get_expression_break_types(self.reference, context, frame_manager)
        break_types.merge(reference_break_types)
        if reference_types is not MISSING:
            reference_types = flatten_out_types(reference_types)

        of_types, of_break_types = get_expression_break_types(self.of, context, frame_manager)
        break_types.merge(of_break_types)
        if of_types is not MISSING:
            of_types = flatten_out_types(of_types)

        rvalue_type, rvalue_break_types = get_expression_break_types(self.rvalue, context, frame_manager)
        break_types.merge(rvalue_break_types)
        if rvalue_type is not MISSING:
            rvalue_type = flatten_out_types(rvalue_type)

        self.invalid_assignment_error = False
        self.invalid_rvalue_error = False
        self.invalid_lvalue_error = False

        if reference_types is not MISSING and of_types is not MISSING and rvalue_type is not MISSING:
            for reference_type in unwrap_types(reference_types):
                try:
                    for reference in reference_type.get_allowed_values():    
                        for of_type in unwrap_types(of_types):
                            micro_op = None
                            if isinstance(of_type, CompositeType) and reference is not None:
                                micro_op = of_type.get_micro_op_type(("insert", reference))
                                if micro_op:
                                    self.direct_micro_ops[reference] = micro_op

                                if not micro_op:
                                    micro_op = of_type.get_micro_op_type(("insert-wildcard",))
                                    if micro_op:
                                        self.wildcard_micro_ops[reference] = micro_op

                            if micro_op:
                                if not micro_op.type.is_copyable_from(rvalue_type):
                                    self.invalid_rvalue_error = True

                                break_types.add("value", NoValueType())

                                if micro_op.type_error or micro_op.key_error:
                                    self.invalid_assignment_error = True
                            else:
                                self.invalid_lvalue_error = True
                except AllowedValuesNotAvailable:
                    self.invalid_lvalue_error = True

        if self.invalid_assignment_error:
            break_types.add("exception", self.INVALID_ASSIGNMENT.get_type())
        if self.invalid_rvalue_error:
            break_types.add("exception", self.INVALID_RVALUE.get_type())
        if self.invalid_lvalue_error:
            break_types.add("exception", self.INVALID_LVALUE.get_type())

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            of = frame.step("of", lambda: evaluate(self.of, context, frame_manager))
            reference = frame.step("reference", lambda: evaluate(self.reference, context, frame_manager))
            rvalue = frame.step("rvalue", lambda: evaluate(self.rvalue, context, frame_manager))

            manager = get_manager(of)

            try:
                direct_micro_op_type = self.direct_micro_ops.get(reference, None)
                if direct_micro_op_type:
                    if self.invalid_rvalue_error and not direct_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
                        return frame.exception(self.INVALID_RVALUE())

                    micro_op = direct_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(rvalue, trust_caller=True))

                wildcard_micro_op_type = self.wildcard_micro_ops.get(reference, None)
                if wildcard_micro_op_type:
                    if self.invalid_rvalue_error and not wildcard_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
                        return frame.exception(self.INVALID_RVALUE())

                    micro_op = wildcard_micro_op_type.create(manager)
                    return frame.value(micro_op.invoke(reference, rvalue, trust_caller=True))

#                 direct_micro_op_type = manager.get_micro_op_type(("insert", reference))
#                 if direct_micro_op_type:
#                     if self.invalid_rvalue_error and not direct_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
#                         return frame.exception(self.INVALID_RVALUE())
# 
#                     micro_op = direct_micro_op_type.create(manager)
#                     return frame.value(micro_op.invoke(rvalue, trust_caller=True))
# 
#                 wildcard_micro_op_type = manager.get_micro_op_type(("insert-wildcard",))
#                 if wildcard_micro_op_type:
#                     if self.invalid_rvalue_error and not wildcard_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
#                         return frame.exception(self.INVALID_RVALUE())
# 
#                     micro_op = wildcard_micro_op_type.create(manager)
#                     return frame.value(micro_op.invoke(reference, rvalue, trust_caller=True))

                return frame.exception(self.INVALID_LVALUE())
            except InvalidAssignmentType:
                return frame.exception(self.INVALID_ASSIGNMENT())
            except InvalidAssignmentKey:
                return frame.exception(self.INVALID_ASSIGNMENT())


def BinaryOp(name, symbol, func, argument_type, result_type):
    class _BinaryOp(Opcode):
        MISSING_OPERANDS = TypeErrorFactory("{}: missing_integers".format(name))

        def __init__(self, data, visitor):
            super(_BinaryOp, self).__init__(data, visitor)
            self.lvalue = enrich_opcode(self.data.lvalue, visitor)
            self.rvalue = enrich_opcode(self.data.rvalue, visitor)
            self.missing_operands_exception = True

        def get_break_types(self, context, frame_manager, immediate_context=None):
            break_types = BreakTypesFactory(self)

            lvalue_type, lvalue_break_types = get_expression_break_types(self.lvalue, context, frame_manager)
            if lvalue_type is not MISSING:
                lvalue_type = flatten_out_types(lvalue_type)
            break_types.merge(lvalue_break_types)

            rvalue_type, rvalue_break_types = get_expression_break_types(self.rvalue, context, frame_manager)
            if rvalue_type is not MISSING:
                rvalue_type = flatten_out_types(rvalue_type)
            break_types.merge(rvalue_break_types)

            if lvalue_type is not MISSING and rvalue_type is not MISSING:
                break_types.add("value", result_type)
            self.missing_operands_exception = False
            if not argument_type.is_copyable_from(lvalue_type) or not argument_type.is_copyable_from(rvalue_type):
                self.missing_operands_exception = True
                break_types.add("exception", self.MISSING_OPERANDS.get_type())

            return break_types.build()

        def jump(self, context, frame_manager, immediate_context=None):
            with frame_manager.get_next_frame(self) as frame:
                def get_lvalue():
                    lvalue = frame.step("lvalue", lambda: evaluate(self.lvalue, context, frame_manager))
                    if self.missing_operands_exception and not argument_type.is_copyable_from(get_type_of_value(lvalue)):
                        raise BreakException(*frame.exception(self.MISSING_OPERANDS()))
                    return lvalue
    
                def get_rvalue():
                    rvalue = frame.step("rvalue", lambda: evaluate(self.rvalue, context, frame_manager))
                    if self.missing_operands_exception and not argument_type.is_copyable_from(get_type_of_value(rvalue)):
                        raise BreakException(*frame.exception(self.MISSING_OPERANDS()))
                    return rvalue

#                print "{} {} {}".format(get_lvalue(), symbol, get_rvalue())

                return frame.value(func(get_lvalue, get_rvalue))

        def to_code(self):
            return "{} {} {}".format(self.lvalue.to_code(), symbol, self.rvalue.to_code())

    return _BinaryOp


class TransformOp(Opcode):
    def __init__(self, data, visitor):
        super(TransformOp, self).__init__(data, visitor)
        if hasattr(self.data, "code"):
            self.expression = enrich_opcode(self.data.code, visitor)
            if not hasattr(self.data, "input"):
                raise PreparationException("input missing in transform opcode")
            self.input = self.data.input
        else:
            self.expression = None
            self.input = None

        if not hasattr(self.data, "output"):
            raise PreparationException("output missing in transform opcode")
        self.output = self.data.output

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        if self.expression:
            expression_break_types = dict(self.expression.get_break_types(context, frame_manager))
            if self.input in expression_break_types:
                expression_break_types[self.output] = expression_break_types.pop(self.input)
            break_types.merge(expression_break_types)
        else:
            break_types.add(self.output, NoValueType())

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            if self.expression:
                with frame_manager.capture(self.input) as capture_result:
                    capture_result.attempt_capture_or_raise(*self.expression.jump(context, frame_manager))

                return frame.unwind(self.output, capture_result.value, None)
            else:
                return frame.unwind(self.output, NO_VALUE, None)
        raise FatalError()

    def to_code(self):
        return "transform({} -> {}\n {}\n)".format(self.input, self.output, self.expression.to_code())


class ShiftOp(Opcode):
    def __init__(self, data, visitor):
        super(ShiftOp, self).__init__(data, visitor)
        self.opcode = enrich_opcode(data.code, visitor)
        self.restart_type = enrich_opcode(data.restart_type, visitor)

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        value_type, other_break_types = get_expression_break_types(self.opcode, context, frame_manager, immediate_context) 
        restart_type_value = evaluate(self.restart_type, context, frame_manager)
        self.restart_type = enrich_type(restart_type_value)

        value_type = flatten_out_types(value_type)
        break_types.merge(other_break_types)

        break_types.add("yield", value_type, self.restart_type)
        break_types.add("value", self.restart_type)

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            if frame.has_restart_value():
                restart_value = frame.pop_restart_value()

                if is_debug():
                    if not self.restart_type.is_copyable_from(get_type_of_value(restart_value)):
                        raise FatalError()

                return frame.unwind("value", restart_value, None)

            value = evaluate(self.opcode, context, frame_manager)

            return frame.yield_(value, self.restart_type)


class ResetOp(Opcode):
    MISSING_IN_BREAK_TYPE = TypeErrorFactory("ResetOp: missing_in_break_type")

    def __init__(self, data, visitor):
        super(ResetOp, self).__init__(data, visitor)
        if hasattr(data, "code"):
            self.opcode = enrich_opcode(data.code, visitor)
            self.function = None
            self.argument = None
        else:
            self.opcode = None
            self.function = enrich_opcode(data.function, visitor)
            self.argument = enrich_opcode(data.argument, visitor)

    def get_value_and_continuation_block_type(self, out_break_type, in_break_type, continuation_break_types):
        return RDHObjectType({
            "value": Const(out_break_type),
            "continuation": Const(ClosedFunctionType(in_break_type, continuation_break_types))
        })

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        if self.opcode:
            opcode_break_types = dict(self.opcode.get_break_types(context, frame_manager))
            self.continuation_break_types = dict(opcode_break_types)
            yield_break_types = opcode_break_types.pop("yield", [])
            break_types.merge(opcode_break_types)
        else:
            function_type, function_break_types = get_expression_break_types(self.function, context, frame_manager)
            function_type = flatten_out_types(function_type)
            break_types.merge(function_break_types)

            self.continuation_break_types = function_type.break_types
            function_break_types = dict(function_type.break_types)
            yield_break_types = function_break_types.pop("yield", [])
            break_types.merge(function_break_types)

        missing_in_error = False

        for yield_break_type in yield_break_types:
            if "in" not in yield_break_type:
                missing_in_error = True
            break_types.add(
                "yield",
                self.get_value_and_continuation_block_type(
                    yield_break_type["out"], yield_break_type["in"], self.continuation_break_types
                )
            )

        if missing_in_error:
            break_types.add("exception", self.MISSING_IN_BREAK_TYPE.get_type(), opcode=self)

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        from rdhlang5.executor.function import Continuation

        with frame_manager.get_next_frame(self) as frame:
            if self.opcode:
                def enter_expression():
                    return self.opcode.jump(context, frame_manager)
                with frame_manager.capture("yield") as capture_result:
                    capture_result.attempt_capture_or_raise(*enter_expression())

                if capture_result.caught_frames is MISSING:
                    return frame.exception(self.MISSING_IN_BREAK_TYPE())

                restart_continuation = capture_result.create_continuation(
                    enter_expression, self.continuation_break_types
                )
            else:
                argument = frame.step("argument", lambda: evaluate(self.argument, context, frame_manager))
                function = frame.step("function", lambda: evaluate(self.function, context, frame_manager))

                def enter_function():
                    return function.invoke(argument, frame_manager)

                with frame_manager.capture("yield") as capture_result:
                    capture_result.attempt_capture_or_raise(*enter_function())

                if capture_result.caught_frames is MISSING:
                    return frame.exception(self.MISSING_IN_BREAK_TYPE())

                if isinstance(function, Continuation):
                    # Avoid using enter_function as the callback, hook into the original
                    # continuation callback, avoiding an infinite chain of linked callbacks.
                    restart_continuation = capture_result.create_continuation(
                        function.callback, self.continuation_break_types
                    )
                else:
                    restart_continuation = capture_result.create_continuation(
                        enter_function, self.continuation_break_types
                    )

            restart_continuation_type = restart_continuation.get_type()

            result = RDHObject({
                "value": capture_result.value,
                "continuation": restart_continuation
            }, bind=self.get_value_and_continuation_block_type(
                get_type_of_value(capture_result.value),
                restart_continuation_type.argument_type,
                restart_continuation_type.break_types
            ))

            return frame.yield_(result)


class CommaOp(Opcode):
    def __init__(self, data, visitor):
        super(CommaOp, self).__init__(data, visitor)
        self.opcodes = [ enrich_opcode(o, visitor) for o in data.opcodes ]

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)
        value_type = [{ "out": NoValueType() }]

        for opcode in self.opcodes:
            value_type, other_break_types = get_expression_break_types(opcode, context, frame_manager)
            break_types.merge(other_break_types)
            if value_type is MISSING:
                break

        if value_type is not MISSING:
            break_types.merge({ "value": value_type })

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        value = NO_VALUE
        with frame_manager.get_next_frame(self) as frame:
            for index, opcode in enumerate(self.opcodes):
                value = frame.step(index, lambda: evaluate(opcode, context, frame_manager))

            return frame.value(value)

    def to_code(self):
        return ";\n".join([ o.to_code() for o in self.opcodes ])


class LoopOp(Opcode):
    def __init__(self, data, visitor):
        self.code = enrich_opcode(data.code, visitor)

    def get_break_types(self, context, frame_manager, immediate_context=None):
        _, other_break_types = get_expression_break_types(self.code, context, frame_manager)
        return other_break_types

    def jump(self, context, frame_manager, immediate_context=None):
        code = self.code
        while 1:
            evaluate(code, context, frame_manager)

    def to_code(self):
        return "Loop {{ {} }}".format(self.code.to_code())


class ConditionalOp(Opcode):
    def __init__(self, data, visitor):
        super(ConditionalOp, self).__init__(data, visitor)
        self.condition = enrich_opcode(data.condition, visitor)
        self.when_true = enrich_opcode(data.when_true, visitor)
        self.when_false = enrich_opcode(data.when_false, visitor)

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        condition_type, condition_break_types = get_expression_break_types(self.condition, context, frame_manager)
        when_true_type, when_true_break_types = get_expression_break_types(self.when_true, context, frame_manager)
        when_false_type, when_false_break_types = get_expression_break_types(self.when_false, context, frame_manager)

        if BooleanType().is_copyable_from(condition_type):
            # TODO be more liberal
            raise FatalError()

        # TODO throw away one branch if condition_type can't be true or false
        break_types.merge(condition_break_types)
        break_types.merge(when_true_break_types)
        break_types.merge(when_false_break_types)

        if condition_type is not MISSING:
            condition_type = flatten_out_types(condition_type)
            if when_true_type is not MISSING:
                when_true_type = flatten_out_types(when_true_type)
                break_types.add("value", when_true_type)
            if when_false_type is not MISSING:
                when_false_type = flatten_out_types(when_false_type)
                break_types.add("value", when_false_type)

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            condition = frame.step("condition", lambda: evaluate(self.condition, context, frame_manager))

            if condition is True:
                result = frame.step("true_result", lambda: evaluate(self.when_true, context, frame_manager))
            elif condition is False:
                result = frame.step("false_result", lambda: evaluate(self.when_false, context, frame_manager))
            else:
                # be more liberal
                raise FatalError()

            return frame.value(result)


class PrepareOp(Opcode):
    PREPARATION_ERROR = TypeErrorFactory("PrepareOp: preparation_error")

    def __init__(self, data, visitor):
        super(PrepareOp, self).__init__(data, visitor)
        self.code = enrich_opcode(data.code, visitor)

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)
        function_value_type, other_break_types = get_expression_break_types(self.code, context, frame_manager, immediate_context)

        break_types.merge(other_break_types)

        if function_value_type is not MISSING:
            break_types.add(
                "value", AnyType()
            )

        break_types.add("exception", self.PREPARATION_ERROR.get_type(), opcode=self)

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            function_data = evaluate(self.code, context, frame_manager)

            from rdhlang5.executor.function import prepare

            immediate_context = immediate_context or {}
            immediate_context["suggested_outer_type"] = get_context_type(context)

            try:
                function = prepare(function_data, context, frame_manager, immediate_context)
            except PreparationException as e:
                return frame.exception(self.PREPARATION_ERROR())

            return frame.value(function)


class CloseOp(Opcode):
    INVALID_FUNCTION = TypeErrorFactory("Close: invalid_function")
    INVALID_OUTER_CONTEXT = TypeErrorFactory("Close: invalid_outer_context")

    def __init__(self, data, visitor):
        super(CloseOp, self).__init__(data, visitor)
        self.function = enrich_opcode(data.function, visitor)
        self.outer_context = enrich_opcode(data.outer_context, visitor)

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        function_type, function_break_types = get_expression_break_types(self.function, context, frame_manager, immediate_context=immediate_context)
        if function_type is not MISSING:
            function_type = flatten_out_types(function_type)
        break_types.merge(function_break_types)

        outer_context_type, outer_context_break_types = get_expression_break_types(self.outer_context, context, frame_manager)
        outer_context_type = flatten_out_types(outer_context_type)
        break_types.merge(outer_context_break_types)

        self.outer_context_type_error = True

        if function_type is not MISSING and outer_context_type is not MISSING:
            if isinstance(function_type, OpenFunctionType):
                break_types.add("value", ClosedFunctionType(function_type.argument_type, function_type.break_types))
                if function_type.outer_type.is_copyable_from(outer_context_type):
                    self.outer_context_type_error = False
            else:
                break_types.add("value", AnyType())

        if self.outer_context_type_error:
            break_types.add("exception", self.INVALID_OUTER_CONTEXT.get_type(), opcode=self)

        if not isinstance(function_type, OpenFunctionType):
            break_types.add("exception", self.INVALID_FUNCTION.get_type(), opcode=self)

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            open_function = frame.step("function", lambda: evaluate(self.function, context, frame_manager, immediate_context))
            outer_context = frame.step("outer", lambda: evaluate(self.outer_context, context, frame_manager, immediate_context))

            from rdhlang5.executor.function import OpenFunction

            if not isinstance(open_function, OpenFunction):
                return frame.exception(self.INVALID_FUNCTION())

            if (is_debug() or self.outer_context_type_error) and not open_function.outer_type.is_copyable_from(get_type_of_value(outer_context)):
                return frame.exception(self.INVALID_OUTER_CONTEXT())

            return frame.value(open_function.close(outer_context))

    def to_code(self):
        return "Closed_{}".format(self.function.to_code())


class StaticOp(Opcode):
    def __init__(self, data, visitor):
        super(StaticOp, self).__init__(data, visitor)
        self.code = enrich_opcode(data.code, visitor)
        self.value = MISSING
        self.mode = MISSING

    def lazy_initialize(self, context, frame_manager, immediate_context):
        if self.value is MISSING and self.mode is MISSING:
            with frame_manager.capture() as capture_result:
                capture_result.attempt_capture_or_raise(*self.code.jump(context, frame_manager, immediate_context))

            self.value = capture_result.value
            self.mode = capture_result.caught_break_mode

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)
        self.lazy_initialize(context, frame_manager, immediate_context)
        if self.value is not MISSING:
            break_types.add(self.mode, get_type_of_value(self.value))
        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            self.lazy_initialize(context, frame_manager, immediate_context)
            return frame.unwind(self.mode, self.value, None)

    def to_code(self):
        if not self.value:
            raise FatalError()
        return self.value.to_code()


class InvokeOp(Opcode):
    INVALID_FUNCTION_TYPE = TypeErrorFactory("Invoke: invalid_function_type")
    INVALID_ARGUMENT_TYPE = TypeErrorFactory("Invoke: invalid_argument_type")

    def __init__(self, data, visitor):
        super(InvokeOp, self).__init__(data, visitor)
        self.function = enrich_opcode(data.function, visitor)
        self.argument = enrich_opcode(data.argument, visitor)

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)

        argument_type, other_argument_break_types = get_expression_break_types(self.argument, context, frame_manager)
        if argument_type is not MISSING:
            argument_type = flatten_out_types(argument_type)
        break_types.merge(other_argument_break_types)

        function_type, other_function_break_types = get_expression_break_types(
            self.function, context, frame_manager, immediate_context={ "suggested_argument_type": argument_type }
        )
        break_types.merge(other_function_break_types)

        if function_type is not MISSING and argument_type is not MISSING:
            function_type = flatten_out_types(function_type)

            argument_type_is_safe = False

            if isinstance(function_type, ClosedFunctionType):
                break_types.merge(function_type.break_types)
                if function_type.argument_type.is_copyable_from(argument_type):
                    argument_type_is_safe = True
            else:
                break_types.add("exception", self.INVALID_FUNCTION_TYPE.get_type(), opcode=self)

            self.invalid_argument_type_exception = False
            if not argument_type_is_safe:
                self.invalid_argument_type_exception = True
                break_types.add("exception", self.INVALID_ARGUMENT_TYPE.get_type(), opcode=self)

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        logger.debug("Invoke:jump")
        from rdhlang5.executor.function import RDHFunction

        with frame_manager.get_next_frame(self) as frame:
            function = frame.step("function", lambda: evaluate(self.function, context, frame_manager))
            argument = frame.step("argument", lambda: evaluate(self.argument, context, frame_manager))

            if not isinstance(function, RDHFunction):
                return frame.exception(self.INVALID_FUNCTION_TYPE())
            if self.invalid_argument_type_exception and not function.get_type().argument_type.is_copyable_from(get_type_of_value(argument)):
                return frame.exception(self.INVALID_ARGUMENT_TYPE()) 

            return function.invoke(argument, frame_manager)

        raise FatalError()

    def to_code(self):
        return "invoke({},\n{}\n)".format(self.argument.to_code(), self.function.to_code())


class MatchOp(Opcode):
    NO_MATCH = TypeErrorFactory("Match: no_match")

    def __init__(self, data, visitor):
        super(MatchOp, self).__init__(data, visitor)
        self.value = enrich_opcode(data.value, visitor)
        self.matchers = [ enrich_opcode(m, visitor) for m in data.matchers ]

    def get_break_types(self, context, frame_manager, immediate_context=None):
        break_types = BreakTypesFactory(self)
        value_type, value_break_types = get_expression_break_types(self.value, context, frame_manager)
        value_type = flatten_out_types(value_type)

        break_types.merge(value_break_types)

        for matcher in self.matchers:
            matcher_function_type, matcher_break_types = get_expression_break_types(
                matcher,
                context,
                frame_manager,
                immediate_context={ "suggested_argument_type": value_type }
            )
            matcher_function_type = flatten_out_types(matcher_function_type)

            break_types.merge(matcher_break_types)
            break_types.merge(matcher_function_type.break_types)

            if matcher_function_type.argument_type.is_copyable_from(value_type):
                break

            value_type = remove_type(value_type, matcher_function_type.argument_type)
        else:
            break_types.add("exception", self.NO_MATCH.get_type())

        return break_types.build()

    def jump(self, context, frame_manager, immediate_context=None):
        with frame_manager.get_next_frame(self) as frame:
            value = frame.step("value", lambda: evaluate(self.value, context, frame_manager))
            value_type = get_type_of_value(value)

            for index, matcher in enumerate(self.matchers):
                matcher_function = frame.step(index, lambda: evaluate(matcher, context, frame_manager))
                if matcher_function.argument_type.is_copyable_from(value_type):
                    return matcher_function.invoke(value, frame_manager)
            else:
                return frame.exception(self.NO_MATCH())

        raise FatalError()

# class CasteOp(Opcode):
#     CASTE_ERROR = TypeErrorFactory("Match: no_match")
# 
#     def __init__(self, data, visitor):
#         self.value = enrich_opcode(data.value, visitor)
#         self.type = enrich_opcode(data.type, visitor)
# 
#     def get_break_types(self, context, flow_manager):
#         break_types = BreakTypesFactory(self)
# 
#         value_type, value_break_types = get_expression_break_types(self.value, context, flow_manager)
#         type_data = evaluate(self.type, context, flow_manager)
# 
#         break_types.merge(value_break_types)
# 
#         if value_type is not MISSING:
#             value_type = flatten_out_types(value_type)
#             try:
#                 caste_type = enrich_type(type_data)
#             except PreparationException():
#                 caste_type = None
# 
#             if not caste_type.is_copyable_from(value_type):
#                 break_types.add("exception", self.CASTE_ERROR.get_type())
# 
#             if caste_type:
#                 break_types.add("value", caste_type)
# 
#         return break_types.build()
# 
#     def jump(self, context, flow_manager):
#         with flow_manager.get_next_frame() as frame:
#             value = frame.step("value", lambda: evaluate(self.value, context, flow_manager))
#             type = frame.step("type", lambda: evaluate(self.type, context, flow_manager))
# 
#         if not type.is_copyable_from(get_type_of_value(value)):
#             flow_manager.exception(self.CASTE_ERROR())
# 
#         get_manager(value).add_composite_type(type)
# 
#         flow_manager.value(value)


OPCODES = {
    "nop": Nop,
    "transform": TransformOp,
    "shift": ShiftOp,
    "reset": ResetOp,
    "literal": LiteralOp,
    "object_template": ObjectTemplateOp,
    "dict_template": DictTemplateOp,
    "list_template": ListTemplateOp,
    "multiplication": BinaryOp("Multiplication", "*", lambda lvalue, rvalue: lvalue() * rvalue(), IntegerType(), IntegerType()),
    "division": BinaryOp("Division", "/", lambda lvalue, rvalue: lvalue() / rvalue(), IntegerType(), IntegerType()),
    "addition": BinaryOp("Addition", "+", lambda lvalue, rvalue: lvalue() + rvalue(), IntegerType(), IntegerType()),
    "subtraction": BinaryOp("Subtraction", "-", lambda lvalue, rvalue: lvalue() - rvalue(), IntegerType(), IntegerType()),
    "mod": BinaryOp("Modulus", "%", lambda lvalue, rvalue: lvalue() % rvalue(), IntegerType(), IntegerType()),
    "lt": BinaryOp("LessThan", "<", lambda lvalue, rvalue: lvalue() < rvalue(), IntegerType(), BooleanType()),
    "lte": BinaryOp("LessThanOrEqual", "<=", lambda lvalue, rvalue: lvalue() <= rvalue(), IntegerType(), BooleanType()),
    "gt": BinaryOp("GreaterThan", ">", lambda lvalue, rvalue: lvalue() > rvalue(), IntegerType(), BooleanType()),
    "gte": BinaryOp("GreaterThanOrEqual", ">=", lambda lvalue, rvalue: lvalue() >= rvalue(), IntegerType(), BooleanType()),
    "eq": BinaryOp("Equality", "==", lambda lvalue, rvalue: lvalue() == rvalue(), IntegerType(), BooleanType()),
    "neq": BinaryOp("Inequality", "!=", lambda lvalue, rvalue: lvalue() != rvalue(), IntegerType(), BooleanType()),
    "or": BinaryOp("Or", "||", lambda lvalue, rvalue: lvalue() or rvalue(), BooleanType(), BooleanType()),
    "and": BinaryOp("And", "&&", lambda lvalue, rvalue: lvalue() and rvalue(), BooleanType(), BooleanType()),
    "dereference": DereferenceOp,
    "dynamic_dereference": DynamicDereferenceOp,
    "assignment": AssignmentOp,
    "insert": InsertOp,
    "context": ContextOp,
    "comma": CommaOp,
    "loop": LoopOp,
    "conditional": ConditionalOp,
    "prepare": PrepareOp,
    "close": CloseOp,
    "static": StaticOp,
    "invoke": InvokeOp,
    "match": MatchOp
}


def enrich_opcode(data, visitor):
    if visitor:
        data = visitor(data)

    opcode = getattr(data, "opcode", MISSING)
    if opcode is MISSING:
        raise PreparationException("No opcode found in {}".format(data))
    if opcode not in OPCODES:
        raise PreparationException("Unknown opcode {} in {}".format(opcode, data))

    return OPCODES[opcode](data, visitor)

