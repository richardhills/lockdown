1. Remove initial_data from CompositeType
    - this was original required to support super broad Composite types that could be safely reduced (reified) to concrete, useful types. For example:
    Object { foo: int } bar = { foo : 123 };
    The variable foo would have type Any, initial value 123, but bar would be more specific, limiting foo to be an int. These could only be reconciled by *knowing* that the initial value of foo was 123.
    This is now redundant. foo now has type get.unit<123> and set.any, and during reification, this is compatible with get.int and set.int, since the constraints are looser.

2. Stop using { type: "object" } and { type: "list" } and move to { type: "composite" }

3. Remove automatic reification, and instead has some default substitute for var that gives good, sensible object values that can be reified downt to from broad object intantiations

4. Decide how PreparationError should be propagated - really have to find a way to generate good, sensible preparation error messages from nested functions that aren't about the fact that the PreparationError isn't handled - no one cares.

5. Drop the built in .methods on list and object types. These don't fit with structural typing.