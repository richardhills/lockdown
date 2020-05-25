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
    def __init__(self, our_break_mode, our_break_types, allowed_break_types, frame_manager, top_level=False, callback=None):
        self.our_break_mode = our_break_mode
        self.our_break_types = our_break_types
        self.frame_manager = frame_manager
        self.callback = callback
        self.top_level = top_level

        if our_break_types and "out" not in our_break_types:
            raise FatalError()

        if our_break_types and "in" in our_break_types and not callback:
            raise FatalError()

        self._result = MISSING
        self._restart_continuation = MISSING

        if our_break_types and not isinstance(our_break_types, dict):
            raise FatalError()

        self.allowed_break_types = defaultdict(lambda: defaultdict(list), allowed_break_types)
        if our_break_types:
            self.permit(our_break_mode, our_break_types)

    def start(self):
        if not self.callback:
            raise FatalError()
        if self._result is not MISSING:
            raise FatalError()
        try:
            mode, value, opcode = self.callback(self)
            if self.attempt_close(mode, value):
                return
            else:
                raise BreakException(mode, value, opcode, False)
        except BreakException as e:
            if self.attempt_close(e.mode, e.value):
                return
            else:
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

    def permit(self, break_mode, break_types):
        can_restart = "in" in break_types
        self.allowed_break_types[break_mode][can_restart].append(break_types)

    def capture(self, break_mode, break_types, callback=None, top_level=False):
        break_block = FlowManager(break_mode, break_types, self.allowed_break_types, self.frame_manager, callback=callback, top_level=top_level)
        if callback:
            break_block.start()
        return break_block

    @property
    def restart_continuation(self):
        if self._restart_continuation is MISSING:
            raise FatalError()
        return self._restart_continuation

    def unwind(self, mode, value, opcode, can_restart):
        if is_debug():
            type_of_value = None # lazily calculated if we need it

            if can_restart:
                allowed_break_types = self.allowed_break_types[mode][True] + self.allowed_break_types[mode][False]
            else:
                allowed_break_types = self.allowed_break_types[mode][False]

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
            return (mode, value, opcode)

    def value(self, value, opcode):
        return self.unwind("value", value, opcode, False)

    def return_(self, value, opcode):
        return self.unwind("return", value, opcode, False)

    def exception(self, value, opcode):
        return self.unwind("exception", value, opcode, False)

    def yield_(self, value, opcode):
        return self.unwind("yield", value, opcode, True)

    def attempt_close(self, mode, value):
        if self._result is not MISSING:
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
    def __init__(self, manager, opcode):
        self.manager = manager
        self.opcode = opcode
        self.locals = {}
        self.restart_value = MISSING

    def step(self, name, func, *args):
        if name not in self.locals:
            self.locals[name] = func(*args)
            return self.locals[name], True
        else:
            return self.locals[name], False

    def step3(self, name, func, a, b, c):
        if name not in self.locals:
            self.locals[name] = func(a, b, c)
            return self.locals[name], True
        else:
            return self.locals[name], False

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
