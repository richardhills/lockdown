# What's Lockdown?

Lockdown is a general-purpose programming language that combines the positive characteristics of both "strongly-typed" and "dynamic" languages, giving the developer the choice about when and how these should be used.

## What does that mean?

It means you can write quick prototype code that looks like Javascript, then ask the interpreter to tell you all the places where errors might occur. You can then lockdown the code, piece by piece, resulting in stronger guarantees about correctness than Java or C#.

## Getting started and current status

Lockdown is actively developed alpha software - I'm keen for anyone to join in.

To set it up, clone this repository, create a python virtual environment and install dependencies:

	mkvirtualenv lockdown
	pip install -r ./requirements.txt

To launch a shell, type:

    workon lockdown
    ./shell.sh

To run the unit tests, type:

    workon lockdown
	./runtests.sh

There are approximately [200 unit tests](lockdown/test.py) for the parser, type system and executor. Some of these unit tests are based on Euler problems [https://projecteuler.net/](https://projecteuler.net/).

## How is it strongly-typed and dynamic at the same time?

*Structural Typing*, *Optional Typing*, *flow control verification* and *flow control inference*.

In Nominally Typed languages (such as Java, C#, etc), we are used to classes and functions defined like this:

		class Container {
		    foo: int, bar: int
		};
		
		function adder(Container container) => int {
			return container.foo + container.bar;
		}
		
		adder(new Container({ foo: 38, bar: 4 }));

( Please note - Lockdown is in alpha! Not all the syntax works yet, but this illustrates my plan. )

### 1. Structural typing

AKA "compile-time duck-typing", where type compatibility is determined at compile time by the structure and shape of your data. See [here](lockdown/type_system/README.md) for how Lockdown implements structural typing, and here [here](STRUCTURAL_TYPING.md) for a broader description.

Structure typing gives the language the feel of dynamic languages, while preserving strong compile-time verification of all types.

		class Container {
		    foo: int, bar: int
		};
		
		function adder(Container container) => int {
			return container.foo + container.bar;
		}
		
		// new Container is not needed! Since the structure matches, and is verified at compile-time
		adder({ foo: 38, bar: 4 });

### 2. Optional Typing

While structural types provide strong verification and run-time safety, they are also optional - code without types will still execute.

This gives a highly dynamic feel, but losses the strong compile-time verification of types.

This is very similar to Gradual Typing, except that in Lockdown the structural types that you specify are actually enforced at run-time. Any "unsafe" code is prevented, at run-time, from modifying any data that would invalidate a compile-time type.

		// As long as the function declares a potential TypeError, this is OK
		function adder(container) => int, throws: TypeError } {
			return container.foo + container.bar;
		}
		
		adder({ foo: 38, bar: 4 });

### 3. Flow Control Verification

Every possible TypeError or other exception, every return, break, continue or yield statement, every try or catch - every aspect of flow control -  is traced by the verified. The verifier then gives you a choice of how to handle these cases.

The verifier can identify and tell you every possible unhandled exception in your code, even when using optional types. It means you can instruct the verifier to ignore these possible errors (because you are knocking together a quick script) or you can instruct the verifier to refuse to build your code (because it is mission critical). And you can decide how you want to handle flow control on a function by function basis, by specifying exactly how that function should be able to return, throw or exit.

See [here](FLOW_CONTROL.md) to see how Lockdown does this.

		function adder(container) => int, throws: void {
			return container.foo + container.bar;
		}
		
		adder({ foo: 38, bar: 4 });

		Verifier: Strict verification failed
		At verification time, the function adder is declared to not throw an exception.
		At run time, it might throw a TypeError.

### 4. Flow Control Inference ###

Having to specify for every function how it might return, throw or exit would involve a lot of typing. Instead, Lockdown allows you to let the verifier infer all flow control in your application. Errors will then bubble to the main function of your application, and the verifier can then provide a list of all the ways that the main function might fail.

To then "lockdown" an application, you would have the verifier list all the possible errors, before fixing them one by one. Once a particular function is locked down, you can specify this on the function's type signature, as a line in the sand for the verifier which will then fail verification if the function is broken again.

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

## List of Features

1. Support for https://en.wikipedia.org/wiki/Language_Server_Protocol so we can write Lockdown in Visual Studio, Eclipse etc
2. Standard primitive types, booleans, strings, ints etc
3. Composite types, such as objects, lists, dictionaries, tuples etc
4. Gradual and structural typing
5. First class function objects and references
6. All standard flow control operators, `if`, `for`, `break`, `try`, `catch` etc
7. Deliminated continuations, based on `shift` and `reset`
8. Closures
9. Experimental Python interoperability, including run time type constraints so that your Python code can't break your Lockdown code.

Lockdown aims to look familiar to the most popular languages, so uses C style braces and flow control operations.

## Todo

1. Solve more Euler problems as unit tests
2. Command line verifier/executor
3. Debugger (language supports continuations which will help suspend and restart)
4. Python interoperability
5. Fleshing out the language, including:


   * Basic IO, reading/writing files and console
   * Array/Dictionary splatting and decomposition (... operator)
   * Classes (sugar on top of CompositeType)

If you're interested, please get in touch: richard.hills at gmail dot com

