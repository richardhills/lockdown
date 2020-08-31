# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest import main
from unittest.case import TestCase

from rdhlang5.executor.bootstrap import bootstrap_function
from rdhlang5.executor.function import prepare
from rdhlang5.executor.raw_code_factories import function_lit, no_value_type, \
    build_break_types, int_type, literal_op, return_op, addition_op, \
    dereference_op, context_op, comma_op, any_type, object_type, \
    object_template_op, unit_type, assignment_op, condition_op, loop_op, \
    equality_op, nop, inferred_type, infer_all, invoke_op, static_op, prepare_op, \
    unbound_dereference, match_op, dereference, prepared_function, one_of_type, \
    string_type, bool_type, try_catch_op, throw_op, const_string_type, \
    function_type, close_op, shift_op
from rdhlang5.type_system.core_types import IntegerType, StringType
from rdhlang5.type_system.default_composite_types import DEFAULT_OBJECT_TYPE, \
    rich_composite_type
from rdhlang5.type_system.list_types import RDHList, RDHListType
from rdhlang5.type_system.managers import get_manager
from rdhlang5.type_system.object_types import RDHObject, RDHObjectType
from rdhlang5.utils import NO_VALUE, set_debug
from rdhlang5.executor.flow_control import FrameManager


class TestPreparedFunction(TestCase):
    def test_basic_function(self):
        func = function_lit(
            no_value_type(), build_break_types(value_type=int_type()), literal_op(42)
        )

        result = bootstrap_function(func)

        self.assertEquals(result.caught_break_mode, "value")
        self.assertEquals(result.value, 42)

    def test_basic_function_return(self):
        func = function_lit(no_value_type(), build_break_types(int_type()), return_op(literal_op(42)))

        result = bootstrap_function(func, check_safe_exit=True)

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_addition(self):
        func = function_lit(no_value_type(), build_break_types(int_type()), return_op(addition_op(literal_op(40), literal_op(2))))

        result = bootstrap_function(func, check_safe_exit=True)

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestDereference(TestCase):
    def test_return_variable(self):
        func = function_lit(
            no_value_type(), build_break_types(int_type()),
            return_op(
                dereference_op(
                    dereference_op(
                        context_op(),
                        literal_op("outer"),
                        True
                    ),
                    literal_op("local"),
                    True
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
        }, wildcard_value_type=rich_composite_type))

        result = bootstrap_function(func, context=context, check_safe_exit=True)

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_add_locals(self):
        func = function_lit(
            no_value_type(), build_break_types(int_type()),
            return_op(
                addition_op(
                    dereference_op(
                        dereference_op(
                            dereference_op(
                                context_op(),
                                literal_op("outer"),
                                True
                            ),
                            literal_op("local"),
                            True
                        ),
                        literal_op(0),
                        True
                    ),
                    dereference_op(
                        dereference_op(
                            dereference_op(
                                context_op(),
                                literal_op("outer"),
                                True
                            ),
                            literal_op("local"),
                            True
                        ),
                        literal_op(1),
                        True
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
        }))

        result = bootstrap_function(func, context=context, check_safe_exit=True)

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestComma(TestCase):
    def test_comma(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(comma_op(literal_op(5), literal_op(8), literal_op(42)))
            ),
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_restart_comma(self):
        context = RDHObject({})

        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(int_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(comma_op(
                    literal_op(5),
                    shift_op(literal_op("first"), int_type()),
                    shift_op(literal_op("second"), int_type())
                ))
            ),
            context, frame_manager
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager)

        with frame_manager.capture("yield") as first_yielder:
            first()
        self.assertEquals(first_yielder.value, "first")

        def second():
            first_yield_restart_continuation = first_yielder.create_continuation(first, func.get_type().break_types)
            first_yield_restart_continuation.invoke(4, frame_manager)

        with frame_manager.capture("yield") as second_yielder:
            second()

        self.assertEquals(second_yielder.value, "second")

        def third():
            second_yield_restart_continuation = second_yielder.create_continuation(second, func.get_type().break_types)
            second_yield_restart_continuation.invoke(42, frame_manager)

        with frame_manager.capture("return") as returner:
            third()

        self.assertEquals(returner.value, 42)


class TestTemplates(TestCase):
    def test_return(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(object_type({ "foo": int_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42) }))
                )
            ),
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, RDHObject))
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.foo, 42)

    def test_nested_return(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(object_type({ "foo": object_type({ "bar": int_type() }) })),
                comma_op(
                    return_op(object_template_op({ "foo": object_template_op({ "bar": literal_op(42) }) }))
                )
            ),
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, RDHObject))
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.foo.bar, 42)

    def test_return_with_dereference1(self):
        result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": unit_type(42), "bar": any_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, RDHObject))
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.foo, 42)
        self.assertEquals(result.value.bar, 42)

    def test_return_with_dereference2(self):
        result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": unit_type(42), "bar": int_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, RDHObject))
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.foo, 42)
        self.assertEquals(result.value.bar, 42)

    def test_return_with_dereference3(self):
        result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": int_type(), "bar": any_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, RDHObject))
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.foo, 42)
        self.assertEquals(result.value.bar, 42)

    def test_return_with_dereference4(self):
        result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": any_type(), "bar": any_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, RDHObject))
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.foo, 42)
        self.assertEquals(result.value.bar, 42)

    def test_return_with_dereference5(self):
        with self.assertRaises(Exception):
            bootstrap_function(
                function_lit(
                    int_type(), build_break_types(object_type({ "foo": any_type(), "bar": unit_type(42) })),
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                ),
                argument=42,
                check_safe_exit=True
            )

    def test_return_rev_const_and_inferred(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(),
                comma_op(
                    return_op(object_template_op({ "foo": object_template_op({ "bar": literal_op(42) }) }))
                )
            ),
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, RDHObject))
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.foo.bar, 42)


class TestLocals(TestCase):
    def test_initialization(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()), int_type(), literal_op(42),
                comma_op(
                    return_op(dereference_op(context_op(), literal_op("local"), True))
                )
            ),
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_initialization_from_argument(self):
        result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(int_type()), int_type(), dereference_op(context_op(), literal_op("argument"), True),
                comma_op(
                    return_op(dereference_op(context_op(), literal_op("local"), True))
                )
            ),
            argument=123,
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 123)

    def test_restart_into_local_initialization(self):
        context = RDHObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                int_type(), shift_op(literal_op("hello"), int_type()),
                return_op(dereference_op(context_op(), literal_op("local"), True))
            ),
            context, frame_manager
        ).close(None)

        def start():
            func.invoke(NO_VALUE, frame_manager)

        with frame_manager.capture("yield") as yielder:
            start()

        self.assertEquals(yielder.value, "hello")

        def restart():
            yielder_restart_continuation = yielder.create_continuation(start, func.get_type().break_types)
            yielder_restart_continuation.invoke(32, frame_manager)

        with frame_manager.capture("return") as returner:
            restart()

        self.assertEquals(returner.value, 32)

    def test_restart_into_local_initialization_and_code(self):
        context = RDHObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                int_type(), shift_op(literal_op("first"), int_type()),
                return_op(addition_op(dereference_op(context_op(), literal_op("local"), True), shift_op(literal_op("second"), int_type())))
            ),
            context, frame_manager
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager)

        with frame_manager.capture("yield") as first_yielder:
            first()
        self.assertEquals(first_yielder.value, "first")

        def second():
            first_restart_continuation = first_yielder.create_continuation(first, func.get_type().break_types)
            first_restart_continuation.invoke(40, frame_manager)

        with frame_manager.capture("yield") as second_yielder:
            second()
        self.assertEquals(second_yielder.value, "second")

        with frame_manager.capture("return") as returner:
            second_restart_continuation = second_yielder.create_continuation(first, func.get_type().break_types)
            second_restart_continuation.invoke(2, frame_manager)

        self.assertEquals(returner.value, 42)


class TestAssignment(TestCase):
    def test_assignment(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()), int_type(), literal_op(0),
                comma_op(
                    assignment_op(context_op(), literal_op("local"), literal_op(42)),
                    return_op(dereference_op(context_op(), literal_op("local"), True))
                )
            ),
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_assignment_from_argument(self):
        result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(int_type()), int_type(), literal_op(0),
                comma_op(
                    assignment_op(context_op(), literal_op("local"), dereference_op(context_op(), literal_op("argument"), True)),
                    return_op(dereference_op(context_op(), literal_op("local"), True))
                )
            ),
            argument=43,
            check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 43)


class TestArguments(TestCase):
    def test_simple_return_argument(self):
        func = function_lit(
            int_type(), build_break_types(int_type()),
            return_op(dereference_op(context_op(), literal_op("argument"), True))
        )

        result = bootstrap_function(func, argument=42, check_safe_exit=True)

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_doubler(self):
        func = function_lit(
            int_type(), build_break_types(int_type()),
            return_op(addition_op(dereference_op(context_op(), literal_op("argument"), True), dereference_op(context_op(), literal_op("argument"), True)))
        )

        result = bootstrap_function(func, argument=21, check_safe_exit=True)

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestConditional(TestCase):
    def test_basic_truth(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(condition_op(literal_op(True), literal_op(34), literal_op(53)))
            ), check_safe_exit=True
        )
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 34)

    def test_basic_false(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(condition_op(literal_op(False), literal_op(34), literal_op(53)))
            ), check_safe_exit=True
        )
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 53)


class TestLoops(TestCase):
    def test_immediate_return(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                loop_op(return_op(literal_op(42)))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_count_then_return(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()), int_type(), literal_op(0),
                loop_op(
                    comma_op(
                        assignment_op(
                            context_op(), literal_op("local"),
                            addition_op(dereference_op(context_op(), literal_op("local"), True), literal_op(1))
                        ),
                        condition_op(equality_op(
                            dereference_op(context_op(), literal_op("local"), True), literal_op(42)
                        ), return_op(dereference_op(context_op(), literal_op("local"))), nop())
                    )
                )
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestInferredBreakTypes(TestCase):
    def test_basic_inferrence(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(inferred_type()),
                return_op(literal_op(42))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_infer_all(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(), return_op(literal_op(42))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_infer_exception(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(), addition_op(literal_op("hello"), literal_op(5))
            )
        )

        self.assertEquals(result.caught_break_mode, "exception")
        self.assertEquals(result.value.type, "TypeError")

    def test_without_infer_exception_fails(self):
        with self.assertRaises(Exception):
            bootstrap_function(
                function_lit(
                    no_value_type(), build_break_types(int_type()), addition_op(literal_op("hello"), literal_op(5))
                )
            )


class TestFunctionPreparation(TestCase):
    def test_basic(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(invoke_op(close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), build_break_types(int_type()), return_op(literal_op(42))
                )))), context_op())))
            )
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestFunctionInvocation(TestCase):
    def test_basic(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                function_type(no_value_type(), build_break_types(int_type())),
                close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), build_break_types(int_type()), return_op(literal_op(42))
                )))), context_op()),
                return_op(invoke_op(dereference_op(context_op(), literal_op("local"), True)))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_basic_with_inferred_types(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                function_type(no_value_type(), build_break_types(int_type())),
                close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), infer_all(), return_op(literal_op(42))
                )))), context_op()),
                return_op(invoke_op(dereference_op(context_op(), literal_op("local"), True)))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_basic_with_inferred_local_type(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                inferred_type(),
                close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), infer_all(), return_op(literal_op(42))
                )))), context_op()),
                return_op(invoke_op(dereference_op(context_op(), literal_op("local"), True)))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestUnboundReference(TestCase):
    def test_unbound_reference_to_arguments(self):
        result = bootstrap_function(
            function_lit(
                object_type({ "foo": int_type(), "bar": int_type() }), infer_all(),
                return_op(addition_op(
                    unbound_dereference("foo"), unbound_dereference("bar")
                ))
            ), check_safe_exit=True, argument=RDHObject({ "foo": 39, "bar": 3 })
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_unbound_reference_to_locals(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                object_type({ "foo": int_type(), "bar": int_type() }),
                object_template_op({ "foo": literal_op(39), "bar": literal_op(3) }),
                return_op(addition_op(
                    unbound_dereference("foo"), unbound_dereference("bar")
                ))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_unbound_reference_to_locals_and_arguments(self):
        result = bootstrap_function(
            function_lit(
                object_type({ "foo": int_type() }), infer_all(),
                object_type({ "bar": int_type() }),
                object_template_op({ "bar": literal_op(3) }),
                return_op(addition_op(
                    unbound_dereference("foo"), unbound_dereference("bar")
                ))
            ), check_safe_exit=True, argument=RDHObject({ "foo": 39 })
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestMatch(TestCase):
    def test_interesting(self):
        func = function_lit(
            any_type(), infer_all(),
            match_op(
                dereference("argument"), [
                    prepared_function(
                        object_type({
                            "foo": int_type()
                        }),
                        return_op(addition_op(dereference("argument.foo"), literal_op(3)))
                    ),
                    prepared_function(
                        any_type(),
                        return_op(literal_op("invalid"))
                    )
                ]
            )
        )

        result = bootstrap_function(
            func, check_safe_exit=True, argument=RDHObject({ "foo": 39 })
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

        result = bootstrap_function(
            func, check_safe_exit=True, argument=RDHObject({ "foo": "hello" })
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "invalid")

    def test_to_string_from_int(self):
        func = function_lit(
            any_type(),
            return_op(
                match_op(
                    dereference("argument"), [
                        prepared_function(
                            unit_type(1),
                            literal_op("one")
                        ),
                        prepared_function(
                            unit_type(2),
                            literal_op("two")
                        ),
                        prepared_function(
                            unit_type(3),
                            literal_op("three")
                        ),
                        prepared_function(
                            unit_type(4),
                            literal_op("four")
                        ),
                        prepared_function(
                            any_type(),
                            literal_op("invalid")
                        )
                    ]
                )
            )
        )

        result = bootstrap_function(func, check_safe_exit=True, argument=1)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "one")
        result = bootstrap_function(func, check_safe_exit=True, argument=2)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "two")
        result = bootstrap_function(func, check_safe_exit=True, argument=3)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "three")
        result = bootstrap_function(func, check_safe_exit=True, argument=4)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "four")
        result = bootstrap_function(func, check_safe_exit=True, argument=5)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "invalid")

    def test_to_match_with_one_of_type_combo(self):
        func = function_lit(
            one_of_type([ string_type(), int_type(), bool_type() ]),
            return_op(
                match_op(
                    dereference("argument"), [
                        prepared_function(
                            int_type(),
                            literal_op("int is not a string")
                        ),
                        prepared_function(
                            bool_type(),
                            literal_op("bool is not a string")
                        ),
                        prepared_function(
                            inferred_type(),
                            dereference("argument")
                        )
                    ]
                )
            )
        )

        result = bootstrap_function(func, check_safe_exit=True, argument=2)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "int is not a string")
        result = bootstrap_function(func, check_safe_exit=True, argument=True)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "bool is not a string")
        result = bootstrap_function(func, check_safe_exit=True, argument="hello world")
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "hello world")

        prepared_func = prepare(func, RDHObject({}), FrameManager())
        self.assertEquals(len(prepared_func.break_types), 1)
        self.assertTrue("return" in prepared_func.break_types)
        for return_break_type in prepared_func.break_types["return"]:
            self.assertTrue(StringType().is_copyable_from(return_break_type["out"]))


class TestTryCatch(TestCase):
    def test_slightly_strange_try_catch(self):
        # Function either throws the same string back at you, or returns an int +1
        func = function_lit(
            one_of_type([ string_type(), int_type() ]),
            try_catch_op(
                throw_op(dereference("argument")),
                prepared_function(int_type(), return_op(addition_op(literal_op(1), dereference("argument")))),
                nop()
            )
        )
        result = bootstrap_function(func, argument="hello world")
        self.assertEquals(result.caught_break_mode, "exception")
        self.assertEquals(result.value, "hello world")
        result = bootstrap_function(func, argument=41)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_silly_tostring_casing(self):
        func = function_lit(
            any_type(),
            try_catch_op(
                return_op(
                    match_op(
                        dereference("argument"), [
                            prepared_function(
                                unit_type(1),
                                literal_op("one")
                            ),
                            prepared_function(
                                unit_type(2),
                                literal_op("two")
                            ),
                            prepared_function(
                                int_type(),
                                throw_op(object_template_op({
                                    "type": literal_op("UnknownInt")
                                }))
                            ),
                            prepared_function(
                                any_type(),
                                throw_op(object_template_op({
                                    "type": literal_op("TypeError")
                                }))
                            )
                        ]
                    )
                ),
                prepared_function(
                    object_type({ "type": unit_type("UnknownInt") }),
                    return_op(literal_op("unknown"))
                )
            )
        )

        result = bootstrap_function(func, argument=1)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "one")
        result = bootstrap_function(func, argument=2)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "two")
        result = bootstrap_function(func, argument=3)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "unknown")
        result = bootstrap_function(func, argument="hello")
        self.assertEquals(result.caught_break_mode, "exception")
        self.assertIsInstance(result.value, RDHObject)
        get_manager(result.value).add_composite_type(DEFAULT_OBJECT_TYPE)
        self.assertEquals(result.value.type, "TypeError")

    def test_catch_real_exception(self):
        #  Function safely handles an internal exception
        func = function_lit(
            try_catch_op(
                dereference_op(context_op(), literal_op("foo"), True),
                prepared_function(
                    object_type({
                        "type": const_string_type(),
                        "message": const_string_type(),
                    }),
                    return_op(dereference("argument.message"))
                ),
                nop()
            )
        )
        result = bootstrap_function(func, check_safe_exit=True)
        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, "DereferenceOp: invalid_dereference foo")


class TestUtilityMethods(TestCase):
    def test_misc1(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                object_type({ "foo": int_type(), "bar": int_type() }),
                object_template_op({ "foo": literal_op(39), "bar": literal_op(3) }),
                return_op(addition_op(
                    dereference("local.foo"), dereference("local.bar")
                ))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_misc2(self):
        result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                inferred_type(),
                prepared_function(
                    object_type({ "foo": int_type(), "bar": int_type() }),
                    return_op(addition_op(
                        dereference("argument.foo"), dereference("argument.bar")
                    ))
                ),
                return_op(invoke_op(
                    dereference("local"),
                    object_template_op({ "foo": literal_op(39), "bar": literal_op(3) }),
                ))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)

    def test_fizzbuzz(self):
        pass


class TestStatics(TestCase):
    def test_static_value_dereference(self):
        result = bootstrap_function(
            function_lit(
                return_op(static_op(addition_op(literal_op(5), literal_op(37))))
            ), check_safe_exit=True
        )

        self.assertEquals(result.caught_break_mode, "return")
        self.assertEquals(result.value, 42)


class TestContinuations(TestCase):
    def test_single_restart(self):
        context = RDHObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op("hello"), int_type()), literal_op(40)))
            ),
            context, frame_manager
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager)
        with frame_manager.capture("yield") as yielder:
            first()

        self.assertEquals(yielder.value, "hello")

        def second():
            yielder.create_continuation(first, {}).invoke(2, frame_manager)
        with frame_manager.capture("return") as returner:
            second()

        self.assertEquals(returner.value, 42)

    def test_repeated_restart(self):
        context = RDHObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(int_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op("first"), int_type()), shift_op(literal_op("second"), int_type())))
            ),
            context, frame_manager
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager)
        with frame_manager.capture("yield") as first_yielder:
            first()

        self.assertEquals(first_yielder.value, "first")

        def second():
            first_yielder_continuation = first_yielder.create_continuation(first, {})
            first_yielder_continuation.invoke(39, frame_manager)
        with frame_manager.capture("yield") as second_yielder:
            second()

        self.assertEquals(second_yielder.value, "second")

        def third():
            second_yielder_continuation = second_yielder.create_continuation(second, {})
            second_yielder_continuation.invoke(3, frame_manager)

        with frame_manager.capture() as returner:
            third()

        self.assertEquals(returner.value, 42)

    def test_repeated_restart_with_outer_return_handling(self):
        context = RDHObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(int_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op("first"), int_type()), shift_op(literal_op("second"), int_type())))
            ),
            context, frame_manager
        ).close(None)

        with frame_manager.capture("return") as return_capturer:
            def first():
                func.invoke(NO_VALUE, frame_manager)
            with frame_manager.capture("yield") as first_yielder:
                first()
            self.assertEquals(first_yielder.value, "first")

            def second():
                first_yielder.create_continuation(first, {}).invoke(39, frame_manager)
            with frame_manager.capture("yield") as second_yielder:
                second()
            self.assertEquals(second_yielder.value, "second")

            second_yielder.create_continuation(second, {}).invoke(3, frame_manager)

        self.assertEquals(return_capturer.value, 42)

    def test_repeated_restart_while_using_restart_values(self):
        context = RDHObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op(30), int_type()), shift_op(literal_op(10), int_type())))
            ),
            context, frame_manager
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager)
        with frame_manager.capture("yield") as first_yielder:
            first()

        def second():
            first_yielder.create_continuation(first, {}).invoke(first_yielder.value + 1, frame_manager)
        with frame_manager.capture("yield") as second_yielder:
            second()

        def third():
            second_yielder.create_continuation(second, {}).invoke(second_yielder.value + 1, frame_manager)
        with frame_manager.capture("return") as returner:
            third()

        self.assertEquals(returner.value, 42)

