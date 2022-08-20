class OpenFunction139817453520152(object):

    @classmethod
    def close_and_invoke(cls, context_139817453520152_argument,
        context_139817453520152_outer_context, _frame_manager, _hooks):
        context_139817453520152 = Universal(True, initial_wrapped={
            'prepare': Context139817464810744, 'outer':
            context_139817453520152_outer_context, 'argument':
            context_139817453520152_argument, 'static':
            Universal139817452497272, '_types':
            CompositeType139817455144744}, debug_reason=
            'local-initialization-transpiled-context')
        local = None
        with scoped_bind(context_139817453520152,
            CompositeType139817455144744, bind=get_environment().rtti):
            local = Universal(True, initial_wrapped={}, initial_length=
                CALCULATE_INITIAL_LENGTH)
        context_139817453520152 = Universal(True, initial_wrapped={
            'prepare': Context139817464810744, 'outer':
            context_139817453520152_outer_context, 'argument':
            context_139817453520152_argument, 'static':
            Universal139817452497272, 'local': local, '_types':
            CompositeType139817455143904}, debug_reason=
            'code-execution-transpiled-context')
        with scoped_bind(context_139817453520152,
            CompositeType139817455143904, bind=get_environment().rtti):
            return 'value', TransformOpTryCatcher1(context_139817453520152,
                _frame_manager, _hooks), None, None

    @classmethod
    def close(cls, outer_context):
        return cls.Closed_OpenFunction139817453520152(cls, outer_context)

    class Closed_OpenFunction139817453520152(LockdownFunction):

        def __init__(self, open_function, outer_context):
            self.open_function = open_function
            self.outer_context = outer_context

        def invoke(self, argument, frame_manager, hooks):
            return self.open_function.close_and_invoke(argument, self.
                outer_context, frame_manager, hooks)

        def get_type(self):
            return ClosedFunctionType(OpenFunctionType139817455857280.
                argument_type, OpenFunctionType139817455857280.break_types)


def stmt_wrapper_2(context_139817453520152, _frame_manager, _hooks):
    raise BreakException(
        'return',
        ClosedFunction139817454467112.invoke(
            Universal(True, initial_wrapped={
                (0): ClosedFunction139817453520880.invoke(
                    Universal(True, initial_wrapped={
                        (0): Universal(True, initial_wrapped={'foo': 3, 'bar': 4, 'baz': 5}, initial_length=CALCULATE_INITIAL_LENGTH)
                    }, initial_length=CALCULATE_INITIAL_LENGTH),
                    _frame_manager, _hooks)[1]
            }, initial_length=CALCULATE_INITIAL_LENGTH), _frame_manager, _hooks)[1],
        TransformOp139817452498784, None
    )
    return 'value', NoValue, None, None


def TransformOpTryCatcher1(context_139817453520152, _frame_manager, _hooks):
    try:
        return stmt_wrapper_2(context_139817453520152, _frame_manager, _hooks)
    except BreakException as b:
        if b.mode == 'return':
            return b.value
        raise
