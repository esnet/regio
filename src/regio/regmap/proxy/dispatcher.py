#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections.abc
import itertools
import sys

#---------------------------------------------------------------------------------------------------
def zip_repeat(proxy, value):
    nproxies = len(proxy)
    if not isinstance(value, collections.abc.Sequence):
        value = itertools.repeat(value, nproxies)
    elif len(value) != nproxies:
        raise ValueError(
            f'Length of values ({len(value)}) must match number of proxies ({nproxies}).')
    return zip(proxy, value)

#---------------------------------------------------------------------------------------------------
class ForIOCall:
    def __call__(self, *pargs, **kargs):
        return self.___context___.new_variable(self.___node___, self.___chain___, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class ForIOContextManager:
    def __enter__(self):
        self.___context___.io.start()

        # Allow caller to bind the object in a 'with X() as x' statement.
        return self

    def __exit__(self, *pargs):
        self.___context___.io.stop()

        # Don't suppress exceptions. Pass along to the caller.
        return False

#---------------------------------------------------------------------------------------------------
class ForIOContextManagerGroup:
    def __enter__(self):
        for proxy in self:
            proxy.___context___.io.start()

        # Allow caller to bind the object in a 'with X() as x' statement.
        return self

    def __exit__(self, *pargs):
        for proxy in reversed(self):
            proxy.___context___.io.stop()

        # Don't suppress exceptions. Pass along to the caller.
        return False

#---------------------------------------------------------------------------------------------------
class ForIOSetattr:
    def __setattr__(self, name, value):
        attr = getattr(self, name)
        try:
            write = attr.___write___
        except AttributeError:
            raise ArrtibuteError(f'Attribute {name} is not writeable on {attr.___node___.spec!r}.')
        else:
            write(value)

#---------------------------------------------------------------------------------------------------
class ForIOSetattrGroup:
    def __setattr__(self, name, value):
        for proxy, value in zip_repeat(self, value):
            attr = getattr(proxy, name)
            try:
                write = attr.___write___
            except AttributeError:
                raise AttributeError(
                    f'Attribute {name} is not writeable on {attr.___node___.spec!r}.')
            else:
                write(value)

#---------------------------------------------------------------------------------------------------
class ForIOSetitem:
    def __setitem__(self, key, value):
        item = self[key]
        try:
            write = item.___write___
        except AttributeError:
            raise ArrtibuteError(f'Item {key!r} is not writeable on {item.___node___.spec!r}.')
        else:
            write(value)

#---------------------------------------------------------------------------------------------------
class ForIOSetitemGroup:
    def __setitem__(self, key, value):
        for proxy, value in zip_repeat(self, value):
            item = proxy[key]
            try:
                write = item.___write___
            except AttributeError:
                raise ArrtibuteError(f'Item {key!r} is not writeable on {item.___node___.spec!r}.')
            else:
                write(value)

#---------------------------------------------------------------------------------------------------
class ForIOFormatting:
    # https://docs.python.org/3/reference/datamodel.html#object.__repr__
    def __repr__(self):
        return repr(self.___node___.spec)

    # https://docs.python.org/3/reference/datamodel.html#object.__str__
    def __str__(self):
        return str(self.___node___.spec)

    # https://docs.python.org/3/reference/datamodel.html#object.__bytes__
#    def __bytes__(self): ...

    # https://docs.python.org/3/reference/datamodel.html#object.__format__
#    def __format__(self, format_spec): ...

#---------------------------------------------------------------------------------------------------
class ForIOFormattingGroup:
    # https://docs.python.org/3/reference/datamodel.html#object.__repr__
    def __repr__(self):
        return repr(proxy.___node___.spec for proxy in self)

    # https://docs.python.org/3/reference/datamodel.html#object.__str__
    def __str__(self):
        return str(proxy.___node___.spec for proxy in self)

#---------------------------------------------------------------------------------------------------
class ForNumericIOFormatting:
    # https://docs.python.org/3/reference/datamodel.html#object.__repr__
    def __repr__(self):
        return repr(self.___node___.spec)

    # https://docs.python.org/3/reference/datamodel.html#object.__str__
    def __str__(self):
        return '0x{0:0{1}x}'.format(int(self), self.___node___.region.nibbles)

    # https://docs.python.org/3/reference/datamodel.html#object.__bytes__
    def __bytes__(self):
        return int(self).to_bytes(self.___node___.region.octets, sys.byteorder)

    # https://docs.python.org/3/reference/datamodel.html#object.__format__
    def __format__(self, format_spec):
        if not format_spec:
            return str(self)
        return format_spec.format(int(self))

#---------------------------------------------------------------------------------------------------
class ForNumericIOFormattingGroup:
    def __repr__(self):
        return repr([repr(proxy.___node___.spec) for proxy in self])

    def __str__(self):
        return str([
            '0x{0:0{1}x}'.format(int(proxy), proxy.___node___.region.nibbles)
            for proxy in self
        ])

    def __format__(self, format_spec):
        if not format_spec:
            return str([str(self) for proxy in self])
        return str([format_spec.format(int(self)) for proxy in self])

#---------------------------------------------------------------------------------------------------
# https://docs.python.org/3/reference/datamodel.html#object.__bool__
# https://docs.python.org/3/reference/datamodel.html#object.__complex__
class ForNumericIOConversion:
    def __bool__(self):
        return self.___read___() != 0

    def __index__(self):
        return self.___read___()

    def __complex__(self):
        return complex(self.___read___(), 0)

    def __int__(self):
        return self.___read___()

    def __float__(self):
        return float(self.___read___())

#---------------------------------------------------------------------------------------------------
class ForNumericIOConversionGroup:
    def __bool__(self):
        return all(proxy.___read___() != 0 for proxy in self)

#---------------------------------------------------------------------------------------------------
# https://docs.python.org/3/reference/datamodel.html#object.__round__
class ForNumericIOTruncation:
    def __round__(self, ndigits=None):
        return self.___read___()

    def __trunc__(self):
        return self.___read___()

    def __floor__(self):
        return self.___read___()

    def __ceil__(self):
        return self.___read___()

#---------------------------------------------------------------------------------------------------
# https://docs.python.org/3/reference/datamodel.html#object.__lt__
class ForNumericIOComparison:
    def __lt__(self, other):
        return self.___read___() < other

    def __le__(self, other):
        return self.___read___() <= other

    def __eq__(self, other):
        return self.___read___() == other

    def __ne__(self, other):
        return self.___read___() != other

    def __gt__(self, other):
        return self.___read___() > other

    def __ge__(self, other):
        return self.___read___() >= other

#---------------------------------------------------------------------------------------------------
# TODO: These operators don't need to return bool, they can return any object so long as it can be
#       evaluated as a bool. It would be possible here to create a sub-class of list and override
#       the __bool__ method to perform the all() on itself (by default, the list.__bool__() is true
#       when the list is non-empty). This would allow returning the list of comparison results.
#       Something along the lines of:
#
# class BoolList(list):
#     def __bool__(self):
#         return all(self)
#
# And then the return in the methods below would be something like:
#       return BoolList(proxy.___read___() < other for proxy, other in zip_repeat(self, other))
#---------------------------------------------------------------------------------------------------
class ForNumericIOComparisonGroup:
    def __lt__(self, other):
        return all(proxy.___read___() < other for proxy, other in zip_repeat(self, other))

    def __le__(self, other):
        return all(proxy.___read___() <= other for proxy, other in zip_repeat(self, other))

    def __eq__(self, other):
        return all(proxy.___read___() == other for proxy, other in zip_repeat(self, other))

    def __ne__(self, other):
        return all(proxy.___read___() != other for proxy, other in zip_repeat(self, other))

    def __gt__(self, other):
        return all(proxy.___read___() > other for proxy, other in zip_repeat(self, other))

    def __ge__(self, other):
        return all(proxy.___read___() >= other for proxy, other in zip_repeat(self, other))

#---------------------------------------------------------------------------------------------------
# https://docs.python.org/3/reference/datamodel.html#object.__add__
# Operators for direct operand: self OP other
class ForNumericIOArithmetic:
    def __add__(self, other):
        return self.___read___() + other

    def __sub__(self, other):
        return self.___read___() - other

    def __mul__(self, other):
        return self.___read___() * other

    def __truediv__(self, other):
        return self.___read___() / other

    def __floordiv__(self, other):
        return self.___read___() // other

    def __mod__(self, other):
        return self.___read___() % other

    def __divmod__(self, other):
        return divmod(self.___read___(), other)

    def __pow__(self, other, modulo=None):
        return pow(self.___read___(), other, modulo)

    def __lshift__(self, other):
        return self.___read___() << other

    def __rshift__(self, other):
        return self.___read___() >> other

    def __and__(self, other):
        return self.___read___() & other

    def __xor__(self, other):
        return self.___read___() ^ other

    def __or__(self, other):
        return self.___read___() | other

#---------------------------------------------------------------------------------------------------
class ForNumericIOArithmeticGroup:
    def __add__(self, other):
        return [proxy.___read___() + other for proxy, other in zip_repeat(self, other)]

    def __sub__(self, other):
        return [proxy.___read___() - other for proxy, other in zip_repeat(self, other)]

    def __mul__(self, other):
        return [proxy.___read___() * other for proxy, other in zip_repeat(self, other)]

    def __truediv__(self, other):
        return [proxy.___read___() / other for proxy, other in zip_repeat(self, other)]

    def __floordiv__(self, other):
        return [proxy.___read___() // other for proxy, other in zip_repeat(self, other)]

    def __mod__(self, other):
        return [proxy.___read___() % other for proxy, other in zip_repeat(self, other)]

    def __divmod__(self, other):
        return [divmod(proxy.___read___(), other) for proxy, other in zip_repeat(self, other)]

    def __pow__(self, other, modulo=None):
        return [pow(proxy.___read___(), other, modulo) for proxy, other in zip_repeat(self, other)]

    def __lshift__(self, other):
        return [proxy.___read___() << other for proxy, other in zip_repeat(self, other)]

    def __rshift__(self, other):
        return [proxy.___read___() >> other for proxy, other in zip_repeat(self, other)]

    def __and__(self, other):
        return [proxy.___read___() & other for proxy, other in zip_repeat(self, other)]

    def __xor__(self, other):
        return [proxy.___read___() ^ other for proxy, other in zip_repeat(self, other)]

    def __or__(self, other):
        return [proxy.___read___() | other for proxy, other in zip_repeat(self, other)]

#---------------------------------------------------------------------------------------------------
# https://docs.python.org/3/reference/datamodel.html#object.__radd__
# Operators for reflected operand: self OP other
class ForNumericIOArithmeticReflected:
    def __radd__(self, other):
        return other + self.___read___()

    def __rsub__(self, other):
        return other - self.___read___()

    def __rmul__(self, other):
        return other * self.___read___()

    def __rtruediv__(self, other):
        return other / self.___read___()

    def __rfloordiv__(self, other):
        return other // self.___read___()

    def __rmod__(self, other):
        return other % self.___read___()

    def __rdivmod__(self, other):
        return divmod(other, self.___read___())

    def __rpow__(self, other, modulo=None):
        return pow(other, self.___read___(), modulo)

    def __rlshift__(self, other):
        return other << self.___read___()

    def __rrshift__(self, other):
        return other >> self.___read___()

    def __rand__(self, other):
        return other & self.___read___()

    def __rxor__(self, other):
        return other ^ self.___read___()

    def __ror__(self, other):
        return other | self.___read___()

#---------------------------------------------------------------------------------------------------
class ForNumericIOArithmeticReflectedGroup:
    def __radd__(self, other):
        return [other + proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rsub__(self, other):
        return [other - proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rmul__(self, other):
        return [other * proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rtruediv__(self, other):
        return [other / proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rfloordiv__(self, other):
        return [other // proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rmod__(self, other):
        return [other % proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rdivmod__(self, other):
        return [divmod(other, proxy.___read___()) for proxy, other in zip_repeat(self, other)]

    def __rpow__(self, other, modulo=None):
        return [pow(other, proxy.___read___(), modulo) for proxy, other in zip_repeat(self, other)]

    def __rlshift__(self, other):
        return [other << proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rrshift__(self, other):
        return [other >> proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rand__(self, other):
        return [other & proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __rxor__(self, other):
        return [other ^ proxy.___read___() for proxy, other in zip_repeat(self, other)]

    def __ror__(self, other):
        return [other | proxy.___read___() for proxy, other in zip_repeat(self, other)]

#---------------------------------------------------------------------------------------------------
# https://docs.python.org/3/reference/datamodel.html#object.__iadd__
class ForNumericIOArithmeticInPlace:
    def __iadd__(self, other):
        self.___write___(self.___read___() + other)

    def __isub__(self, other):
        self.___write___(self.___read___() - other)

    def __imul__(self, other):
        self.___write___(self.___read___() * other)

    def __itruediv__(self, other):
        self.___write___(self.___read___() / other)

    def __ifloordiv__(self, other):
        self.___write___(self.___read___() // other)

    def __imod__(self, other):
        self.___write___(self.___read___() % other)

    def __ipow__(self, other, modulo=None):
        self.___write___(pow(self.___read___(), other, modulo))

    def __ilshift__(self, other):
        self.___write___(self.___read___() << other)

    def __irshift__(self, other):
        self.___write___(self.___read___() >> other)

    def __iand__(self, other):
        self.___write___(self.___read___() & other)

    def __ixor__(self, other):
        self.___write___(self.___read___() ^ other)

    def __ior__(self, other):
        self.___write___(self.___read___() | other)

#---------------------------------------------------------------------------------------------------
class ForNumericIOArithmeticInPlaceGroup:
    def __iadd__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() + other)

    def __isub__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() - other)

    def __imul__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() * other)

    def __itruediv__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() / other)

    def __ifloordiv__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() // other)

    def __imod__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() % other)

    def __ipow__(self, other, modulo=None):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(pow(proxy.___read___(), other, modulo))

    def __ilshift__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() << other)

    def __irshift__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() >> other)

    def __iand__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() & other)

    def __ixor__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() ^ other)

    def __ior__(self, other):
        for proxy, other in zip_repeat(self, other):
            proxy.___write___(proxy.___read___() | other)

#---------------------------------------------------------------------------------------------------
# https://docs.python.org/3/reference/datamodel.html#object.__neg__
class ForNumericIOArithmeticUnary:
    def __neg__(self):
        return -self.___read___()

    def __pos__(self):
        return self.___read___()

    def __abs__(self):
        return self.___read___()

    def __invert__(self):
        return ~self.___read___() & self.___node___.region.mask

#---------------------------------------------------------------------------------------------------
class ForNumericIOArithmeticUnaryGroup:
    def __neg__(self):
        return [-proxy.___read___() for proxy in self]

    def __pos__(self):
        return [proxy.___read___() for proxy in self]

    def __invert__(self):
        return [~proxy.___read___() & proxy.___node___.region.mask for proxy in self]

#---------------------------------------------------------------------------------------------------
class ForNumericIOOperators(
        ForNumericIOFormatting,
        ForNumericIOConversion,
        ForNumericIOTruncation,
        ForNumericIOComparison,
        ForNumericIOArithmetic,
        ForNumericIOArithmeticReflected,
        ForNumericIOArithmeticInPlace,
        ForNumericIOArithmeticUnary,
): ...

class ForNumericIOOperatorsGroup(
        ForNumericIOFormattingGroup,
        ForNumericIOConversionGroup,
        ForNumericIOComparisonGroup,
        ForNumericIOArithmeticGroup,
        ForNumericIOArithmeticReflectedGroup,
        ForNumericIOArithmeticInPlaceGroup,
        ForNumericIOArithmeticUnaryGroup,
): ...

#---------------------------------------------------------------------------------------------------
class ForIO(ForIOCall, ForIOContextManager): ...
class ForIOGroup(ForIOCall, ForIOContextManagerGroup): ...

class ForStructureIO(ForIO, ForIOSetattr, ForIOFormatting): ...
class ForStructureIOGroup(ForIOGroup, ForIOSetattrGroup, ForIOFormattingGroup): ...

class ForArrayIO(ForIO, ForIOSetitem, ForIOFormatting): ...
class ForArrayIOGroup(ForIOGroup, ForIOSetitemGroup, ForIOFormattingGroup): ...

#---------------------------------------------------------------------------------------------------
class ForNumericIO(ForIO, ForIOSetattr, ForNumericIOOperators):
    def ___read___(self):
        return self.___context___.io.read_region(self.___node___.region)

class ForNumericIOGroup(ForIOGroup, ForIOSetattrGroup, ForNumericIOOperatorsGroup): ...

#---------------------------------------------------------------------------------------------------
class ForRegisterIO(ForNumericIO):
    def ___write___(self, value):
        self.___context___.io.write_region(self.___node___.region, value)

class ForRegisterIOGroup(ForNumericIOGroup): ...

#---------------------------------------------------------------------------------------------------
class ForFieldIO(ForNumericIO):
    def ___write___(self, value):
        self.___context___.io.update_region(self.___node___.region, value)

class ForFieldIOGroup(ForNumericIOGroup): ...
