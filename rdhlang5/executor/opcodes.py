# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from abc import abstractmethod, ABCMeta

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
from rdhlang5.type_system.list_types import RDHListType, RDHList, ListGetterType, \
    ListSetterType, ListWildcardGetterType, ListWildcardSetterType, \
    ListWildcardDeletterType, ListInsertType, ListWildcardInsertType
from rdhlang5.type_system.managers import get_type_of_value, get_manager
from rdhlang5.type_system.object_types import RDHObject, RDHObjectType, \
    ObjectGetterType, ObjectSetterType, ObjectWildcardGetterType, \
    ObjectWildcardSetterType
from rdhlang5.utils import MISSING, NO_VALUE, is_debug


def evaluate(opcode, context, flow_manager, immediate_context=None):
    with flow_manager.capture("value", { "out": AnyType() }) as new_flow_manager:
        mode, value, opcode = opcode.jump(context, new_flow_manager, immediate_context)
        if not new_flow_manager.attempt_close(mode, value):
            raise BreakException(mode, value, opcode, False)
    return new_flow_manager.result


def get_expression_break_types(expression, context, flow_manager, immediate_context=None):
    other_break_types = expression.get_break_types(context, flow_manager, immediate_context)

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

    value_break_types = other_break_types.pop("value", MISSING)
    return value_break_types, other_break_types


def flatten_out_types(break_types):
    return merge_types([b["out"] for b in break_types], "super")


class TypeErrorFactory(object):
    def __init__(self, message=None):
        self.message = message

    def __call__(self):
        data = {
            "type": "TypeError",
        }
        if self.message:
            data["message"] = self.message
        return RDHObject(data, bind=self.get_type(), debug_reason="type-error")

    def get_type(self):
        properties = {
            "type": Const(UnitType("TypeError"))
        }
        if self.message:
            properties["message"] = Const(UnitType(self.message))
        return RDHObjectType(properties, name=self.message)


class Opcode(object):
    def __init__(self, data, visitor):
        self.data = data

#    __metaclass__ = ABCMeta

    @abstractmethod
    def get_break_types(self, context, flow_manager, immediate_context=None):
        raise NotImplementedError()

    @abstractmethod
    def jump(self, context, flow_manager, immediate_context=None):
        raise NotImplementedError()

    def get_line_and_column(self):
        return getattr(self.data, "line", None), getattr(self.data, "column", None)


class Nop(Opcode):
    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()
        break_types.add("value", NoValueType())
        return break_types.build()

    def jump(self, context, manager, immediate_context=None):
        return manager.value(NO_VALUE, self)


class LiteralOp(Opcode):
    def __init__(self, data, visitor):
        super(LiteralOp, self).__init__(data, visitor)
        self.value = data.value
        self.type = get_type_of_value(self.value)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()
        break_types.add("value", self.type)
        return break_types.build()

    def jump(self, context, break_manager, immediate_context=None):
        return break_manager.value(self.value, self)


class ObjectTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(ObjectTemplateOp, self).__init__(data, visitor)
        self.opcodes = { key: enrich_opcode(opcode, visitor) for key, opcode in data.opcodes.items() }

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        micro_ops = {}
        initial_data = {}

        all_value_types = []

        for key, opcode in self.opcodes.items():
            value_type, other_break_types = get_expression_break_types(opcode, context, flow_manager)
            break_types.merge(other_break_types)
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

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            result = {}
            for key, opcode in self.opcodes.items():
                result[key], _ = frame.step(key, lambda: evaluate(opcode, context, flow_manager))

        return flow_manager.value(RDHObject(result, debug_reason="object-template"), self)


class DictTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(DictTemplateOp, self).__init__(data, visitor)
        self.opcodes = { key: enrich_opcode(opcode, visitor) for key, opcode in data.opcodes.items() }

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        micro_ops = {}
        initial_data = {}

        for key, opcode in self.opcodes.items():
            value_type, other_break_types = get_expression_break_types(opcode, context, flow_manager)
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

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            result = {}
            for key, opcode in self.opcodes.items():
                result[key], _ = frame.step(key, lambda: evaluate(opcode, context, flow_manager))

        return flow_manager.value(RDHDict(result), self)


class ListTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(ListTemplateOp, self).__init__(data, visitor)
        self.opcodes = [ enrich_opcode(opcode, visitor) for opcode in data.opcodes ]

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        micro_ops = {}
        initial_data = {}

        all_value_types = []

        for index, opcode in enumerate(self.opcodes):
            value_type, other_break_types = get_expression_break_types(opcode, context, flow_manager)
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

        combined_value_types = merge_types(all_value_types, "exact")

        micro_ops[("get-wildcard",)] = ListWildcardGetterType(combined_value_types, True, False)
        micro_ops[("set-wildcard",)] = ListWildcardSetterType(AnyType(), True, True)
        micro_ops[("insert", 0)] = ListInsertType(AnyType(), 0, False, False)
        micro_ops[("delete-wildcard",)] = ListWildcardDeletterType(True)
        micro_ops[("insert-wildcard",)] = ListWildcardInsertType(AnyType(), True, False)

        break_types.add("value", CompositeType(micro_ops, initial_data=initial_data, is_revconst=True))

        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            result = []
            for index, opcode in enumerate(self.opcodes):
                new_value, _ = frame.step(index, lambda: evaluate(opcode, context, flow_manager))
                result.append(new_value)

        return flow_manager.value(RDHList(result), self)


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
    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()
        break_types.add("value", get_context_type(context))
        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        return flow_manager.value(context, self)


class DereferenceOp(Opcode):
    INVALID_DEREFERENCE = TypeErrorFactory("DereferenceOpcode: invalid_dereference")

    def __init__(self, data, visitor):
        super(DereferenceOp, self).__init__(data, visitor)
        self.of = enrich_opcode(data.of, visitor)
        self.reference = enrich_opcode(data.reference, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        reference_types, reference_break_types = get_expression_break_types(self.reference, context, flow_manager)
        break_types.merge(reference_break_types)
        if reference_types is not MISSING:
            reference_types = flatten_out_types(reference_types)

        of_types, of_break_types = get_expression_break_types(self.of, context, flow_manager)
        break_types.merge(of_break_types)
        if of_types is not MISSING:
            of_types = flatten_out_types(of_types)

        self.invalid_dereference_error = False

        if reference_types is not MISSING and of_types is not MISSING:
            for reference_type in unwrap_types(reference_types):
                try:
                    for reference in reference_type.get_allowed_values():
                        for of_type in unwrap_types(of_types):
                            micro_op = None

                            if isinstance(of_type, CompositeType):
                                micro_op = of_type.get_micro_op_type(("get", reference))
                                if micro_op is None:
                                    micro_op = of_type.get_micro_op_type(("get-wildcard",))

                            if micro_op:
                                break_types.add("value", micro_op.type)
                                if micro_op.type_error or micro_op.key_error:
                                    self.invalid_dereference_error = True
                            else:
                                self.invalid_dereference_error = True
                except AllowedValuesNotAvailable:
                    self.invalid_dereference_error = True

        if self.invalid_dereference_error:
            break_types.add("exception", self.INVALID_DEREFERENCE.get_type(), opcode=self)

        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            of, _ = frame.step("of", lambda: evaluate(self.of, context, flow_manager))
            reference, _ = frame.step("reference", lambda: evaluate(self.reference, context, flow_manager))

            manager = get_manager(of)

            try:
                direct_micro_op_type = manager.get_micro_op_type(("get", reference))
                if direct_micro_op_type:
                    micro_op = direct_micro_op_type.create(manager)
                    return flow_manager.value(micro_op.invoke(trust_caller=True), self)

                wildcard_micro_op_type = manager.get_micro_op_type(("get-wildcard",))
                if wildcard_micro_op_type:
                    micro_op = wildcard_micro_op_type.create(manager)
                    return flow_manager.value(micro_op.invoke(reference, trust_caller=True), self)

                raise flow_manager.exception(self.INVALID_DEREFERENCE(), self)
            except InvalidDereferenceType:
                raise flow_manager.exception(self.INVALID_DEREFERENCE(), self)
            except InvalidDereferenceKey:
                raise flow_manager.exception(self.INVALID_DEREFERENCE(), self)


class DynamicDereferenceOp(Opcode):
    INVALID_DEREFERENCE = TypeErrorFactory("DereferenceOpcode: invalid_dereference")

    def __init__(self, data, visitor):
        super(DynamicDereferenceOp, self).__init__(data, visitor)
        self.reference = data.reference

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        break_types.add("exception", self.INVALID_DEREFERENCE.get_type())

        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        raise FatalError()


class AssignmentOp(Opcode):
    INVALID_LVALUE = TypeErrorFactory("AssignmentOp: invalid_lvalue")
    INVALID_RVALUE = TypeErrorFactory("AssignmentOp: invalid_rvalue")
    INVALID_ASSIGNMENT = TypeErrorFactory("AssignmentOp: invalid_assignment")

    def __init__(self, data, visitor):
        self.of = enrich_opcode(data.of, visitor)
        self.reference = enrich_opcode(data.reference, visitor)
        self.rvalue = enrich_opcode(data.rvalue, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        reference_types, reference_break_types = get_expression_break_types(self.reference, context, flow_manager)
        break_types.merge(reference_break_types)
        if reference_types is not MISSING:
            reference_types = flatten_out_types(reference_types)

        of_types, of_break_types = get_expression_break_types(self.of, context, flow_manager)
        break_types.merge(of_break_types)
        if of_types is not MISSING:
            of_types = flatten_out_types(of_types)

        rvalue_type, rvalue_break_types = get_expression_break_types(self.rvalue, context, flow_manager)
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
                                micro_op = of_type.get_micro_op_type(("set", reference))

                                if not micro_op:
                                    micro_op = of_type.get_micro_op_type(("set-wildcard",))

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

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            of, _ = frame.step("of", lambda: evaluate(self.of, context, flow_manager))
            reference, _ = frame.step("reference", lambda: evaluate(self.reference, context, flow_manager))
            rvalue, _ = frame.step("rvalue", lambda: evaluate(self.rvalue, context, flow_manager))

            if reference in ("result", "test", "i", "j", "testResult"):
                logger.debug("{} = {}".format(reference, rvalue))

            manager = get_manager(of)

            try:
                direct_micro_op_type = manager.get_micro_op_type(("set", reference))
                if direct_micro_op_type:
                    if self.invalid_rvalue_error and not direct_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
                        raise flow_manager.exception(self.INVALID_RVALUE(), self)

                    micro_op = direct_micro_op_type.create(manager)
                    return flow_manager.value(micro_op.invoke(rvalue, trust_caller=True), self)

                wildcard_micro_op_type = manager.get_micro_op_type(("set-wildcard",))
                if wildcard_micro_op_type:
                    if self.invalid_rvalue_error and not wildcard_micro_op_type.type.is_copyable_from(get_type_of_value(rvalue)):
                        raise flow_manager.exception(self.INVALID_RVALUE(), self)

                    micro_op = wildcard_micro_op_type.create(manager)
                    return flow_manager.value(micro_op.invoke(reference, rvalue, trust_caller=True), self)

                raise flow_manager.exception(self.INVALID_LVALUE(), self)
            except InvalidAssignmentType:
                raise flow_manager.exception(self.INVALID_ASSIGNMENT(), self)
            except InvalidAssignmentKey:
                raise flow_manager.exception(self.INVALID_ASSIGNMENT(), self)


def BinaryOp(name, func, argument_type, result_type):
    class _BinaryOp(Opcode):
        MISSING_OPERANDS = TypeErrorFactory("{}: missing_integers".format(name))

        def __init__(self, data, visitor):
            super(_BinaryOp, self).__init__(data, visitor)
            self.lvalue = enrich_opcode(self.data.lvalue, visitor)
            self.rvalue = enrich_opcode(self.data.rvalue, visitor)

        def get_break_types(self, context, flow_manager, immediate_context=None):
            break_types = BreakTypesFactory()

            lvalue_type, lvalue_break_types = get_expression_break_types(self.lvalue, context, flow_manager)
            if lvalue_type is not MISSING:
                lvalue_type = flatten_out_types(lvalue_type)
            break_types.merge(lvalue_break_types)

            rvalue_type, rvalue_break_types = get_expression_break_types(self.rvalue, context, flow_manager)
            if rvalue_type is not MISSING:
                rvalue_type = flatten_out_types(rvalue_type)
            break_types.merge(rvalue_break_types)

            if lvalue_type is not MISSING and rvalue_type is not MISSING:
                break_types.add("value", result_type)
            if not argument_type.is_copyable_from(lvalue_type) or not argument_type.is_copyable_from(rvalue_type):
                break_types.add("exception", self.MISSING_OPERANDS.get_type())

            return break_types.build()

        def jump(self, context, break_manager, immediate_context=None):
            with break_manager.get_next_frame(self) as frame:
                def get_lvalue():
                    lvalue, _ = frame.step("lvalue", lambda: evaluate(self.lvalue, context, break_manager))
                    if not argument_type.is_copyable_from(get_type_of_value(lvalue)):
                        raise break_manager.exception(self.MISSING_OPERANDS(), self)
                    return lvalue
    
                def get_rvalue():
                    rvalue, _ = frame.step("rvalue", lambda: evaluate(self.rvalue, context, break_manager))
                    if not argument_type.is_copyable_from(get_type_of_value(rvalue)):
                        raise break_manager.exception(self.MISSING_OPERANDS(), self)
                    return rvalue

                return break_manager.value(func(get_lvalue, get_rvalue), self)

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

        self.restart = None
        if hasattr(self.data, "restart"):
            self.restart = self.data.restart
            self.restart_type = enrich_opcode(self.data.restart_type, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        if self.restart:
            restart_type = enrich_type(evaluate(self.restart_type, context, flow_manager))

        if self.expression:
            expression_break_types = self.expression.get_break_types(context, flow_manager)
            if self.input in expression_break_types:
                expression_break_types[self.output] = expression_break_types.pop(self.input)
                if self.restart:
                    for output_break_type in expression_break_types[self.output]:
                        output_break_type["in"] = restart_type
            break_types.merge(expression_break_types)
        else:
            break_types.add(self.output, NoValueType())
        if self.restart:
            break_types.add(self.restart, restart_type)
        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            if frame.has_restart_value():
                restart_value = frame.pop_restart_value()
                restart_type = enrich_type(evaluate(self.restart_type, context, flow_manager))
                if not restart_type.is_copyable_from(get_type_of_value(restart_value)):
                    raise FatalError()
                raise flow_manager.unwind(self.restart, restart_value, self, False)

            can_restart = self.restart is not None

            if self.expression:
                with flow_manager.capture(self.input, { "out": AnyType() }) as new_flow_manager:
                    mode, value, opcode = self.expression.jump(context, new_flow_manager)
                    if not new_flow_manager.attempt_close(mode, value):
                        raise BreakException(mode, value, opcode, False)
                return flow_manager.unwind(self.output, new_flow_manager.result, self, can_restart)
            else:
                return flow_manager.unwind(self.output, NO_VALUE, self, can_restart)
        raise FatalError()


class CommaOp(Opcode):
    def __init__(self, data, visitor):
        super(CommaOp, self).__init__(data, visitor)
        self.opcodes = [ enrich_opcode(o, visitor) for o in data.opcodes ]

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()
        value_type = [{ "out": NoValueType() }]

        for opcode in self.opcodes:
            value_type, other_break_types = get_expression_break_types(opcode, context, flow_manager)
            break_types.merge(other_break_types)
            if value_type is MISSING:
                break

        if value_type is not MISSING:
            break_types.merge({ "value": value_type })

        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        value = NO_VALUE
        with flow_manager.get_next_frame(self) as frame:
            for index, opcode in enumerate(self.opcodes):
                value, _ = frame.step(index, lambda: evaluate(opcode, context, flow_manager))

        return flow_manager.value(value, self)
        

class LoopOp(Opcode):
    def __init__(self, data, visitor):
        self.code = enrich_opcode(data.code, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        _, other_break_types = get_expression_break_types(self.code, context, flow_manager)
        return other_break_types

    def jump(self, context, flow_manager, immediate_context=None):
        while True:
            evaluate(self.code, context, flow_manager)


class ConditionalOp(Opcode):
    def __init__(self, data, visitor):
        self.condition = enrich_opcode(data.condition, visitor)
        self.when_true = enrich_opcode(data.when_true, visitor)
        self.when_false = enrich_opcode(data.when_false, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        condition_type, condition_break_types = get_expression_break_types(self.condition, context, flow_manager)
        when_true_type, when_true_break_types = get_expression_break_types(self.when_true, context, flow_manager)
        when_false_type, when_false_break_types = get_expression_break_types(self.when_false, context, flow_manager)

        if BooleanType().is_copyable_from(condition_type):
            # TODO be more liberal
            raise FatalError()

        # TODO throw away one branch if condition_type can't be true of false
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

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            condition, _ = frame.step("condition", lambda: evaluate(self.condition, context, flow_manager))

            if condition is True:
                result, _ = frame.step("result", lambda: evaluate(self.when_true, context, flow_manager))
            elif condition is False:
                result, _ = frame.step("result", lambda: evaluate(self.when_false, context, flow_manager))
            else:
                # be more liberal
                raise FatalError()

            return flow_manager.value(result, self)


class PrepareOp(Opcode):
    def __init__(self, data, visitor):
        self.code = enrich_opcode(data.code, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        raise PreparationException()

        # I've left this code for reference, not sure how to use in future...
#         break_types = BreakTypesFactory()
# 
#         function_data = evaluate(self.code, context, flow_manager)
# 
#         from rdhlang5.executor.function import prepare
# 
#         self.function = prepare(function_data, context, flow_manager, immediate_context)
# 
#         break_types.add("value", self.function.get_type())
# 
#         return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        function_data = evaluate(self.code, context, flow_manager)

        from rdhlang5.executor.function import prepare

        immediate_context = immediate_context or {}
        immediate_context["suggested_outer_type"] = get_context_type(context)

        function = prepare(function_data, context, flow_manager, immediate_context)

        return flow_manager.value(function, self)


class CloseOp(Opcode):
    INVALID_FUNCTION = TypeErrorFactory("Close: invalid_function")
    INVALID_OUTER_CONTEXT = TypeErrorFactory("Close: invalid_outer_context")

    def __init__(self, data, visitor):
        self.function = enrich_opcode(data.function, visitor)
        self.outer_context = enrich_opcode(data.outer_context, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        function_type, function_break_types = get_expression_break_types(self.function, context, flow_manager, immediate_context=immediate_context)
        function_type = flatten_out_types(function_type)
        break_types.merge(function_break_types)

        outer_context_type, outer_context_break_types = get_expression_break_types(self.outer_context, context, flow_manager)
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
            break_types.add("exception", self.INVALID_OUTER_CONTEXT.get_type())

        if not isinstance(function_type, OpenFunctionType):
            break_types.add("exception", self.INVALID_FUNCTION.get_type())

        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        open_function = evaluate(self.function, context, flow_manager, immediate_context)
        outer_context = evaluate(self.outer_context, context, flow_manager, immediate_context)

        from rdhlang5.executor.function import OpenFunction

        if not isinstance(open_function, OpenFunction):
            flow_manager.exception(self.INVALID_FUNCTION(), self)

        if (is_debug() or self.outer_context_type_error) and not open_function.outer_type.is_copyable_from(get_type_of_value(outer_context)):
            flow_manager.exception(self.INVALID_OUTER_CONTEXT(), self)

        return flow_manager.value(open_function.close(outer_context), self)


class StaticOp(Opcode):
    def __init__(self, data, visitor):
        self.code = enrich_opcode(data.code, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()
        try:
            self.value = evaluate(self.code, context, flow_manager, immediate_context)
            break_types.add("value", get_type_of_value(self.value))
            return break_types.build()
        except Exception as e:
            raise
            raise PreparationException(e)

    def jump(self, context, flow_manager, immediate_context=None):
        return flow_manager.value(self.value, self)


class InvokeOp(Opcode):
    INVALID_FUNCTION_TYPE = TypeErrorFactory("Invoke: invalid_function_type")
    INVALID_ARGUMENT_TYPE = TypeErrorFactory("Invoke: invalid_argument_type")

    def __init__(self, data, visitor):
        super(InvokeOp, self).__init__(data, visitor)
        self.function = enrich_opcode(data.function, visitor)
        self.argument = enrich_opcode(data.argument, visitor)

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()

        argument_type, other_argument_break_types = get_expression_break_types(self.argument, context, flow_manager)
        argument_type = flatten_out_types(argument_type)
        break_types.merge(other_argument_break_types)

        function_type, other_function_break_types = get_expression_break_types(
            self.function, context, flow_manager, immediate_context={ "suggested_argument_type": argument_type }
        )
        break_types.merge(other_function_break_types)

        if function_type is not MISSING:
            function_type = flatten_out_types(function_type)

            argument_type_is_safe = False

            if isinstance(function_type, ClosedFunctionType):
                break_types.merge(function_type.break_types)
                if function_type.argument_type.is_copyable_from(argument_type):
                    argument_type_is_safe = True
            else:
                break_types.add("exception", self.INVALID_FUNCTION_TYPE.get_type(), opcode=self)

            if not argument_type_is_safe:
                break_types.add("exception", self.INVALID_ARGUMENT_TYPE.get_type(), opcode=self)

        return break_types.build()

    def jump(self, context, flow_manager, immediate_context=None):
        logger.debug("Invoke:jump")
        from rdhlang5.executor.function import RDHFunction
        function = evaluate(self.function, context, flow_manager)
        logger.debug("Invoke:jump:function")
        argument = evaluate(self.argument, context, flow_manager)
        logger.debug("Invoke:jump:argument")

        if not isinstance(function, RDHFunction):
            flow_manager.exception(self.INVALID_FUNCTION_TYPE(), self)

        logger.debug("Invoke:jump:argument_check")
        if not function.get_type().argument_type.is_copyable_from(get_type_of_value(argument)):
            flow_manager.exception(self.INVALID_ARGUMENT_TYPE(), self) 
        logger.debug("Invoke:jump:invoke")
        return function.invoke(argument, flow_manager)

        raise FatalError()


class MatchOp(Opcode):
    NO_MATCH = TypeErrorFactory("Match: no_match")

    def __init__(self, data, visitor):
        super(MatchOp, self).__init__(data, visitor)
        self.value = enrich_opcode(data.value, visitor)
        self.matchers = [ enrich_opcode(m, visitor) for m in data.matchers ]

    def get_break_types(self, context, flow_manager, immediate_context=None):
        break_types = BreakTypesFactory()
        value_type, value_break_types = get_expression_break_types(self.value, context, flow_manager)
        value_type = flatten_out_types(value_type)

        break_types.merge(value_break_types)

        for matcher in self.matchers:
            matcher_function_type, matcher_break_types = get_expression_break_types(
                matcher,
                context,
                flow_manager,
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

    def jump(self, context, flow_manager, immediate_context=None):
        with flow_manager.get_next_frame(self) as frame:
            value, _ = frame.step("value", lambda: evaluate(self.value, context, flow_manager))
            value_type = get_type_of_value(value)

            for index, matcher in enumerate(self.matchers):
                matcher_function, _ = frame.step(index, lambda: evaluate(matcher, context, flow_manager))
                if matcher_function.argument_type.is_copyable_from(value_type):
                    return matcher_function.invoke(value, flow_manager)
            else:
                return flow_manager.exception(self.NO_MATCH(), self)

        raise FatalError()

# class CasteOp(Opcode):
#     CASTE_ERROR = TypeErrorFactory("Match: no_match")
# 
#     def __init__(self, data, visitor):
#         self.value = enrich_opcode(data.value, visitor)
#         self.type = enrich_opcode(data.type, visitor)
# 
#     def get_break_types(self, context, flow_manager):
#         break_types = BreakTypesFactory()
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
    "literal": LiteralOp,
    "object_template": ObjectTemplateOp,
    "dict_template": DictTemplateOp,
    "list_template": ListTemplateOp,
    "multiplication": BinaryOp("Multiplication", lambda lvalue, rvalue: lvalue() * rvalue(), IntegerType(), IntegerType()),
    "division": BinaryOp("Division", lambda lvalue, rvalue: lvalue() / rvalue(), IntegerType(), IntegerType()),
    "addition": BinaryOp("Addition", lambda lvalue, rvalue: lvalue() + rvalue(), IntegerType(), IntegerType()),
    "subtraction": BinaryOp("Subtraction", lambda lvalue, rvalue: lvalue() - rvalue(), IntegerType(), IntegerType()),
    "mod": BinaryOp("Modulus", lambda lvalue, rvalue: lvalue() % rvalue(), IntegerType(), IntegerType()),
    "lt": BinaryOp("LessThan", lambda lvalue, rvalue: lvalue() < rvalue(), IntegerType(), BooleanType()),
    "lte": BinaryOp("LessThanOrEqual", lambda lvalue, rvalue: lvalue() <= rvalue(), IntegerType(), BooleanType()),
    "gt": BinaryOp("GreaterThan", lambda lvalue, rvalue: lvalue() > rvalue(), IntegerType(), BooleanType()),
    "gte": BinaryOp("GreaterThanOrEqual", lambda lvalue, rvalue: lvalue() >= rvalue(), IntegerType(), BooleanType()),
    "eq": BinaryOp("Equality", lambda lvalue, rvalue: lvalue() == rvalue(), IntegerType(), BooleanType()),
    "neq": BinaryOp("Inequality", lambda lvalue, rvalue: lvalue() != rvalue(), IntegerType(), BooleanType()),
    "or": BinaryOp("Or", lambda lvalue, rvalue: lvalue() or rvalue(), BooleanType(), BooleanType()),
    "and": BinaryOp("And", lambda lvalue, rvalue: lvalue() and rvalue(), BooleanType(), BooleanType()),
    "dereference": DereferenceOp,
    "dynamic_dereference": DynamicDereferenceOp,
    "assignment": AssignmentOp,
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

