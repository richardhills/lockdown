# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.reasoner import DUMMY_REASONER


class PermittedValuesDoesNotExist(Exception):
    pass

class Type(object):
    """
    Base class for all types in Lockdown.

    Supports 2 methods: is_copyable_from(other_type) and get_all_permitted_values(), which can
    throw for types without a finite set of values.
    """
    def is_copyable_from(self, other, reasoner):
        raise NotImplementedError()

    def is_nominally_the_same(self, other):
        return other is self

    def get_all_permitted_values(self):
        raise PermittedValuesDoesNotExist(self)

    def __str__(self):
        return repr(self)

    def short_str(self):
        return str(self)

class AnyType(Type):
    """
    The Top Type of Lockdown, from while all other types are derived, and to which all
    other types are copyable.

    https://en.wikipedia.org/wiki/Top_type
    """
    def is_copyable_from(self, other, reasoner):
        return True

    def __repr__(self):
        return "AnyType"

class BottomType(Type):
    def is_copyable_from(self, other, reasoner):
        return isinstance(other, BottomType)

    def __repr__(self):
        return "BottomType"
    
class ValueType(Type):
    def is_copyable_from(self, other, reasoner):
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        return not isinstance(other, NoValueType)


class NoValueType(Type):
    """
    A Lockdown type that can take no value.

    This is not quite a Bottom Type (https://en.wikipedia.org/wiki/Bottom_type), because expressions
    that break with NoValueType can break - but they do not return a value that can be used by the
    invoker.

    It is also not a Unit Type (https://en.wikipedia.org/wiki/Unit_type), because NoValueTypes can not
    be passed around and used in expressions, while UnitTypes can be passed around even if they take a
    single value.

    It is used for ops that break, but not with a useful value. For example, Nop() has break mode
    "value", with NoValueType. A return statement with no value has break mode "return" with
    NoValueType.

    To indicate that an expression does not terminate in a particular break mode (return, value, exception etc)
    the expression should simply exclude that break mode from the list of break modes that it supports.
    """
    def is_copyable_from(self, other, reasoner):
        if isinstance(other, BottomType):
            return True
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        if not isinstance(other, NoValueType):
            reasoner.push_not_copyable_type(self, other)
            return False
        return True

    def __repr__(self):
        return "NoValueType"

class UnitType(Type):
    """
    A Lockdown type that can only take a single value. https://en.wikipedia.org/wiki/Unit_type
    """
    def __init__(self, value):
        self.value = value

    def is_copyable_from(self, other, reasoner):
        if isinstance(other, BottomType):
            return True
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        if not isinstance(other, UnitType):
            reasoner.push_not_copyable_type(self, other)
            return False
        if other.value != self.value:
            reasoner.push_not_copyable_type(self, other)
            return False
        return True

    def get_all_permitted_values(self):
        return [ self.value ]

    def __repr__(self):
        if isinstance(self.value, basestring):
            return "U<\"{}\">".format(self.value)
        else:
            return "U<{}>".format(self.value)

class StringType(Type):
    """
    A Lockdown type that supports unicode strings, backed by Python's unicode/str objects
    """
    def is_copyable_from(self, other, reasoner):
        if isinstance(other, BottomType):
            return True
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        if not (isinstance(other, StringType) or (isinstance(other, UnitType) and isinstance(other.value, basestring))):
            reasoner.push_not_copyable_type(self, other)
            return False
        return True

    def __repr__(self):
        return "StringType"


class IntegerType(Type):
    """
    An Lockdown type that supports ints, backed by Python's int type
    """
    def is_copyable_from(self, other, reasoner):
        if isinstance(other, BottomType):
            return True
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        if not (isinstance(other, IntegerType) or (isinstance(other, UnitType) and isinstance(other.value, int) and not isinstance(other.value, bool))):
            reasoner.push_not_copyable_type(self, other)
            return False
        return True

    def __repr__(self):
        return "IntegerType"

class BooleanType(Type):
    """
    An Lockdown type that supports ints, backed by Python's bool
    """
    def is_copyable_from(self, other, reasoner):
        if isinstance(other, BottomType):
            return True
        if isinstance(other, OneOfType):
            return other.is_copyable_to(self, reasoner)
        if not (isinstance(other, BooleanType) or (isinstance(other, UnitType) and isinstance(other.value, bool))):
            reasoner.push_not_copyable_type(self, other)
            return False
        return True

    def __repr__(self):
        return "BooleanType"

def unwrap_types(type):
    if isinstance(type, OneOfType):
        return type.types
    return [ type ]

def remove_type(target, subtype):
    return merge_types([t for t in unwrap_types(target) if not subtype.is_copyable_from(t, DUMMY_REASONER)], "exact")

def merge_types(types, mode):
    if mode not in ("exact", "super", "sub"):
        raise FatalError()

    for t in types:
        if not isinstance(t, Type):
            raise FatalError()

    to_drop = []
    for i1, t1 in enumerate(types):
        for i2, t2 in enumerate(types):
            if i1 > i2 and t1.is_copyable_from(t2, DUMMY_REASONER) and t2.is_copyable_from(t1, DUMMY_REASONER):
                to_drop.append(i1)

    types = [t for i, t in enumerate(types) if i not in to_drop]

    to_drop = []
    if mode != "exact":
        for i1, t1 in enumerate(types):
            for i2, t2 in enumerate(types):
                if i1 != i2 and t1.is_copyable_from(t2, DUMMY_REASONER):
                    if mode == "super":
                        to_drop.append(i2)
                    elif mode == "sub":
                        to_drop.append(i1)
        types = [t for i, t in enumerate(types) if i not in to_drop]

    if len(types) == 0:
        return NoValueType()
    elif len(types) == 1:
        return types[0]
    else:
        return OneOfType(types)

class OneOfType(ValueType):
    """
    A UnionType: https://en.wikipedia.org/wiki/Tagged_union

    The value can take one of several types.
    """
    def __init__(self, types):
        if len(types) <= 1:
            raise FatalError()
        self.types = types
        for t in types:
            if isinstance(t, OneOfType):
                raise FatalError()

    def is_copyable_from(self, other, reasoner):
        if isinstance(other, BottomType):
            return True
        for other_sub_type in unwrap_types(other):
            for t in self.types:
                if t.is_copyable_from(other_sub_type, reasoner):
                    break
            else:
                reasoner.push_not_copyable_type(self, other)
                return False
        return True

    def is_copyable_to(self, other, reasoner):
        if isinstance(other, OneOfType):
            raise FatalError()
        for t in self.types:
            if not other.is_copyable_from(t, reasoner):
                reasoner.push_not_copyable_type(other, t)
                return False
        return True

    def map(self, mapper):
        new_types = []
        requires_new_one_of_type = False

        for t in self.types:
            new_t = mapper(t)
            new_types.append(new_t)
            if not new_t.is_nominally_the_same(t):
                requires_new_one_of_type = True

        if requires_new_one_of_type:
            return merge_types(new_types, "exact")
        return self

    def __repr__(self, *args, **kwargs):
        return "OneOfType<{}>".format(", ".join(t.short_str() for t in self.types))

class Const(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped
