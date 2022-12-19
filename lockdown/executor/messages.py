from lockdown.type_system.managers import get_manager


def break_exception_to_string(mode, value, caused_by):
    result = "BreakException<{}: {}>".format(mode, value)
    if caused_by:
        result = "{}\n{}".format(result, caused_by)
    return result

def format_unhandled_break_type(break_type):
    out_break_type = break_type["out"]

    opcode = break_type["opcode"]

    return format_code(opcode, out_break_type)

def format_unhandled_break(mode, value, caused_by, opcode, data):
    break_str = break_exception_to_string(mode, value, caused_by)

    return format_code(opcode, break_str)

def format_code(opcode, pointer_text):
    if not opcode:
        if pointer_text:
            return pointer_text + " (no opcode)"
        return ""

    start, _ = opcode.get_start_and_end()

    if not start:
        if pointer_text:
            return pointer_text + " (no line and column)"
        return ""

    raw_code = opcode.raw_code

    if not raw_code:
        if pointer_text:
            return pointer_text + " (code attached to opcode)"
        return ""

    lines = raw_code.split("\n")

    padding = " " * start._get("column")

    line = start._get("line") - 1
    highlighted_code = "{}: {}".format(line, lines[line])

    if pointer_text:
        return """
{}
{}^
{}| {}""".format(highlighted_code, padding, padding, pointer_text)
    else:
        return highlighted_code

def format_stacktrace_from_frames(frames):
    result = ""
    for frame in frames:
        result = result + format_code(frame.target, None)

    return result

def format_preparation_exception(break_exception):
    from lockdown.executor.opcodes import InvokeOp, PrepareOp
    from lockdown.executor.flow_control import BreakException

    result = ""

    while break_exception:
        if isinstance(break_exception, BreakException):
            frames = break_exception.frames
            for frame in frames:
                if isinstance(frame.target, (InvokeOp, PrepareOp)):
                    result = "{}{}\n".format(result, format_code(frame.target, None))

        break_exception = break_exception.__cause__

    return result
