# What's Lockdown?

Lockdown is a general-purpose programming language that combines the positive characteristics of both "strongly-typed" and "dynamic" languages, giving the developer the choice about when and how these should be used.

## What does that mean?

It means you can write quick prototype code that looks like Javascript, then ask the interpreter to tell you all the places where errors might occur. You can then lockdown the code, resulting in stronger guarantees about correctness than Java or C#.

## How does it do this?

*Structural Typing*, *Optional Typing*, *flow control verification* and *flow control inference*.

In many Nominally Typed languages (such as Java, C#, etc), we are used to seeing classes and functions like this:

		class Container {
		    foo: int, bar: int
		};
		
		function adder(Container container) => int {
			return container.foo + container.bar;
		}
		
		adder(new Container({ foo: 38, bar: 4 }));

Please note - Lockdown is in alpha! These examples don't all work yet, but illustrate what I'm aiming for.

### 1. Structural typing

AKA "compile-time duck-typing", where type compatibility is determined by the structure and shape of your data. See [here](lockdown/type_system/README.md) for how Lockdown implements structural typing, and here [here](STRUCTURAL_TYPING.md) for a broader description.

In brief, this gives a more dynamic feel, while keeping strong compile-time verification of all types.

		class Container {
		    foo: int, bar: int
		};
		
		function adder(Container container) => int {
			return container.foo + container.bar;
		}
		
		// Permitted, since the structure matches, and is verified at compile-time
		adder({ foo: 38, bar: 4 });

### 2. Optional Typing

The structural types provide strong verification and run-time safety, but they are also optional - code without types will still execute.

This gives a highly dynamic feel, but losses the strong compile-time verification of types.

This is very similar to Gradual Typing, except that in Lockdown the structural types that you specify are actually enforced at run-time. Any "unsafe" code is prevented, at run-time, from modifying any data that would invalidate a compile-time type.

		// As long as the function declares a potential TypeError, this is OK
		function adder(container) => { return: int, throws: TypeError } {
			return container.foo + container.bar;
		}
		
		adder({ foo: 38, bar: 4 });

### 3. Flow Control Verification

Every possible TypeError or other exception, every return, break, continue or yield statement, every try or catch - every aspect of flow control -  is traced. The verifier then gives you a choice of how to handle these cases.

The verifier can identify and tell you every possible unhandled exception in your code, even when using optional types. It means you can instruct the verifier to ignore these possible errors (because you are writing a quick script) or you can instruct the verifier to refuse to build your code (because it is mission critical). It means your source editor can highlight run-time flow control, on a line-by-line basis.

See [here](FLOW_CONTROL.md) to see how Lockdown does this.

		function adder(container) => { return: int, throws: none } {
			return container.foo + container.bar;
		}
		
		adder({ foo: 38, bar: 4 });

		Verifier:
		Verification failed - function adder declares nothing is thrown.
		At run time, it might throw TypeError.

### 4. Flow Control Inference ###

Lockdown infers all flow control at verification time, and can warn the developer exactly where any errors might occur at run-time, so that they might be prevented. When Lockdown is run in debug mode, it will also verify every flow-control step at run-time, against the flow-control checked at verification-time, helping to identify bugs in the Lockdown run-time environment, although this comes with a performance penalty. 

Inference is the default. The following example demonstrates how this can help the developer:

		// return int and throw TypeError are infered
		function adder(container) {
			return container.foo + container.bar;
		}
		
		adder({ foo: 38, bar: 4 });

		Verifier:
		This application might terminate with a TypeError.
		Use -v to see where these possible errors are generated.
		Use -s to enforce safe termination.

## Getting started and current status

Lockdown is alpha software - I'm hoping it will inspire debate, and I'm keen for anyone to join in.

To run the unit tests, create a virtual environment, install the dependencies and use the `runtests.sh` script.

	mkvirtualenv lockdown
	pip install -r ./requirements.txt
	./runtests.sh

The main focus so far has been on [~200 unit tests](lockdown/test.py) for the parser, type system and executor. Some of these unit tests are based on Euler problems [https://projecteuler.net/](https://projecteuler.net/). There is not yet a command line compiler or shell, but it should be easy to add these.

## List of Features

1. Standard primitive types, booleans, strings, ints etc
2. Composite types, such as objects, lists, dictionaries, tuples etc
3. Gradual and structural typing
4. First class function objects and references
5. All standard flow control operators, `if`, `for`, `break`, `try`, `catch` etc
6. Deliminated continuations, based on `shift` and `reset`
7. Closures
8. Experimental Python interoperability, including run time type constraints so that your Python code can't break your Lockdown code.
9. Debug mode, where all flow control operations at run time are compared against those predicted at verification time, to test the interpreter.

Lockdown aims to look familiar to the most popular languages, so uses C style braces and flow control operations.

## Todo

1. Solve more Euler problems as unit tests
2. Command line verifier/executor
3. Debugger (language supports continuations which will help suspend and restart)
3. Support for https://en.wikipedia.org/wiki/Language_Server_Protocol so we can write Lockdown in Visual Studio, Eclipse etc
4. Python interoperability
5. Fleshing out the language, including:
   * Basic IO, reading/writing files and console
   * Syntax for more complex function arguments
   * Explicit exception declaration in function signatures
   * Array/Dictionary splatting and decomposition (... operator)
   * Classes (sugar on top of CompositeType)

If you're interested, please get in touch: richard.hills at gmail dot com

