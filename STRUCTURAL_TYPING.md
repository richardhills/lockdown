# Structural typing

AKA "compile-time duck-typing", is where type compatibility is determined by the structure of your types. The structure might include the field names, modifiers, or the operations supported by the type.

For example, in Lockdown, the following code executes:

		typedef Object {
		    foo: int
		} FooContainer;
		
		function fooExtracter(FooContainer fooContainer) {
			return fooContainer.foo;
		}
		
		fooExtracter(FooContainer({ foo: 42 })); // Traditional Nominative usage
		fooExtracter({ foo: 42 }); // Allowed under Structural Typing

The `fooExtracter` function accepts any object that *looks like* a FooContainer, meaning that it has a field `foo` that contains an `int`.

*Structural typing* is often contrasted with *Nominal typing*, where compatibility is determined by the names of the types and explicitly declared relationships between them. For example, in Java classes must explicitly list all the interfaces that they support. In Structural typing systems, a class implicitly supports an interface as long as the function declarations match. Nominal typing is less flexible, but offers the same strong compile time safety of Structural typing.

*Structural typing* is also often compared with *Duck typing*, where code executes as long as the data shape matches at run-time. For example, in Python `foo.bar` can execute, or might throw a TypeError (or any error really), but can only be determined at run-time based on the shape of `foo`. Duck typing is flexible, but offers no compile time safety.
