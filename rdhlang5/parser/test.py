# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import time
from unittest.case import TestCase
import unittest.main

import jsonpickle

from rdhlang5.executor.bootstrap import bootstrap_function
from rdhlang5.executor.exceptions import PreparationException
from rdhlang5.parser.parser import parse
from rdhlang5.type_system.object_types import RDHObject
from rdhlang5.utils import set_debug


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

    def test_some_const_locals(self):
        code = parse("""
            function() {
                int foo = 1;
                int bar = foo + 37;
                return bar + 4;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_many_const_locals(self):
        code = parse("""
            function() {
                int foom = 1;
                int bar = foom + 40;
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

class TestBuiltIns(TestCase):
    def test_range(self):
        code = parse("""
            function() {
                return list(range([ 1, 5 ]));
            }
        """, debug=True)
        result = bootstrap_function(code, check_safe_exit=True)
        list(result.value)
        self.assertEquals(result.mode, "value")
        self.assertEquals(len(result.value), 4)
        # The values come out in reverse due to the list function using insert(0, element) repeatedly. Need an append(element) operator
        self.assertEquals(list(result.value), [ 4, 3, 2, 1 ])

class TestInferredTypes(TestCase):
    def test_inferred_locals(self):
        code = parse("""
            function() {
                var x = 5;
                var y = 37;
                var z = x + y;
                return z;
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

class TestFunctionDeclaration(TestCase):
    def test_local_function(self):
        code = parse("""
            function() {
                var x = function() {
                    return 42;
                };
                return x();
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 42)

    def test_access_outer_context(self):
        code = parse("""
            function() {
                int x = 4;
                var y = function() {
                    return x * 3;
                };
                return y();
            }
        """)
        result = bootstrap_function(code)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 12)

    def test_mutate_outer_context(self):
        code = parse("""
            function() {
                int x = 4;
                var doubler = function() {
                    x = x * 2;
                };
                var getter = function() {
                    return x;
                };
                doubler();
                doubler();
                doubler();
                return getter();
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 32)

    def test_mutate_outer_context_loop(self):
        code = parse("""
            function() {
                int x = 1;
                var doubler = function() {
                    x = x * 2;
                };
                int i = 0;
                while(i < 3) {
                    int j = 0;
                    while(j < 3) {
                        doubler();
                        j = j + 1;
                    };
                    i = i + 1;
                };
                return x;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 2 ** (3 * 3))

class TestLoops(TestCase):
    def test_counter(self):
        code = parse("""
            function() {
                int foo = 1;
                while(foo < 10) {
                    foo = foo + 1;
                };
                return foo;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.mode, "value")
        self.assertEquals(result.value, 10)

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

class TestSpeed(TestCase):
    def test_loops(self):
        start = time()
        code = parse("""
            function() {
                int i = 0, j = 0;
                while(i < 10) {
                    j = 0;
                    while(j < 10) {
                        int foo = i * j;
                        int bar = i * j;
                        int baz = i * j;
                        j = j + 1;
                    };
                    i = i + 1;
                };
                return i * j;
            }
        """, debug=True)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 10 * 10)
        end = time()
        self.assertLess(end - start, 25)
        print end - start

class TestEuler(TestCase):
    """
    https://projecteuler.net/
    https://github.com/luckytoilet/projecteuler-solutions/blob/master/Solutions.md
    """

    def test_1(self):
        return
        code = parse("""
            function() {
                int i = 1, result = 0;
                while(i < 1000) {
                    if(i % 3 == 0 || i % 5 == 0) {
                        result = result + i;
                    };
                    i = i + 1;
                };
                return result;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 233168)

    def test_2(self):
        return
        code = parse("""
            function() {
                int i = 1, j = 2, result = 0;
                while(j < 4000000) {
                    if(j % 2 == 0) {
                        result = result + j;
                    };
                    var k = j;
                    j = i + j;
                    i = k;
                };
                return result;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 4613732)

    def test_3(self):
        return
        code = parse("""
            function() {
                int test = 2, result = 600851475143;
                while(result != 1) {
                    if(result % test == 0) {
                        result = result / test;
                    } else {
                        test = test + 1;
                    };
                };
                return test;
            }
        """)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 6857)

    def test_4(self):
        code = parse("""
            function() {
                int bestResult = 0;
                int i = 999;
                while(i >= 100) {
                    int j = 999;
                    while(j >= i) {
                        int testResult = i * j;
                        if(testResult <= bestResult) {
                            break;
                        };
                        if(testResult > 100000
                                && testResult > bestResult
                                && testResult / 1 % 10 == testResult / 100000 % 10
                                && testResult / 10 % 10 == testResult / 10000 % 10
                                && testResult / 100 % 10 == testResult / 1000 % 10
                        ) {
                            bestResult = testResult;
                        };
                        j = j - 1;
                    };
                    i = i - 1;
                };
                return bestResult;
            }
        """, debug=True)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 906609)

    def test_6(self):
        code = parse("""
            function() {
                int sumSquares = 0, sum = 0;
                int i = 1;
                while(i <= 100) {
                    sumSquares = sumSquares + i * i;
                    sum = sum + i;
                    i = i + 1;
                };
                return sum * sum - sumSquares;
            }
        """, debug=True)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 25164150)

    def test_9(self):
        return # this test takes about 30 seconds in non-debug mode
        code = parse("""
            function() {
                int a = 1;
                while(a < 998) {
                    int b = 1;
                    while(b < a) {
                        int c = 1000 - a - b;
                        if(c <= 0) {
                            break;
                        };
                        int test = a * a + b * b - c * c;
                        if(test < 0) {
                            break;
                        };
                        if(test == 0) {
                            return a * b * c;
                        };
                        b = b + 1;
                    };
                    a = a + 1;
                };
            }
        """, debug=True)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 31875000)


    def test_14(self):
        return # This test is currently too slow - requires caching of results to speed up
        code = parse("""
            function() {
                var testStartingNumber = function(int) {
                    int current = argument;
                    int count = 1;
                    while(current != 1) {
                        if(current % 2 == 0) {
                            current = current / 2;
                        } else {
                            current = 3 * current + 1;
                        };
                        count = count + 1;
                    };
                    return count;
                };
                int longestChain = 0, startingNumberWithLongestChain = 0;
                int test = 1;
                while(test < 1000000) {
                    int newChainLength = testStartingNumber(test);
                    if(newChainLength > longestChain) {
                        longestChain = newChainLength;
                        startingNumberWithLongestChain = test;
                    };
                    test = test + 1;
                };
                return startingNumberWithLongestChain;
            }
        """, debug=True)
        result = bootstrap_function(code, check_safe_exit=True)
        self.assertEquals(result.value, 837799)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    set_debug(True)
    unittest.main()
