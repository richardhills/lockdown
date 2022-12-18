# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from time import time
from unittest.case import TestCase

from lockdown.executor.bootstrap import bootstrap_function
from lockdown.executor.exceptions import PreparationException
from lockdown.parser.parser import parse
from lockdown.type_system.composites import scoped_bind
from lockdown.type_system.managers import get_manager
from lockdown.type_system.universal_type import DEFAULT_READONLY_COMPOSITE_TYPE, \
    PythonList, PythonObject, PythonDict
from lockdown.utils.utils import environment, fastest


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
        self.assertEqual(ast._to_dict(), { }) 
       
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
        CORRECT = PythonObject({ "foo": "bar" })
        self.assertEqual(ast._to_dict(), CORRECT._to_dict())

    def test_nested_object(self):
        ast = parse("""
            { "foo": {
                "bar": 42
            } }
        """)
        self.assertEqual(ast._get_in("foo", "bar"), 42)


class TestBasicFunction(TestCase):
    def test_returns_42(self):
        code = parse("""
            function() { return 42; }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_returns_false(self):
        code = parse("""
            function() { return !true; }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, False)

    def test_returns_true(self):
        code = parse("""
            function() { return !false; }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, True)

    def test_returns_string(self):
        code = parse("""
            function() { return "hello"; }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, "hello")

    def test_addition(self):
        code = parse("""
            function() { return 12 + 30; }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_precidence(self):
        code = parse("""
            function() { return (1 + 1) * 23 - 2 * 1 + 2; }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_return_argument(self):
        code = parse("""
            function(int) { return argument; }
        """)
        _, result = bootstrap_function(code, argument=42)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_dereference_argument_parameter(self):
        code = parse("""
            function(Object { foo: int }) { return foo; }
        """)
        _, result = bootstrap_function(code, argument=PythonObject({ "foo": 42 }))
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_initialize_and_return_local(self):
        code = parse("""
            function() { int foo = 40; return foo + 2; }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_initialize_and_return_local_object(self):
        code = parse("""
            function() {
                Object { foo: int } bar = { foo: 40 };
                return bar.foo + 2;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_some_const_locals(self):
        code = parse("""
            function() {
                int foo = 1;
                int bar = foo + 37;
                return bar + 4;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_many_const_locals(self):
        code = parse("""
            function() {
                int foom = 1;
                int bar = foom + 40;
                int baz = bar - 3;
                return baz + 4;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_list(self):
        code = parse("""
            function() {
                List<int> foo = [ 1, 2, 3 ];
                return foo[0] * foo[1] * foo[2];
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 6)

    def test_list_of_objects(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                return foo[0].bar * foo[1].bar;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 6)

    def test_object_with_lists(self):
        code = parse("""
            function() {
                Object { foo: List<int> } bar = { foo: [ 1, 2, 3 ] };
                return bar.foo[0] * bar.foo[1] * bar.foo[2];
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 6)

    def test_mutate_list_of_objects(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo[1] = { bar: 6 };
                return foo[0].bar * foo[1].bar;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 12)

    def test_mutate_object_in_list(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo[1].bar = 6;
                return foo[0].bar * foo[1].bar;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 12)

    def test_duplicate_object_in_list(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo[0] = foo[1];
                return foo[0].bar * foo[1].bar;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 9)

    def test_insert_into_list(self):
        code = parse("""
            function() {
                List<int> foo = [ 1, 2, 3 ];
                foo[0] << 4;
                return foo[0];
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 4)

    def test_insert_object_into_list(self):
        code = parse("""
            function() {
                List<Object { bar: int }> foo = [ { bar: 2 }, { bar: 3 } ];
                foo[0] << { bar: 6 };
                return foo[0].bar;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 6)


class TestBuiltIns(TestCase):
    def test_list_from_range(self):
        code = parse("""
            function() {
                var x = for(var i from range(0, 100)) { continue i * i; };
                return x;
            }
        """)
        func, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertIsInstance(result.value, PythonList)
        self.assertTrue(len(result.value) == 100)

    def test_range(self):
        code = parse("""
            function() {
                return list<int>(range(1, 5));
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertIsInstance(result.value, PythonList)
        result = result.value._to_list()
        self.assertEqual(len(result), 4)
        self.assertEqual(result, [ 1, 2, 3, 4 ])

    def test_irange(self):
        code = parse("""
            function() {
                for(var i from irange()) {
                    if(i == 10) {
                        return i;
                    };
                };
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 10)

    # def test_tuple(self):    
    #     code = parse("""
    #         function() {
    #             return tuple<int, 3>(7);
    #         }
    #     """, debug=True)
    #     _, result = bootstrap_function(code)
    #     self.assertEqual(result.caught_break_mode, "value")
    #     self.assertEqual(result.value._to_list(), [ 7, 7, 7 ])

#
#     def test_tuple_range(self):
#
#
# # static tuple_range = function(int start, int end) {
# #   return dynamic function() => Tuple<tuple<int, end - start>> {
# #     var result = tuple<int, (end - start)>(0);
# #     return result *|> {
# #       continue argument[0] + start;
# #     };
# #   };
# # };
#
#         code = parse("""
#             function() => Tuple<int, int, int> {
#                 return tuple_range(3, 6);
#             }
#         """, debug=True)
#         _, result = bootstrap_function(code)
#         self.assertEqual(result.caught_break_mode, "value")
#         self.assertIsInstance(result.value, PythonList)
#         get_manager(result.value).add_composite_type(DEFAULT_READONLY_COMPOSITE_TYPE)
#         self.assertEqual(len(result.value), 3)
#         self.assertEqual(list(result.value), [ 3, 4, 5 ])

    def test_find(self):
        code = parse("""
            function() {
                var squareGenerator = function() {
                    for(var i from irange()) {
                        yield i * i;
                    };
                };
                return find(squareGenerator, function(i: int) { return i > 50; } );
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 64)

    def test_array_length(self):
        code = parse("""
            function() {
                return length([ 1, 4, 6 ]);
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 3)

    def test_object_length(self):
        code = parse("""
            function() {
                return length({ foo: "bar" });
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 0)

    def test_keys(self):
        code = parse("""
            function() {
                return keys({ foo: "bar", baz: 4 });
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(sorted(result.value._to_list()), [ "baz", "foo" ])

    def test_values(self):
        code = parse("""
            function() {
                return values<any>({ foo: "bar", baz: 4 });
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_list(), [ "bar", 4 ])

    def test_sums(self):
        code = parse("""
            function() {
                return sum([ 4, 6, 2 ]);
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(12, result.value)

#    def test_reverse(self):
#        code = parse("""
#            function() {
#                return reversed([ 4, 6, 2 ]);
#            }
#        """, debug=True)
#        _, result = bootstrap_function(code)
#        self.assertEqual(result.caught_break_mode, "value")
#        self.assertEqual([ 2, 6, 4 ], result._to_list())

class TestRRTI(TestCase):
    def test_unit_type(self):
        code = parse("""
            function() {
                return typeof(5);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "type": "Unit", "value": 5 });

    def test_unit_type2(self):
        code = parse("""
            function() {
                return typeof("hello");
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "type": "Unit", "value": "hello" });

    def test_ints(self):
        code = parse("""
            function() {
                int x = 5;
                return typeof(x);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "type": "Integer" });

    def test_var(self):
        code = parse("""
            function() {
                var x = 5;
                return typeof(x);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "type": "Unit", "value": 5 })

    def test_list(self):
        code = parse("""
            function() {
                List<int> x = [ 4, 5 ];
                return typeof(x);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._get("type"), "Universal")

        micro_op_types = sorted(
            result.value._get_in("micro_ops")._to_list(),
            key=lambda micro_op: micro_op._get("type")
        )
        types = [ m._get("type") for m in micro_op_types ]
        self.assertEqual(
            types,
            [ "get-wildcard", "insert-end", "insert-start", "insert-wildcard", "iter", "remove-wildcard", "set-wildcard" ]
        )
        params = [ [ p._to_dict() if isinstance(p, PythonDict) else p for p in m._get("params")._to_list() ] for m in micro_op_types ]
        self.assertEqual(
            params,
            [ [ {"type": "Integer"}, {"type": "Integer"}, True ],
              [ {"type": "Integer"}, False ],
              [ {"type": "Integer"}, False ],
              [ {"type": "Integer"}, True, False ],
              [ {"type": "Integer"} ],
              [ True, False ],
              [ {"type": "Integer"}, {"type": "Integer"}, True, False ] ]
        )

    def test_tuple2(self):
        code = parse("""
            function() {
                var x = [ 4, 5 ];
                return typeof(x);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._get("type"), "Universal")

        micro_op_types = sorted(
            result.value._get_in("micro_ops")._to_list(),
            key=lambda micro_op: micro_op._get("type")
        )
        types = [ m._get("type") for m in micro_op_types ]
        self.assertEqual(
            types,
            [ "delete-wildcard", "get", "get", "get-wildcard", "insert-end", "iter", "set", "set", "set-wildcard" ]
        )
        params = [ [ p._to_dict() if isinstance(p, PythonDict) else p for p in m._get("params")._to_list() ] for m in micro_op_types ]
        self.assertEqual(
            params,
            [ [ {"type": "Any"}, True ],
              [ 0, {"type": "Unit", "value": 4}],
              [ 1, {"type": "Unit", "value": 5}],
              [ {"type": "Any"}, {"type": "Any"}, True ],
              [ {"type": "Any"}, False ],
              [ {"type": "Any"} ],
              [ 0, {"type": "Unit", "value": 4}],
              [ 1, {"type": "Unit", "value": 5}],
              [ {"type": "Any"}, { "type": "Any"}, False, True ]
            ]
        )

    def test_tuple3(self):
        code = parse("""
            function() {
                Tuple<int, int> x = [ 4, 5 ];
                return typeof(x);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._get("type"), "Universal")
        micro_op_types = [
            micro_op._get("type") for micro_op in result.value._get_in("micro_ops")._to_list()
        ]
        micro_op_types = sorted(micro_op_types)
        self.assertEqual(
            micro_op_types,
            [ "get", "get", "set", "set" ]
        )

    def test_object(self):
        code = parse("""
            function() {
                return typeof({ x: 5 });
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._get("type"), "Universal")
        micro_op_types = [
            micro_op._get("type") for micro_op in result.value._get_in("micro_ops")._to_list()
        ]
        micro_op_types = sorted(micro_op_types)
        self.assertEqual(
            micro_op_types,
            [ "delete-wildcard", "get", "get-wildcard", "insert-end", "insert-start", "insert-wildcard", "iter", "remove-wildcard", "set", "set-wildcard" ]
        )


class TestMaths(TestCase):
    def test_gcm1(self):
        code = parse("""
            function() {
                return gcd(1, 1);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 1);

    def test_gcm2(self):
        code = parse("""
            function() {
                return gcd(5, 5);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 5);

    def test_gcm3(self):
        code = parse("""
            function() {
                return gcd(5, 25);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 5);

    def test_gcm4(self):
        code = parse("""
            function() {
                return gcd(15, 25);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 5);

    def test_gcm5(self):
        code = parse("""
            function() {
                return gcd(7, 13);
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 1);


class TestPipeline(TestCase):
    def test_value_pipeline(self):
        code = parse("""
            function() {
                return { foo: "bar", baz: 4 } |> values<any>;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertIn("bar", result.value._to_list())
        self.assertIn(4, result.value._to_list())

    def test_max_pipeline(self):
        code = parse("""
            function() {
                return [ 3, 4, 5 ] |> max;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 5)

    def test_length_pipeline_chain(self):
        code = parse("""
            function() {
                return { foo: 3, bar: 4, baz: 5 } |> values<int> |> length;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 3)

    def test_max_pipeline_chain(self):
        code = parse("""
            function() {
                return { foo: 3, bar: 4, baz: 5 } |> values<int> |> sum;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 12)

class TestMapPipeline(TestCase):
    def test_map_pipeline(self):
        code = parse("""
            function() {
                return [ 4, 6, 2 ] *|> { continue value + 1; };
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_list(), [ 5, 7, 3 ])

    def test_index_pipeline(self):
        code = parse("""
            function() {
                return [ 4, 6, 2 ] *|> { continue index; };
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_list(), [ 0, 1, 2 ])

    def test_keys_pipeline(self):
        code = parse("""
            function() {
                return { foo: 3, bar: 5 } *|> { continue key; };
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_list(), [ "foo", "bar" ])

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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)


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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 12)

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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 32)

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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 2 ** (3 * 3))

class TestFunctionVarArgs(TestCase):
    def test_only_var_args(self):
        code = parse("""
            function() {
                var func = function(...vars: int) {
                    return vars[1];
                };
                return func(3, 4, 8);
            }
        """, debug=True)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 4)

    def test_slice_args(self):
        code = parse("""
            function() {
                var func = function(...vars: int) {
                    return vars;
                };
                return func(3, 4, 8);
            }
        """, debug=True)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_list(), [ 3, 4, 8 ])

    def test_var_args_after_other_args(self):
        code = parse("""
            function() {
                var func = function(foo: int, bar: int, ...vars: int) {
                    return vars;
                };
                return func(3, 4, 8);
            }
        """, debug=True)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_list(), [ 8 ])

    def test_var_args_with_mixed_types(self):
        code = parse("""
            function() {
                var func = function(foo: int, bar: int, ...vars: any) {
                    return vars;
                };
                return func(3, 4, "hello", "yes");
            }
        """, debug=True)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_list(), [ "hello", "yes" ])

class TestObjectConstructing(TestCase):
    def test_clone_constructor(self):
        code = parse("""
            function() {
                var foo = { bar: 5 };
                var baz = { ...foo };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bar": 5 })

    def test_complex_constructor(self):
        code = parse("""
            function() {
                var foo = { bar: 5 };
                var baz = { bam: 10, ...foo };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bar": 5, "bam": 10 })

    def test_pre_constructor(self):
        code = parse("""
            function() {
                var foo = { bar: 5 };
                var baz = { bar: 10, ...foo };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bar": 5 })

    def test_post_constructor(self):
        code = parse("""
            function() {
                var foo = { bar: 5 };
                var baz = { ...foo, bar: 10 };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bar": 10 })


    def test_pre_and_post_constructor(self):
        code = parse("""
            function() {
                var foo = { bar: 5 };
                var baz = { bar: 3, ...foo, bar: 10 };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bar": 10 })

    def test_multiple_constructor(self):
        code = parse("""
            function() {
                var foo = { bar: 5 };
                var fam = { bar: 9 };
                var baz = { ...foo, ...fam };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bar": 9 })

    def test_dereference_constructor(self):
        code = parse("""
            function() {
                var foo = { bar: { bam: 42 } };
                var baz = { ...foo.bar };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bam": 42 })

    def test_dereference_constructor2(self):
        code = parse("""
            function() {
                var foo = { bar: { bam: 42 } };
                var baz = { bam: 10, ...foo.bar };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bam": 42 })

    def test_dereference_constructor3(self):
        code = parse("""
            function() {
                var foo = { bar: { bam: 42 } };
                var baz = { ...foo.bar, bam: 10 };
                return baz;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value._to_dict(), { "bam": 10 })


class TestObjectDestructuring(TestCase):
    def test_single_initialization_destructure(self):
        code = parse("""
            function() {
                { int foo } = { foo: 42 };
                return foo;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_double_initialization_destructure(self):
        code = parse("""
            function() {
                { int foo, int bar } = { foo: 12, bar: 30 };
                return foo + bar;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_single_assignment_destructure(self):
        code = parse("""
            function() {
                int foo = 0;
                { foo } = { foo: 12, bar: 30 };
                return foo;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 12)

    def test_double_assignment_destructure(self):
        code = parse("""
            function() {
                int foo = 0, bar = 0;
                { foo, bar } = { foo: 12, bar: 30 };
                return foo + bar;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_mixed_destructure(self):
        code = parse("""
            function() {
                int foo = 0;
                { foo, int bar } = { foo: 12, bar: 30 };
                return foo + bar;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_inferred_types_in_destructure(self):
        code = parse("""
            function() {
                int foo = 0;
                { foo, var bar } = { foo: 12, bar: 30 };
                return foo + bar;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)


class TestListDestructuring(TestCase):
    def test_single_initialization_destructure(self):
        code = parse("""
            function() {
                [ int foo ] = [ 42 ];
                return foo;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_double_initialization_destructure(self):
        code = parse("""
            function() {
                [ int foo, int bar ] = [ 12, 30 ];
                return foo + bar;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_single_assignment_destructure(self):
        code = parse("""
            function() {
                int foo = 0;
                [ foo ] = [ 12, 30 ];
                return foo;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 12)

    def test_double_assignment_destructure(self):
        code = parse("""
            function() {
                int foo = 0, bar = 0;
                [ foo, bar ] = [ 12, 30 ];
                return foo + bar;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_mixed_destructure(self):
        code = parse("""
            function() {
                int foo = 0;
                [ foo, int bar ] = [ 12, 30 ];
                return foo + bar;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_inferred_types_in_destructure(self):
        code = parse("""
            function() {
                int foo = 0;
                [ foo, var bar ] = [ 12, 30 ];
                return foo + bar;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)


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
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 10)

    def test_for_range(self):
        code = parse("""
            function() {
                int result = 0;
                for(var i from range(1, 5)) {
                    result = result + i;
                };
                return result;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 1 + 2 + 3 + 4)

class TestMatch(TestCase):
    def test_basic_is(self):
        code = parse("""
            function() => any {
                var i = 5;
                if(i is int) {
                    return i;
                };
                return 10;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 5)

    def test_basic_is2(self):
        code = parse("""
            function() => any {
                var i = 5;
                if(i is string) {
                    return i;
                };
                return 10;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 10)

    def test_basic_is3(self):
        code = parse("""
            function() => int {
                any i = 5;
                if(i is int) {
                    return i;
                };
                return 10;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 5)

    def test_basic_is4(self):
        code = parse("""
            function() => int {
                any i = 5;
                if(i is int) {
                    return i + 4;
                };
                return 10;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 9)

class TestDictionary(TestCase):
    def test_basic_dictionary(self):
        code = parse("""
            function() {
                Dictionary<int: int> foo = { 3 : 55 };
                return foo[3];
            }
        """)
        func, result = bootstrap_function(code, check_safe_exit=False)
        if hasattr(func, "break_types"):
            self.assertIn("exception", func.break_types)
            self.assertEqual(func.break_types["exception"][0]["out"].get_micro_op_type(("get", "type")).value_type.value, "DereferenceOp: invalid_dereference")
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 55)


    def test_basic_dictionary2(self):
        code = parse("""
            function() {
                Dictionary<int: int> foo = { 3 : 55 };
                return foo[3]?;
            }
        """)
        func, result = bootstrap_function(code, check_safe_exit=False)
        if hasattr(func, "break_types"):
            self.assertNotIn("exception", func.break_types)
            self.assertEqual(func.break_types["value"][1]["out"].get_micro_op_type(("get", "type")).value_type.value, "DereferenceOp: invalid_dereference")
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 55)


    def test_basic_dictionary3(self):
        code = parse("""
            function() {
                Dictionary<int: int> foo = { 3 : 55 };
                return foo[6];
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "exception")
        self.assertEqual(result.value._to_dict()["type"], "DereferenceOp: invalid_dereference")


    def test_basic_dictionary4(self):
        code = parse("""
            function() => int {
                var foo = { 3 : 55 };
                return foo[3];
            }
        """)
        func, result = bootstrap_function(code)
        if hasattr(func, "break_types"):
            self.assertNotIn("exception", func.break_types)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 55)

    def test_basic_dictionary5(self):
        code = parse("""
            function() {
                Dictionary<int : int> foo = {};
                foo[3] = 55;
                foo[6] = 99;
                return foo[3]?;
            }
        """)
        func, result = bootstrap_function(code, check_safe_exit=False)
        if hasattr(func, "break_types"):
            self.assertNotIn("exception", func.break_types)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 55)

class TestParserMisc(TestCase):
    def test_invalid_list_assignment(self):
        code = parse("""
            function() {
                List<int> foo = [ { bar: 2 }, { bar: 3 } ];
                return foo[0].bar;
            }
        """)
        with self.assertRaises(PreparationException):
            bootstrap_function(code)

    def test_dynamic_assignment(self):
        code = parse("""
            function() {
                Object { bar: int } foo = { bar: 42 };
                foo.bam = 54;
                return foo.bam;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.value, 54)

class TestDynamic(TestCase):
    def test_local(self):
        code = parse("""
            function() {
                foo = 321123;
                return foo;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 321123)


    def test_dynamic_maths(self):
        code = parse("""
            function() {
                foo = 40;
                bar = 2;
                return foo + bar;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)

    def test_dynamic_object(self):
        code = parse("""
            function() {
                foo = { bar : 42 };
                return foo.bar;
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 42)


class TestSpeed(TestCase):
    def test_loops(self):
        start = time()
        code = parse("""
            function() {
                int i = 0, j = 0;
                while(i < 20) {
                    j = 0;
                    while(j < 20) {
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
        with environment(transpile=True, return_value_optimization=True):
            _, result = bootstrap_function(code)
        self.assertEqual(result.value, 20 * 20)
        end = time()
        #self.assertLess(end - start, 20)

    def test_loop_faster(self):
        start = time()
        code = parse("""
            function() {
                int i = 0, j = 0;
                while(i < 100) {
                    j = 0;
                    while(j < 100) {
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
        with environment(**fastest):
            _, result = bootstrap_function(code)
        self.assertEqual(result.value, 100 * 100)
        end = time()
        self.assertLess(end - start, 25)

class TestError(TestCase):
    def test_1(self):
        code = parse("""
            function(foo: int) => int {
                return foo;
            }
        """, debug=True)
        _, result = bootstrap_function(
            code,
            argument=PythonList([ 5 ])
        )
        self.assertEqual(result.value, 5)

    def test_2(self):
        code = parse("""
            function(foo: any) {
                return foo.bar;
            }
        """, debug=True)
        _, result = bootstrap_function(
            code,
            argument=PythonList([ PythonObject({ "bar" : 5 }, bind=DEFAULT_READONLY_COMPOSITE_TYPE) ]),
            check_safe_exit=False
        )
        self.assertEqual(result.value, 5)

    def test_3(self):
        code = parse("""
            function(foo: any) {
                return foo + 3;
            }
        """, debug=True)
        _, result = bootstrap_function(
            code,
            argument=PythonList([ 5 ]),
            check_safe_exit=False
        )
        self.assertEqual(result.value, 8)
        
    def test_4(self):
        code = parse("""
            function(foo: any) {
                foo = "hello";
                return foo;
            }
        """, debug=True)
        _, result = bootstrap_function(
            code,
            argument=PythonList([ 5 ]),
            check_safe_exit=False
        )
        self.assertEqual(result.value, "hello")


class TestEuler(TestCase):
    """
    https://projecteuler.net/
    https://github.com/luckytoilet/projecteuler-solutions/blob/master/Solutions.md
    """

    def test_1(self):
        code = parse("""
            function() {
                int result = 0;
                for(var i from range(1, 1000)) {
                    if(i % 3 == 0 || i % 5 == 0) {
                        result = result + i;
                    };
                };
                return result;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 233168)

    def test_1a(self):
        code = parse("""
            function() {
                return sum(for(var i from range(1, 1000)) {
                    if(i % 3 == 0 || i % 5 == 0) {
                        continue i;
                    };
                });
            }
        """, debug=True)
 
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 233168)

    def test_2(self):
        code = parse("""
            function() {
                int i = 1, j = 2, result = 0;
                while(j < 4000000) {
                    if(j % 2 == 0) {
                        result = result + j;
                    };
                    [ i, j ] = [ j, i + j ];
                };
                return result;
            }
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 4613732)

    def test_3(self):
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
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 6857)

    def test_4(self):
        code = parse("""
            function() {
                int bestResult = 0, i = 999;
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
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 906609)

    def test_5(self):
        code = parse("""
            function() {
                var solve = function(test: int) {
                    int result = 1;
                    for(var i from range(1, test + 1)) {
                        result = result * i / gcd(result, i);
                    };
                    return result;
                };
                return solve(20);
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 232792560)

    def test_6(self):
        code = parse("""
            function() {
                int sumSquares = 0, sum = 0;
                for(var i from range(1, 101)) {
                    sumSquares = sumSquares + i * i;
                    sum = sum + i;
                };
                return sum * sum - sumSquares;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 25164150)

    def test_7_slow(self):
        code = parse("""
            function() => int {
                var isPrime = function(number: int) => bool {
                    for(var i from range(2, number / 2)) {
                        if(number % i == 0) {
                            return false;
                        };
                    };
                    return true;
                };

                int count = 1, test = 3;
                loop {
                    if(isPrime(test)) {
                        count = count + 1;
                        if(count >= 20) {
                            return test;
                        };
                    };
                    test = test + 2;
                };
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 71)

    def test_7_fast(self):
        code = parse("""
            function() => int {
                var isPrime = function(number: int) => bool {
                    for(var i from range(2, number / 2)) {
                        if(number % i == 0) {
                            return false;
                        };
                    };
                    return true;
                };

                int count = 1, test = 3;
                loop {
                    if(isPrime(test)) {
                        count = count + 1;
                        if(count >= 100) {
                            return test;
                        };
                    };
                    test = test + 2;
                };
            }
        """, debug=True)
        with environment(**fastest):
            _, result = bootstrap_function(code)
        self.assertEqual(result.value, 541)

    def test_9(self):
        code = parse("""
             function() {
                 int a = 1, topb = 998;
                 while(a < 998) {
                     int b = topb;
                     while(b > a) {
                         int c = 1000 - a - b;
                         int test = a * a + b * b - c * c;
                         if(test < 0) {
                             topb = b + 1;
                             break;
                         };
                         if(test == 0) {
                             return a * b * c;
                         };
                         b = b - 1;
                     };
                     a = a + 1;
                 };
             }

        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 31875000)

    def test_12(self):
        # The original test goes to 500, but I can only do 10 atm...
        code = parse("""
            function() {
                var countDivisors = function(number: int) {
                    int test = number, count = 1;
                    for(var test from range(1, number)) {
                        if(number % test == 0) {
                            count = count + 1;
                        };
                    };
                    return count;
                };

                int triangleNumber = 1, step = 2;
                while(countDivisors(triangleNumber) < 10) {
                    triangleNumber = triangleNumber + step;
                    step = step + 1;
                };
                return triangleNumber;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 120)

    def test_12a(self):
        code = parse("""
            function() {
                var countDivisors = function(number: int) {
                    return length(
                        for(var test from range(1, number)) {
                            if(number % test == 0) {
                                continue test;
                            };
                        }
                    );
                };
            
                var triangleNumberGenerator = function() {
                    int i = 0;
                    for(var step from irange()) {
                        yield i;
                        i = i + step;
                    };
                };

                return find(triangleNumberGenerator, function(number: int) {
                    return countDivisors(number) > 10;
                });
            }             
        """)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 120)


    def test_14(self):
        code = parse("""
            function() => int {
                Dictionary<int : int> cachedResults = { 1: 1 };

                Function<int> => int testNumber = function(number: int) => int {
                    return 0;
                };

                testNumber = function(number: int) => int {
                    var cachedResult = cachedResults[number]?;

                    if(cachedResult is int) {
                        return cachedResult;
                    };

                    int calcedResult = testNumber(number % 2 == 0 ? number / 2 : number * 3 + 1) + 1;
                    cachedResults[number] = calcedResult;
                    return calcedResult;
                };

                Tuple<int...> results = for(var test in list<int><range(1, 10)>) { continue testNumber(test); };
                return max(results);
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 20)

    def test_15(self):
        code = parse("""
            function() {
                var binomial = function(n: int, k: int) {
                    return factorial(n) / factorial(k) / factorial(n - k);
                };
                return binomial(40, 20);
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 1378465288200)

    def test_18(self):
        code = parse("""
            function() {
                List<int> calcRow =
                    [  4, 62, 98, 27, 23,  9, 70, 98, 73, 93, 38, 53, 60,  4, 23 ];

                List<List<int>> tree = [
                    [ 63, 66,  4, 68, 89, 53, 67, 30, 73, 16, 69, 87, 40, 31 ],
                    [ 91, 71, 52, 38, 17, 14, 91, 43, 58, 50, 27, 29, 48 ],
                    [ 70, 11, 33, 28, 77, 73, 17, 78, 39, 68, 17, 57 ],
                    [ 53, 71, 44, 65, 25, 43, 91, 52, 97, 51, 14 ],
                    [ 41, 48, 72, 33, 47, 32, 37, 16, 94, 29 ],
                    [ 41, 41, 26, 56, 83, 40, 80, 70, 33 ],
                    [ 99, 65,  4, 28,  6, 16, 70, 92 ],
                    [ 88,  2, 77, 73,  7, 63, 67 ],
                    [ 19,  1, 23, 75,  3, 34 ],
                    [ 20,  4, 82, 47, 65 ],
                    [ 18, 35, 87, 10 ],
                    [ 17, 47, 82 ],
                    [ 95, 64 ],
                    [ 75 ]
                ];

                tree *|> {
                    calcRow = value *|> {
                        continue value + max([
                            calcRow[index],
                            calcRow[index + 1]
                        ]);
                    };
                };

                return calcRow[0];
            }
        """)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.caught_break_mode, "value")
        self.assertEqual(result.value, 1074)


    def test_28(self):
        code = parse("""
            function() => int {
                int sum = 1, n = 3;
                while(n <= 1001) {
                    sum = sum + 4 * n * n - 6 * (n - 1);
                    n = n + 2;
                };
                return sum;
            }
        """, debug=True)
        _, result = bootstrap_function(code)
        self.assertEqual(result.value, 669171001)

    def test_31(self):
        return
        code = parse("""
            function() {
                List<int> coins = [ 1, 2, 5, 10, 20, 50, 100, 200 ];
                Dictionary<Tuple<int, int>: int> ways = {};
                ways[ [0, 0] ] = 1;
                for(var i from range(0, 8)) {
                    var coin = coins[i];
                    for (var j from range(0, 200)) {
                        ways[ [i + 1, j] ] = ways[ [i, j] ] + (j >= coin ? ways[ [i + 1, j - coin] ] : 0);
                    };
                };
                return ways[ [ length(COINS), TOTAL ] ];
            }
        """, debug=True)
        _, result = bootstrap_function(code, check_safe_exit=False)
        self.assertEqual(result.value, 73682)


class TestTranspilation(TestCase):
    def test_basic(self):
        code = parse("""
            function() {
                return 42;
            }
        """)
        with environment(transpile=True, return_value_optimization=True):
            _, result = bootstrap_function(code)
        self.assertEqual(result.value, 42)

    def test_multiplication(self):
        code = parse("""
            function() {
                return 21 * 2;
            }
        """)
        with environment(transpile=True, return_value_optimization=True):
            _, result = bootstrap_function(code)
        self.assertEqual(result.value, 42)

    def test_comma_op(self):
        code = parse("""
            function() {
                100 + 1;
                return 21 * 2;
            }
        """)
        with environment(transpile=True, return_value_optimization=True):
            _, result = bootstrap_function(code)
        self.assertEqual(result.value, 42)

    def test_loops(self):
        code = parse("""
            function() {
                int result = 0;
                for(var i from range(0, 100)) {
                    result = result + i;
                };
                return result;
            }
        """)
        with environment(transpile=True, return_value_optimization=True):
            _, result = bootstrap_function(code)
        self.assertEqual(result.value, 4950)

