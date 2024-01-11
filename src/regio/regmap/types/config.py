#---------------------------------------------------------------------------------------------------
__all__ = ()

import collections.abc

#---------------------------------------------------------------------------------------------------
# Used instead of None to allow None as a valid configuration value.
class NoValue: ...

#---------------------------------------------------------------------------------------------------
class SequenceChecker:
    def __init__(self, *item_checkers):
        self.item_checkers = item_checkers

    def apply(self, name, value):
        if not isinstance(value, collections.abc.Sequence):
            raise TypeError(f'Value {value!r} of "{name}" configuration must be a sequence.')

        for i, v in enumerate(value):
            n = f'{name}[{i}]'
            for c in self.item_checkers:
                c.apply(n, v)

#---------------------------------------------------------------------------------------------------
class TypeChecker:
    def __init__(self, *types):
        self.types = types
        self.msg = ' | '.join(repr(t) for t in types)

    def apply(self, name, value):
        if not isinstance(value, self.types):
            raise TypeError(
                f'Value {value!r} of "{name}" configuration must be of type {self.msg}.')

#---------------------------------------------------------------------------------------------------
class SubClassChecker(TypeChecker):
    def apply(self, name, value):
        if not issubclass(value, self.types):
            raise TypeError(
                f'Value {value!r} of "{name}" configuration must be a sub-class of {self.msg}.')

#---------------------------------------------------------------------------------------------------
class PositiveChecker:
    def apply(self, name, value):
        if value < 0:
            raise ValueError(f'Value {value!r} of "{name}" configuration must be positive.')

#---------------------------------------------------------------------------------------------------
class EnumChecker:
    def __init__(self, enum_cls):
        self.enum_cls = enum_cls
        self.enum_names = tuple(e.name for e in enum_cls)
        self.enum_values = tuple(e.value for e in enum_cls)

    def apply(self, name, value):
        if (not isinstance(value, self.enum_cls) and
            value not in self.enum_names and
            value not in self.enum_values):
            raise ValueError(
                f'Value {value!r} of "{name}" configuration must be an instance, name or value of '
                f'enum type {self.enum_cls!r}.')

#---------------------------------------------------------------------------------------------------
class Descriptor:
    CHECKERS = ()

    def __init__(self, default=NoValue):
        self.default = default

    def _check(self, value):
        for checker in self.CHECKERS:
            checker.apply(self.name, value)

    def __set_name__(self, cls, name):
        self.cls = cls
        self.name = name
        self.attr = '___config_' + name + '___'

        # Make sure the default is valid.
        if self.default is not NoValue:
            self._check(self.default)

        # Let the configuration class know the state.
        if self.default is NoValue:
            cls.add_required(name)
        else:
            cls.add_optional(name)

    def __get__(self, obj, cls=None):
        # Attribute looked up on the class.
        if obj is None:
            return self

        # Attribute looked up on an instance.
        try:
            return getattr(obj, self.attr)
        except AttributeError:
            if self.default is not NoValue:
                return self.default
        raise AttributeError(f'Configuration {self.name} on {self.cls!r} has not been set.')

    def _set(self, obj, value):
        setattr(obj, self.attr, value)

    def __set__(self, obj, value):
        if hasattr(obj, self.attr):
            raise AttributeError(f'Configuration {self.name} on {self.cls!r} is already set.')

        # Validate and set the value on the instance.
        self._check(value)
        self._set(obj, value)
        self.cls.add_changed(self.name)

    def __delete__(self, obj):
        raise AttributeError(f'Configuration {self.name} on {self.cls!r} is read-only.')

#---------------------------------------------------------------------------------------------------
class Bool(Descriptor):
    CHECKERS = (
        TypeChecker(bool),
    )

#---------------------------------------------------------------------------------------------------
class PositiveInt(Descriptor):
    CHECKERS = (
        TypeChecker(int),
        PositiveChecker(),
    )

#---------------------------------------------------------------------------------------------------
class PositiveIntSequence(Descriptor):
    CHECKERS = (
        SequenceChecker(
            TypeChecker(int),
            PositiveChecker(),
        ),
    )

#---------------------------------------------------------------------------------------------------
class SubClass(Descriptor):
    CHECKERS = (
        TypeChecker(type),
    )

    def __init__(self, cls, *pargs, **kargs):
        self.CHECKERS += (SubClassChecker(cls),)
        super().__init__(cls, *pargs, **kargs)

#---------------------------------------------------------------------------------------------------
class EnumFromStr(Descriptor):
    CHECKERS = (
        TypeChecker(str),
    )

    def __init__(self, enum_cls, *pargs, **kargs):
        self.enum_cls = enum_cls
        self.CHECKERS += (EnumChecker(enum_cls),)
        super().__init__(*pargs, **kargs)

    def _set(self, obj, value):
        super()._set(obj, self.enum_cls[value])

#---------------------------------------------------------------------------------------------------
class Config:
    ___required___ = ()
    ___optional___ = ()
    ___changed___ = ()

    @classmethod
    def add_required(cls, name):
        cls.___required___ += (name,)

    @classmethod
    def add_optional(cls, name):
        cls.___optional___ += (name,)

    @classmethod
    def add_changed(cls, name):
        cls.___changed___ += (name,)

    def __init__(self, obj, kargs):
        # Check for unknown configuration keywords.
        names = set(kargs)
        names.difference_update(self.___required___)
        names.difference_update(self.___optional___)
        if names:
            raise ValueError(f'Unknown keywords {names!r} in configuration for {obj!r}.')

        # Validate and set the required configuration.
        for name in self.___required___:
            try:
                value = kargs[name]
            except KeyError:
                raise KeyError(f'Missing required "{name}" configuration for {obj!r}.')

            try:
                # Set the property for the keyword. The property will check for validity.
                setattr(self, name, value)
            except Exception as e:
                raise type(e)(f'[{obj!r}]: ' + str(e)) from None

        # Validate and set the optional configuration.
        for name in self.___optional___:
            try:
                value = kargs[name]
            except KeyError:
                continue

            try:
                # Set the property for the keyword. The property will check for validity.
                setattr(self, name, value)
            except Exception as e:
                raise type(e)(f'[{obj!r}]: ' + str(e)) from None

    @property
    def required_map(self):
        return dict((name, getattr(self, name)) for name in self.___required___)

    @property
    def optional_map(self):
        return dict((name, getattr(self, name)) for name in self.___optional___)

    @property
    def changed_map(self):
        return dict((name, getattr(self, name)) for name in self.___changed___)
