from sys import stdin

from lockdown.executor.bootstrap import bootstrap_function
from lockdown.parser.parser import parse
from lockdown.utils.utils import environment

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

def repl():
    with environment(base=True, transpile=False):
        try:
            while True:
                try:
                    value = read_input()
                    code = parse(value)
                    func, capturer = bootstrap_function(code, check_safe_exit=False)
                    print("break modes: {}".format(func.break_types))
                    print("{}: {}".format(capturer.caught_break_mode, capturer.value))
                except Exception as e:
                    print("Error on input {}: {} {}".format(value, type(e), e))
        except KeyboardInterrupt as e:
            print("\nExiting...")


if __name__ == "__main__":
    print()
    print("Welcome to lockdown-REPL")
    print("crtl-c to quit")
    print()
    repl()
