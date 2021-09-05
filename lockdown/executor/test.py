# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest import main
from unittest.case import TestCase

from lockdown.executor.bootstrap import bootstrap_function
from lockdown.executor.flow_control import FrameManager
from lockdown.executor.function import prepare
from lockdown.executor.raw_code_factories import function_lit, no_value_type, \
    build_break_types, int_type, literal_op, return_op, addition_op, \
    dereference_op, context_op, comma_op, any_type, object_type, \
    object_template_op, unit_type, assignment_op, condition_op, loop_op, \
    equality_op, nop, inferred_type, infer_all, invoke_op, static_op, prepare_op, \
    unbound_dereference, match_op, dereference, prepared_function, one_of_type, \
    string_type, bool_type, try_catch_op, throw_op, const_string_type, \
    function_type, close_op, shift_op
from lockdown.type_system.core_types import IntegerType, StringType
from lockdown.type_system.managers import get_manager
from lockdown.type_system.reasoner import DUMMY_REASONER
from lockdown.type_system.universal_type import PythonObject, \
    DEFAULT_READONLY_COMPOSITE_TYPE, PythonList, UniversalTupleType, \
    UniversalObjectType, RICH_READONLY_TYPE, Universal
from lockdown.utils.utils import NO_VALUE


class TestPreparedFunction(TestCase):
    def test_basic_function(self):
        func = function_lit(
            no_value_type(), build_break_types(value_type=int_type()), literal_op(42)
        )

        _, result = bootstrap_function(func)

        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_basic_function_return(self):
        func = function_lit(no_value_type(), build_break_types(int_type()), return_op(literal_op(42)))

        _, result = bootstrap_function(func)

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_addition(self):
        func = function_lit(no_value_type(), build_break_types(int_type()), return_op(addition_op(literal_op(40), literal_op(2))))

        _, result = bootstrap_function(func)

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


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

        context = PythonObject({
            "local": 42,
            "_types": PythonObject({
                "local": IntegerType()
            })
        }, bind=UniversalObjectType({
            "local": IntegerType(),
            "_types": DEFAULT_READONLY_COMPOSITE_TYPE
        }, wildcard_type=RICH_READONLY_TYPE))

        _, result = bootstrap_function(func, outer_context=context)

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

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

        context = PythonObject({
            "local": PythonList([ 39, 3 ]),
            "_types": PythonObject({
                "local": UniversalTupleType([ IntegerType(), IntegerType() ])
            })
        }, bind=UniversalObjectType({
            "local": UniversalTupleType([ IntegerType(), IntegerType() ]),
            "_types": DEFAULT_READONLY_COMPOSITE_TYPE
        }))

        _, result = bootstrap_function(func, outer_context=context)

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


class TestComma(TestCase):
    def test_comma(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(comma_op(literal_op(5), literal_op(8), literal_op(42)))
            ),
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_restart_comma(self):
        context = PythonObject({})

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
            context, frame_manager, None
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager, None)

        with frame_manager.capture("yield") as first_yielder:
            first()
        self.assertEqual(first_yielder.value, "first")

        def second():
            first_yield_restart_continuation = first_yielder.create_continuation(first, func.get_type().break_types)
            first_yield_restart_continuation.invoke(4, frame_manager, None)

        with frame_manager.capture("yield") as second_yielder:
            second()

        self.assertEqual(second_yielder.value, "second")

        def third():
            second_yield_restart_continuation = second_yielder.create_continuation(second, func.get_type().break_types)
            second_yield_restart_continuation.invoke(42, frame_manager, None)

        with frame_manager.capture("return") as returner:
            third()

        self.assertEqual(returner.value, 42)


class TestTemplates(TestCase):
    def test_return(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(object_type({ "foo": int_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42) }))
                )
            ),
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, Universal))
        get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
        self.assertEqual(result.value._get("foo"), 42)

    def test_nested_return(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(object_type({ "foo": object_type({ "bar": int_type() }) })),
                comma_op(
                    return_op(object_template_op({ "foo": object_template_op({ "bar": literal_op(42) }) }))
                )
            ),
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, Universal))
        get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
        self.assertEqual(result.value._get("foo")._get("bar"), 42)

    def test_return_with_dereference1(self):
        _, result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": unit_type(42), "bar": any_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, Universal))
        get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
        self.assertEqual(result.value._get("foo"), 42)
        self.assertEqual(result.value._get("bar"), 42)

    def test_return_with_dereference2(self):
        _, result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": unit_type(42), "bar": int_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, Universal))
        get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
        self.assertEqual(result.value._get("foo"), 42)
        self.assertEqual(result.value._get("bar"), 42)

    def test_return_with_dereference3(self):
        _, result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": int_type(), "bar": any_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, Universal))
        get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
        self.assertEqual(result.value._get("foo"), 42)
        self.assertEqual(result.value._get("bar"), 42)

    def test_return_with_dereference4(self):
        _, result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(object_type({ "foo": any_type(), "bar": any_type() })),
                comma_op(
                    return_op(object_template_op({ "foo": literal_op(42), "bar": dereference_op(context_op(), literal_op("argument"), True) }))
                )
            ),
            argument=42,
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, Universal))
        get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
        self.assertEqual(result.value._get("foo"), 42)
        self.assertEqual(result.value._get("bar"), 42)

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
        _, result = bootstrap_function(
            function_lit(
                no_value_type(),
                comma_op(
                    return_op(object_template_op({ "foo": object_template_op({ "bar": literal_op(42) }) }))
                )
            ),
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertTrue(isinstance(result.value, Universal))
        get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
        self.assertEqual(result.value._get("foo")._get("bar"), 42)


class TestLocals(TestCase):
    def test_initialization(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()), int_type(), literal_op(42),
                comma_op(
                    return_op(dereference_op(context_op(), literal_op("local"), True))
                )
            ),
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_initialization_from_argument(self):
        _, result = bootstrap_function(
            function_lit(
                int_type(), build_break_types(int_type()), int_type(), dereference_op(context_op(), literal_op("argument"), True),
                comma_op(
                    return_op(dereference_op(context_op(), literal_op("local"), True))
                )
            ),
            argument=123,
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 123)

    def test_restart_into_local_initialization(self):
        context = PythonObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                int_type(), shift_op(literal_op("hello"), int_type()),
                return_op(dereference_op(context_op(), literal_op("local"), True))
            ),
            context, frame_manager, None
        ).close(None)

        def start():
            func.invoke(NO_VALUE, frame_manager, None)

        with frame_manager.capture("yield") as yielder:
            start()

        self.assertEqual(yielder.value, "hello")

        def restart():
            yielder_restart_continuation = yielder.create_continuation(start, func.get_type().break_types)
            yielder_restart_continuation.invoke(32, frame_manager, None)

        with frame_manager.capture("return") as returner:
            restart()

        self.assertEqual(returner.value, 32)

    def test_restart_into_local_initialization_and_code(self):
        context = PythonObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                int_type(), shift_op(literal_op("first"), int_type()),
                return_op(addition_op(dereference_op(context_op(), literal_op("local"), True), shift_op(literal_op("second"), int_type())))
            ),
            context, frame_manager, None
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager, None)

        with frame_manager.capture("yield") as first_yielder:
            first()
        self.assertEqual(first_yielder.value, "first")

        def second():
            first_restart_continuation = first_yielder.create_continuation(first, func.get_type().break_types)
            first_restart_continuation.invoke(40, frame_manager, None)

        with frame_manager.capture("yield") as second_yielder:
            second()
        self.assertEqual(second_yielder.value, "second")

        with frame_manager.capture("return") as returner:
            second_restart_continuation = second_yielder.create_continuation(first, func.get_type().break_types)
            second_restart_continuation.invoke(2, frame_manager, None)

        self.assertEqual(returner.value, 42)


class TestAssignment(TestCase):
    def test_assignment(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()), int_type(), literal_op(0),
                comma_op(
                    assignment_op(context_op(), literal_op("local"), literal_op(42)),
                    return_op(dereference_op(context_op(), literal_op("local"), True))
                )
            ),
            check_safe_exit=True
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_assignment_from_argument(self):
        _, result = bootstrap_function(
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

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 43)


class TestArguments(TestCase):
    def test_simple_return_argument(self):
        func = function_lit(
            int_type(), build_break_types(int_type()),
            return_op(dereference_op(context_op(), literal_op("argument"), True))
        )

        _, result = bootstrap_function(func, argument=42)

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_doubler(self):
        func = function_lit(
            int_type(), build_break_types(int_type()),
            return_op(addition_op(dereference_op(context_op(), literal_op("argument"), True), dereference_op(context_op(), literal_op("argument"), True)))
        )

        _, result = bootstrap_function(func, argument=21)

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


class TestConditional(TestCase):
    def test_basic_truth(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(condition_op(literal_op(True), literal_op(34), literal_op(53)))
            )
        )
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 34)

    def test_basic_false(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(condition_op(literal_op(False), literal_op(34), literal_op(53)))
            )
        )
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 53)


class TestLoops(TestCase):
    def test_immediate_return(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                loop_op(return_op(literal_op(42)))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_count_then_return(self):
        _, result = bootstrap_function(
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
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


class TestInferredBreakTypes(TestCase):
    def test_basic_inferrence(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(inferred_type()),
                return_op(literal_op(42))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_infer_all(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(), return_op(literal_op(42))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_infer_exception(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(), addition_op(literal_op("hello"), literal_op(5))
            ), check_safe_exit=False
        )

        self.assertEqual(result.caught_break_mode, "exception")
        self.assertEqual(result.value.type, "TypeError")

    def test_without_infer_exception_fails(self):
        with self.assertRaises(Exception):
            bootstrap_function(
                function_lit(
                    no_value_type(), build_break_types(int_type()), addition_op(literal_op("hello"), literal_op(5))
                )
            )


class TestFunctionPreparation(TestCase):
    def test_basic(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                return_op(invoke_op(close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), build_break_types(int_type()), return_op(literal_op(42))
                )))), context_op())))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


class TestFunctionInvocation(TestCase):
    def test_basic(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), build_break_types(int_type()),
                function_type(no_value_type(), build_break_types(int_type())),
                close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), build_break_types(int_type()), return_op(literal_op(42))
                )))), context_op()),
                return_op(invoke_op(dereference_op(context_op(), literal_op("local"), True)))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_basic_with_inferred_types(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                function_type(no_value_type(), build_break_types(int_type())),
                close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), infer_all(), return_op(literal_op(42))
                )))), context_op()),
                return_op(invoke_op(dereference_op(context_op(), literal_op("local"), True)))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_basic_with_inferred_local_type(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                inferred_type(),
                close_op(static_op(prepare_op(literal_op(function_lit(
                    no_value_type(), infer_all(), return_op(literal_op(42))
                )))), context_op()),
                return_op(invoke_op(dereference_op(context_op(), literal_op("local"), True)))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


class TestUnboundReference(TestCase):
    def test_unbound_reference_to_arguments(self):
        _, result = bootstrap_function(
            function_lit(
                object_type({ "foo": int_type(), "bar": int_type() }), infer_all(),
                return_op(addition_op(
                    unbound_dereference("foo"), unbound_dereference("bar")
                ))
            ), argument=PythonObject({ "foo": 39, "bar": 3 })
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_unbound_reference_to_locals(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                object_type({ "foo": int_type(), "bar": int_type() }),
                object_template_op({ "foo": literal_op(39), "bar": literal_op(3) }),
                return_op(addition_op(
                    unbound_dereference("foo"), unbound_dereference("bar")
                ))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_unbound_reference_to_locals_and_arguments(self):
        _, result = bootstrap_function(
            function_lit(
                object_type({ "foo": int_type() }), infer_all(),
                object_type({ "bar": int_type() }),
                object_template_op({ "bar": literal_op(3) }),
                return_op(addition_op(
                    unbound_dereference("foo"), unbound_dereference("bar")
                ))
            ), argument=PythonObject({ "foo": 39 })
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


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

        _, result = bootstrap_function(
            func, argument=PythonObject({ "foo": 39 }, bind=UniversalObjectType({ "foo": IntegerType() }))
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

        _, result = bootstrap_function(
            func, argument=PythonObject({ "foo": "hello" })
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "invalid")

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

        _, result = bootstrap_function(func, argument=1)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "one")
        _, result = bootstrap_function(func, argument=2)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "two")
        _, result = bootstrap_function(func, argument=3)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "three")
        _, result = bootstrap_function(func, argument=4)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "four")
        _, result = bootstrap_function(func, argument=5)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "invalid")

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

        _, result = bootstrap_function(func, argument=2)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "int is not a string")
        _, result = bootstrap_function(func, argument=True)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "bool is not a string")
        _, result = bootstrap_function(func, argument="hello world")
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "hello world")

        prepared_func = prepare(func, PythonObject({}), FrameManager())
        self.assertEqual(len(prepared_func.break_types), 1)
        self.assertTrue("return" in prepared_func.break_types)
        for return_break_type in prepared_func.break_types["return"]:
            self.assertTrue(StringType().is_copyable_from(return_break_type["out"], DUMMY_REASONER))


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
        _, result = bootstrap_function(func, argument="hello world", check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "exception")
        self.assertEqual(result.value, "hello world")
        _, result = bootstrap_function(func, argument=41, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

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

        _, result = bootstrap_function(func, argument=1, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "one")
        _, result = bootstrap_function(func, argument=2, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "two")
        _, result = bootstrap_function(func, argument=3, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "unknown")
        _, result = bootstrap_function(func, argument="hello", check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "exception")
        self.assertIsInstance(result.value, Universal)
        self.assertEqual(result.value._get("type"), "TypeError")

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
        _, result = bootstrap_function(func)
        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, "DereferenceOp: invalid_dereference")


class TestUtilityMethods(TestCase):
    def test_misc1(self):
        _, result = bootstrap_function(
            function_lit(
                no_value_type(), infer_all(),
                object_type({ "foo": int_type(), "bar": int_type() }),
                object_template_op({ "foo": literal_op(39), "bar": literal_op(3) }),
                return_op(addition_op(
                    dereference("local.foo"), dereference("local.bar")
                ))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_misc2(self):
        _, result = bootstrap_function(
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
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)

    def test_fizzbuzz(self):
        pass


class TestStatics(TestCase):
    def test_static_value_dereference(self):
        _, result = bootstrap_function(
            function_lit(
                return_op(static_op(addition_op(literal_op(5), literal_op(37))))
            )
        )

        self.assertEqual(result.caught_break_mode, "return")
        self.assertEqual(result.value, 42)


class TestContinuations(TestCase):
    def test_single_restart(self):
        context = PythonObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op("hello"), int_type()), literal_op(40)))
            ),
            context, frame_manager, None
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager, None)
        with frame_manager.capture("yield") as yielder:
            first()

        self.assertEqual(yielder.value, "hello")

        def second():
            yielder.create_continuation(first, {}).invoke(2, frame_manager, None)
        with frame_manager.capture("return") as returner:
            second()

        self.assertEqual(returner.value, 42)

    def test_repeated_restart(self):
        context = PythonObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(int_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op("first"), int_type()), shift_op(literal_op("second"), int_type())))
            ),
            context, frame_manager, None
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager, None)
        with frame_manager.capture("yield") as first_yielder:
            first()

        self.assertEqual(first_yielder.value, "first")

        def second():
            first_yielder_continuation = first_yielder.create_continuation(first, {})
            first_yielder_continuation.invoke(39, frame_manager, None)
        with frame_manager.capture("yield") as second_yielder:
            second()

        self.assertEqual(second_yielder.value, "second")

        def third():
            second_yielder_continuation = second_yielder.create_continuation(second, {})
            second_yielder_continuation.invoke(3, frame_manager, None)

        with frame_manager.capture() as returner:
            third()

        self.assertEqual(returner.value, 42)

    def test_repeated_restart_with_outer_return_handling(self):
        context = PythonObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(), build_break_types(int_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op("first"), int_type()), shift_op(literal_op("second"), int_type())))
            ),
            context, frame_manager, None
        ).close(None)

        with frame_manager.capture("return") as return_capturer:
            def first():
                func.invoke(NO_VALUE, frame_manager, None)
            with frame_manager.capture("yield") as first_yielder:
                first()
            self.assertEqual(first_yielder.value, "first")

            def second():
                first_yielder.create_continuation(first, {}).invoke(39, frame_manager, None)
            with frame_manager.capture("yield") as second_yielder:
                second()
            self.assertEqual(second_yielder.value, "second")

            second_yielder.create_continuation(second, {}).invoke(3, frame_manager, None)

        self.assertEqual(return_capturer.value, 42)

    def test_repeated_restart_while_using_restart_values(self):
        context = PythonObject({})
        frame_manager = FrameManager()

        func = prepare(
            function_lit(
                no_value_type(),
                build_break_types(return_type=any_type(), yield_types={ "out": any_type(), "in": int_type() }),
                return_op(addition_op(shift_op(literal_op(30), int_type()), shift_op(literal_op(10), int_type())))
            ),
            context, frame_manager, None
        ).close(None)

        def first():
            func.invoke(NO_VALUE, frame_manager, None)
        with frame_manager.capture("yield") as first_yielder:
            first()

        def second():
            first_yielder.create_continuation(first, {}).invoke(first_yielder.value + 1, frame_manager, None)
        with frame_manager.capture("yield") as second_yielder:
            second()

        def third():
            second_yielder.create_continuation(second, {}).invoke(second_yielder.value + 1, frame_manager, None)
        with frame_manager.capture("return") as returner:
            third()

        self.assertEqual(returner.value, 42)

