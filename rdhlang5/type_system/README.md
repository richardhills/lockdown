# Structural Typing in Lockdown

## CompositeTypes

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
