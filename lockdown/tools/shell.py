from sys import stdin

from lockdown.executor.bootstrap import bootstrap_function, \
    get_default_global_context
from lockdown.executor.flow_control import FrameManager
from lockdown.executor.function import prepare
from lockdown.executor.raw_code_factories import prepared_function, shift_op, \
    nop, function_type, invoke_op, no_value_type, close_op, prepare_op, \
    context_op, dereference, any_type, reset_op, literal_op, function_lit, \
    transform_op, static_op, transform
from lockdown.parser.parser import parse, CodeBlockBuilder
from lockdown.utils.utils import environment, NO_VALUE
from log import logger

import readline

def read_input():
    value = raw_input(">> ")

    if value == "--":
        multi_line_value = []
        value = None

        while True:
            value = raw_input()
            if value != "--":
                multi_line_value.append(value)
            else:
                break

        value = "\n".join(multi_line_value)

    return value

def build_looper():
    return invoke_op(close_op(prepare_op(
        shift_op(literal_op(42), any_type())
    ), context_op()), nop())

def build_executor(raw_code):
    return function_lit(
        transform_op(
            "yield", "read",
            reset_op(
                close_op(static_op(prepare_op(literal_op(
                    parse(
                        raw_code,
                        post_chain_function=CodeBlockBuilder([
                            build_looper()
                        ])
                    )
                ))), context_op()), nop()
            )
        )
    )

def bootstraped_executor(frame_manager):
    return prepare(
        function_lit(
            transform_op(
                "yield", "read",
                reset_op(build_looper())
            )
        ), get_default_global_context(), frame_manager
    ).close(NO_VALUE)

def repl():
    with environment(base=True, transpile=False):
        try:
            frame_manager = FrameManager()

            with frame_manager.capture("read") as previous_capturer:
                previous_capturer.attempt_capture_or_raise(
                    *bootstraped_executor(frame_manager).invoke(NO_VALUE, frame_manager)
                )

            while True:
                try:
                    raw_code = read_input()

                    code = build_executor(raw_code)

                    continuation = previous_capturer.value.continuation

                    with frame_manager.capture() as new_capturer:
                        new_capturer.attempt_capture_or_raise(*continuation.invoke(code, frame_manager))

                    if new_capturer.caught_break_mode == "read":
                        previous_capturer = new_capturer
                    else:
                        print("command broke out by {}: {}".format(
                            new_capturer.caught_break_mode,
                            new_capturer.value
                        ))
                except Exception as e:
                    logger.exception("Error on input {}: {} {}".format(raw_code, type(e), e))
        except KeyboardInterrupt as e:
            print("\nExiting...")


if __name__ == "__main__":
    print()
    print("Welcome to lockdown-REPL")
    print("crtl-c to quit")
    print()
    repl()
