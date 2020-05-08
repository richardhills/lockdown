

def raise_if_safe(ExceptionType, can_fail):
    if can_fail:
        raise ExceptionType()
    else:
        raise FatalError()


class FatalError(Exception):
    pass


class MicroOpTypeConflict(Exception):
    pass


class MicroOpConflict(Exception):
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

