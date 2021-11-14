# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def raise_if_safe(ExceptionType, can_fail):
    if can_fail:
        raise ExceptionType()
    else:
        raise FatalError()


class FatalError(Exception):
    def __init__(self, *args, **kwargs):
        super(FatalError, self).__init__(*args, **kwargs)
        import ipdb
        ipdb.set_trace()

    pass

class CompositeTypeIncompatibleWithTarget(Exception):
    pass

class CompositeTypeIsInconsistent(Exception):
    pass

class MissingMicroOp(Exception):
    pass
 
 
class InvalidData(Exception):
    pass

class InvalidDereferenceKey(Exception):
    pass
 
class InvalidDereferenceType(Exception):
    pass
 
class InvalidAssignmentKey(Exception):
    pass
 
class InvalidAssignmentType(Exception):
    pass
 
class InvalidInferredType(Exception):
    pass

class DanglingInferredType(Exception):
    pass

class IsNotCopyable(object):
    def __bool__(self):
        return False
    def __nonzero__(self):
        return False
 
class IsNotCompositeType(IsNotCopyable):
    pass
 
class ConflictingMicroOpTypes(IsNotCopyable):
    pass
 
class NoInitialData(IsNotCopyable):
    pass
 
class RuntimeInitialDataConflict(IsNotCopyable):
    def __init__(self, binding_micro_op, initial_data):
        self.binding_micro_op = binding_micro_op
        self.initial_data = initial_data
 
    def __repr__(self):
        return "RuntimeInitialDataConflict<{}, {}>".format(self.binding_micro_op, self.initial_data)

