from rdhlang5_types.utils import InternalMarker


def spread_dict(*args, **kwargs):
    result = {}
    for arg in args:
        result.update(arg)
    result.update(kwargs)
    return result

def default(value, marker, default_if_marker):
    if value is marker:
        return default_if_marker
    return value

MISSING = InternalMarker("MISSING")
