## Functions
- value: AnyType
- exception: ExceptionType
- yield: AnyType => AnyType
- anything else...

## Generators
- yield: AnyType => NoValueType	# With new values
- value: AnyType				# When finishing

## Loops
- value: AnyType 	# is swallowed
- continue: AnyType	# is captured
- end: NoValueType	# terminates loop with continue values
- break: AnyType	# terminates loop with value

## ShiftOp
- yield: AnyType => AnyType	# When first run
- value: AnyType			# When restarted

## ResetOp
- yield: { value: AnyType, continuation: FunctionType<> }	# From an inner yield
- value: AnyType											# From an inner value
