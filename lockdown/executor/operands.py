# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from lockdown.executor.exceptions import PreparationException
from lockdown.executor.flow_control import BreakTypesFactory
from lockdown.executor.raw_code_factories import is_opcode
from lockdown.executor.utils import get_operand_type, get_expression_break_types, \
    flatten_out_types, evaluate, TypeErrorFactory
from lockdown.type_system.composites import is_type_bindable_to_value
from lockdown.type_system.core_types import Type, AnyType
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.reasoner import DUMMY_REASONER
from lockdown.utils.utils import MISSING


class OpcodeOperandMixin(object):
    def __init__(self, data, visitor):
        super(OpcodeOperandMixin, self).__init__(data, visitor)
        for name, operand in self.get_unbound_operands():
            setattr(self, name, operand.create_bound_operand(self, name, data, visitor))

    def get_unbound_operands(self):
        return [ (k, v) for k, v in type(self).__dict__.items() if isinstance(v, Operand) ]

class Operand(object):
    def __init__(self, required_type, invalid_type_exception_factory):
        if not isinstance(required_type, Type):
            raise FatalError()
        if invalid_type_exception_factory and not isinstance(invalid_type_exception_factory, TypeErrorFactory):
            raise FatalError()
        self.required_type = required_type
        self.invalid_type_exception_factory = invalid_type_exception_factory

    def create_bound_operand(self, opcode, name, data, visitor):
        if not data._contains(name):
            raise PreparationException()

        from lockdown.executor.opcodes import enrich_opcode

        return BoundOperand(
            name,
            opcode,
            enrich_opcode(data._get(name), visitor),
            self.required_type,
            self.invalid_type_exception_factory
        )

class BoundOperand(object):
    def __init__(self, name, opcode, expression, required_type, invalid_type_exception_factory):
        from lockdown.executor.opcodes import Opcode
        if not isinstance(opcode, Opcode):
            raise FatalError()
        if not isinstance(expression, Opcode):
            raise FatalError()
        if not isinstance(required_type, Type):
            raise FatalError()
        if invalid_type_exception_factory and not isinstance(invalid_type_exception_factory, TypeErrorFactory):
            raise FatalError()

        self.name = name
        self.opcode = opcode
        self.expression = expression
        self.required_type = required_type
        self.invalid_type_exception_factory = invalid_type_exception_factory

        self.safe = False
        self.value_type = None

    def to_ast(self, *args, **kwargs):
        return self.expression.to_ast(*args, **kwargs)

    def prepare(self, break_types, context, frame_manager, hooks, immediate_context):
        self.value_type, other_break_types = get_expression_break_types(
            self.expression, context, frame_manager, hooks, immediate_context=immediate_context
        )
        break_types.merge(other_break_types)

        if self.value_type is not MISSING:
            self.value_type = flatten_out_types(self.value_type)

            if not self.required_type.is_copyable_from(self.value_type, DUMMY_REASONER):
                break_types.add(self.opcode, "exception", self.invalid_type_exception_factory.get_type())
            else:
                self.safe = True
            return True

        return False

    def get(self, context, frame, hooks):
        value = frame.step(self.name, lambda: evaluate(self.expression, context, frame.manager, hooks))

        if not is_type_bindable_to_value(value, self.required_type):
            is_type_bindable_to_value(value, self.required_type)
            return frame.exception(self.opcode, self.invalid_type_exception_factory())

        return value

    def __str__(self):
        return str(self.expression)
