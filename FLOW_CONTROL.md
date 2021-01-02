# Lockdown Flow Control

The Lockdown verifier traces how execution flow moves through an application. Every opcode and function declares the different ways that flow control can "leave" it. It also allows new flow control methods to be added without changing the tracer. This helps the developer in multiple ways:

1. Highlighting whether a line of code might generate a run-time error.
2. Generating warnings that an application might terminate in a non-standard way.
3. Helping a developer gradually lockdown a script to prepare for production usage.
4. Allowing new flow control operators to be added to the language easily

Much of the heavy lifting of declaring these ways of flow control is done by the language itself through inference, but the developer can step in at various places to assert control and guarantee flow-control safety when they choose.

## How does it do this?

Consider the standard flow control keywords in Java, C# and Python:

* return
* yield
* break
* continue
* throw/raise

Lockdown supports all these with a single common flow control opcode, called *break*.

By using a single common opcode, all flow control can be verified with the same algorithm.

At run-time, after execution has entered an opcode or a function, it can then generate a *break* with a *mode* and a *value*. At verification time, the opcode must declare all the break modes that might happen, and the types of the values.

For example, to return `5` from a function, an opcode can generate a break:

		{
			mode: "return",
			value: 5
		}

To raise an exception, an opcode might generate a break:

		{
			mode: "exception",
			value: {
				type: "TypeError",
				message: "Reference foo not found"
			}
		}

Even simple opcodes returning a value, such as `BinaryOp` used in addition, use a break with mode `value`:

		{
			mode: "value",
			value: 42
		}

The mode is just a string - new flow control operations can be created and used in an application, while still being verified. So far, Lockdown uses *return*, *break*, *continue*, *end*, *yield*, *value*, *exit* - see [here](PROTOCOLS.md) for details of how these are used.

When an opcode in Lockdown sees a break, it can either capture it, or allow it to continue up the stack to other opcodes. Any unhandled breaks will be traced by the verifier to warn the developer about abnormal program termination.

Lockdown provides an opcode, `TransformOp`, which will receive a break in one mode and re-raise it in another mode. A huge range of behaviours in other languages are then covered by a single opcode:

1. `try-catch` blocks: `exception` to `value`
2. `throw` expressions: `value` to `exception`
3. `exit()` program terminations: `value` to `exit`
4. `?` operator in Rust: `exception` to `return`
5. `return` statement: `value` to `return`
6. `()` function invocations (on return): `return` to `value`

The single flow control algorithm can then verify that all flow control is managed correctly.
