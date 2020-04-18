from unittest import main
from unittest.case import TestCase

from rdhlang5.executor.bootstrap import bootstrap_function, prepare, \
    create_application_flow_manager, create_no_escape_flow_manager
from rdhlang5.executor.raw_code_factories import function_lit, literal_op, \
    no_value_type, return_op, int_type, addition_op, dereference_op, context_op, \
    comma_op, yield_op, any_type, build_break_types
from rdhlang5_types.core_types import AnyType, IntegerType
from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE, \
    rich_composite_type
from rdhlang5_types.list_types import RDHList, RDHListType
from rdhlang5_types.object_types import RDHObject, RDHObjectType
from rdhlang5_types.utils import NO_VALUE


class TestPreparedFunction(TestCase):
    def test_basic_function(self):
        func = function_lit(
            no_value_type, build_break_types(no_value_type, exception_type=any_type), literal_op(42)
        )

        result = bootstrap_function(func)
        
        self.assertEquals(result.mode, "exception")
        self.assertEquals(result.value.type, "TypeError")


    def test_basic_function_return(self):
        func = function_lit(no_value_type, build_break_types(int_type), return_op(literal_op(42)))

        result = bootstrap_function(func, check_safe_exit=True)

        self.assertEquals(result.mode, "return")
        self.assertEquals(result.value, 42)

    def test_addition(self):
        func = function_lit(no_value_type, build_break_types(int_type), return_op(addition_op(literal_op(40), literal_op(2))))

        result = bootstrap_function(func, check_safe_exit=True)

        self.assertEquals(result.mode, "return")
        self.assertEquals(result.value, 42)

class TestDereference(TestCase):
    def test_return_variable(self):
        func = function_lit(
            no_value_type, build_break_types(int_type),
            return_op(
                dereference_op(
                    dereference_op(
                        context_op(),
                        literal_op("outer")
                    ),
                    literal_op("local")
                )
            )
        )

        context = RDHObject({
            "local": 42,
            "types": RDHObject({
                "local": IntegerType()
            })
        }, bind=RDHObjectType({
            "local": IntegerType(),
            "types": DEFAULT_OBJECT_TYPE
        }, wildcard_type=rich_composite_type))

        result = bootstrap_function(func, context=context, check_safe_exit=True)

        self.assertEquals(result.mode, "return")
        self.assertEquals(result.value, 42)


    def test_add_locals(self):
        func = function_lit(
            no_value_type, build_break_types(int_type),
            return_op(
                addition_op(
                    dereference_op(
                        dereference_op(
                            dereference_op(
                                context_op(),
                                literal_op("outer")
                            ),
                            literal_op("local")
                        ),
                        literal_op(0)
                    ),
                    dereference_op(
                        dereference_op(
                            dereference_op(
                                context_op(),
                                literal_op("outer")
                            ),
                            literal_op("local")
                        ),
                        literal_op(1)
                    )
                )
            )
        )

        context = RDHObject({
            "local": RDHList([ 39, 3 ]),
            "types": RDHObject({
                "local": RDHListType([ IntegerType(), IntegerType() ], None)
            })
        }, bind=RDHObjectType({
            "local": RDHListType([ IntegerType(), IntegerType() ], None),
            "types": DEFAULT_OBJECT_TYPE
        }, wildcard_type=rich_composite_type))

        result = bootstrap_function(func, context=context, check_safe_exit=True)

        self.assertEquals(result.mode, "return")
        self.assertEquals(result.value, 42)

class TestComma(TestCase):
    def test_comma(self):
        result = bootstrap_function(
            function_lit(
                no_value_type, build_break_types(int_type),
                return_op(comma_op(literal_op(5), literal_op(8), literal_op(42)))
            ),
            check_safe_exit=True
        )

        self.assertEquals(result.mode, "return")
        self.assertEquals(result.value, 42)

    def test_restart_comma(self):
        context = RDHObject({})
        flow_manager = create_application_flow_manager()

        func = prepare(
            function_lit(
                no_value_type, build_break_types(int_type, yield_types={ "out": any_type, "in": int_type }),
                return_op(comma_op(
                    literal_op(5),
                    yield_op(literal_op("first"), int_type),
                    yield_op(literal_op("second"), int_type)
                ))
            ),
            context, create_no_escape_flow_manager()
        )

        first_yielder = flow_manager.capture("yield", { "out": AnyType(), "in": IntegerType() }, lambda new_fm: func.invoke(NO_VALUE, context, new_fm))
        self.assertEquals(first_yielder.result, "first")

        second_yielder = flow_manager.capture("yield", { "out": AnyType(), "in": IntegerType() }, lambda new_fm: first_yielder.restart_continuation.invoke(4, context, new_fm))
        self.assertEquals(second_yielder.result, "second")

        returner = flow_manager.capture("return", { "out": AnyType() }, lambda new_fm: second_yielder.restart_continuation.invoke(42, context, new_fm))

        self.assertEquals(returner.result, 42)

class TestContinuations(TestCase):
    def test_single_restart(self):
        context = RDHObject({})
        flow_manager = create_application_flow_manager()

        func = prepare(
            function_lit(
                no_value_type, build_break_types(any_type, yield_types={ "out": any_type, "in": int_type }),
                return_op(addition_op(yield_op(literal_op("hello"), int_type), literal_op(40)))
            ),
            context, create_no_escape_flow_manager()
        )

        yielder = flow_manager.capture("yield", { "out": AnyType(), "in": IntegerType() }, lambda new_fm: func.invoke(NO_VALUE, context, new_fm))

        self.assertEquals(yielder.result, "hello")

        returner = flow_manager.capture("return", { "out": AnyType() }, lambda new_fm: yielder.restart_continuation.invoke(2, context, new_fm))

        self.assertEquals(returner.result, 42)

    def test_repeated_restart(self):
        context = RDHObject({})
        flow_manager = create_application_flow_manager()

        func = prepare(
            function_lit(
                no_value_type, build_break_types(int_type, yield_types={ "out": any_type, "in": int_type }),
                return_op(addition_op(yield_op(literal_op("first"), int_type), yield_op(literal_op("second"), int_type)))
            ),
            context, create_no_escape_flow_manager()
        )

        first_yielder = flow_manager.capture("yield", { "out": AnyType(), "in": IntegerType() }, lambda new_fm: func.invoke(NO_VALUE, context, new_fm))
        self.assertEquals(first_yielder.result, "first")

        second_yielder = flow_manager.capture("yield", { "out": AnyType(), "in": IntegerType() }, lambda new_fm: first_yielder.restart_continuation.invoke(39, context, new_fm))
        self.assertEquals(second_yielder.result, "second")

        returner = flow_manager.capture("return", { "out": AnyType() }, lambda new_fm: second_yielder.restart_continuation.invoke(3, context, new_fm))

        self.assertEquals(returner.result, 42)

    def test_repeated_restart_with_outer_return_handling(self):
        context = RDHObject({})
        flow_manager = create_application_flow_manager()

        func = prepare(
            function_lit(
                no_value_type, build_break_types(int_type, yield_types={ "out": any_type, "in": int_type }),
                return_op(addition_op(yield_op(literal_op("first"), int_type), yield_op(literal_op("second"), int_type)))
            ),
            context, create_no_escape_flow_manager()
        )

        with flow_manager.capture("return", { "out": AnyType() }) as returner:
            first_yielder = returner.capture("yield", { "out": AnyType(), "in": IntegerType() }, lambda new_bm: func.invoke(NO_VALUE, context, new_bm))
            self.assertEquals(first_yielder.result, "first")

            second_yielder = returner.capture("yield", { "out": AnyType(), "in": IntegerType() }, lambda new_bm: first_yielder.restart_continuation.invoke(39, context, new_bm))
            self.assertEquals(second_yielder.result, "second")

            second_yielder.restart_continuation.invoke(3, context, returner)

        self.assertEquals(returner.result, 42)

    def test_repeated_restart_while_using_restart_values(self):
        context = RDHObject({})
        flow_manager = create_application_flow_manager()

        func = prepare(
            function_lit(
                no_value_type, build_break_types(any_type, yield_types={ "out": any_type, "in": int_type }),
                return_op(addition_op(yield_op(literal_op(30), int_type), yield_op(literal_op(10), int_type)))
            ),
            context, create_no_escape_flow_manager()
        )

        first_yielder = flow_manager.capture(
            "yield", { "out": AnyType(), "in": IntegerType() },
            lambda new_fm: func.invoke(NO_VALUE, context, new_fm)
        )
        second_yielder = flow_manager.capture(
            "yield", { "out": AnyType(), "in": IntegerType() },
            lambda new_fm: first_yielder.restart_continuation.invoke(first_yielder.result + 1, context, new_fm)
        )
        returner = flow_manager.capture(
            "return", { "out": AnyType() },
            lambda new_fm: second_yielder.restart_continuation.invoke(second_yielder.result + 1, context, new_fm)
        )

        self.assertEquals(returner.result, 42)

if __name__ == '__main__':
    main()
