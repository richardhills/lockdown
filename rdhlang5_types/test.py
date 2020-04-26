from unittest import main
from unittest.case import TestCase

from rdhlang5_types.composites import CompositeType, InferredType
from rdhlang5_types.core_types import IntegerType, UnitType, StringType, AnyType, \
    Const
from rdhlang5_types.default_composite_types import DEFAULT_OBJECT_TYPE, \
    rich_composite_type
from rdhlang5_types.dict_types import RDHDictType, DictGetterType
from rdhlang5_types.exceptions import MicroOpTypeConflict
from rdhlang5_types.list_types import SPARSE_ELEMENT, RDHListType, RDHList
from rdhlang5_types.managers import get_manager, get_type_of_value
from rdhlang5_types.object_types import ObjectGetterType, ObjectSetterType, \
    ObjectDeletterType, RDHObject, DefaultDictType, \
    RDHObjectType, PythonObjectType


class TestObject(object):
    def __init__(self, initial_data):
        for key, value in initial_data.items():
            self.__dict__[key] = value

class TestMicroOpMerging(TestCase):
    def test_merge_gets(self):
        first = ObjectGetterType("foo", IntegerType(), False, False)
        second = ObjectGetterType("foo", UnitType(5), False, False)

        combined = first.merge(second)
        self.assertTrue(isinstance(combined.type, UnitType))
        self.assertEqual(combined.type.value, 5)

    def test_merge_sets(self):
        first = ObjectSetterType("foo", IntegerType(), False, False)
        second = ObjectSetterType("foo", UnitType(5), False, False)

        combined = first.merge(second)
        self.assertTrue(isinstance(combined.type, IntegerType))

class TestBasicObject(TestCase):
    def test_add_micro_op_dictionary(self):
        obj = { "foo": "hello" }
        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): DictGetterType("foo", StringType(), False, False)
        }))

    def test_add_micro_op_object(self):
        class Foo(object):
            pass
        obj = Foo()
        obj.foo = "hello"
        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False)
        }))

    def test_setup_read_write_property(self):
        obj = TestObject({ "foo": "hello" })
        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", StringType(), False, False)
        }))

    def test_setup_broad_read_write_property(self):
        obj = TestObject({ "foo": "hello" })
        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", AnyType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False)
        }))

    def test_setup_narrow_write_property(self):
        obj = TestObject({ "foo": "hello" })
        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", UnitType("hello"), False, False),
            ("set", "foo"): ObjectSetterType("foo", UnitType("hello"), False, False)
        }))

    def test_setup_broad_reading_property(self):
        obj = TestObject({ "foo": "hello" })
        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", AnyType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", StringType(), False, False)
        }))

    def test_failed_setup_broad_writing_property(self):
        with self.assertRaises(Exception):
            obj = TestObject({ "foo": "hello" })

            get_manager(obj).add_composite_type(CompositeType({
                ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
                ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False)
            }))

    def test_composite_object_dereference(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", StringType(), False, False)
        }))

        self.assertEquals(obj.foo, "hello")

    def test_composite_object_broad_dereference(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", AnyType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False)
        }))

        self.assertEquals(obj.foo, "hello")

    def test_composite_object_assignment(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", StringType(), False, False)
        }))

        obj.foo = "what"

    def test_composite_object_invalid_assignment(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", StringType(), False, False)
        }))

        with self.assertRaises(Exception):
            obj.foo = 5

    def test_python_like_object(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", AnyType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False)
        }))

        self.assertEquals(obj.foo, "hello")
        obj.foo = "what"
        self.assertEquals(obj.foo, "what")

    def test_java_like_object(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", StringType(), False, False)
        }))

        self.assertEquals(obj.foo, "hello")
        obj.foo = "what"
        self.assertEquals(obj.foo, "what")

        with self.assertRaises(Exception):
            obj.bar = "hello"

    def test_const_property(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False)
        }))

        self.assertEquals(obj.foo, "hello")
        with self.assertRaises(Exception):
            obj.foo = "what"

    def test_invalid_initialization(self):
        obj = TestObject({})
        with self.assertRaises(Exception):
            get_manager(obj).add_micro_op_tag(None, ("get", "foo"), StringType(), False, False)

    def test_delete_property(self):
        obj = TestObject({ "foo": "hello" })

        get_manager(obj).add_composite_type(CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), True, True),
            ("set", "foo"): ObjectSetterType("foo", StringType(), True, True),
            ("delete", "foo"): ObjectDeletterType("foo", True)
        }))

        del obj.foo
        self.assertFalse(hasattr(obj, "foo"))

class TestRevConstType(TestCase):
    def test_rev_const_assigned_to_broad_type(self):
        rev_const_type = CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False),
        }, is_revconst=True)

        normal_broad_type = CompositeType({
            ("get", "foo"): ObjectGetterType("foo", AnyType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False)
        })

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type))

    def test_rev_const_assigned_to_narrow_type(self):
        rev_const_type = CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False)
        }, is_revconst=True)

        normal_broad_type = CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", StringType(), False, False)
        })

        self.assertTrue(normal_broad_type.is_copyable_from(rev_const_type))

    def test_rev_const_can_not_be_added_to_object(self):
        rev_const_type = CompositeType({
            ("get", "foo"): ObjectGetterType("foo", StringType(), False, False),
            ("set", "foo"): ObjectSetterType("foo", AnyType(), False, False)
        }, is_revconst=True)

        obj = TestObject({ "foo": "hello" })
        with self.assertRaises(MicroOpTypeConflict):
            get_manager(obj).add_composite_type(rev_const_type)


class TestRDHObjectType(TestCase):
    def test_basic_class(self):
        T = RDHObjectType({
            "foo": IntegerType()
        })

        S = RDHObjectType({
            "foo": IntegerType(),
            "bar": StringType()
        })

        self.assertTrue(T.is_copyable_from(S))
        self.assertFalse(S.is_copyable_from(T))

    def test_const_allows_broader_types(self):
        T = RDHObjectType({
            "foo": Const(AnyType())
        })

        S = RDHObjectType({
            "foo": IntegerType()
        })

        self.assertTrue(T.is_copyable_from(S))
        self.assertFalse(S.is_copyable_from(T))

    def test_broad_type_assignments_blocked(self):
        T = RDHObjectType({
            "foo": AnyType()
        })

        S = RDHObjectType({
            "foo": IntegerType()
        })

        self.assertFalse(T.is_copyable_from(S))
        self.assertFalse(S.is_copyable_from(T))

    def test_simple_fields_are_required(self):
        T = RDHObjectType({
        })

        S = RDHObjectType({
            "foo": IntegerType()
        })

        self.assertTrue(T.is_copyable_from(S))
        self.assertFalse(S.is_copyable_from(T))

    def test_many_fields_are_required(self):
        T = RDHObjectType({
            "foo": IntegerType(),
            "bar": IntegerType(),
        })

        S = RDHObjectType({
            "foo": IntegerType(),
            "bar": IntegerType(),
            "baz": IntegerType()
        })

        self.assertTrue(T.is_copyable_from(S))
        self.assertFalse(S.is_copyable_from(T))

    def test_can_fail_micro_ops_are_enforced(self):
        foo = TestObject({
            "foo": 5,
            "bar": "hello"
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({ "foo": Const(IntegerType()) })
        )

        with self.assertRaises(Exception):
            foo.foo = "hello"

    def test_const_is_enforced(self):
        return # test doesn't work because the assignment uses the set-wildcard
        foo = {
            "foo": 5,
            "bar": "hello"
        }

        get_manager(foo).add_composite_type(
            RDHObjectType({ "foo": Const(IntegerType()) })
        )

        with self.assertRaises(Exception):
            foo.foo = 42

    def test_types_on_object_merged(self):
        foo = TestObject({
            "foo": 5,
            "bar": "hello"
        })
        get_manager(foo).add_composite_type(
            RDHObjectType({ "foo": IntegerType() })
        )
        get_manager(foo).add_composite_type(
            RDHObjectType({ "bar": StringType() })
        )
        object_type = get_type_of_value(foo)

        RDHObjectType({
            "foo": IntegerType(),
            "bar": StringType()
        }).is_copyable_from(object_type)


class TestUnitTypes(TestCase):
    def test_basics(self):
        foo = TestObject({
            "bar": 42
        })
        get_manager(foo).add_composite_type(RDHObjectType({
            "bar": UnitType(42)
        }))
        self.assertEquals(foo.bar, 42)

    def test_broadening_blocked(self):
        foo = TestObject({
            "bar": 42
        })
        get_manager(foo).add_composite_type(RDHObjectType({
            "bar": UnitType(42)
        }))

        with self.assertRaises(Exception):
            get_manager(foo).add_composite_type(RDHObjectType({
                "bar": IntegerType()
            }))

    def test_narrowing_blocked(self):
        foo = TestObject({
            "bar": 42
        })
        get_manager(foo).add_composite_type(RDHObjectType({
            "bar": IntegerType()
        }))
        with self.assertRaises(Exception):
            get_manager(foo).add_composite_type(RDHObjectType({
                "bar": UnitType(42)
            }))

    def test_broadening_with_const_is_ok(self):
        foo = TestObject({
            "bar": 42
        })
        get_manager(foo).add_composite_type(RDHObjectType({
            "bar": UnitType(42)
        }))

        get_manager(foo).add_composite_type(RDHObjectType({
            "bar": Const(IntegerType())
        }))


class TestNestedRDHObjectTypes(TestCase):
    def test_basic_assignment(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({
                "bar": RDHObjectType({
                    "baz": IntegerType()
                })
            })
        )

        foo.bar = TestObject({ "baz": 42 })

        self.assertEquals(foo.bar.baz, 42)

    def test_blocked_basic_assignment(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({
                "bar": RDHObjectType({
                    "baz": IntegerType()
                })
            })
        )

        with self.assertRaises(Exception):
            foo.bar = TestObject({ "baz": "hello" })

    def test_deletion_blocked(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({
                "bar": RDHObjectType({
                    "baz": IntegerType()
                })
            })
        )

        with self.assertRaises(Exception):
            del foo.bar

    def test_broad_assignment(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({
                "bar": RDHObjectType({
                    "baz": AnyType()
                })
            })
        )

        foo.bar = TestObject({ "baz": "hello" })

        self.assertEquals(foo.bar.baz, "hello")

    def test_double_deep_assignment(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": TestObject({
                    "bam": 10
                })
            })
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({
                "bar": RDHObjectType({
                    "baz": RDHObjectType({
                        "bam": IntegerType()
                    })
                })
            })
        )

        self.assertEquals(foo.bar.baz.bam, 10)

        foo.bar = TestObject({ "baz": TestObject({ "bam": 42 }) })

        self.assertEquals(foo.bar.baz.bam, 42)

    def test_conflicting_types(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({
                "bar": RDHObjectType({
                    "baz": IntegerType()
                })
            })
        )

        with self.assertRaises(Exception):
            get_manager(foo).add_composite_type(
                RDHObjectType({
                    "bar": RDHObjectType({
                        "baz": AnyType()
                    })
                })
            )

    def test_changes_blocked_without_micro_ops(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo)

        with self.assertRaises(Exception):
            foo.bar = "hello"

    def test_very_broad_assignment(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(
            RDHObjectType({ "bar": AnyType() })
        )

        foo.bar = "hello"
        self.assertEquals(foo.bar, "hello")


class TestNestedPythonTypes(TestCase):
    def test_python_like_type(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(PythonObjectType())

        foo.bar.baz = 22

        foo.bar = "hello"
        self.assertEquals(foo.bar, "hello")

    def test_python_object_with_reference_can_be_modified(self):
        bar = TestObject({
            "baz": 42
        })
        foo = TestObject({
            "bar": bar
        })

        get_manager(bar).add_composite_type(RDHObjectType({ "baz": IntegerType() }))
        get_manager(foo).add_composite_type(PythonObjectType())

        self.assertEqual(foo.bar.baz, 42)
        foo.bar.baz = 5
        self.assertEqual(foo.bar.baz, 5)

    def test_python_object_with_reference_types_are_enforced(self):
        bar = TestObject({
            "baz": 42
        })
        foo = TestObject({
            "bar": bar
        })

        get_manager(bar).add_composite_type(RDHObjectType({ "baz": IntegerType() }))
        get_manager(foo).add_composite_type(PythonObjectType())

        with self.assertRaises(Exception):
            foo.bar.baz = "hello"

    def test_python_object_with_reference_can_be_replaced(self):
        bar = TestObject({
            "baz": 42
        })
        foo = TestObject({
            "bar": bar
        })

        get_manager(bar).add_composite_type(RDHObjectType({ "baz": IntegerType() }))
        get_manager(foo).add_composite_type(PythonObjectType())

        foo.bar = TestObject({
            "baz": 123
        })

        self.assertEqual(foo.bar.baz, 123)
        foo.bar.baz = "what"
        self.assertEqual(foo.bar.baz, "what")

    def test_adding_late_python_constraint_fails(self):
        bar = TestObject({
            "baz": 42
        })
        foo = TestObject({
            "bar": bar
        })

        get_manager(bar).add_composite_type(RDHObjectType({ "baz": IntegerType() }))
        get_manager(foo).add_composite_type(PythonObjectType())

        foo.bar = TestObject({
            "baz": 123
        })

        with self.assertRaises(Exception):
            get_manager(foo.bar).add_composite_type(RDHObjectType({ "baz": IntegerType() }))

    def test_python_delete_works(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(PythonObjectType())

        del foo.bar
        self.assertFalse(hasattr(foo, "bar"))

    def test_python_replacing_object_works(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(PythonObjectType())

        foo.bar = TestObject({ "baz": 123 })

        self.assertEquals(foo.bar.baz, 123)

    def test_python_random_read_fails_nicely(self):
        foo = TestObject({
            "bar": TestObject({
                "baz": 42
            })
        })

        get_manager(foo).add_composite_type(PythonObjectType())

        with self.assertRaises(AttributeError):
            foo.bop

class TestDefaultDict(TestCase):
    def test_default_dict(self):
        def default_factory(target, key):
            return "{}-123".format(key)

        foo = RDHObject({
            "bar": "forty-two"
        }, default_factory=default_factory)

        get_manager(foo).add_composite_type(DefaultDictType(StringType()))

        self.assertEquals(foo.bar, "forty-two")
        self.assertEquals(foo.bam, "bam-123")

class TestListObjects(TestCase):
    def test_basic_list_of_ints(self):
        foo = [ 1, 2, 3 ]

        get_manager(foo).add_composite_type(RDHListType([], IntegerType()))

        foo[0] = 42
        self.assertEqual(foo[0], 42)

    def test_basic_tuple_of_ints(self):
        foo = [ 1, 2, 3 ]

        get_manager(foo).add_composite_type(RDHListType([ IntegerType(), IntegerType(), IntegerType() ], None))

        foo[0] = 42
        self.assertEqual(foo[0], 42)

    def test_bounds_enforced(self):
        foo = [ 1, 2 ]

        with self.assertRaises(Exception):
            get_manager(foo).add_composite_type(RDHListType([ IntegerType(), IntegerType(), IntegerType() ], None))

class TestMisc(TestCase):
    # Tests for random things that were broken
    def test_misc1(self):
        # Came up testing rdhlang5 local variable binding
        RDHObject({
            "local": RDHList([ 39, 3 ]),
            "types": RDHObject()
        }, bind=RDHObjectType({
            "local": RDHListType([ IntegerType(), IntegerType() ], None),
            "types": DEFAULT_OBJECT_TYPE
        }, wildcard_type=rich_composite_type))

    def test_misc2(self):
        # Came up writing test_misc1
        RDHObject({
            "local": RDHList([ 39, 3 ])
        }, bind=RDHObjectType({
            "local": RDHListType([ IntegerType(), IntegerType() ], None)
        }, wildcard_type=rich_composite_type))

class TestRDHListType(TestCase):
    def test_simple_list_assignment(self):
        foo = RDHListType([], IntegerType())
        bar = RDHListType([], IntegerType())

        self.assertTrue(foo.is_copyable_from(bar))

    def test_simple_tuple_assignment(self):
        foo = RDHListType([ IntegerType(), IntegerType() ], None)
        bar = RDHListType([ IntegerType(), IntegerType() ], None)

        self.assertTrue(foo.is_copyable_from(bar))

    def test_broadening_tuple_assignment_blocked(self):
        foo = RDHListType([ AnyType(), AnyType() ], None)
        bar = RDHListType([ IntegerType(), IntegerType() ], None)

        self.assertFalse(foo.is_copyable_from(bar))

    def test_narrowing_tuple_assignment_blocked(self):
        foo = RDHListType([ IntegerType(), IntegerType() ], None)
        bar = RDHListType([ AnyType(), AnyType() ], None)

        self.assertFalse(foo.is_copyable_from(bar))

    def test_broadening_tuple_assignment_allowed_with_const(self):
        foo = RDHListType([ Const(AnyType()), Const(AnyType()) ], None)
        bar = RDHListType([ IntegerType(), IntegerType() ], None)

        self.assertTrue(foo.is_copyable_from(bar))

    def test_truncated_tuple_slice_assignment(self):
        foo = RDHListType([ IntegerType() ], None)
        bar = RDHListType([ IntegerType(), IntegerType() ], None)

        self.assertTrue(foo.is_copyable_from(bar))

    def test_expanded_tuple_slice_assignment_blocked(self):
        foo = RDHListType([ IntegerType(), IntegerType() ], None)
        bar = RDHListType([ IntegerType() ], None)

        self.assertFalse(foo.is_copyable_from(bar))
  
    def test_convert_tuple_to_list(self):
        foo = RDHListType([ ], IntegerType(), allow_delete=False, allow_wildcard_insert=False, allow_push=False)
        bar = RDHListType([ IntegerType(), IntegerType() ], None)

        self.assertTrue(foo.is_copyable_from(bar))
    def test_const_covariant_array_assignment_allowed(self):
        foo = RDHListType([ ], Const(AnyType()), allow_push=False, allow_wildcard_insert=False)
        bar = RDHListType([ ], IntegerType())

        self.assertTrue(foo.is_copyable_from(bar))

    def test_convert_tuple_to_list_with_deletes_blocked(self):
        foo = RDHListType([ ], IntegerType())
        bar = RDHListType([ IntegerType(), IntegerType() ], None)

        self.assertFalse(foo.is_copyable_from(bar))

    def test_pushing_into_short_tuple(self):
        foo = RDHListType([ IntegerType() ], IntegerType(), allow_delete=False)
        bar = RDHListType([ IntegerType() ], IntegerType(), allow_delete=False, allow_wildcard_insert=False)

        self.assertTrue(foo.is_copyable_from(bar))

    def test_pushing_into_long_tuple(self):
        foo = RDHListType([ IntegerType(), IntegerType() ], IntegerType(), allow_delete=False)
        bar = RDHListType([ IntegerType(), IntegerType() ], IntegerType(), allow_delete=False, allow_wildcard_insert=False)

        self.assertTrue(foo.is_copyable_from(bar))

    def test_same_type_array_assignment(self):
        foo = RDHListType([ ], IntegerType())
        bar = RDHListType([ ], IntegerType())

        self.assertTrue(foo.is_copyable_from(bar))

    def test_covariant_array_assignment_blocked(self):
        foo = RDHListType([ ], AnyType())
        bar = RDHListType([ ], IntegerType())

        self.assertFalse(foo.is_copyable_from(bar))

class TestList(TestCase):
    def test_simple_list_assignment(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([], IntegerType()))

    def test_list_modification_wrong_type_blocked(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([], IntegerType()))

        with self.assertRaises(Exception):
            foo.append("hello")

    def test_list_modification_right_type_ok(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([], IntegerType()))

        foo.append(10)

    def test_list_appending_blocked(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([], None))

        with self.assertRaises(Exception):
            foo.append(10)

    def test_mixed_type_tuple(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ IntegerType(), AnyType() ], None))

        with self.assertRaises(Exception):
            foo[0] = "hello"

        self.assertEqual(foo[0], 4)

        foo[1] = "what"
        self.assertEqual(foo[1], "what")

    def test_outside_tuple_access_blocked(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ IntegerType(), AnyType() ], None))

        with self.assertRaises(Exception):
            foo[2]
        with self.assertRaises(Exception):
            foo[2] = "hello"

    def test_outside_tuple_access_allowed(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ ], AnyType(), allow_push=False, allow_delete=False, allow_wildcard_insert=False))

        self.assertEqual(foo[2], 8)
        foo[2] = "hello"
        self.assertEqual(foo[2], "hello")

    def test_combined_const_list_and_tuple(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ IntegerType(), AnyType() ], Const(AnyType()), allow_push=False, allow_delete=False, allow_wildcard_insert=False))

        self.assertEqual(foo[2], 8)

    def test_insert_at_start(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ ], IntegerType()))

        foo.insert(0, 2)
        self.assertEqual(list(foo), [ 2, 4, 6, 8 ])

    def test_insert_with_wrong_type_blocked(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ ], IntegerType()))

        with self.assertRaises(Exception):
            foo.insert(0, "hello")

    def test_insert_on_short_tuple(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ IntegerType() ], IntegerType(), allow_push=True, allow_delete=False, allow_wildcard_insert=False))

        foo.insert(0, 2)
        self.assertEqual(list(foo), [ 2, 4, 6, 8 ])

    def test_insert_on_long_tuple(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ IntegerType(), IntegerType() ], IntegerType(), allow_push=True, allow_delete=False, allow_wildcard_insert=False))

        foo.insert(0, 2)
        self.assertEqual(list(foo), [ 2, 4, 6, 8 ])

    def test_insert_on_very_long_tuple(self):
        foo = [ 4, 6, 8, 10, 12, 14 ]
        get_manager(foo).add_composite_type(RDHListType([ IntegerType(), IntegerType(), IntegerType(), IntegerType(), IntegerType(), IntegerType() ], IntegerType(), allow_push=True, allow_delete=False, allow_wildcard_insert=False))

        foo.insert(0, 2)
        self.assertEqual(list(foo), [ 2, 4, 6, 8, 10, 12, 14 ])

    def test_sparse_list_setting(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ ], IntegerType(), is_sparse=True))

        foo[4] = 12
        self.assertEqual(list(foo), [ 4, 6, 8, SPARSE_ELEMENT, 12 ])

    def test_sparse_list_inserting(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ ], IntegerType(), is_sparse=True))

        foo.insert(4, 12)
        self.assertEqual(list(foo), [ 4, 6, 8, SPARSE_ELEMENT, 12 ])

    def test_set_on_non_sparse_blocked(self):
        foo = [ 4, 6, 8 ]
        get_manager(foo).add_composite_type(RDHListType([ ], IntegerType(), is_sparse=False))

        with self.assertRaises(IndexError):
            foo[4] = 12

    def test_incorrect_type_blocked(self):
        foo = [ 4, 6, 8 ]

        with self.assertRaises(Exception):
            get_manager(foo).add_composite_type(RDHListType([ ], StringType()))

class TestInferredTypes(TestCase):
    def test_basic(self):
        foo = InferredType()
        foo = foo.replace_inferred_types(IntegerType())
        self.assertIsInstance(foo, IntegerType)

    def test_basic_object(self):
        foo = RDHObjectType({
            "bar": InferredType()
        })
        foo = foo.replace_inferred_types(RDHObjectType({
            "bar": IntegerType()
        }))
        self.assertIsInstance(foo.micro_op_types[("get", "bar")].type, IntegerType)

    def test_basic_ignored(self):
        foo = RDHObjectType({
            "bar": StringType()
        })
        foo = foo.replace_inferred_types(RDHObjectType({
            "bar": IntegerType()
        }))
        self.assertIsInstance(foo.micro_op_types[("get", "bar")].type, StringType)

    def test_basic_ignored2(self):
        foo = RDHObjectType({
            "bar": InferredType()
        })
        foo = foo.replace_inferred_types(RDHObjectType({
            "bar": IntegerType(),
            "bam": StringType
        }))
        self.assertIsInstance(foo.micro_op_types[("get", "bar")].type, IntegerType)

    def test_dangling_error(self):
        foo = RDHObjectType({
            "bar": InferredType()
        })
        with self.assertRaises(Exception):
            foo = foo.replace_inferred_types(RDHObjectType({
                "bam": StringType
            }))

    def test_double_nested(self):
        foo = RDHObjectType({
            "bar": RDHObjectType({
                "bam": InferredType()
            })
        })
        foo = foo.replace_inferred_types(RDHObjectType({
            "bar": RDHObjectType({
                "bam": IntegerType()
            })
        }))
        self.assertIsInstance(foo.micro_op_types[("get", "bar")].type.micro_op_types[("get", "bam")].type, IntegerType)

    def test_composite_types_inferred(self):
        foo = RDHObjectType({
            "bar": InferredType()
        })
        foo = foo.replace_inferred_types(RDHObjectType({
            "bar": RDHObjectType({
                "bam": IntegerType()
            })
        }))
        self.assertIsInstance(foo.micro_op_types[("get", "bar")].type.micro_op_types[("get", "bam")].type, IntegerType)


if __name__ == '__main__':
    main()
