from abc import abstractmethod, ABCMeta

from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.executor.flow_control import BreakTypesFactory
from rdhlang5.executor.type_factories import enrich_type
from rdhlang5.utils import MISSING
from rdhlang5_types.composites import CompositeType
from rdhlang5_types.core_types import NoValueType, IntegerType, UnitType, Const, \
    AnyType, CrystalValueCanNotBeGenerated, merge_types, unwrap_types
from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE, \
    DEFAULT_LIST_TYPE
from rdhlang5_types.exceptions import FatalError, InvalidDereferenceKey, \
    InvalidDereferenceType
from rdhlang5_types.list_types import RDHListType, RDHList
from rdhlang5_types.managers import get_type_of_value, get_manager
from rdhlang5_types.object_types import RDHObjectType, RDHObject
from rdhlang5_types.utils import NO_VALUE


def evaluate(opcode, context, break_manager):
    with break_manager.capture("value", { "out": AnyType() }) as new_break_manager:
        opcode.jump(context, new_break_manager)
    return new_break_manager.result


def get_expression_break_types(expression, context, flow_manager):
    other_break_types = expression.get_break_types(context, flow_manager)
    value_break_types = other_break_types.pop("value", MISSING)
    return value_break_types, other_break_types

def flatten_out_types(break_types):
    return merge_types([b["out"] for b in  break_types], "super")

class TypeErrorFactory(object):
    def __init__(self, message=None):
        self.message = message

    def __call__(self):
        data = {
            "type": "TypeError",
        }
        if self.message:
            data["message"] = self.message
        return RDHObject(data, bind=self.get_type())

    def get_type(self):
        properties = {
            "type": Const(UnitType("TypeError"))
        }
        if self.message:
            properties["message"] = Const(UnitType(self.message))
        return RDHObjectType(properties)


class Opcode(object):
    def __init__(self, data, visitor):
        self.data = data

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_break_types(self, context, flow_manager):
        raise NotImplementedError()

    @abstractmethod
    def jump(self, context, flow_manager):
        raise NotImplementedError()


class Nop(Opcode):
    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()
        break_types.add("value", NoValueType())
        return break_types.build()

    def jump(self, context, manager):
        return manager.value(NO_VALUE)


class LiteralOp(Opcode):
    def __init__(self, data, visitor):
        super(LiteralOp, self).__init__(data, visitor)
        self.value = data.value
        self.type = get_type_of_value(self.value)

    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()
        break_types.add("value", self.type)
        return break_types.build()

    def jump(self, context, break_manager):
        return break_manager.value(self.value, self)

class ObjectTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(ObjectTemplateOp, self).__init__(data, visitor)
        self.opcodes = { key: enrich_opcode(opcode, visitor) for key, opcode in data.opcodes.items() }

    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()

        sub_types = {}
        for key, opcode in self.opcodes.items():
            value_type, other_break_types = get_expression_break_types(opcode, context, flow_manager)
            break_types.merge(other_break_types)
            sub_types[key] = flatten_out_types(value_type)

        break_types.add("value", RDHObjectType(sub_types, AnyType()))

        return break_types.build()

    def jump(self, context, flow_manager):
        with flow_manager.get_next_frame(self) as frame:
            result = {}
            for key, opcode in self.opcodes.items():
                result[key], _ = frame.step(key, lambda: evaluate(opcode, context, flow_manager))

        return flow_manager.value(RDHObject(result, bind=DEFAULT_OBJECT_TYPE), self)

class ListTemplateOp(Opcode):
    def __init__(self, data, visitor):
        super(ListTemplateOp, self).__init__(data, visitor)
        self.opcodes = [ enrich_opcode(opcode, visitor) for opcode in data.opcodes ]

    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()

        sub_types = []
        for opcode in self.opcodes:
            value_type, other_break_types = get_expression_break_types(opcode, context, flow_manager)
            break_types.merge(other_break_types)
            sub_types.append(flatten_out_types(value_type))

        break_types.add("value", RDHListType(sub_types, AnyType()))

        return break_types.build()

    def jump(self, context, flow_manager):
        with flow_manager.get_next_frame(self) as frame:
            result = []
            for index, opcode in enumerate(self.opcodes):
                new_value, _ = frame.step(index, lambda: evaluate(opcode, context, flow_manager))
                result.append(new_value)

        return flow_manager.value(RDHList(result, bind=DEFAULT_LIST_TYPE), self)

def get_context_type(context):
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
        if hasattr(context, "static"):
            value_type["static"] = get_type_of_value(context.static)
        context_manager._context_type = RDHObjectType(value_type)
    return context_manager._context_type

class ContextOp(Opcode):
    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()
        break_types.add("value", get_context_type(context))
        return break_types.build()

    def jump(self, context, flow_manager):
        return flow_manager.value(context, self)

class DereferenceOp(Opcode):
    INVALID_DEREFERENCE = TypeErrorFactory("DereferenceOpcode: invalid_dereference")

    def __init__(self, data, visitor):
        super(DereferenceOp, self).__init__(data, visitor)
        self.of = enrich_opcode(data.of, visitor)
        self.reference = enrich_opcode(data.reference, visitor)

    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()

        reference_types, reference_break_types = get_expression_break_types(self.reference, context, flow_manager)
        break_types.merge(reference_break_types)
        if reference_types is not MISSING:
            reference_types = flatten_out_types(reference_types)

        of_types, of_break_types = get_expression_break_types(self.of, context, flow_manager)
        break_types.merge(of_break_types)
        if of_types is not MISSING:
            of_types = flatten_out_types(of_types)

        if reference_types is MISSING or of_types is MISSING:
            break_types.add("exception", self.INVALID_DEREFERENCE.get_type())
        else:
            for reference_type in unwrap_types(reference_types):
                try:
                    reference = reference_type.get_crystal_value()
                except CrystalValueCanNotBeGenerated:
                    reference = None
    
                for of_type in unwrap_types(of_types):
                    micro_op = None
                    if isinstance(of_type, CompositeType) and reference is not None:
                        micro_op = of_type.get_micro_op_type(("get", reference))

                    if micro_op:
                        break_types.add("value", micro_op.type)
                        if micro_op.type_error or micro_op.key_error:
                            break_types.add("exception", self.INVALID_DEREFERENCE.get_type())
                    else:
                        break_types.add("exception", self.INVALID_DEREFERENCE.get_type())

        return break_types.build()

    def jump(self, context, flow_manager):
        with flow_manager.get_next_frame(self) as frame:
            of, _ = frame.step("of", lambda: evaluate(self.of, context, flow_manager))
            reference, _ = frame.step("reference", lambda: evaluate(self.reference, context, flow_manager))

            manager = get_manager(of)
            default_type = manager.default_type

            try:
                micro_op_type = manager.get_micro_op_type(default_type, ("get", reference))
                if micro_op_type:
                    micro_op = micro_op_type.create(of, default_type)
                    return flow_manager.value(micro_op.invoke(), self)

                raise flow_manager.exception(self.INVALID_DEREFERENCE(), self)
            except InvalidDereferenceType:
                raise flow_manager.exception(self.INVALID_DEREFERENCE(), self)
            except InvalidDereferenceKey:
                raise flow_manager.exception(self.INVALID_DEREFERENCE(), self)

class AdditionOp(Opcode):
    MISSING_INTEGERS = TypeErrorFactory("Addition: missing_integers")

    def __init__(self, data, visitor):
        super(AdditionOp, self).__init__(data, visitor)
        self.lvalue = enrich_opcode(self.data.lvalue, visitor)
        self.rvalue = enrich_opcode(self.data.rvalue, visitor)

    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()

        lvalue_type, lvalue_break_types = get_expression_break_types(self.lvalue, context, flow_manager)
        if lvalue_type is not MISSING:
            lvalue_type = flatten_out_types(lvalue_type)
        break_types.merge(lvalue_break_types)

        rvalue_type, rvalue_break_types = get_expression_break_types(self.rvalue, context, flow_manager)
        if rvalue_type is not MISSING:
            rvalue_type = flatten_out_types(rvalue_type)
        break_types.merge(rvalue_break_types)

        int_type = IntegerType()

        if lvalue_type is not MISSING and rvalue_type is not MISSING:
            break_types.add("value", int_type)
        if not int_type.is_copyable_from(lvalue_type) or not int_type.is_copyable_from(rvalue_type):
            break_types.add("exception", self.MISSING_INTEGERS.get_type())

        return break_types.build()

    def jump(self, context, break_manager):
        with break_manager.get_next_frame(self) as frame:
            lvalue, _ = frame.step("lvalue", lambda: evaluate(self.lvalue, context, break_manager))
            if not isinstance(lvalue, int):
                break_manager.exception(self.MISSING_INTEGERS(), self)

            rvalue, _ = frame.step("rvalue", lambda: evaluate(self.rvalue, context, break_manager))
            if not isinstance(rvalue, int):
                break_manager.exception(self.MISSING_INTEGERS(), self)

        return break_manager.value(lvalue + rvalue, self)


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

    def get_break_types(self, context, flow_manager):
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

    def jump(self, context, break_manager):
        with break_manager.get_next_frame(self) as frame:
            if frame.has_restart_value():
                restart_value = frame.pop_restart_value()
                restart_type = enrich_type(evaluate(self.restart_type, context, break_manager))
                if not restart_type.is_copyable_from(get_type_of_value(restart_value)):
                    raise FatalError()
                raise break_manager.unwind(self.restart, restart_value, self, False)

            can_restart = self.restart is not None

            if self.expression:
                with break_manager.capture(self.input, { "out": AnyType() }) as new_break_manager:
                    self.expression.jump(context, new_break_manager)
    
                raise break_manager.unwind(self.output, new_break_manager.result, self, can_restart)
            else:
                raise break_manager.unwind(self.output, NO_VALUE, self, can_restart)
        raise FatalError()

class CommaOp(Opcode):
    def __init__(self, data, visitor):
        super(CommaOp, self).__init__(data, visitor)
        self.opcodes = [ enrich_opcode(o, visitor) for o in data.opcodes ]

    def get_break_types(self, context, flow_manager):
        break_types = BreakTypesFactory()
        value_type = NoValueType()

        for opcode in self.opcodes:
            value_type, other_break_types = get_expression_break_types(opcode, context, flow_manager)
            break_types.merge(other_break_types)

        break_types.merge({ "value": value_type })

        return break_types.build()

    def jump(self, context, flow_manager):
        value = NO_VALUE
        with flow_manager.get_next_frame(self) as frame:
            for index, opcode in enumerate(self.opcodes):
                value, _ = frame.step(index, lambda: evaluate(opcode, context, flow_manager))

        return flow_manager.value(value, self)

OPCODES = {
    "transform": TransformOp,
    "literal": LiteralOp,
    "object_template": ObjectTemplateOp,
    "list_template": ListTemplateOp,
    "addition": AdditionOp,
    "dereference": DereferenceOp,
    "context": ContextOp,
    "comma": CommaOp
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

