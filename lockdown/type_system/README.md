# Structural Typing in Lockdown

## Verification versus Execution time Typing

Lockdown attempts to be as liberal as possible, while providing solid safety when required by the programmer.

The programmer can use the type system to describe structural constraints on data, but is not required to in order to access or process it.

These constraints are strongly applied at run time, even in external code written in Python that does not recognise the constraints. Attempting to access or mutate data that would invalidate a constraint will generate an exception.

And the constraints are indirectly enforced at verification time. All potential exceptions are checked to ensure that they are managed appropriately, whether that is by catching and handling them, or propagating and shutting down the application.

At one end of the spectrum, you can write code that looks like Python or Javascript, with no type declarations and run time variable binding. Or you can declare constraints and write code that looks more like Java or C#, while still calling into Python code safely.

## Categories of Types

There are 3 categories if types in Lockdown:

1. Primitives - ints, bools, strings, units, functions etc
2. CompositeTypes - Used to build standard types like "Records", "Classes", "Lists", "Arrays", "Tuples" etc. In Lockdown, CompositeTypes have MicroOps - small opcodes that can be invoked and are associated with other types. 
3. OneOfTypes - a type that accepts one of several other types. Similar to Sum types in other languages

## Structural Typing - Verification Time

In Lockdown, the question of "can a value of type T be set using a value of type S?" is determined by the structure and not the nominal type of T and S. It is mostly relevant for CompositeTypes, but applies to Primitives and OneOfTypes too.

For example, the following code compiles and runs in Lockdown:

		Object { x: int } foo = { x: 5 };

For CompositeTypes, each MicroOp on the LHS must be *derivable* from a MicroOp on the RHS. In this example, the following MicroOps are present on the two types:

		LHS: get.x.int, set.x.int
		RHS: get.x.unit<5>, set.x.any

A microop is derivable if the original version can be used as a drop-in substitute for the derived version.

`get.x.int` is derivable from `get.x.unit<5>` because a programmer invoking the microop, expecting an `int`, will not be disappointed in receiving a `5`.

`set.x.int` is derivable from `set.x.any` because the original microop accepts `int` as a value (as well other strings and other types), so a caller using an integer can be confident there wont be a Type Error.

Not all microops on the RHS have to be matched up with a microop on the LHS. The following example also works:

		Object { x: int } foo = { x: 5, y: "hello" };

The RHS has `get.y.unit<hello>` and `set.y.any` microops, but these are ignored by the LHS. The following example how is prohibited, and will generate a TypeError:

		Object { x: int, y: string } foo = { x: 5 };

The RHS in these examples are *inconsistent*. This means that the microops on the RHS types conflict with each other, for example, by invoking `set.x.any` with "hello" and then invoking `get.x.unit<5>` and not getting the number `5`.

*Inconsistent* types are a powerful feature of Lockdown that allow very broad, liberal use of data on the RHS of code like this, but are then prohibited for use in LHS type declarations. In a nutshell, Lockdown forces you to select which version of the inconsistent microops are most relevant to you, *after* the inconsistent type is declared.

This allows code such as the following, which looks very Javascript like, but is in fact fully type checked:

		Object { x: any } foo = { x: { y: 42 } };
		foo.x = "hello";
		foo.x = 42;

		Object { x: Object { y: int } } foo = { x: { y: 42 } };
		foo.x.y = 123;
		foo.x = { y: 256 };

Structural typing also applies to Primitive types and OneOfTypes. For example, an `int` type can be assigned from a value of `unit<5>` without unboxing. A `OneOf<int, string>` can be assigned from a `string` type also. This is because the value of the primitive is copied into the receiving variable.

## Structural Types - Runtime

At runtime, Lockdown uses a number of Composite objects to wrap standard Python data structures, including objects with `__dict__`, actual `dicts`, `lists` and `tuples`.

These Composite objects can have CompositeTypes added to them dynamically at run time, so that the constraints defined by those types are enforced.

In Python (within the Lockdown executor and third party code), these constraints are applied:

		obj = RDHObject({ "foo": 123 })
		get_manager(obj).add_composite_type(RDHObjectType({ "foo": IntegerType() }))
		
		obj.foo = 42 # Changes the object
		obj.foo = "baz" # Throws a TypeError

At runtime, multiple CompositeTypes can be added to an object, with the microops of all of them being enforced. It is not possible to add two CompositeTypes that are inconsistent with each other, for example, one that contains `get.x.int` and another that supports `set.x.string`. Whichever one is added second will fail.

These runtime checks are entirely consistent with typical Normative typing. Consider the following code in Java:

		List<Integer> foo = new ArrayList<Integer>();
		Collection<Integer> bam = foo;

We start with the most specific type, `ArrayList<Integer>`, and gradual move through less specific interfaces, `List<Integer>` and `Collection<Integer>`.

In the same way, in Lockdown, you start with a very specific CompositeType with many microops associated with it. You then gradually have less specific CompositeTypes, with fewer microops with broader definitions.
