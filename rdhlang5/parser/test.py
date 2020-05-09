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


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
