# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest import main
from unittest.case import TestCase

from lockdown.type_system.composites import CompositeType, InferredType, \
    check_dangling_inferred_types, prepare_lhs_type, add_composite_type,\
    scoped_bind
from lockdown.type_system.core_types import IntegerType, UnitType, StringType, \
    AnyType, Const, OneOfType, BooleanType, merge_types
from lockdown.type_system.exceptions import CompositeTypeIncompatibleWithTarget, \
    CompositeTypeIsInconsistent, FatalError, DanglingInferredType, \
    InvalidAssignmentType
from lockdown.type_system.managers import get_manager, get_type_of_value
from lockdown.type_system.reasoner import Reasoner, DUMMY_REASONER
from lockdown.type_system.universal_type import PythonObject, \
    DEFAULT_READONLY_COMPOSITE_TYPE, GetterMicroOpType, SetterMicroOpType, \
    UniversalObjectType, PythonList, UniversalTupleType, RICH_READONLY_TYPE, PythonDict, \
    DeletterWildcardMicroOpType, GetterWildcardMicroOpType, \
    SetterWildcardMicroOpType, UniversalDefaultDictType, UniversalListType, \
    SPARSE_ELEMENT, UniversalLupleType, InsertStartMicroOpType, RICH_TYPE, \
    DEFAULT_COMPOSITE_TYPE, NO_SETTER_ERROR_COMPOSITE_TYPE, Universal
from lockdown.utils.utils import skipIfNoOpcodeBindings

class TestMicroOpMerging(TestCase):
    def test_merge_gets(self):
        first = GetterMicroOpType("foo", IntegerType())
        second = GetterMicroOpType("foo", UnitType(5))

        combined = first.merge(second)
        self.assertTrue(isinstance(combined.value_type, UnitType))
        self.assertEqual(combined.value_type.value, 5)

    def test_merge_sets(self):
        first = SetterMicroOpType("foo", IntegerType())
        second = SetterMicroOpType("foo", UnitType(5))

        combined = first.merge(second)
        self.assertTrue(isinstance(combined.value_type, IntegerType))


class TestBasicObject(TestCase):
    def test_add_micro_op_dictionary(self):
        obj = PythonDict({ "foo": "hello" })
        add_composite_type(get_manager(obj), CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType())
        }, name="test"))

    def test_add_micro_op_object(self):
        class Foo(PythonObject):
            pass
        obj = Foo({ "foo": "hello" })
        add_composite_type(get_manager(obj), CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType())
        }, name="test"))

    def test_setup_read_write_property(self):
        obj = PythonObject({ "foo": "hello" })
        add_composite_type(get_manager(obj), CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test"))

    def test_setup_broad_read_write_property(self):
        obj = PythonObject({ "foo": "hello" })
        add_composite_type(get_manager(obj), CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", AnyType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType())
        }, name="test"))

    def test_setup_narrow_write_property(self):
        obj = PythonObject({ "foo": "hello" })
        add_composite_type(get_manager(obj), CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", UnitType("hello")),
            ("set", "foo"): SetterMicroOpType("foo", UnitType("hello"))
        }, name="test"))

    def test_setup_broad_reading_property(self):
        obj = PythonObject({ "foo": "hello" })
        add_composite_type(get_manager(obj), CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", AnyType()),
            ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test"))

    @skipIfNoOpcodeBindings
    def test_failed_setup_broad_writing_property(self):
        obj = PythonObject({ "foo": "hello" })

        with self.assertRaises(CompositeTypeIsInconsistent):
            add_composite_type(get_manager(obj), CompositeType({
                ("get", "foo"): GetterMicroOpType("foo", StringType()),
                ("set", "foo"): SetterMicroOpType("foo", AnyType())
            }, name="test"))

    def test_composite_object_dereference(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test")):
            self.assertEqual(obj.foo, "hello")

    def test_composite_object_broad_dereference(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", AnyType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType())
        }, name="test")):
            self.assertEqual(obj.foo, "hello")

    def test_composite_object_assignment(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test")):
            obj.foo = "what"

    def test_composite_object_invalid_assignment(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test")):
            with self.assertRaises(TypeError):
                obj.foo = 5

    def test_python_like_object(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", AnyType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType())
        }, name="test")):
            self.assertEqual(obj.foo, "hello")
            obj.foo = "what"
            self.assertEqual(obj.foo, "what")

    def test_java_like_object(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
                ("get", "foo"): GetterMicroOpType("foo", StringType()),
                ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test")):
            self.assertEqual(obj.foo, "hello")
            obj.foo = "what"
            self.assertEqual(obj.foo, "what")

            with self.assertRaises(AttributeError):
                obj.bar = "hello"

    def test_const_property(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType())
        }, name="test")):
            self.assertEqual(obj.foo, "hello")
            with self.assertRaises(AttributeError):
                obj.foo = "what"

    def test_delete_property(self):
        obj = PythonObject({ "foo": "hello" })

        with scoped_bind(obj, CompositeType({
            ("delete-wildcard", ): DeletterWildcardMicroOpType(StringType(), True)
        }, name="test")):
            del obj.foo
            self.assertFalse(hasattr(obj, "foo"))


class TestRevConstType(TestCase):
    def test_rev_const_assigned_to_broad_type(self):
        rev_const_type = CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType()),
        }, name="test")

        normal_broad_type = CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", AnyType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType())
        }, name="test")

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type, DUMMY_REASONER))

    def test_rev_const_assigned_to_narrow_type(self):
        rev_const_type = CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType())
        }, name="test")

        normal_broad_type = CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test")

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type, DUMMY_REASONER))

    @skipIfNoOpcodeBindings
    def test_rev_const_can_not_be_added_to_object(self):
        rev_const_type = CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType())
        }, name="test")

        obj = PythonObject({ "foo": "hello" })
        with self.assertRaises(CompositeTypeIsInconsistent):
            add_composite_type(get_manager(obj), rev_const_type)

    def test_rev_const_narrowing(self):
        rev_const_type = CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", AnyType())
        }, name="test")

        normal_broad_type = CompositeType({
            ("get", "foo"): GetterMicroOpType("foo", StringType()),
            ("set", "foo"): SetterMicroOpType("foo", StringType())
        }, name="test")

        rev_const_type = prepare_lhs_type(rev_const_type, None)

        self.assertTrue(isinstance(rev_const_type.get_micro_op_type(("set", "foo")).value_type, StringType))

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type, DUMMY_REASONER))

    def test_rev_const_wildcard(self):
        rev_const_type = CompositeType({
            ("get-wildcard", ): GetterWildcardMicroOpType(StringType(), StringType(), True),
            ("set-wildcard", ): SetterWildcardMicroOpType(StringType(), AnyType(), False, False)
        }, name="test")

        normal_broad_type = CompositeType({
            ("get-wildcard", ): GetterWildcardMicroOpType(StringType(), AnyType(), True),
            ("set-wildcard", ): SetterWildcardMicroOpType(StringType(), AnyType(), False, False)
        }, name="test")

        rev_const_type = prepare_lhs_type(rev_const_type, None)

        self.assertTrue(isinstance(rev_const_type.get_micro_op_type(("set-wildcard",)).value_type, AnyType))

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type, DUMMY_REASONER))

    def test_rev_const_flatten_tuple(self):
        rev_const_type = CompositeType({
            ("get", 0): GetterMicroOpType(0, StringType()),
            ("set", 0): SetterMicroOpType(0, AnyType())
        }, name="test")

        normal_broad_type = CompositeType({
            ("get", 0): GetterMicroOpType(0, StringType()),
            ("set", 0): SetterMicroOpType(0, StringType())
        }, name="test")

        rev_const_type = prepare_lhs_type(rev_const_type, None)

        self.assertTrue(isinstance(rev_const_type.get_micro_op_type(("set", 0)).value_type, StringType))

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type, DUMMY_REASONER))

    def test_rev_const_flatten_list(self):
        rev_const_type = CompositeType({
            ("get", 0): GetterMicroOpType(0, StringType()),
            ("set", 0): SetterMicroOpType(0, AnyType()),
            ("insert-start",): InsertStartMicroOpType(IntegerType(), False)
        }, name="test")

        normal_broad_type = CompositeType({
            ("get", 0): GetterMicroOpType(0, StringType()),
            ("set", 0): SetterMicroOpType(0, StringType()),
        }, name="test")

        rev_const_type = prepare_lhs_type(rev_const_type, None)

        self.assertTrue(rev_const_type.is_self_consistent(DUMMY_REASONER))

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type, DUMMY_REASONER))

    def test_rev_const_merge_types_in_list(self):
        rev_const_type = CompositeType({
            ("get", 0): GetterMicroOpType(0, StringType()),
            ("set", 0): SetterMicroOpType(0, StringType()),
            ("get", 1): GetterMicroOpType(1, IntegerType()),
            ("set", 1): SetterMicroOpType(1, IntegerType()),
            ("get", 2): GetterMicroOpType(2, AnyType()),
            ("set", 2): SetterMicroOpType(2, AnyType()),
            ("insert-start", ): InsertStartMicroOpType(StringType(), False)
        }, name="test")

        normal_broad_type = CompositeType({
            ("get", 0): GetterMicroOpType(0, StringType()),
            ("set", 0): SetterMicroOpType(0, StringType()),
            ("get", 1): GetterMicroOpType(1, IntegerType()),
            ("set", 1): SetterMicroOpType(1, IntegerType()),
            ("get", 2): GetterMicroOpType(2, AnyType()),
            ("set", 2): SetterMicroOpType(2, AnyType()),
        }, name="test")

        self.assertFalse(rev_const_type.is_self_consistent(DUMMY_REASONER))

        rev_const_type = prepare_lhs_type(rev_const_type, None)

        self.assertTrue(rev_const_type.is_self_consistent(DUMMY_REASONER))

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type, DUMMY_REASONER))

class TestUniversalObjectType(TestCase):
    def test_basic_class(self):
        T = UniversalObjectType({
            "foo": IntegerType()
        })

        S = UniversalObjectType({
            "foo": IntegerType(),
            "bar": StringType()
        })

        self.assertTrue(T.is_copyable_from(S, DUMMY_REASONER))
        self.assertFalse(S.is_copyable_from(T, DUMMY_REASONER))

    def test_const_allows_broader_types(self):
        T = UniversalObjectType({
            "foo": Const(AnyType())
        })

        S = UniversalObjectType({
            "foo": IntegerType()
        })

        self.assertTrue(T.is_copyable_from(S, DUMMY_REASONER))
        self.assertFalse(S.is_copyable_from(T, DUMMY_REASONER))

    def test_broad_type_assignments_blocked(self):
        T = UniversalObjectType({
            "foo": AnyType()
        })

        S = UniversalObjectType({
            "foo": IntegerType()
        })

        self.assertFalse(T.is_copyable_from(S, DUMMY_REASONER))
        self.assertFalse(S.is_copyable_from(T, DUMMY_REASONER))

    def test_simple_fields_are_required(self):
        T = UniversalObjectType({
        })

        S = UniversalObjectType({
            "foo": IntegerType()
        })

        self.assertTrue(T.is_copyable_from(S, DUMMY_REASONER))
        self.assertFalse(S.is_copyable_from(T, DUMMY_REASONER))

    def test_many_fields_are_required(self):
        T = UniversalObjectType({
            "foo": IntegerType(),
            "bar": IntegerType(),
        })

        S = UniversalObjectType({
            "foo": IntegerType(),
            "bar": IntegerType(),
            "baz": IntegerType()
        })

        self.assertTrue(T.is_copyable_from(S, DUMMY_REASONER))
        self.assertFalse(S.is_copyable_from(T, DUMMY_REASONER))

    def test_can_fail_micro_ops_are_enforced(self):
        foo = PythonObject({
            "foo": 5,
            "bar": "hello"
        })

        with scoped_bind(foo,
            UniversalObjectType({ "foo": Const(IntegerType()) })
        ):
            with self.assertRaises(Exception):
                foo.foo = "hello"

    def test_const_is_enforced(self):
        return  # test doesn't work because the assignment uses the set-wildcard
        foo = {
            "foo": 5,
            "bar": "hello"
        }

        add_composite_type(get_manager(foo),
            UniversalObjectType({ "foo": Const(IntegerType()) })
        )

        with self.assertRaises(Exception):
            foo.foo = 42

    def test_types_on_object_merged(self):
        foo = PythonObject({
            "foo": 5,
            "bar": "hello"
        })
        with scoped_bind(foo,
            UniversalObjectType({ "foo": IntegerType() })
        ):
            with scoped_bind(foo,
                UniversalObjectType({ "bar": StringType() })
            ):
                object_type = get_manager(foo).get_effective_composite_type()

                UniversalObjectType({
                    "foo": IntegerType(),
                    "bar": StringType()
                }).is_copyable_from(object_type, DUMMY_REASONER)


class TestUnitTypes(TestCase):
    def test_basics(self):
        foo = PythonObject({
            "bar": 42
        })
        with scoped_bind(foo, UniversalObjectType({
            "bar": UnitType(42)
        })):
            self.assertEqual(foo.bar, 42)

    def test_broadening_blocked(self):
        foo = PythonObject({
            "bar": 42
        })
        with scoped_bind(foo, UniversalObjectType({
            "bar": UnitType(42)
        })):
            with self.assertRaises(CompositeTypeIncompatibleWithTarget):
                add_composite_type(get_manager(foo), UniversalObjectType({
                    "bar": IntegerType()
                }))

    def test_narrowing_blocked(self):
        foo = PythonObject({
            "bar": 42
        })
        with scoped_bind(foo, UniversalObjectType({
                "bar": IntegerType()
            })):
            with self.assertRaises(CompositeTypeIncompatibleWithTarget):
                add_composite_type(get_manager(foo), UniversalObjectType({
                    "bar": UnitType(42)
                }))

    def test_broadening_with_const_is_ok(self):
        foo = PythonObject({
            "bar": 42
        })
        with scoped_bind(foo, UniversalObjectType({
            "bar": UnitType(42)
        })):
            with scoped_bind(foo, UniversalObjectType({
                "bar": Const(IntegerType())
            })):
                pass


class TestNestedUniversalObjectTypes(TestCase):
    def test_basic_assignment(self):
        Bar = UniversalObjectType({
            "baz": IntegerType()
        })
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo,
            UniversalObjectType({
                "bar": Bar
            })
        ):
            foo.bar = PythonObject({ "baz": 42 }, bind=Bar)

            self.assertEqual(foo.bar.baz, 42)

    def test_blocked_basic_assignment(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo,
            UniversalObjectType({
                "bar": UniversalObjectType({
                    "baz": IntegerType()
                })
            })
        ):
            with self.assertRaises(Exception):
                foo.bar = PythonObject({ "baz": "hello" })

    def test_deletion_blocked(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo,
            UniversalObjectType({
                "bar": UniversalObjectType({
                    "baz": IntegerType()
                })
            })
        ):
            with self.assertRaises(Exception):
                del foo.bar

    def test_broad_assignment(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        Bar = UniversalObjectType({
            "baz": AnyType()
        })

        with scoped_bind(foo,
            UniversalObjectType({
                "bar": Bar
            })
        ):
            foo.bar = PythonObject({ "baz": "hello" }, bind=Bar)

            self.assertEqual(foo.bar.baz, "hello")

    def test_double_deep_assignment(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": PythonObject({
                    "bam": 10
                })
            })
        })

        Baz = UniversalObjectType({
            "bam": IntegerType()
        })

        Bar = UniversalObjectType({
            "baz": Baz
        })

        with scoped_bind(foo,
            UniversalObjectType({
                "bar": Bar
            })
        ):
            self.assertEqual(foo.bar.baz.bam, 10)

            foo.bar = PythonObject({ "baz": PythonObject({ "bam": 42 }) }, bind=Bar)

            self.assertEqual(foo.bar.baz.bam, 42)

    def test_conflicting_types(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo,
            UniversalObjectType({
                "bar": UniversalObjectType({
                    "baz": IntegerType()
                })
            })
        ):
            with self.assertRaises(Exception):
                add_composite_type(get_manager(foo),
                    UniversalObjectType({
                        "bar": UniversalObjectType({
                            "baz": AnyType()
                        })
                    })
                )

    def test_changes_blocked_without_micro_ops(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with self.assertRaises(Exception):
            foo.bar = "hello"

    def test_very_broad_assignment(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo,
            UniversalObjectType({ "bar": AnyType() })
        ):
            foo.bar = "hello"
            self.assertEqual(foo.bar, "hello")


class TestNestedPythonTypes(TestCase):
    def test_python_like_type(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
            foo.bar.baz = 22

            foo.bar = "hello"
            self.assertEqual(foo.bar, "hello")

    def test_python_object_with_reference_can_be_modified(self):
        bar = PythonObject({
            "baz": 42
        })
        foo = PythonObject({
            "bar": bar
        })

        with scoped_bind(bar, UniversalObjectType({ "baz": IntegerType() })):
            with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
                self.assertEqual(foo.bar.baz, 42)
                foo.bar.baz = 5
                self.assertEqual(foo.bar.baz, 5)

    def test_python_object_with_reference_types_are_enforced(self):
        bar = PythonObject({
            "baz": 42
        })
        foo = PythonObject({
            "bar": bar
        })

        add_composite_type(get_manager(bar), UniversalObjectType({ "baz": IntegerType() }))
        add_composite_type(get_manager(foo), DEFAULT_COMPOSITE_TYPE)

        with self.assertRaises(Exception):
            foo.bar.baz = "hello"

    def test_python_object_with_reference_can_be_replaced(self):
        bar = PythonObject({
            "baz": 42
        })
        foo = PythonObject({
            "bar": bar
        })

        with scoped_bind(bar, UniversalObjectType({ "baz": IntegerType() })):
            with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
                foo.bar = PythonObject({
                    "baz": 123
                })

                self.assertEqual(foo.bar.baz, 123)
                foo.bar.baz = "what"
                self.assertEqual(foo.bar.baz, "what")

    def test_that_python_constraints_dont_spread_to_constrained_children(self):
        bar = PythonObject({
            "baz": 42
        })
        foo = PythonObject({
            "bar": bar
        })

        # The first, stronger, type prevents the NO_SETTER_ERROR_COMPOSITE_TYPE spreading from foo to bar
        with scoped_bind(bar, UniversalObjectType({ "baz": IntegerType() })):
            with scoped_bind(foo, NO_SETTER_ERROR_COMPOSITE_TYPE):
                self.assertIs(foo.bar, bar)

                self.assertEqual(len(get_manager(foo).get_attached_nodes()), 1)
                self.assertEqual(len(get_manager(foo.bar).get_attached_nodes()), 1)

                # ... but when bar is replaced with a new object without constraints, the PythonObjectType
                # spreads to the new object
                foo.bar = PythonObject({
                    "baz": 123
                })

                self.assertIsNot(foo.bar, bar)

                self.assertEqual(len(get_manager(foo.bar).get_attached_nodes()), 1)

                # Now that the new object has the PythonObjectType constraint, we can't bind a stronger
                # constraint
                with self.assertRaises(CompositeTypeIncompatibleWithTarget):
                    add_composite_type(get_manager(foo.bar), UniversalObjectType({ "baz": IntegerType() }))

    def test_python_constraints_work_with_lists(self):
        foo = PythonObject({
            "bar": PythonList([ 1, 2, 3 ])
        })

        with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
            del foo.bar[1]

    def test_python_constraints_work_with_lists2(self):
        foo = PythonObject({
            "bar": PythonList([ 1, 2, 3 ])
        })

        with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
            foo.bar.insert(2, 5)
            self.assertListEqual([ 1, 2, 5, 3 ], foo._get("bar")._to_list())

    def test_python_constraints_work_with_lists3(self):
        foo = Universal(True, initial_wrapped={
            "bar": Universal(False, initial_wrapped={ 0: 1, 1: 2, 2: 3 })
        })

        with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
            Bar = get_manager(foo._get("bar")).get_effective_composite_type()

            iter = Bar.get_micro_op_type(("iter", ))

            self.assertIsNotNone(iter)

    def test_python_delete_works(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
            del foo.bar
            self.assertFalse(hasattr(foo, "bar"))

    def test_python_replacing_object_works(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
            foo.bar = PythonObject({ "baz": 123 })
            self.assertEqual(foo.bar.baz, 123)

    def test_python_random_read_fails_nicely(self):
        foo = PythonObject({
            "bar": PythonObject({
                "baz": 42
            })
        })

        with scoped_bind(foo, DEFAULT_COMPOSITE_TYPE):
            with self.assertRaises(AttributeError):
                foo.bop

class TestDefaultDict(TestCase):
    def test_default_dict_is_consistent_type(self):
        type = UniversalDefaultDictType(StringType(), StringType(), name="test")
        self.assertTrue(type.is_self_consistent(DUMMY_REASONER))

    def test_default_dict(self):
        def default_factory(target, key):
            return "{}-123".format(key)

        foo = PythonObject({
            "bar": "forty-two"
        }, default_factory=default_factory)

        with scoped_bind(foo, UniversalDefaultDictType(StringType(), StringType(), name="test")):
            self.assertEqual(foo.bar, "forty-two")
            self.assertEqual(foo.bam, "bam-123")

class TestListObjects(TestCase):
    def test_lists_cant_be_accessed_without_types(self):
        foo = PythonList([ 1, 2, 3 ])
        with self.assertRaises(IndexError):
            foo[0]

    def test_basic_list_of_ints(self):
        foo = PythonList([ 1, 2, 3 ])

        with scoped_bind(foo, UniversalListType(IntegerType())):
            foo[0] = 42
            self.assertEqual(foo[0], 42)

    def test_basic_tuple_of_ints(self):
        foo = PythonList([ 1, 2, 3 ])

        with scoped_bind(foo, UniversalTupleType([ IntegerType(), IntegerType(), IntegerType() ])):
            foo[0] = 42
            self.assertEqual(foo[0], 42)

    def test_bounds_enforced(self):
        foo = PythonList([ 1, 2 ])

        with self.assertRaises(Exception):
            add_composite_type(get_manager(foo), UniversalTupleType([ IntegerType(), IntegerType(), IntegerType() ]))


class TestTypeSystemMisc(TestCase):
    # Tests for random things that were broken
    def test_misc1(self):
        # Came up testing lockdown local variable binding
        PythonObject({
            "local": PythonList([ 39, 3 ]),
            "types": PythonObject({})
        }, bind=UniversalObjectType({
            "local": UniversalTupleType([ IntegerType(), IntegerType() ]),
            "types": DEFAULT_READONLY_COMPOSITE_TYPE
        }, wildcard_type=RICH_READONLY_TYPE))

    def test_misc2(self):
        # Came up writing test_misc1
        PythonObject({
            "local": PythonList([ 39, 3 ])
        }, bind=UniversalObjectType({
            "local": UniversalTupleType([ IntegerType(), IntegerType() ])
        }, wildcard_type=RICH_READONLY_TYPE))

    def test_misc3(self):
        t = UniversalTupleType([ IntegerType(), IntegerType() ])
        self.assertTrue(t.is_self_consistent(DUMMY_REASONER))

class TestDefaultCompositeTypes(TestCase):
    def test_all_consistent(self):
        self.assertTrue(DEFAULT_READONLY_COMPOSITE_TYPE.is_self_consistent(DUMMY_REASONER))
        self.assertTrue(DEFAULT_COMPOSITE_TYPE.is_self_consistent(DUMMY_REASONER))

class TestUniversalListType(TestCase):
    def test_simple_list_assignment(self):
        foo = UniversalTupleType([], IntegerType())
        bar = UniversalTupleType([], IntegerType())

        self.assertTrue(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_simple_tuple_assignment(self):
        foo = UniversalTupleType([ IntegerType(), IntegerType() ], None)
        bar = UniversalTupleType([ IntegerType(), IntegerType() ], None)

        self.assertTrue(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_broadening_tuple_assignment_blocked(self):
        foo = UniversalTupleType([ AnyType(), AnyType() ], None)
        bar = UniversalTupleType([ IntegerType(), IntegerType() ], None)

        self.assertFalse(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_narrowing_tuple_assignment_blocked(self):
        foo = UniversalTupleType([ IntegerType(), IntegerType() ])
        bar = UniversalTupleType([ AnyType(), AnyType() ])

        self.assertFalse(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_broadening_tuple_assignment_allowed_with_const(self):
        foo = UniversalTupleType([ Const(AnyType()), Const(AnyType()) ])
        bar = UniversalTupleType([ IntegerType(), IntegerType() ])

        self.assertTrue(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_truncated_tuple_slice_assignment(self):
        foo = UniversalTupleType([ IntegerType() ])
        bar = UniversalTupleType([ IntegerType(), IntegerType() ])

        self.assertTrue(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_expanded_tuple_slice_assignment_blocked(self):
        foo = UniversalTupleType([ IntegerType(), IntegerType() ])
        bar = UniversalTupleType([ IntegerType() ])

        self.assertFalse(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_const_covariant_array_assignment_allowed(self):
        foo = UniversalListType(Const(AnyType()))
        bar = UniversalListType(IntegerType())

        self.assertTrue(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_convert_tuple_to_list_with_deletes_blocked(self):
        foo = UniversalListType(IntegerType())
        bar = UniversalTupleType([ IntegerType(), IntegerType() ], None)

        self.assertFalse(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_same_type_array_assignment(self):
        foo = UniversalListType(IntegerType())
        bar = UniversalListType(IntegerType())

        self.assertTrue(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_covariant_array_assignment_blocked(self):
        foo = UniversalListType(AnyType())
        bar = UniversalListType(IntegerType())

        self.assertFalse(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_narrowing_assignment_blocked(self):
        foo = UniversalListType(IntegerType())
        bar = UniversalListType(Const(AnyType()))

        self.assertTrue(bar.is_copyable_from(foo, DUMMY_REASONER))
        self.assertFalse(foo.is_copyable_from(bar, DUMMY_REASONER))

    def test_extreme_type1_contains_conflicts(self):
        foo = UniversalLupleType([ IntegerType() ], StringType())
        self.assertFalse(foo.is_self_consistent(DUMMY_REASONER))

    def test_reified_extreme_type_contains_no_conflicts(self):
        foo = prepare_lhs_type(UniversalLupleType([ IntegerType() ], IntegerType()), None)
        self.assertTrue(foo.is_self_consistent(DUMMY_REASONER))

    def test_simple_type1_has_no_conflicts(self):
        foo = UniversalListType(IntegerType())
        self.assertTrue(foo.is_self_consistent(DUMMY_REASONER))

    def test_simple_type2_has_no_conflicts(self):
        foo = UniversalTupleType([ IntegerType() ])
        self.assertTrue(foo.is_self_consistent(DUMMY_REASONER))

    def test_extreme_type_tamed1_has_no_conflicts(self):
        foo = UniversalLupleType([ IntegerType() ], IntegerType())
        self.assertTrue(foo.is_self_consistent(DUMMY_REASONER))

    def test_extreme_type_tamed2_contains_conflicts(self):
        foo = UniversalLupleType([ IntegerType() ], AnyType())
        self.assertTrue(foo.is_self_consistent(DUMMY_REASONER))

class TestList(TestCase):
    def test_simple_list_assignment(self):
        foo = PythonList([ 4, 6, 8 ])
        add_composite_type(get_manager(foo), UniversalListType(IntegerType()))

    def test_list_modification_wrong_type_blocked(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalListType(IntegerType())):
            with self.assertRaises(TypeError):
                foo.append("hello")

    def test_list_modification_right_type_ok(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalListType(IntegerType())):
            foo.append(10)

    def test_list_appending_blocked(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalTupleType([])):
            with self.assertRaises(IndexError):
                foo.append(10)

    def test_mixed_type_tuple(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalTupleType([ IntegerType(), AnyType() ])):
            with self.assertRaises(TypeError):
                foo[0] = "hello"

            self.assertEqual(foo[0], 4)

            foo[1] = "what"
            self.assertEqual(foo[1], "what")

    def test_outside_tuple_access_blocked(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalTupleType([ IntegerType(), AnyType() ])):
            with self.assertRaises(IndexError):
                foo[2]
            with self.assertRaises(IndexError):
                foo[2] = "hello"

    def test_outside_tuple_access_allowed(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalListType(AnyType())):
            self.assertEqual(foo[2], 8)
            foo[2] = "hello"
            self.assertEqual(foo[2], "hello")

    def test_combined_const_list_and_tuple(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalLupleType([ IntegerType(), AnyType() ], Const(AnyType()))):
            self.assertEqual(foo[2], 8)

    def test_insert_at_start(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalListType(IntegerType())):
            foo.insert(0, 2)
            self.assertEqual(list(foo), [ 2, 4, 6, 8 ])

    def test_insert_with_wrong_type_blocked(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalListType(IntegerType())):
            with self.assertRaises(Exception):
                foo.insert(0, "hello")

    def test_luple_type_is_consistent(self):
        type = UniversalLupleType(
            [ IntegerType(), IntegerType() ],
            IntegerType()
        )
        self.assertTrue(type.is_self_consistent(DUMMY_REASONER))

    def test_insert_on_short_tuple(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalLupleType([ IntegerType() ], IntegerType())):
            foo.insert(0, 2)
            self.assertEqual(list(foo), [ 2, 4, 6, 8 ])

    def test_insert_on_long_tuple(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo,
            UniversalLupleType(
                [ IntegerType(), IntegerType() ],
                IntegerType()
            )
        ):
            foo.insert(0, 2)
            self.assertEqual(list(foo), [ 2, 4, 6, 8 ])

    def test_insert_on_very_long_tuple(self):
        foo = PythonList([ 4, 6, 8, 10, 12, 14 ])
        with scoped_bind(foo, UniversalLupleType([ IntegerType(), IntegerType(), IntegerType(), IntegerType(), IntegerType(), IntegerType() ], IntegerType())):
            foo.insert(0, 2)
            self.assertEqual(list(foo), [ 2, 4, 6, 8, 10, 12, 14 ])

    def test_sparse_list_setting(self):
        foo = PythonList([ 4, 6, 8 ], is_sparse=True)
        with scoped_bind(foo, UniversalListType(IntegerType(), is_sparse=True)):
            foo[4] = 12
            self.assertEqual(list(foo), [ 4, 6, 8, SPARSE_ELEMENT, 12 ])

    def test_sparse_list_inserting(self):
        foo = PythonList([ 4, 6, 8 ], is_sparse=True)
        with scoped_bind(foo, UniversalListType(IntegerType(), is_sparse=True)):
            foo.insert(4, 12)
            self.assertEqual(list(foo), [ 4, 6, 8, SPARSE_ELEMENT, 12 ])

    def test_set_on_non_sparse_blocked(self):
        foo = PythonList([ 4, 6, 8 ])
        with scoped_bind(foo, UniversalListType(IntegerType(), is_sparse=False)):
            with self.assertRaises(IndexError):
                foo[4] = 12

    def test_incorrect_type_blocked(self):
        foo = PythonList([ 4, 6, 8 ])

        with self.assertRaises(Exception):
            add_composite_type(get_manager(foo), UniversalListType(StringType()))


class TestInferredTypes(TestCase):
    def test_basic(self):
        foo = InferredType()
        foo = prepare_lhs_type(foo, IntegerType())
        self.assertIsInstance(foo, IntegerType)

    def test_basic_object(self):
        foo = UniversalObjectType({
            "bar": InferredType()
        })
        foo = prepare_lhs_type(foo, UniversalObjectType({
            "bar": IntegerType()
        }))
        self.assertIsInstance(foo.get_micro_op_type(("get", "bar")).value_type, IntegerType)

    def test_basic_ignored(self):
        foo = UniversalObjectType({
            "bar": StringType()
        })
        foo = prepare_lhs_type(foo, UniversalObjectType({
            "bar": IntegerType()
        }))
        self.assertIsInstance(foo.get_micro_op_type(("get", "bar")).value_type, StringType)

    def test_basic_ignored2(self):
        foo = UniversalObjectType({
            "bar": InferredType()
        })
        foo = prepare_lhs_type(foo, UniversalObjectType({
            "bar": IntegerType(),
            "bam": StringType()
        }))
        self.assertIsInstance(foo.get_micro_op_type(("get", "bar")).value_type, IntegerType)

    def test_dangling_error(self):
        foo = UniversalObjectType({
            "bar": InferredType()
        })
        with self.assertRaises(DanglingInferredType):
            foo = prepare_lhs_type(foo, UniversalObjectType({
                "bam": StringType()
            }))
        check_dangling_inferred_types(foo, {})

    def test_double_nested(self):
        Initial_Foo = UniversalObjectType({
            "bar": UniversalObjectType({
                "bam": InferredType()
            })
        })
        RHS_Foo = UniversalObjectType({
            "bar": UniversalObjectType({
                "bam": IntegerType()
            })
        })

        resolved_Foo = prepare_lhs_type(Initial_Foo, RHS_Foo)
        self.assertIsInstance(resolved_Foo.get_micro_op_type(("get", "bar")).value_type.get_micro_op_type(("get", "bam")).value_type, IntegerType)

    def test_composite_types_inferred(self):
        foo = UniversalObjectType({
            "bar": InferredType()
        })
        foo = prepare_lhs_type(foo, UniversalObjectType({
            "bar": UniversalObjectType({
                "bam": IntegerType()
            })
        }))
        self.assertIsInstance(foo.get_micro_op_type(("get", "bar")).value_type.get_micro_op_type(("get", "bam")).value_type, IntegerType)


class TestOneOfTypes(TestCase):
    def test_basic(self):
        self.assertTrue(OneOfType([IntegerType(), StringType()]).is_copyable_from(IntegerType(), DUMMY_REASONER))
        self.assertTrue(OneOfType([IntegerType(), StringType()]).is_copyable_from(StringType(), DUMMY_REASONER))
        self.assertFalse(StringType().is_copyable_from(OneOfType([IntegerType(), StringType()]), DUMMY_REASONER))

    def test_nested(self):
        self.assertTrue(
            UniversalObjectType({
                "foo": OneOfType([ IntegerType(), StringType() ])
            }).is_copyable_from(UniversalObjectType({
                "foo": OneOfType([ IntegerType(), StringType() ])
            }), DUMMY_REASONER)
        )

        # Blocked because the receiver could set obj.foo = "hello", breaking the sender
        self.assertFalse(
            UniversalObjectType({
                "foo": OneOfType([ IntegerType(), StringType() ])
            }).is_copyable_from(UniversalObjectType({
                "foo": IntegerType()
            }), DUMMY_REASONER)
        )

        self.assertTrue(
            UniversalObjectType({
                "foo": Const(OneOfType([ IntegerType(), StringType() ]))
            }).is_copyable_from(UniversalObjectType({
                "foo": IntegerType()
            }), DUMMY_REASONER)
        )

    def test_runtime(self):
        obj = PythonObject({
            "foo": 5
        })
        add_composite_type(get_manager(obj),
            UniversalObjectType({
                "foo": OneOfType([ IntegerType(), StringType() ])
            })
        )

class TestRuntime(TestCase):
    def test_repeated_adding(self):
        A = PythonObject({
            "foo": 5
        })
        B = PythonObject({
            "bar": A
        })

        At = UniversalObjectType({
            "foo": IntegerType()
        })

        Bt = UniversalObjectType({
            "bar": At
        })

        Atn = add_composite_type(get_manager(A), At)
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 1)
        Btn = add_composite_type(get_manager(B), Bt)
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 1)
        Btn2 = add_composite_type(get_manager(B), Bt)
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 1)


    def test_wildcard_extensions(self):
        B = PythonObject({
            "foo": 5
        })
        A = PythonObject({
            "bar": B
        })

        Bt = UniversalObjectType({
            "foo": IntegerType()
        })
        At = UniversalObjectType({
            "bar": Bt
        }, wildcard_type=Bt)

        Atn = add_composite_type(get_manager(A), At)
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 1)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 1)

        Atn = None
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 0)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 0)


    def test_overlapping_types(self):
        B = PythonObject({
            "foo": 5
        })
        A = PythonObject({
            "bar": B
        })

        Bt = UniversalObjectType({
            "foo": IntegerType()
        })
        At = UniversalObjectType({
            "bar": Bt
        })

        Bs = UniversalObjectType({
            "foo": IntegerType()
        })
        As = UniversalObjectType({
            "bar": Bs
        })

        Atn = add_composite_type(get_manager(A), At)
        Asn = add_composite_type(get_manager(A), As)
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 2)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 2)

        Atn = None
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 1)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 1)

        Asn = None
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 0)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 0)


    def test_overlapping_with_rich_type(self):
        B = PythonObject({
            "foo": 5
        })
        A = PythonObject({
            "bar": B
        })

        Bt = UniversalObjectType({
            "foo": IntegerType()
        })

        At = UniversalObjectType({
            "bar": Bt
        })

        Atn = add_composite_type(get_manager(A), At)
        Dtn = add_composite_type(get_manager(A), DEFAULT_COMPOSITE_TYPE)
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 2)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 2)

        Atn = None
        Dtn = None
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 0)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 0)


    def test_modifying(self):
        At = UniversalObjectType({
            "foo": IntegerType()
        })

        Bt = UniversalObjectType({
            "bar": At
        })

        A = PythonObject({
            "foo": 5
        })
        B = PythonObject({
            "bar": A
        }, bind=Bt)

        self.assertEqual(len(get_manager(A).get_attached_nodes()), 1)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 1)

        B.bar = PythonObject({
            "foo": 42
        }, bind=At)
        
        self.assertEqual(len(get_manager(A).get_attached_nodes()), 0)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 1)

    def test_modifying2(self):
        Bt = UniversalObjectType({
            "foo": IntegerType()
        })

        At = UniversalObjectType({
            "bar": Bt
        })

        B = PythonObject({
            "foo": 5
        })
        A = PythonObject({
            "bar": B
        })

        Atn = add_composite_type(get_manager(A), At)
        Dtn = add_composite_type(get_manager(A), DEFAULT_COMPOSITE_TYPE)

        self.assertEqual(len(get_manager(A).get_attached_nodes()), 2)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 2)

        B2 = PythonObject({
            "foo": 42
        })

        A.bar = B2

        self.assertEqual(len(get_manager(A).get_attached_nodes()), 2)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 0)
        self.assertEqual(len(get_manager(B2).get_attached_nodes()), 2)

    def test_modifying_list(self):
        Bt = UniversalObjectType({
            "foo": IntegerType()
        })

        At = UniversalListType(Bt)

        B = PythonObject({
            "foo": 5
        })
        A = PythonList([ B ])

        Atn = add_composite_type(get_manager(A), At)
        Dtn = add_composite_type(get_manager(A), DEFAULT_COMPOSITE_TYPE)

        self.assertEqual(len(get_manager(A).get_attached_nodes()), 2)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 2)

        B2 = PythonObject({
            "foo": 42
        })

        A[0] = B2

        self.assertEqual(len(get_manager(A).get_attached_nodes()), 2)
        self.assertEqual(len(get_manager(B).get_attached_nodes()), 0)
        self.assertEqual(len(get_manager(B2).get_attached_nodes()), 2)

class TestRDHInstances(TestCase):
    def test_object_set_and_get(self):
        foo = PythonObject({})
        foo._set("foo", 42)

        self.assertEqual(foo._get("foo"), 42)

    def test_list_set_and_get(self):
        foo = PythonList([ 123 ])
        foo._set(0, 42)

        self.assertEqual(foo._get(0), 42)

    def test_list_insert(self):
        foo = PythonList([ 123 ])
        foo._insert(0, 42)

        self.assertEqual(foo._to_list(), [ 42, 123 ])
        

class TestCoreTypes(TestCase):
    def test_ints_and_bools(self):
        self.assertTrue(IntegerType().is_copyable_from(IntegerType(), DUMMY_REASONER))
        self.assertTrue(BooleanType().is_copyable_from(BooleanType(), DUMMY_REASONER))
        self.assertFalse(BooleanType().is_copyable_from(IntegerType(), DUMMY_REASONER))
        self.assertFalse(IntegerType().is_copyable_from(BooleanType(), DUMMY_REASONER))
        self.assertTrue(BooleanType().is_copyable_from(UnitType(True), DUMMY_REASONER))
        self.assertTrue(IntegerType().is_copyable_from(UnitType(5), DUMMY_REASONER))
        self.assertFalse(BooleanType().is_copyable_from(UnitType(5), DUMMY_REASONER))
        self.assertFalse(IntegerType().is_copyable_from(UnitType(True), DUMMY_REASONER))

    def test_merge_singleton_basic_types(self):
        self.assertTrue(isinstance(merge_types([ IntegerType() ], "super"), IntegerType))
        self.assertTrue(isinstance(merge_types([ IntegerType() ], "sub"), IntegerType))
        self.assertTrue(isinstance(merge_types([ IntegerType() ], "exact"), IntegerType))

    def test_merge_pairwise_parent_and_child_types(self):
        self.assertTrue(isinstance(merge_types([ AnyType(), IntegerType() ], "super"), AnyType))
        self.assertTrue(isinstance(merge_types([ AnyType(), IntegerType() ], "sub"), IntegerType))
        self.assertTrue(isinstance(merge_types([ AnyType(), IntegerType() ], "exact"), OneOfType))
        self.assertTrue(len(merge_types([ AnyType(), IntegerType() ], "exact").types) == 2)

    def test_merge_pairwise_unrelated_types(self):
        self.assertTrue(isinstance(merge_types([ StringType(), IntegerType() ], "super"), OneOfType))
        self.assertTrue(len(merge_types([ StringType(), IntegerType() ], "super").types) == 2)
        self.assertTrue(isinstance(merge_types([ StringType(), IntegerType() ], "sub"), OneOfType))
        self.assertTrue(len(merge_types([ StringType(), IntegerType() ], "sub").types) == 2)
        self.assertTrue(isinstance(merge_types([ StringType(), IntegerType() ], "exact"), OneOfType))
        self.assertTrue(len(merge_types([ StringType(), IntegerType() ], "exact").types) == 2)

    def test_merge_irrelevant_types(self):
        self.assertTrue(isinstance(merge_types([ StringType(), StringType(), IntegerType() ], "super"), OneOfType))
        self.assertTrue(len(merge_types([ StringType(), StringType(), IntegerType() ], "super").types) == 2)
        self.assertTrue(isinstance(merge_types([ StringType(), StringType(), IntegerType() ], "sub"), OneOfType))
        self.assertTrue(len(merge_types([ StringType(), StringType(), IntegerType() ], "sub").types) == 2)
        self.assertTrue(isinstance(merge_types([ StringType(), StringType(), IntegerType() ], "exact"), OneOfType))
        self.assertTrue(len(merge_types([ StringType(), IntegerType() ], "exact").types) == 2)
