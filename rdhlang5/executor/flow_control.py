# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from _collections import defaultdict

from rdhlang5.type_system.core_types import Type
from rdhlang5.type_system.exceptions import FatalError
from rdhlang5.type_system.managers import get_type_of_value
from rdhlang5.utils import MISSING, InternalMarker, is_debug


class BreakException(Exception):
    def __init__(self, mode, value, opcode, restart_type, caused_by=None):
        self.mode = mode
        self.value = value
        self.opcode = opcode
        self.restart_type = restart_type
        self.caused_by = caused_by

    def __str__(self):
        result = "BreakException<{}: {}>".format(self.mode, self.value)
        if self.caused_by:
            result = "{}\n{}".format(result, self.caused_by)
        return result

class BreakTypesFactory(object):
    def __init__(self):
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
            if isinstance(break_types, InternalMarker):
                pass
            if len(break_types) > 0:
                self.result[mode].extend(break_types)

    def build(self):
        return dict(self.result)

class FlowManager(object):
    __slots__ = [ "our_break_mode", "our_break_types", "frame_manager", "callback", "top_level", "_result", "_restart_continuation", "allowed_break_types", "continuation_break_types" ]

    def __init__(self, our_break_mode, our_break_types, allowed_break_types, frame_manager, top_level=False, callback=None, continuation_break_types=None):
        self.our_break_mode = our_break_mode
        self.our_break_types = our_break_types
        self.frame_manager = frame_manager
        self.callback = callback
        self.continuation_break_types = continuation_break_types
        self.top_level = top_level
        self._result = MISSING
        self._restart_continuation = MISSING

        if is_debug():
            if our_break_types and "out" not in our_break_types:
                raise FatalError()

            if our_break_types and "in" in our_break_types and not callback:
                raise FatalError()

            if our_break_types and not isinstance(our_break_types, dict):
                raise FatalError()

            if our_break_types:
                self.allowed_break_types = dict(allowed_break_types)

                if our_break_mode not in self.allowed_break_types:
                    self.allowed_break_types[our_break_mode] = []

                self.allowed_break_types[our_break_mode].append(our_break_types)
            else:
                self.allowed_break_types = allowed_break_types
        else:
            self.allowed_break_types = None

    def start(self):
        if is_debug():
            if not self.callback:
                raise FatalError()
            if self._result is not MISSING:
                raise FatalError()

        try:
            mode, value, opcode, restart_type = self.callback(self)
            self.attempt_close_or_raise(mode, value, opcode, restart_type)
            return
        except BreakException as e:
            if self.attempt_close(e.mode, e.value, e.restart_type):
                return
            raise

        if not self.top_level:
            raise FatalError()

    def get_next_frame(self, opcode):
        return self.frame_manager.get_next_frame(opcode)

    @property
    def result(self):
        if self._result is MISSING:
            raise FatalError()
        return self._result

    @property
    def has_result(self):
        return self._result is not MISSING

    def capture(self, break_mode, break_types, callback=None, top_level=False, continuation_break_types=None):
        flow_manager = FlowManager(break_mode, break_types, self.allowed_break_types, self.frame_manager, callback=callback, top_level=top_level, continuation_break_types=continuation_break_types)
        if callback:
            flow_manager.start()
        return flow_manager

    @property
    def has_restart_continuation(self):
        return self._restart_continuation is not MISSING

    @property
    def restart_continuation(self):
        if self._restart_continuation is MISSING:
            raise FatalError()
        return self._restart_continuation

    def unwind(self, mode, value, opcode, restart_type):
        if mode == "yield":
            pass
        if is_debug():
            type_of_value = None # lazily calculated if we need it

            if restart_type is not None and not isinstance(restart_type, Type):
                raise FatalError()

            if mode not in self.allowed_break_types:
                type_of_value = get_type_of_value(value)
                raise FatalError("Can not unwind {} with type {}, allowed {}".format(mode, type_of_value, self.allowed_break_types))

            allowed_break_types = self.allowed_break_types[mode]

            for allowed_types in allowed_break_types:
                allowed_out = allowed_types["out"]
                allowed_in = allowed_types.get("in", None)

                out_is_compatible = False
                in_is_compatible = False

                if allowed_out.always_is_copyable_from:
                    out_is_compatible = True
                else:
                    if type_of_value is None:
                        type_of_value = get_type_of_value(value)
                    if allowed_out.is_copyable_from(type_of_value):
                        out_is_compatible = True

                if allowed_in is None or restart_type.is_copyable_from(allowed_in):
                    in_is_compatible = True

                if out_is_compatible and in_is_compatible:
                    break
            else:
                type_of_value = get_type_of_value(value)
                raise FatalError("Can not unwind {} with type {}, allowed {}".format(mode, type_of_value, self.allowed_break_types))

        if is_debug() or restart_type is not None:
            raise BreakException(mode, value, opcode, restart_type)
        else:
            return (mode, value, opcode, None)

    def value(self, value, opcode):
        return self.unwind("value", value, opcode, None)

    def exception(self, value, opcode):
        return self.unwind("exception", value, opcode, None)

    def attempt_close_or_raise(self, mode, value, opcode, restart_type):
        if not self.attempt_close(mode, value):
            raise BreakException(mode, value, opcode, restart_type)

    def attempt_close(self, mode, value, restart_type):
        if is_debug() and self._result is not MISSING:
            raise FatalError()
        accepted_out_type = self.our_break_types["out"]
        accepted_in_type = self.our_break_types.get("in", None)

        out_type_is_compatible = (
            accepted_out_type.always_is_copyable_from
            or accepted_out_type.is_copyable_from(get_type_of_value(value))
        )

        in_type_is_compatible = (
            accepted_in_type is None
            or (restart_type is not None and restart_type.is_copyable_from(accepted_in_type))
        )

        if mode == self.our_break_mode and out_type_is_compatible and in_type_is_compatible:
            self._result = value
            if restart_type is not None:
                if accepted_in_type is not None:
                    self._restart_continuation = self.frame_manager.create_continuation(
                        self.callback, restart_type, self.continuation_break_types
                    )
                else:
                    self.frame_manager.abandon_continuation()
            return True
        else:
            return False

    def __enter__(self):
        if is_debug():
            if self.callback:
                raise FatalError()
            if self._result is not MISSING:
                raise FatalError()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if isinstance(exc_value, BreakException):
            return self.attempt_close(exc_value.mode, exc_value.value, exc_value.restart_type)
        if self._result is MISSING and exc_value is None and not self.top_level:
            raise FatalError()

class FrameManager(object):
    def __init__(self):
        self.frames = []
        self.index = 0

    def get_next_frame(self, opcode):
        if self.index == len(self.frames):
            return Frame(self, opcode)
        else:
            old_frame = self.frames[self.index]
            if old_frame.opcode is not opcode:
                raise FatalError()
            return old_frame

    def create_continuation(self, callback, restart_type, break_types):
        if self.index == len(self.frames):
            raise FatalError()

        from rdhlang5.executor.function import Continuation

        new_continuation = Continuation(self, self.frames[self.index:], callback, restart_type, break_types)
        self.frames = self.frames[:self.index]
        return new_continuation

    def abandon_continuation(self):
        if self.index == len(self.frames):
            raise FatalError()
        self.frames = self.frames[:self.index]

    def prepare_restart(self, frames, restart_value):
        self.frames = self.frames + frames
        self.frames[-1].restart_value = restart_value

class Frame(object):
    __slots__ = [ "manager", "opcode", "locals", "restart_value" ]

    def __init__(self, manager, opcode):
        self.manager = manager
        self.opcode = opcode
        self.locals = {}
        self.restart_value = MISSING

    def step(self, name, func):
        locals = self.locals
        value = locals.get(name, MISSING)
        if value is MISSING:
            locals[name] = value = func()
            return value, True
        else:
            return value, False

    def has_restart_value(self):
        return self.restart_value is not MISSING

    def pop_restart_value(self):
        if not self.has_restart_value():
            raise FatalError()
        restart_value = self.restart_value
        self.restart_value = MISSING
        return restart_value

    def __enter__(self):
        if self.manager.index == len(self.manager.frames):
            self.manager.frames.append(self)

        self.manager.index += 1

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        exc_type_allows_restart = exc_value and isinstance(exc_value, BreakException) and exc_value.restart_type is not None

        if not exc_type_allows_restart and self.manager.index == len(self.manager.frames):
            del self.manager.frames[-1]

        self.manager.index -= 1
