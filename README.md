# What's Lockdown?

Lockdown is a general-purpose programming language that combines the positive properties of both "strongly-typed" and "dynamic" languages, giving the developer the choice about when and how these properties should be applied.

## What does that mean?

It means you can write quick prototype code that looks like Javascript, then ask the interpreter to tell you all the places where errors might occur. You can then lockdown the code, resulting in stronger guarantees about correctness than Java or C#.

## How does it do this?

1. Structural typing, also known as "duck-typing". This is verified at compile time, with the compiler identifying all potential incompatibilities between types, and enforced at run time.

	You can write code that looks like Javascript:

	`question({ answer: 42 });`

	... and get the same type safety guarantees as from C#.

2. 100% flow control analysis. For every individual operation in an application, the compiler identifies all the possible things that could happen next, whether producing a value, returning from a function, throwing an exception, reseting or shifting a continuation. It then helps the developer understand these flow modes, and allows the developer to decide how they are handled.

	This might sound like a lot of work, but when combined with ...

3. Mass inference of type and flow control across the entire application. You can write an application that looks like Javascript, but the compiler knows exactly where values are returned from, where exceptions are generated, and all other flow control.

4. Conservative run time verification that checks for all type errors (as in Python) combined with more liberal compile time verification that all flow control is handled correctly.

For example, you can write:
```
foo = {};      // No type guarantees or constraints applied
...			   // foo might be modified, have type constraints added
foo.bar = 123; // Add a property that doesn't match type signature
```
The compiler will identify several potential type errors on the last line, including KeyErrors if creating key bar is not allowed, and TypeError if bar has a type constraint, like being a string. The compiler will then bubble these potential errors up through all the calling functions by adding them to their type signatures until it reaches the application entry point. A conservative developer can choose to modify the code to prevent these potential errors.

At run time, if the final line does not break any actual type constraints while the application is executing, then it executes with no type error.

All in all, we get code that is strongly checked and verified like C# or Java, but at run time can behave very dynamically, like Python or Javascript.

## Examples

### Fibonacci
```
function fib() {           // return type of function inferred
	var a = 1, b = 1;      // local variable types inferred
	while(b < 1000) {
	    a, b = b, a + b;
	};
	return a;
};
```
The compiler verifies that this code *will not* terminate except by returning an int - it is completely exception safe, a stronger guarantee than many other languages.

### Weighted Sum with possible Array Out Of Bounds
```
function weighted_sum(List<int> first, List<int> second) {
	var result = 0;
	for(var i = 0; i < first.length; i++) {
		// The compiler detects a potential array out of bound exception,
		// but still compiles the application and runs it.
		result = result + first[i] * second[i]; 
	};
	return result; // return type is inferred as int
};
```
The compiler has worked out that this function can exit in 2 ways: either by returning an int, or by throwing an array out of bounds exception. This becomes part of the functions signature (although not written by the developer). Callers to this function can decide how to handle these 2 cases.

### Improved Weighted Sum
```
function weighted_sum(List<int> first, List<int> second) {
	var result = 0;
	for(var a, b from zip(first, second)) {
		result = result + a * b; 
	};
	return result; // return type is inferred as int
};
```
This improved version of the same function is safe from the array out of bounds exception by using a built in function that is safe. This time, callers do not need to handle the array out of bounds error.

## Current status

Lockdown is alpha software - I hope it will inspire debate about how developers and languages work together, but don't use in production!

The main focus so far has been on ~200 unit tests for the parser, type system and executor. Some of these unit tests are based on Euler problems: https://projecteuler.net/. There is not yet a command line compiler or shell, but it should be easy to add these.

## Some properties of the language

1. Standard primitive types, booleans, strings, ints etc
2. Composite types, such as objects, lists, dictionaries, tuples etc
3. First class function objects and references
4. All standard flow control operators, `if`, `for`, `break`, `try`, `catch` etc
5. Deliminated continuations, based on `shift` and `reset`
6. Closures
7. Structural Typing
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
   * Extending standard built in types and functions (list.push, dictionary.get etc)#
   * Array/Dictionary splatting and decomposition (... operator)
   * Classes (have ObjectTypes already)

If you're interested, please get in touch: richard.hills at gmail dot com

