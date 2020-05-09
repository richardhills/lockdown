# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest.case import TestCase
import unittest.main

from rdhlang5.parser.parser import parse
from rdhlang5.type_system.object_types import RDHObject
from rdhlang5.executor.bootstrap import bootstrap_function


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

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
