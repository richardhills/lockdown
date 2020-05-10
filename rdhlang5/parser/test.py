# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest.case import TestCase
import unittest.main

from rdhlang5.parser.parser import parse
from rdhlang5.type_system.object_types import RDHObject
from rdhlang5.executor.bootstrap import bootstrap_function
from rdhlang5.executor.exceptions import PreparationException


class TestJSONParsing(TestCase):
    maxDiff = 65536

    def test_number(self):
        ast = parse("""
            42
        """)
        self.assertEqual(ast, 42)

    def test_string(self):
        ast = parse("""
            "hello world"
        """)
        self.assertEqual(ast, "hello world")

    def test_empty_object(self):
        ast = parse("""
            {}
        """)
        self.assertEqual(ast.__dict__, { }) 
       
    def test_true(self):
        ast = parse("""
            true
        """)
        self.assertEqual(ast, True)        

    def test_false(self):
        ast = parse("""
            false
        """)
        self.assertEqual(ast, False)        

    def test_null(self):
        ast = parse("""
            null
        """)
        self.assertEqual(ast, None)        

    def test_object(self):
        ast = parse("""
            { "foo": "bar" }
        """)
        CORRECT = RDHObject({ "foo": "bar" })
        self.assertEqual(ast.__dict__, CORRECT.__dict__)

    def test_nested_object(self):
        ast = parse("""
            { "foo": {
                "bar": 42
            } }
        """)
        self.assertEqual(ast.foo.bar, 42)

class TestBasicFunction(TestCase):
    def test_returns_42(self):
        code = parse("""
            function() { return 42; }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_returns_string(self):
        code = parse("""
            function() { return "hello"; }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, "hello")

    def test_addition(self):
        code = parse("""
            function() { return 12 + 30; }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_precidence(self):
        code = parse("""
            function() { return (1 + 1) * 23 - 2 * 1 + 2; }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_return_argument(self):
        code = parse("""
            function(int) { return argument; }
        """)
        result = bootstrap_function(code, argument=42, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_dereference_argument_parameter(self):
        code = parse("""
            function(Object { foo: int }) { return foo; }
        """)
        result = bootstrap_function(code, argument=RDHObject({ "foo": 42 }), check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_initialize_and_return_local(self):
        code = parse("""
            function() { int foo = 40; return foo + 2; }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_initialize_and_return_local_object(self):
        code = parse("""
            function() {
                Object { foo: int } bar = { foo: 40 };
                return bar.foo + 2;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_many_const_locals(self):
        code = parse("""
            function() {
                int foo = 1;
                int bar = foo + 40;
                int baz = bar - 3;
                return baz + 4;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_mutate_locals(self):
        code = parse("""
            function() {
                int foo = 1;
                foo = foo + 30;
                foo = foo * 2;
                foo = foo - 20;
                return foo;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)


    def test_mix_of_initialization_and_mutation(self):
        code = parse("""
            function() {
                int foo = 2;
                foo = foo + 30;
                int bar = 15;
                bar = bar / 3;
                return foo + bar * 2;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)


    def test_mix_of_initialization_and_mutation_on_object(self):
        code = parse("""
            function() {
                Object { baz: int } foo = { baz: 2 };
                foo.baz = foo.baz + 30;
                int bar = 15;
                bar = bar / 3;
                return foo.baz + bar * 2;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_list(self):
        code = parse("""
            function() {
                List<int> foo = [ 1, 2, 3 ];
                return foo[0] * foo[1] * foo[2];
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 6)

    def test_list_of_objects(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                return foo[0].bar * foo[1].bar;
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 6)

    def test_object_with_lists(self):
        code = parse("""
            function() {
                Object { foo: List<int> } bar = { foo: [ 1, 2, 3 ] };
                return bar.foo[0] * bar.foo[1] * bar.foo[2];
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 6)


    def test_mutate_list_of_objects(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo[1] = { bar: 6 };
                return foo[0].bar * foo[1].bar;
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 12)


    def test_mutate_object_in_list(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo[1].bar = 6;
                return foo[0].bar * foo[1].bar;
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 12)


    def test_duplicate_object_in_list(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo[0] = foo[1];
                return foo[0].bar * foo[1].bar;
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 9)

    def test_insert_into_list(self):
        code = parse("""
            function() {
                List<int> foo = [ 1, 2, 3 ];
                foo.insert([ 0, 4 ]);
                return foo[0];
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 4)

    def test_insert_object_into_list(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo.insert([ 0, { bar: 6 } ]);
                return foo[0].bar;
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 6)

class TestMisc(TestCase):
    def test_invalid_list_assignment(self):
        code = parse("""
            function() {
                List<int> foo = [ { bar: 2 }, { bar: 3 } ];
                foo.insert([ 0, { bar: 6 } ]);
                return foo[0].bar;
            }
        """)
        with self.assertRaises(PreparationException):
            bootstrap_function(code)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
