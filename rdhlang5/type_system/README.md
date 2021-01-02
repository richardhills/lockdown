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

For example:

		obj = RDHObject({ "foo": 123 })
		get_manager(obj).add_composite_type(RDHObjectType({ "foo": IntegerType() }))
		
		obj.foo = 42 # Changes the object
		obj.foo = "baz" # Throws a TypeError

At runtime, multiple CompositeTypes can be added to an object, with the microops of all of them being enforced. It is not possible to add two CompositeTypes that are inconsistent with each other, for example, one that contains `get.x.int` and another that supports `set.x.string`. Whichever is added second will fail.

These runtime checks are entirely consistent with typical Normative typing. Consider the following code in Java:

		List<Integer> foo = new ArrayList<Integer>();
		Collection<Integer> bam = foo;

We start with the most specific type, `ArrayList<Integer>`, and gradual move through less specific interfaces, `List<Integer>` and `Collection<Integer>`.

In the same way, in Lockdown, you start with a very specific CompositeType with many microops associated with it. You then gradually have less specific CompositeTypes, with fewer microops with broader definitions.

## CompositeTypes - OLD

Composite types consist of a set of micro ops that can be indexed by keys and invoked against the target object. Micro ops are normally for accessing or modifying state on the composite object, and include descriptions of their own failure modes.

For example:

  - (get, "foo", int): ObjectGetter: a getter for object types that returns the value of property foo, which is always an int
  - (set, "baz", string): ObjectSetter: a setter for object types that sets the property baz and takes a string
  - (get, *!, any!): ObjectWildcardGetter: a getter for object types that takes the name of a property and returns its value, which can be any, but it might throw a key\_error or a type\_error on invocation

Typical error modes for micro ops are key\_error and type\_error.

MicroOps might conflict, for obvious reasons. For example:

  - (set, "foo", string)
  - (get, "foo", int)

In real code, at run time, invoking the first MicroOp will prevent the second from being invokable.

Some conflicts can be solved by having one of the micro ops generate an exception at run time. For example

  - (get, "foo", string)
  - (set, *, any!)

These do not conflict. The first promises to always return a string when invoked, from property foo. The second allows the caller to set any property on the object to any type, but might raise a type error. The conflict is resolved if the second micro op throws a type error when settings foo to be anything other than a string, which is checked at run time by looking at all the micro ops on the composite type.

There are 2 phases for CompositeTypes:

1. At verification time, RevConst CompositeTypes, where the most broad possible set of micro ops can be found, and the micro ops can even conflict with each other. The micro ops on these types can not be invoked at this stage. The RevConst types are reified when they appear as rvalues in an assignment, and the lvalue type has micro ops without conflicts.
2. Post reification, actually used types where micro ops are invoked, and the micro ops must not conflict with each other.

Type checks are carried out in 3 ways:

1. At verification time: check that for each assignment the lvalue can be copied from the rvalue. For composite types, copyability requires that:
  * All operators on the lvalue composite can be derived from operators on the rvalue
  * OR operators on the lvalue can be derived from an initial value on the rvalue (is this necessary with revconst types?)
  * AND there are no conflicts between operators on the lvalue with those on the rvalue
2. Binding types at run time: composite types are bound to run time objects, and all object access must be conducted through these types, with conflict rules enforced. Note that:
  * This requires that there is no conflict between any of the micro ops on the newly bound type and any previously bound type
  * It does not require that the newly bound type can somehow be derived from previously bound types. It is valid to add completely new types (giving dynamic, runtime caste like behaviour)
3. Invoking individual micro ops at run time: Every micro op that is marked as potentially generating an error must check its own invocation against all other micro ops on the type before execution. 
