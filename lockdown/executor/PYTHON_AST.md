ClosedFunctions are compiled down to:

AST, dependencies, context_name

The context_name is determined by the ClosedFunction, and the dependencies are determined by the opcodes.

Each function takes _argument and _frame_manager as parameters. The _argument variable is immediately stored in the context.

Each opcode, if compiled to a function, takes the context_name and the _frame_manager as arguments.
