# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from _collections import defaultdict

from rdhlang5.type_system.core_types import Type
from rdhlang5.type_system.exceptions import FatalError
from rdhlang5.type_system.managers import get_type_of_value
from rdhlang5.utils import MISSING, InternalMarker, is_debug


class BreakException(Exception):
    def __init__(self, mode, value, opcode, can_restart, caused_by=None):
        self.mode = mode
        self.value = value
        self.opcode = opcode
        self.can_restart = can_restart
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
            break_type["enter"] = in_type
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
    __slots__ = [ "our_break_mode", "our_break_types", "frame_manager", "callback", "top_level", "_result", "_restart_continuation", "allowed_break_types" ]

    def __init__(self, our_break_mode, our_break_types, allowed_break_types, frame_manager, top_level=False, callback=None):
        self.our_break_mode = our_break_mode
        self.our_break_types = our_break_types
        self.frame_manager = frame_manager
        self.callback = callback
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
                can_restart = "in" in our_break_types
                if our_break_mode not in self.allowed_break_types:
                    self.allowed_break_types[our_break_mode] = ([], [])
                self.allowed_break_types[our_break_mode][1 if can_restart else 0].append(our_break_types)
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
            mode, value, opcode, can_restart = self.callback(self)
            self.attempt_close_or_raise(mode, value, opcode, can_restart)
            return
        except BreakException as e:
            if self.attempt_close(e.mode, e.value):
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

    def capture(self, break_mode, break_types, callback=None, top_level=False):
        flow_manager = FlowManager(break_mode, break_types, self.allowed_break_types, self.frame_manager, callback=callback, top_level=top_level)
        if callback:
            flow_manager.start()
        return flow_manager

    @property
    def restart_continuation(self):
        if self._restart_continuation is MISSING:
            raise FatalError()
        return self._restart_continuation

    def unwind(self, mode, value, opcode, can_restart):
        if is_debug():
            type_of_value = None # lazily calculated if we need it

            if can_restart:
                allowed_break_types = self.allowed_break_types[mode][0] + self.allowed_break_types[mode][1]
            else:
                allowed_break_types = self.allowed_break_types[mode][0]

            for allowed_types in allowed_break_types:
                allowed_out = allowed_types["out"]

                if allowed_out.always_is_copyable_from:
                    break
                else:
                    if type_of_value is None:
                        type_of_value = get_type_of_value(value)
                    if allowed_out.is_copyable_from(type_of_value):
                        break
            else:
                raise FatalError("Can not unwind {} with type {}, allowed {}".format(mode, type_of_value, self.allowed_break_types))

        if is_debug() or can_restart:
            raise BreakException(mode, value, opcode, can_restart)
        else:
            return (mode, value, opcode, False)

    def value(self, value, opcode):
        return self.unwind("value", value, opcode, False)

    def return_(self, value, opcode):
        return self.unwind("return", value, opcode, False)

    def exception(self, value, opcode):
        return self.unwind("exception", value, opcode, False)

    def yield_(self, value, opcode):
        return self.unwind("yield", value, opcode, True)

    def attempt_close_or_raise(self, mode, value, opcode, can_restart):
        if not self.attempt_close(mode, value):
            raise BreakException(mode, value, opcode, can_restart)

    def attempt_close(self, mode, value):
        if is_debug() and self._result is not MISSING:
            raise FatalError()
        accepted_out_type = self.our_break_types["out"]
        if mode == self.our_break_mode and (
            accepted_out_type.always_is_copyable_from
            or accepted_out_type.is_copyable_from(get_type_of_value(value))
        ):
            self._result = value
            if "in" in self.our_break_types:
                self._restart_continuation = self.frame_manager.create_continuation(self.callback, self.our_break_types["in"])
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
            return self.attempt_close(exc_value.mode, exc_value.value)
        if self._result is MISSING and exc_value is None and not self.top_level:
            raise FatalError()

class Continuation(object):
    def __init__(self, frame_manager, frames, callback, restart_type):
        self.frame_manager = frame_manager
        self.frames = frames
        self.callback = callback
        self.restart_type = restart_type

    def get_break_types(self):
        raise ValueError()
        return {}

    def invoke(self, restart_value, break_manager):
        if not self.restart_type.is_copyable_from(get_type_of_value(restart_value)):
            raise FatalError()
        self.restarted = True
        self.frame_manager.prepare_restart(self.frames, restart_value)
        raise self.callback(break_manager)

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

    def create_continuation(self, callback, restart_type):
        if self.index == len(self.frames):
            raise FatalError()
        new_continuation = Continuation(self, self.frames[self.index:], callback, restart_type)
        self.frames = self.frames[:self.index]
        return new_continuation

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
        exc_type_allows_restart = exc_value and isinstance(exc_value, BreakException) and exc_value.can_restart

        if not exc_type_allows_restart and self.manager.index == len(self.manager.frames):
            del self.manager.frames[-1]

        self.manager.index -= 1
