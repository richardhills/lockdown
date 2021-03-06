# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __builtin__ import True
from _collections import defaultdict

from lockdown.type_system.composites import is_type_bindable_to_value, \
    CompositeType, does_value_fit_through_type
from lockdown.type_system.core_types import Type
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.reasoner import DUMMY_REASONER, Reasoner
from lockdown.utils.utils import MISSING, InternalMarker, get_environment


class BreakException(Exception):
    """
    Represents execution leaving an opcode or function. 
    """
    def __init__(self, mode, value, opcode, restart_type, caused_by=None):
        self.mode = mode
        self.value = value
        self.opcode = opcode
        self.restart_type = restart_type
        self.caused_by = caused_by

    def __str__(self):
        return break_exception_to_string(self.mode, self.value, self.caused_by)

def break_exception_to_string(mode, value, caused_by):
    result = "BreakException<{}: {}>".format(mode, value)
    if caused_by:
        result = "{}\n{}".format(result, caused_by)
    return result

class BreakTypesFactory(object):
    """
    Utility Factory for Opcodes.get_break_types() to build the break types data structure. 
    """
    def __init__(self, target):
        self.target = target
        self.result = defaultdict(list)

    def add(self, mode, out_type, in_type=None, opcode=None):
        if not isinstance(out_type, Type):
            raise FatalError()
        if in_type and not isinstance(in_type, Type):
            raise FatalError()
        if opcode:
            out_type.from_opcode = opcode
        break_type = {
            "out": out_type,
        }
        if in_type:
            break_type["in"] = in_type
        self.result[mode].append(break_type)

    def merge(self, break_types):
        for mode, break_types in break_types.items():
            if len(break_types) > 0:
                self.result[mode].extend(break_types)

    def build(self):
        result = dict(self.result)
        if self.target:
            if getattr(self.target, "break_types", None) is not None:
                raise FatalError()
            self.target.break_types = result
        return result

class Capturer(object):
    __slots__ = [ "frame_manager", "break_mode", "top_level", "value", "caught_break_mode", "caught_restart_type", "caught_frames", "opcode" ]

    def __init__(self, frame_manager, break_mode=None, top_level=False):
        self.frame_manager = frame_manager
        self.break_mode = break_mode
        self.top_level = top_level

        self.value = MISSING
        self.caught_break_mode = MISSING
        self.caught_restart_type = MISSING
        self.caught_frames = MISSING
        self.opcode = MISSING

    def attempt_capture(self, mode, value, opcode, restart_type):
        if self.break_mode is None or self.break_mode == mode:
            self.value = value
            self.caught_break_mode = mode
            self.opcode = opcode

            if restart_type:
                self.caught_restart_type = restart_type
                self.caught_frames = self.frame_manager.slice_frames()

            return True
        return False

    def attempt_capture_or_raise(self, mode, value, opcode, restart_type):
        if not self.attempt_capture(mode, value, opcode, restart_type):
            raise BreakException(mode, value, opcode, restart_type)

    def create_continuation(self, callback, break_types):
        from lockdown.executor.function import Continuation
 
        return Continuation(self.frame_manager, self.caught_frames, callback, self.caught_restart_type, break_types)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if isinstance(exc_value, FatalError):
            return False
        if isinstance(exc_value, BreakException):
            return self.attempt_capture(exc_value.mode, exc_value.value, exc_value.opcode, exc_value.restart_type)
        return False

def is_restartable(thing):
    if hasattr(thing, "_is_restartable"):
        return thing._is_restartable
    if thing.break_types is None:
        return True
    for break_types in thing.break_types.values():
        for break_type in break_types:
            if "in" in break_type:
                thing._is_restartable = True
                return True
    thing._is_restartable = False
    return False

class FrameManager(object):
    """
    Manages the opcode frame stack, allowing deliminated continuations, unwinds, rewinds of the stack.

    Any opcode that calculates intermediate values while executing (such as addition), will call
    get_next_frame() - this will either return a new Frame object if the opcode is being executed,
    or it will return a previously used Frame object if the continuation is being restarted. This way,
    any opcodes written using the FrameManager get restartability largely for free.

    The Frame returned by get_next_frame should be used in a context with: block, so that it can
    verify the break mode and type when debugging the executor itself.
    """
    __slots__ = [ "frames", "index", "mode" ]

    def __init__(self):
        self.frames = []
        self.index = 0
        self.mode = "wind"

    def get_next_frame(self, thing):
        if self.fully_wound():
            if get_environment().frame_shortcut and not is_restartable(thing):
                return PASS_THROUGH_FRAME

            if self.mode != "wind":
                raise FatalError()
            return Frame(self, thing)
        else:
            if self.mode not in ("shift", "reset"):
                raise FatalError()
            old_frame = self.frames[self.index]
            if old_frame.target is not thing:
                raise FatalError()
            return old_frame

    def fully_wound(self):
        return self.index == len(self.frames)

    def pop_frame(self):
        del self.frames[-1]

    def capture(self, break_mode=None, top_level=False):
        return Capturer(self, break_mode, top_level)

    def slice_frames(self):
        if self.fully_wound():
            raise FatalError()

        self.mode = "wind"

        sliced_frames = self.frames[self.index:]
        self.frames = self.frames[:self.index]
        return sliced_frames

    def prepare_restart(self, frames, restart_value):
        self.mode = "reset"
        self.frames = self.frames + [f.clone() for f in frames]

        for f in self.frames:
            if f.has_restart_value():
                raise FatalError()

        self.frames[-1].restart_value = restart_value

class PassThroughFrame(object):
    """
    An optimized version of Frame where we *know* we will never restart, so we are safe reusing the
    same PassThroughFrame every time for performance.
    """
    def step(self, name, func):
        return func()

    def unwind(self, mode, value, opcode, restart_type):
        if get_environment().return_value_optimization and restart_type is None:
            return mode, value, opcode, None
        raise BreakException(mode, value, opcode, restart_type)

    def value(self, value, opcode=None):
        return self.unwind("value", value, opcode, None)

    def exception(self, value, opcode=None):
        return self.unwind("exception", value, opcode, None)

    def yield_(self, value, restart_type=None):
        return self.unwind("yield", value, None, restart_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

PASS_THROUGH_FRAME = PassThroughFrame()

class Frame(object):
    __slots__ = [ "manager", "target", "locals", "restart_value" ]

    def __init__(self, manager, target, initial_locals=None):
        self.manager = manager
        self.target = target
        self.locals = initial_locals or {}
        self.restart_value = MISSING

    def clone(self):
        return Frame(
            self.manager,
            self.target,
            initial_locals=dict(self.locals)
        )

    def unwind(self, mode, value, opcode, restart_type):
        if restart_type:
            self.manager.mode = "shift"

        if get_environment().return_value_optimization and restart_type is None:
            return mode, value, self.target, None

        raise BreakException(mode, value, self.target, restart_type)

    def value(self, value):
        return self.unwind("value", value, None, None)

    def exception(self, value, opcode=None):
        return self.unwind("exception", value, opcode, None)

    def yield_(self, value, restart_type=None):
        return self.unwind("yield", value, None, restart_type)

    def step(self, name, func):
        locals = self.locals
        value = locals.get(name, MISSING)
        if value is MISSING:
            locals[name] = value = func()
        return value

    def has_restart_value(self):
        return self.restart_value is not MISSING

    def pop_restart_value(self):
        if not self.has_restart_value():
            raise FatalError()
        restart_value = self.restart_value
        self.restart_value = MISSING
        self.manager.mode = "wind"
        return restart_value

    def __enter__(self):
        if self.manager.fully_wound():
            if self.manager.mode not in ("wind", "reset"):
                raise FatalError()
            self.manager.mode = "wind"
            self.manager.frames.append(self)
        else:
            if self.manager.mode not in ("reset", "shift"):
                raise FatalError()
            self.manager.mode = "reset"

        self.manager.index += 1

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if isinstance(exc_value, FatalError):
            return

        if get_environment().validate_flow_control and isinstance(exc_value, BreakException) and self.target.break_types is not None:
            # Verifies that execution is leaving the target opcode at run-time in a way that was forecast
            # at verification time. 
            break_types = self.target.break_types.get(exc_value.mode, []) + self.target.break_types.get("*", [])

#            if break_types is MISSING:
#                raise FatalError("Can not unwind {}: {}, target {} allowed {}".format(exc_value.mode, exc_value.value, self.target, break_types))

            failures = []

            reasoner = Reasoner()

            for allowed_break_type in break_types:
                allowed_out = allowed_break_type["out"]
                allowed_in = allowed_break_type.get("in", None)

                out_is_compatible = does_value_fit_through_type(exc_value.value, allowed_out, reasoner=reasoner)
                in_is_compatible = allowed_in is None or (
                    exc_value.restart_type is not None and exc_value.restart_type.is_copyable_from(allowed_in, reasoner)
                )

                if not out_is_compatible:
                    failures.append(out_is_compatible)

                if out_is_compatible and in_is_compatible:
                    break
            else:
                raise FatalError("Can not unwind {} {}, target {}, allowed {}: {}".format(exc_value.mode, exc_value.value, self.target, break_types, reasoner.to_message()))

        exc_type_allows_restart = exc_value and isinstance(exc_value, BreakException) and exc_value.restart_type is not None

        if get_environment().validate_flow_control and self.manager.mode == "reset":
            raise FatalError()

        if not exc_type_allows_restart and self.manager.fully_wound():
            self.manager.pop_frame()
        else:
            if get_environment().validate_flow_control and exc_type_allows_restart:
                if self.manager.mode not in ("shift",):
                    raise FatalError()

        self.manager.index -= 1
